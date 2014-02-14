#!/usr/bin/python3

import math
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
from pro import ChalListHandler
from chal import ChalService
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
    def get(self,acct_id):
        acct_id = int(acct_id)

        err,acct = yield from UserService.inst.getinfo(acct_id)
        if err:
            self.finish(err)
            return

        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
                'SUM("test_valid_rate"."rate" * "test_config"."weight" * '
                '    CASE "valid_test"."expire" WHEN \'infinity\' THEN '
                '    1 ELSE '
                '    (1 - (GREATEST(date_part(\'days\',justify_interval('
                '    age("valid_test"."timestamp","valid_test"."expire") '
                '    - \'1 days\')),-1) + 1) * 0.15) '
                '    END) '
                'AS "rate" FROM "test_valid_rate" '
                'INNER JOIN ('
                '    SELECT "test"."pro_id","test"."test_idx",'
                '    MIN("test"."timestamp") AS "timestamp","problem"."expire" '
                '    FROM "test" '
                '    INNER JOIN "account" '
                '    ON "test"."acct_id" = "account"."acct_id" '
                '    INNER JOIN "problem" '
                '    ON "test"."pro_id" = "problem"."pro_id" '
                '    WHERE "account"."acct_id" = %s '
                '    AND "test"."state" = %s '
                '    AND "account"."class" && "problem"."class" '
                '    GROUP BY "test"."pro_id","test"."test_idx","problem"."expire"'
                ') AS "valid_test" '
                'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
                'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx" '
                'INNER JOIN "test_config" '
                'ON "test_valid_rate"."pro_id" = "test_config"."pro_id" '
                'AND "test_valid_rate"."test_idx" = "test_config"."test_idx";',
                (acct_id,ChalService.STATE_AC))
        if cur.rowcount != 1:
            self.finish('Unknown')
            return
        
        rate = cur.fetchone()[0]
        if rate == None:
            rate = 0
        
        else:
            rate = math.floor(rate / 100)

        self.render('acct',acct = acct,rate = rate)
        return

    @reqenv
    def post(self):
        return

if __name__ == '__main__':
    httpsock = tornado.netutil.bind_sockets(6000)
    #tornado.process.fork_processes(0)

    db = pg.AsyncPG(config.DBNAME_OJ,config.DBUSER_OJ,config.DBPW_OJ,
            dbtz = '+8')
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
        ('/acct/(.*)',AcctHandler,args),
        ('/proset',ProsetHandler,args),
        ('/pro/(.*)',ProHandler,args),
        ('/submit',SubmitHandler,args),
        ('/submit/(.*)',SubmitHandler,args),
        ('/chal',ChalListHandler,args),
        ('/chal/(.*)',ChalHandler,args),
        ('/manage',ManageHandler,args),
        ('/manage/(.*)',ManageHandler,args),
        ('/pack',PackHandler,args),
    ],cookie_secret = config.COOKIE_SEC,autoescape = 'xhtml_escape')

    httpsrv = tornado.httpserver.HTTPServer(app)
    httpsrv.add_sockets(httpsock)
    
    tornado.ioloop.IOLoop.instance().start()
