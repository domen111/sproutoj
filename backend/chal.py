import os
import json
from tornado.gen import coroutine
from tornado.websocket import websocket_connect

from user import UserConst
from req import Service

class ChalConst:
    STATE_AC = 1
    STATE_WA = 2
    STATE_RE = 3
    STATE_TLE = 4
    STATE_MLE = 5
    STATE_CE = 6
    STATE_ERR = 7
    STATE_JUDGE = 100

    STATE_STR = {
        STATE_AC:'AC',
        STATE_WA:'WA',
        STATE_RE:'RE',
        STATE_TLE:'TLE',
        STATE_MLE:'MLE',
        STATE_CE:'CE',
        STATE_ERR:'IE',
        STATE_JUDGE:'JDG',
    }

class ChalService:
    STATE_AC = 1
    STATE_WA = 2
    STATE_RE = 3
    STATE_TLE = 4
    STATE_MLE = 5
    STATE_CE = 6
    STATE_ERR = 7
    STATE_JUDGE = 100

    STATE_STR = {
        STATE_AC:'Accepted',
        STATE_WA:'Wrong Answer',
        STATE_RE:'Runtime Error',
        STATE_TLE:'Time Limit Exceed',
        STATE_MLE:'Memory Limit Exceed',
        STATE_CE:'Compile Error',
        STATE_ERR:'Internal Error',
        STATE_JUDGE:'Judging',
    }

    def __init__(self,db,rs):
        self.db = db
        self.rs = rs
        self.ws = None

        self._collect_judge()

        ChalService.inst = self

    def add_chal(self,pro_id,acct_id,code):
        if Service.Contest.running()[1] == False:
            return ('Eacces',None)

        cur = yield self.db.cursor()
        yield cur.execute(('INSERT INTO "challenge" '
            '("pro_id","acct_id") '
            'VALUES (%s,%s) RETURNING "chal_id";'),
            (pro_id,acct_id))

        if cur.rowcount != 1:
            return ('Eunk',None)

        chal_id = cur.fetchone()[0]

        os.mkdir('code/%d'%chal_id)
        code_f = open('code/%d/main.cpp'%chal_id,'wb')
        code_f.write(code.encode('utf-8'))
        code_f.close()

        return (None,chal_id)

    def reset_chal(self,chal_id):
        cur = yield self.db.cursor()
        yield cur.execute('DELETE FROM "test" WHERE "chal_id" = %s;',
                (chal_id,))

        yield cur.execute('REFRESH MATERIALIZED VIEW challenge_state;')
        yield cur.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')
        self.rs.delete('rate@kernel_True')
        self.rs.delete('rate@kernel_False')

        return (None,None)

    def get_chal(self,chal_id,acct):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
            '"challenge"."pro_id",'
            '"challenge"."acct_id",'
            '"challenge"."timestamp",'
            '"account"."name" AS "acct_name" '
            'FROM "challenge" '
            'INNER JOIN "account" '
            'ON "challenge"."acct_id" = "account"."acct_id" '
            'WHERE "chal_id" = %s;'),
            (chal_id,))

        if cur.rowcount != 1:
            return ('Enoext',None)

        pro_id,acct_id,timestamp,acct_name = cur.fetchone()

        yield cur.execute(('SELECT "test_idx","state","runtime","memory" '
            'FROM "test" '
            'WHERE "chal_id" = %s ORDER BY "test_idx" ASC;'),
            (chal_id,))

        testl = list()
        for test_idx,state,runtime,memory in cur:
            testl.append({
                'test_idx':test_idx,
                'state':state,
                'runtime':int(runtime),
                'memory':int(memory),
            })
        
        if (acct['acct_id'] == acct_id or
                acct['acct_type'] == UserConst.ACCTTYPE_KERNEL):
            code_f = open('code/%d/main.cpp'%chal_id,'rb')
            code = code_f.read().decode('utf-8')
            code_f.close()

        else:
            code = None

        return (None,{
            'chal_id':chal_id,
            'pro_id':pro_id,
            'acct_id':acct_id,
            'acct_name':acct_name,
            'timestamp':timestamp,
            'testl':testl,
            'code':code
        })

    def emit_chal(self,chal_id,pro_id,testm_conf,code_path,res_path):
        cur = yield self.db.cursor()

        yield cur.execute(('SELECT "acct_id","timestamp" FROM "challenge" '
            'WHERE "chal_id" = %s;'),
            (chal_id,))
        if cur.rowcount != 1:
            return ('Enoext',None)

        acct_id,timestamp = cur.fetchone()

        testl = list()
        for test_idx,test_conf in testm_conf.items():
            testl.append({
                'test_idx':test_idx,
                'comp_type':test_conf['comp_type'],
                'check_type':test_conf['check_type'],
                'timelimit':test_conf['timelimit'],
                'memlimit':test_conf['memlimit'],
                'metadata':test_conf['metadata']
            })

            yield cur.execute(('INSERT INTO "test" '
                '("chal_id","acct_id","pro_id","test_idx","state","timestamp") '
                'VALUES (%s,%s,%s,%s,%s,%s);'),
                (chal_id,acct_id,pro_id,test_idx,
                    ChalService.STATE_JUDGE,timestamp))

        yield cur.execute('REFRESH MATERIALIZED VIEW challenge_state;')

        if self.ws == None:
            self.ws = yield websocket_connect('ws://localhost:2501/judge')

        self.ws.write_message(json.dumps({
            'chal_id':chal_id,
            'testl':testl,
            'code_path':code_path,
            'res_path':res_path
        }))

        return (None,None)

    def list_chal(self,off,num,min_accttype = UserConst.ACCTTYPE_USER,
            flt = {'pro_id':None,'acct_id':None}):

        fltquery,fltarg = self._get_fltquery(flt)

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
            '"challenge"."chal_id",'
            '"challenge"."pro_id",'
            '"challenge"."acct_id",'
            '"challenge"."timestamp",'
            '"account"."name" AS "acct_name",'
            '"challenge_state"."state",'
            '"challenge_state"."runtime",'
            '"challenge_state"."memory" '
            'FROM "challenge" '
            'INNER JOIN "account" '
            'ON "challenge"."acct_id" = "account"."acct_id" '
            'LEFT JOIN "challenge_state" '
            'ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            'WHERE "account"."acct_type" >= %s' +  fltquery +
            'ORDER BY "challenge"."timestamp" DESC OFFSET %s LIMIT %s;'),
            [min_accttype] + fltarg + [off,num])
        
        challist = list()
        for (chal_id,pro_id,acct_id,timestamp,acct_name,
                state,runtime,memory) in cur:
            if state == None:
                state = ChalService.STATE_JUDGE

            if runtime == None:
                runtime = 0
            else:
                runtime = int(runtime)

            if memory == None:
                memory = 0
            else:
                memory = int(memory)

            challist.append({
                'chal_id':chal_id,
                'pro_id':pro_id,
                'acct_id':acct_id,
                'timestamp':timestamp,
                'acct_name':acct_name,
                'state':state,
                'runtime':runtime,
                'memory':memory
            })

        return (None,challist)

    def get_stat(self,min_accttype = UserConst.ACCTTYPE_USER,flt = None):
        fltquery,fltarg = self._get_fltquery(flt)

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT COUNT(1) FROM "challenge" '
            'INNER JOIN "account" '
            'ON "challenge"."acct_id" = "account"."acct_id" '
            'WHERE "account"."acct_type" >= %s' + fltquery + ';'),
            [min_accttype] + fltarg)

        if cur.rowcount != 1:
            return ('Eunk',None)

        total_chal = cur.fetchone()[0]
        return (None,{
            'total_chal':total_chal    
        })

    def update_test(self,chal_id,test_idx,state,runtime,memory):
        cur = yield self.db.cursor()

        yield cur.execute(('UPDATE "test" '
            'SET "state" = %s,"runtime" = %s,"memory" = %s '
            'WHERE "chal_id" = %s AND "test_idx" = %s;'),
            (state,runtime,memory,chal_id,test_idx))

        if cur.rowcount != 1:
            return ('Enoext',None)

        yield cur.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')
        yield cur.execute('REFRESH MATERIALIZED VIEW challenge_state;')
        self.rs.delete('prolist')
        self.rs.delete('rate@kernel_True')
        self.rs.delete('rate@kernel_False')

        return (None,None)

    def _get_fltquery(self,flt):
        query = ' '
        arg = []
        if flt['pro_id'] != None:
            query += 'AND "challenge"."pro_id" = %s '
            arg.append(flt['pro_id'])

        if flt['acct_id'] != None:
            query += 'AND "challenge"."acct_id" = %s '
            arg.append(flt['acct_id'])

        return (query,arg)

    @coroutine
    def _collect_judge(self):
        if self.ws == None:
            self.ws = yield websocket_connect('ws://localhost:2501/judge')

        while True:
            ret = yield self.ws.read_message()
            if ret == None:
                break

            res = json.loads(ret,'utf-8')
            err,ret = yield from self.update_test(
                    res['chal_id'],
                    res['test_idx'],
                    res['state'],
                    res['runtime'],
                    res['memory'])
