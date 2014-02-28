import math

from user import UserConst
from pro import ProConst
from req import RequestHandler
from req import reqenv
from req import Service

class RateService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs

    def list_rate(self):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "acct_id","name","class" FROM "account" '
            'WHERE "acct_type" = %s;'),
            (UserConst.ACCTTYPE_USER,))

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
            (UserConst.ACCTTYPE_USER,ProConst.STATUS_ONLINE))

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
            (UserConst.ACCTTYPE_USER,ProConst.STATUS_ONLINE))
        
        err,prolist = yield from Service.Pro.list_pro()
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

        acctlist.sort(key = lambda acct : acct['rate'],reverse = True)
        return (None,acctlist)

    def list_state(self):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "challenge"."acct_id","challenge"."pro_id",'
            'MIN("challenge_state"."state") AS "state" '
            'FROM "challenge" '
            'INNER JOIN "challenge_state" '
            'ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            'GROUP BY "challenge"."acct_id","challenge"."pro_id";'))

        statemap = {}
        for acct_id,pro_id,state in cur:
            if acct_id not in statemap:
                statemap[acct_id] = {}
            
            statemap[acct_id][pro_id] = state

        return (None,statemap)

class RateHandler(RequestHandler):
    @reqenv
    def get(self):
        err,ratelist = yield from Service.Rate.list_rate()
        if err:
            self.finish(err)
            return

        self.render('rate',ratelist = ratelist)
        return

class ScbdHandler(RequestHandler):
    @reqenv
    def get(self):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "acct_id","name","class" FROM "account" '
            'WHERE "acct_type" = %s;'),
            (UserConst.ACCTTYPE_USER,))

        acctlist = list()
        for acct_id,name,clas in cur:
            acctlist.append({
                'acct_id':acct_id,
                'name':name,
                'class':clas[0]
            })

        err,acctlist = yield from Service.Acct.list_acct()
        err,prolist = yield from Service.Pro.list_pro()
        err,statemap = yield from Service.Rate.list_state()

        self.render('scbd',
                acctlist = acctlist,
                prolist = prolist,
                statemap = statemap)
        return
