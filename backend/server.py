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

class RateHandler(RequestHandler):
    @reqenv
    def get(self):
        acctlist = yield self.mc.get('ratelist')
        if acctlist != None:
            yield from update_ratelist(self.db,self.mc)
            acctlist = yield self.mc.get('ratelist')

        self.render('rate',acctlist = acctlist)
        return

def update_ratelist(db,mc):
    cur = yield db.cursor()
    yield cur.execute(('SELECT "acct_id","name","class" FROM "account" '
        'WHERE "acct_type" = %s;'),
        (UserService.ACCTTYPE_USER,))

    acctlist = list()
    for acct_id,name,clas in cur:
        acctlist.append({
            'acct_id':acct_id,
            'name':name,
            'class':clas[0]
        })

    yield cur.execute(('SELECT "sum"."acct_id",SUM("sum"."rate") FROM ('
        '    SELECT "challenge"."acct_id","challenge"."pro_id",'
        '    MAX("challenge_state"."rate" * '
        '        CASE WHEN "challenge"."timestamp" < "problem"."expire" '
        '        THEN 1 ELSE '
        '        (1 - (GREATEST(date_part(\'days\',justify_interval('
        '        age("challenge"."timestamp","problem"."expire") '
        '        + \'1 days\')),-1)) * 0.15) '
        '        END) '
        '    AS "rate" '
        '    FROM "challenge" '
        '    INNER JOIN "problem" '
        '    ON "challenge"."pro_id" = "problem"."pro_id" '
        '    INNER JOIN "account" '
        '    ON "challenge"."acct_id" = "account"."acct_id" '
        '    INNER JOIN "challenge_state" '
        '    ON "challenge"."chal_id" = "challenge_state"."chal_id" '
        '    WHERE "account"."class" && "problem"."class" '
        '    AND "account"."acct_type" = %s '
        '    AND "problem"."status" = %s '
        '    GROUP BY "challenge"."acct_id","challenge"."pro_id"'
        ') AS "sum" '
        'GROUP BY "sum"."acct_id" ORDER BY "sum"."acct_id" ASC;'),
        (UserService.ACCTTYPE_USER,ProService.STATUS_ONLINE))

    ratemap = {}
    for acct_id,rate in cur:
        ratemap[acct_id] = rate

    yield cur.execute(('SELECT "rank"."acct_id","rank"."pro_id",'
        '(0.3 * power(0.66,("rank"."rank" - 1))) AS "weight" FROM ('
        '    SELECT "challenge"."acct_id","challenge"."pro_id",'
        '    row_number() OVER ('
        '        PARTITION BY "challenge"."pro_id" ORDER BY MIN('
        '        "challenge"."chal_id") ASC) AS "rank" '
        '    FROM "challenge" '
        '    INNER JOIN "problem" '
        '    ON "challenge"."pro_id" = "problem"."pro_id" '
        '    INNER JOIN "account" '
        '    ON "challenge"."acct_id" = "account"."acct_id" '
        '    INNER JOIN "challenge_state" '
        '    ON "challenge"."chal_id" = "challenge_state"."chal_id" '
        '    WHERE "account"."class" && "problem"."class" '
        '    AND "challenge_state"."state" = 1 '
        '    AND "account"."acct_type" = %s '
        '    AND "problem"."status" = %s '
        '    GROUP BY "challenge"."acct_id","challenge"."pro_id"'
        ') AS "rank" WHERE "rank"."rank" < 17;'),
        (UserService.ACCTTYPE_USER,ProService.STATUS_ONLINE))
    
    err,prolist = yield from ProService.inst.list_pro()
    promap = {}
    for pro in prolist:
        promap[pro['pro_id']] = pro['rate']

    bonusmap = {}
    for acct_id,pro_id,weight in cur:
        ratemap[acct_id] += promap[pro_id] * float(weight)

    for acct in acctlist:
        acct_id = acct['acct_id']
        if acct_id in ratemap:
            acct['rate'] = math.floor(ratemap[acct_id])

        else:
            acct['rate'] = 0

        '''
        yield cur.execute('SELECT '
                'SUM("test_valid_rate"."rate" * '
                '    CASE WHEN "valid_test"."timestamp" < "valid_test"."expire" '
                '    THEN 1 ELSE '
                '    (1 - (GREATEST(date_part(\'days\',justify_interval('
                '    age("valid_test"."timestamp","valid_test"."expire") '
                '    + \'1 days\')),-1)) * 0.15) '
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
                'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx" ',
                (acct['acct_id'],ChalService.STATE_AC))
        if cur.rowcount != 1:
            return

        rate = cur.fetchone()[0]
        rate = None
        if rate == None:
            rate = 0
        
        extrate = 0
        if acct['class'] == 0:
            yield cur.execute('SELECT '
                    'SUM("test_valid_rate"."rate") '
                    'AS "rate" FROM "test_valid_rate" '
                    'INNER JOIN ('
                    '    SELECT "test"."pro_id","test"."test_idx" '
                    '    FROM "test" '
                    '    INNER JOIN "problem" '
                    '    ON "test"."pro_id" = "problem"."pro_id" '
                    '    WHERE "test"."acct_id" = %s '
                    '    AND "test"."state" = %s '
                    '    AND %s && "problem"."class" '
                    '    GROUP BY "test"."pro_id","test"."test_idx"'
                    ') AS "valid_test" '
                    'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
                    'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx" ',
                    (acct['acct_id'],ChalService.STATE_AC,[2]))
            if cur.rowcount != 1:
                return

            extrate = cur.fetchone()[0]
            if extrate == None:
                extrate = 0
        '''

        '''
        yield cur.execute(('SELECT '
            '"pro_rank"."pro_id",'
            '(0.3 * power(0.66,("pro_rank"."rank" - 1))) AS "weight" FROM ('
            '    SELECT '
            '    "challenge"."pro_id","challenge"."acct_id",'
            '    row_number() OVER ('
            '        PARTITION BY "challenge"."pro_id" ORDER BY MIN('
            '        "challenge"."chal_id") ASC) AS "rank" '
            '    FROM "challenge" '
            '    INNER JOIN ('
            '        SELECT "pro_id" FROM "challenge" '
            '        WHERE "challenge"."acct_id" = %s'
            '    ) AS need_id ON "challenge"."pro_id" = "need_id"."pro_id" '
            '    INNER JOIN "challenge_state" '
            '    ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            '    INNER JOIN "problem" ON '
            '    "challenge"."pro_id" = "problem"."pro_id" '
            '    INNER JOIN "account" '
            '    ON "challenge"."acct_id" = "account"."acct_id" '
            '    WHERE "challenge_state"."state" = %s '
            '    AND "problem"."class" && "account"."class" '
            '    GROUP BY "challenge"."pro_id","challenge"."acct_id"'
            ') AS "pro_rank" WHERE "pro_rank"."acct_id" = %s;'),
            (acct['acct_id'],ChalService.STATE_AC,acct['acct_id']))

        weightmap = {}
        for pro_id,weight in cur:
            weightmap[pro_id] = float(weight)

        bonus = 0
        for pro in prolist:
            pro_id = pro['pro_id']
            if pro_id in weightmap:
                bonus += pro['rate'] * weightmap[pro_id]

        totalrate = (math.floor(rate) + math.floor(extrate) +
                math.floor(bonus))

        acct['rate'] = totalrate
        '''

    acctlist.sort(key = lambda acct : acct['rate'],reverse = True)
    yield mc.set('ratelist',acctlist)

if __name__ == '__main__':
    @coroutine
    def _update_ratelist():
        yield from update_ratelist(db,mc)

    httpsock = tornado.netutil.bind_sockets(6000)
    #tornado.process.fork_processes(0)

    db = pg.AsyncPG(config.DBNAME_OJ,config.DBUSER_OJ,config.DBPW_OJ,
            dbtz = '+8')
    rs = redis.StrictRedis(host = 'localhost',port = 6379,db = 1)
    mc = mcd.AsyncMCD()
    UserService(db,rs)
    ProService(db,rs)
    ChalService(db,mc)
    PackService(db,mc)

    args = {
        'db':db,
        'mc':mc,
        'rs':rs
    }
    app = tornado.web.Application([
        ('/index',IndexHandler,args),
        ('/rate',RateHandler,args),
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
