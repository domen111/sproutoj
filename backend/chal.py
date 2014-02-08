import os
import json
from tornado.websocket import websocket_connect

class ChalService:
    STATE_AC = 1
    STATE_WA = 2
    STATE_JUDGE = 100

    STATE_STR = {
        STATE_AC:'Solved',        
        STATE_WA:'Wrong Answer',
        STATE_JUDGE:'Judging',
    }

    def __init__(self,db,mc):
        self.db = db
        self.mc = mc
        self.ws = None

        ChalService.inst = self

    def add_chal(self,pro_id,acct_id,code):
        cur = yield self.db.cursor()
        yield cur.execute(('INSERT INTO "challenge" '
            '("pro_id","acct_id","state") '
            'VALUES (%s,%s,%s) RETURNING "chal_id";'),
            (pro_id,acct_id,ChalService.STATE_JUDGE))

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
            'SET "state" = %s,meta = \'\' WHERE "chal_id" = %s;'),
            (ChalService.STATE_JUDGE,chal_id))

        if cur.rowcount != 1:
            return ('Enoext',None)

        yield cur.execute('DELETE FROM "test" WHERE "chal_id" = %s;',
                (chal_id,))

        return (None,None)

    def get_chal(self,chal_id):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
            '"pro_id","acct_id","state","meta","timestamp" '
            'FROM "challenge" WHERE "chal_id" = %s;'),
            (chal_id,))

        if cur.rowcount != 1:
            return ('Eunk',None)

        pro_id,acct_id,state,meta,timestamp = cur.fetchone()

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
                'memory':memory
            })
        
        code_f = open('code/%d/main.cpp'%chal_id,'rb')
        code = code_f.read().decode('utf-8')
        code_f.close()

        return (None,{
            'chal_id':chal_id,
            'pro_id':pro_id,
            'acct_id':acct_id,
            'state':state,
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
