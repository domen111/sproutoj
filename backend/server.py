#!/usr/bin/python3

import math
import pg
import mcd
import redis
import tornado.ioloop
import tornado.netutil
import tornado.process
import tornado.httpserver
import tornado.web
from tornado.gen import coroutine

import config
from req import Service
from req import RequestHandler
from req import reqenv
from user import UserService
from acct import AcctHandler
from acct import SignHandler
from pro import ProService
from pro import ProsetHandler
from pro import ProStaticHandler
from pro import ProHandler
from pro import SubmitHandler
from pro import ChalHandler
from pro import ChalListHandler
from chal import ChalService
from rate import RateService
from rate import RateHandler
from rate import ScbdHandler
from manage import ManageHandler
from pack import PackHandler
from pack import PackService
    
class IndexHandler(RequestHandler):
    @reqenv
    def get(self):
        manage = False

        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            name = ''

        else:
            name = self.acct['name']

            if self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
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

            err,acct_id = yield from UserService.inst.sign_in(mail,pw)
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

            err,acct_id = yield from UserService.inst.sign_up(mail,pw,name)
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


if __name__ == '__main__':
    httpsock = tornado.netutil.bind_sockets(6000)
    #tornado.process.fork_processes(0)

    db = pg.AsyncPG(config.DBNAME_OJ,config.DBUSER_OJ,config.DBPW_OJ,
            dbtz = '+8')
    rs = redis.StrictRedis(host = 'localhost',port = 6379,db = 1)
    mc = mcd.AsyncMCD()

    Service.Acct = UserService(db,rs)
    Service.Pro = ProService(db,rs)
    Service.Chal = ChalService(db,mc)
    Service.Rate = RateService(db,rs)
    Service.Pack = PackService(db,mc)

    args = {
        'db':db,
        'mc':mc,
        'rs':rs
    }
    app = tornado.web.Application([
        ('/index',IndexHandler,args),
        ('/rate',ScbdHandler,args),
        ('/sign',SignHandler,args),
        ('/acct/(\d+)',AcctHandler,args),
        ('/acct',AcctHandler,args),
        ('/proset',ProsetHandler,args),
        ('/pro/(\d+)/(.+)',ProStaticHandler,args),
        ('/pro/(\d+)',ProHandler,args),
        ('/submit/(\d+)',SubmitHandler,args),
        ('/submit',SubmitHandler,args),
        ('/chal/(\d+)',ChalHandler,args),
        ('/chal',ChalListHandler,args),
        ('/manage/(.+)',ManageHandler,args),
        ('/manage',ManageHandler,args),
        ('/pack',PackHandler,args),
    ],cookie_secret = config.COOKIE_SEC,autoescape = 'xhtml_escape')

    httpsrv = tornado.httpserver.HTTPServer(app)
    httpsrv.add_sockets(httpsock)
    
    #timer = tornado.ioloop.PeriodicCallback(_update_ratelist,30000)
    #timer.start()
    tornado.ioloop.IOLoop.instance().start()
