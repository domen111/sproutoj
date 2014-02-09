import os
import json
from tornado.gen import coroutine
from tornado.websocket import websocket_connect

from user import UserService

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
        STATE_AC:'Solved',        
        STATE_WA:'Wrong Answer',
        STATE_RE:'Runtime Error',
        STATE_TLE:'Time Limit Exceed',
        STATE_MLE:'Memory Limit Exceed',
        STATE_CE:'Compile Error',
        STATE_ERR:'Internal Error',
        STATE_JUDGE:'Judging',
    }

    def __init__(self,db,mc):
        self.db = db
        self.mc = mc
        self.ws = None

        self._collect_judge()

        ChalService.inst = self

    def add_chal(self,pro_id,acct_id,code):
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
        yield cur.execute(('UPDATE "challenge" '
            'SET meta = \'\' WHERE "chal_id" = %s;'),
            (chal_id,))

        if cur.rowcount != 1:
            return ('Enoext',None)

        yield cur.execute('DELETE FROM "test" WHERE "chal_id" = %s;',
                (chal_id,))

        yield cur.execute('REFRESH MATERIALIZED VIEW collect_test;')

        return (None,None)

    def get_chal(self,chal_id):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
            '"challenge"."pro_id",'
            '"challenge"."acct_id",'
            '"challenge"."meta",'
            '"challenge"."timestamp",'
            '"account"."name" AS "acct_name" '
            'FROM "challenge" '
            'INNER JOIN "account" '
            'ON "challenge"."acct_id" = "account"."acct_id" '
            'WHERE "chal_id" = %s;'),
            (chal_id,))

        if cur.rowcount != 1:
            return ('Enoext',None)

        pro_id,acct_id,meta,timestamp,acct_name = cur.fetchone()

        yield cur.execute(('SELECT "test_idx","state","runtime","memory" '
            'FROM "test" '
            'WHERE "chal_id" = %s ORDER BY "test_idx" ASC;'),
            (chal_id,))

        tests = list()
        for test_idx,state,runtime,memory in cur:
            tests.append({
                'test_idx':test_idx,
                'state':state,
                'runtime':runtime,
                'memory':memory,
            })
        
        code_f = open('code/%d/main.cpp'%chal_id,'rb')
        code = code_f.read().decode('utf-8')
        code_f.close()

        return (None,{
            'chal_id':chal_id,
            'pro_id':pro_id,
            'acct_id':acct_id,
            'acct_name':acct_name,
            'meta':meta,
            'timestamp':timestamp,
            'tests':tests,
            'code':code
        })

    def emit_chal(self,chal_id,timelimit,memlimit,tests,code_path,res_path):
        cur = yield self.db.cursor()

        for i in range(len(tests)):
            tests[i]['test_idx'] = i
            tests[i]['state'] = ChalService.STATE_JUDGE

            yield cur.execute(('INSERT INTO "test" '
                '("chal_id","test_idx","state") VALUES (%s,%s,%s);'),
                (chal_id,i,ChalService.STATE_JUDGE))

        yield cur.execute('REFRESH MATERIALIZED VIEW collect_test;')

        if self.ws == None:
            self.ws = yield websocket_connect('ws://localhost:2501/judge')

        self.ws.write_message(json.dumps({
            'chal_id':chal_id,
            'timelimit':timelimit,
            'memlimit':memlimit,
            'tests':tests,
            'code_path':code_path,
            'res_path':res_path
        }))

        return (None,None)

    def update_test(self,chal_id,test_idx,state,runtime,memory):
        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "test" '
            'SET "state" = %s,"runtime" = %s,"memory" = %s '
            'WHERE "chal_id" = %s AND "test_idx" = %s;'),
            (state,runtime,memory,chal_id,test_idx))

        if cur.rowcount != 1:
            return ('Enoext',None)

        yield cur.execute('REFRESH MATERIALIZED VIEW collect_test;')

        return (None,None)

    def list_chal(self,off,num,max_accttype = UserService.ACCTTYPE_USER):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
            '"challenge"."chal_id",'
            '"challenge"."pro_id",'
            '"challenge"."acct_id",'
            '"challenge"."timestamp",'
            '"account"."name" AS "acct_name",'
            '"collect_test"."state",'
            '"collect_test"."runtime",'
            '"collect_test"."memory" '
            'FROM "challenge" '
            'INNER JOIN "account" '
            'ON "challenge"."acct_id" = "account"."acct_id" '
            'INNER JOIN "collect_test" '
            'ON "challenge"."chal_id" = "collect_test"."chal_id" '
            'WHERE "account"."type" <= %s '
            'ORDER BY "challenge"."timestamp" DESC OFFSET %s LIMIT %s;'),
            (max_accttype,off,num))
        
        challist = list()
        for (chal_id,pro_id,acct_id,timestamp,acct_name,
                state,runtime,memory) in cur:
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

    def get_stat(self):
        cur = yield self.db.cursor()
        yield cur.execute('SELECT COUNT("chal_id") FROM "challenge";')

        if cur.rowcount != 1:
            return ('Eunk',None)

        total_chal = cur.fetchone()[0]

        return (None,{
            'total_chal':total_chal    
        })

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
