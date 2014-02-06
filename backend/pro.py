import tornado.process
import tornado.concurrent

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
            err,ret = yield PackService.inst.unpack(
                    pack_token,'problem/%d'%pro_id,True)
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
            err,ret = yield PackService.inst.unpack(
                    pack_token,'problem/%d'%pro_id,True)
            if err:
                return (err,None)

        return (None,None)
