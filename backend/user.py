import base64
import bcrypt
import psycopg2
from tornado.gen import coroutine

import config

class UserService:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 32
    NAME_MIN = 1

    ACCTTYPE_KERNEL = 0
    ACCTTYPE_USER = 3

    def __init__(self,db,mc):
        self.db = db
        self.mc = mc

        UserService.inst = self

    def signin(self,mail,pw):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "acct_id","password" FROM "account" '
            'WHERE "mail" = %s;'),
            (mail,))

        if cur.rowcount != 1:
            return ('Esign',None)

        acct_id,hpw = cur.fetchone()
        hpw = base64.b64decode(hpw.encode('utf-8'))

        if bcrypt.hashpw(pw.encode('utf-8'),hpw) == hpw:
            return (None,acct_id)

        return ('Esign',None)

    def signup(self,mail,pw,name):
        if len(mail) < UserService.MAIL_MIN:
            return ('Emailmin',None)
        if len(mail) > UserService.MAIL_MAX:
            return ('Emailmax',None)
        if len(pw) < UserService.PW_MIN:
            return ('Epwmin',None)
        if len(pw) > UserService.PW_MAX:
            return ('Epwmax',None)
        if len(name) < UserService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > UserService.NAME_MAX:
            return ('Enamemax',None)

        cur = yield self.db.cursor()
        hpw = bcrypt.hashpw(pw.encode('utf-8'),bcrypt.gensalt(12))

        try:
            yield cur.execute(('INSERT INTO "account" '
                '("mail","password","name","type") '
                'VALUES (%s,%s,%s,%s) RETURNING "acct_id";'),
                (mail,base64.b64encode(hpw).decode('utf-8'),name,
                    UserService.ACCTTYPE_USER))

        except psycopg2.IntegrityError:
            return ('Eexist',None)

        if cur.rowcount != 1:
            return ('Eunk',None)

        return (None,cur.fetchone()[0])

    def getsign(self,req):
        acct_id = req.get_secure_cookie('id')
        if acct_id == None:
            return ('Esign',None)

        acct_id = int(acct_id)

        acct = yield self.mc.get('account@%d'%acct_id)
        if acct == None:
            cur = yield self.db.cursor()
            yield cur.execute('SELECT 1 FROM "account" WHERE "acct_id" = %s;',
                    (acct_id,))

            if cur.rowcount != 1:
                return ('Esign',None)

        return (None,acct_id)

    def getinfo(self,acct_id):
        acct = yield self.mc.get('account@%d'%acct_id)
        if acct == None:
            cur = yield self.db.cursor()
            yield cur.execute(('SELECT "mail","name","type" FROM "account" '
                'WHERE "acct_id" = %s;'),
                (acct_id,))

            if cur.rowcount != 1:
                return ('Enoext',None)

            mail,name,typ = cur.fetchone()
            acct = {
                'acct_id':acct_id,
                'mail':mail,
                'name':name,
                'type':typ
            }

            yield self.mc.set('account@%d'%acct_id,acct)

        return (None,{
            'acct_id':acct['acct_id'],
            'name':acct['name'],
            'type':acct['type']
        })
