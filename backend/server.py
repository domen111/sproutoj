#!/usr/bin/python3

import pg
import mcd
import tornado.ioloop
import tornado.netutil
import tornado.process
import tornado.httpserver
import tornado.web
from tornado.gen import coroutine

import config
from req import RequestHandler
from req import reqenv
from user import UserService
from pro import ProService
from pro import ProsetHandler
from pro import ProHandler
from pro import SubmitHandler
from pro import ChalHandler
from chal import ChalService
from manage import ManageHandler
from pack import PackHandler
from pack import PackService
    
class IndexHandler(RequestHandler):
    @reqenv
    def get(self):
        name = ''
        manage = False

        if self.acct_id != None:
            err,user = yield from UserService.inst.getinfo(self.acct_id)
            if err:
                name = ''

            name = user['name']

            if user['type'] == UserService.ACCTTYPE_KERNEL:
                manage = True

        self.render('index',name = name,manage = manage)
        return

class SignHandler(RequestHandler):
    @reqenv
    def get(self):
        self.render('sign')
        return

    @reqenv
    def post(self):
        cur = yield self.db.cursor()

        reqtype = self.get_argument('reqtype')
        if reqtype == 'signin':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')

            err,acct_id = yield from UserService.inst.signin(mail,pw)
            if err:
                self.finish(err)
                return

            self.set_secure_cookie('id',str(acct_id),
                    path = '/oj',httponly = True) 
            self.finish('S')
            return

        elif reqtype == 'signup':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')
            name = self.get_argument('name')

            err,acct_id = yield from UserService.inst.signup(mail,pw,name)
            if err:
                self.finish(err)
                return

            self.set_secure_cookie('id',str(acct_id),
                    path = '/oj',httponly = True) 
            self.finish('S')
            return

        elif reqtype == 'signout':
            self.clear_cookie('id',path = '/oj')
            self.finish('S')
            return

class AcctHandler(RequestHandler):
    @reqenv
    def get(self):
        self.render('acct')
        return

    @reqenv
    def post(self):
        return

if __name__ == '__main__':
    httpsock = tornado.netutil.bind_sockets(6000)
    #tornado.process.fork_processes(0)

    db = pg.AsyncPG(config.DBNAME_OJ,config.DBUSER_OJ,config.DBPW_OJ)
    mc = mcd.AsyncMCD()
    UserService(db,mc)
    ProService(db,mc)
    ChalService(db,mc)
    PackService(db,mc)

    args = {
        'db':db,
        'mc':mc,
    }
    app = tornado.web.Application([
        ('/index',IndexHandler,args),
        ('/sign',SignHandler,args),
        ('/acct',AcctHandler,args),
        ('/proset',ProsetHandler,args),
        ('/pro/(.*)',ProHandler,args),
        ('/submit',SubmitHandler,args),
        ('/submit/(.*)',SubmitHandler,args),
        ('/chal/(.*)',ChalHandler,args),
        ('/manage',ManageHandler,args),
        ('/manage/(.*)',ManageHandler,args),
        ('/pack',PackHandler,args),
    ],cookie_secret = config.COOKIE_SEC,autoescape = 'xhtml_escape')

    httpsrv = tornado.httpserver.HTTPServer(app)
    httpsrv.add_sockets(httpsock)
    
    tornado.ioloop.IOLoop.instance().start()
