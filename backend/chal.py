import os

class ChalService:
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
        
        code_f = open('code/%d/main.cpp'%chal_id,'rb')
        code = code_f.read().decode('utf-8')
        code_f.close()

        pro_id,acct_id,state,meta,timestamp = cur.fetchone()
        return (None,{
            'chal_id':chal_id,
            'pro_id':pro_id,
            'acct_id':acct_id,
            'state':state,
            'meta':meta,
            'timestamp':timestamp,
            'code':code
        })
