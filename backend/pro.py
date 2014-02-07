import os
import json
import tornado.process
import tornado.concurrent

from req import RequestHandler
from req import reqenv
from user import UserService
from chal import ChalService
from pack import PackService

class ProService:
    NAME_MIN = 1
    NAME_MAX = 64
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

    def __init__(self,db,mc):
        self.db = db
        self.mc = mc

        ProService.inst = self

    def get_pro(self,pro_id,acct):
        max_status = self._get_acct_limit(acct)

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "pro_id","name","status" FROM "problem" '
            'WHERE "pro_id" = %s AND "status" <= %s;'),
            (pro_id,max_status))

        if cur.rowcount != 1:
            return ('Enoext',None)

        pro_id,name,status = cur.fetchone()
        return (None,{
            'pro_id':pro_id,
            'name':name,
            'status':status
        })

    def list_pro(self,max_status = STATUS_ONLINE):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "pro_id","name","status" FROM "problem" '
            'WHERE "status" <= %s ORDER BY "pro_id" ASC;'),
            (max_status,))

        prolist = list()
        for pro_id,name,status in cur:
            prolist.append({
                'pro_id':pro_id,
                'name':name,
                'status':status
            })

        return (None,prolist)

    def add_pro(self,name,status,pack_token = None):
        size = len(name)
        if size < ProService.NAME_MIN:
            return ('Enamemin',None)
        if size > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)

        cur = yield self.db.cursor()
        yield cur.execute(('INSERT INTO "problem" '
            '("name","status") '
            'VALUES (%s,%s) RETURNING "pro_id";'),
            (name,status))

        if cur.rowcount != 1:
            return ('Eunk',None)
        
        pro_id = cur.fetchone()[0]

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_token)
            if err:
                return (err,None)

        return (None,pro_id)

    def update_pro(self,pro_id,name,status,pack_token = None):
        if len(name) < ProService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)

        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "problem" '
            'SET "name" = %s,"status" = %s '
            'WHERE "pro_id" = %s;'),
            (name,status,pro_id))

        if cur.rowcount != 1:
            return ('Eunk',None)

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_token)
            if err:
                return (err,None)
        
        return (None,None)

    def _get_acct_limit(self,acct):
        if acct['type'] == UserService.ACCTTYPE_KERNEL:
            return ProService.STATUS_OFFLINE

        else:
            return ProService.STATUS_ONLINE

    def _unpack_pro(self,pro_id,pack_token):
        err,ret = yield PackService.inst.unpack(
                pack_token,'problem/%d'%pro_id,True)
        if err:
            return (err,None)

        os.chmod('problem/%d'%pro_id,0o755)
        try:
            os.symlink(os.path.abspath('problem/%d/http'%pro_id),
                    '../http/problem/%d'%pro_id)

        except FileExistsError:
            pass

        return (None,None)

class ProsetHandler(RequestHandler):
    @reqenv
    def get(self,page = None):
        err,prolist = yield from ProService.inst.list_pro()
        self.render('proset',prolist = prolist)
        return

    @reqenv
    def psot(self):
        pass

class ProHandler(RequestHandler):
    @reqenv
    def get(self,pro_id):
        pro_id = int(pro_id)

        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        self.render('pro',pro = pro)
        return

class SubmitHandler(RequestHandler):
    @reqenv
    def get(self,pro_id):
        pro_id = int(pro_id)

        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        self.render('submit',pro = pro)
        return

    @reqenv
    def post(self):
        pro_id = int(self.get_argument('pro_id'))
        code = self.get_argument('code')

        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        err,chal_id = yield from ChalService.inst.add_chal(
                pro_id,self.acct['acct_id'],code)

        self.finish(json.dumps(chal_id))
        return
