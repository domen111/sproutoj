import os
import json

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

    def emit_chal(self,chal_id,tests):
        cur = yield self.db.cursor()

        for i in range(len(tests)):
            yield cur.execute(('INSERT INTO "test" '
                '("chal_id","test_idx","state") VALUES (%s,%s,%s);'),
                (chal_id,i,tests[i]['state']))

        return (None,None)
