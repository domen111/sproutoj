import os
import json
import math
import tornado.process
import tornado.concurrent
import tornado.web
from collections import OrderedDict

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
        yield cur.execute(('SELECT "name","status","expire" FROM "problem" '
            'WHERE "pro_id" = %s AND "status" <= %s;'),
            (pro_id,max_status))

        if cur.rowcount != 1:
            return ('Enoext',None)

        name,status,expire = cur.fetchone()

        yield cur.execute(('SELECT "test_idx","compile_type","score_type",'
            '"check_type","timelimit","memlimit","metadata" '
            'FROM "test_config" WHERE "pro_id" = %s ORDER BY "test_idx" ASC;'),
            (pro_id,))

        testm_conf = OrderedDict()
        for (test_idx,comp_type,score_type,check_type,timelimit,memlimit,
                metadata) in cur:
            testm_conf[test_idx] = {
                'comp_type':comp_type,
                'score_type':score_type,
                'check_type':check_type,
                'timelimit':timelimit,
                'memlimit':memlimit,
                'metadata':json.loads(metadata,'utf-8')
            }

        return (None,{
            'pro_id':pro_id,
            'name':name,
            'status':status,
            'expire':expire,
            'testm_conf':testm_conf
        })

    def list_pro(self,acct,state = False):
        cur = yield self.db.cursor()

        max_status = self._get_acct_limit(acct)
        if state == False:
            yield cur.execute(('SELECT "pro_id","name","status","expire",NULL '
                'FROM "problem" WHERE "status" <= %s ORDER BY "pro_id" ASC;'),
                (max_status,))

        else:
            yield cur.execute(('SELECT '
                '"problem"."pro_id",'
                '"problem"."name",'
                '"problem"."status",'
                '"problem"."expire",'
                'MIN("challenge_state"."state") AS "state" '
                'FROM "challenge" '
                'INNER JOIN "challenge_state" '
                'ON "challenge"."chal_id" = "challenge_state"."chal_id" '
                'AND "challenge"."acct_id" = %s '
                'RIGHT JOIN "problem" '
                'ON "challenge"."pro_id" = "problem"."pro_id" '
                'WHERE "problem"."status" <= %s '
                'GROUP BY "problem"."pro_id" '
                'ORDER BY "pro_id" ASC;'),
                (acct['acct_id'],max_status))

        prolist = list()
        for pro_id,name,status,expire,state in cur:
            prolist.append({
                'pro_id':pro_id,
                'name':name,
                'status':status,
                'expire':expire,
                'state':state
            })

        return (None,prolist)

    def add_pro(self,name,status,expire,pack_token = None):
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
            '("name","status","expire") '
            'VALUES (%s,%s,%s) RETURNING "pro_id";'),
            (name,status,expire))

        if cur.rowcount != 1:
            return ('Eunk',None)
        
        pro_id = cur.fetchone()[0]

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_token)
            if err:
                return (err,None)

        return (None,pro_id)

    def update_pro(self,pro_id,name,status,expire,pack_token = None):
        if len(name) < ProService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)

        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "problem" '
            'SET "name" = %s,"status" = %s,"expire" = %s '
            'WHERE "pro_id" = %s;'),
            (name,status,expire,pro_id))

        if cur.rowcount != 1:
            return ('Enoext',None)

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_token)
            if err:
                return (err,None)
        
        return (None,None)

    def _get_acct_limit(self,acct):
        if acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
            return ProService.STATUS_OFFLINE

        else:
            return ProService.STATUS_ONLINE

    def _unpack_pro(self,pro_id,pack_token):
        err,ret = yield from PackService.inst.unpack(
                pack_token,'problem/%d'%pro_id,True)
        if err:
            return (err,None)

        try:
            os.chmod('problem/%d'%pro_id,0o755)
            os.symlink(os.path.abspath('problem/%d/http'%pro_id),
                    '../http/problem/%d'%pro_id)

        except FileExistsError:
            pass

        try:
            conf_f = open('problem/%d/conf.json'%pro_id)
            conf = json.load(conf_f)
            conf_f.close()

        except Exception:
            return ('Econf',None)

        comp_type = conf['compile']
        score_type = conf['score']
        check_type = conf['check']
        timelimit = conf['timelimit']
        memlimit = conf['memlimit'] * 1024

        cur = yield self.db.cursor()
        yield cur.execute('DELETE FROM "test_config" WHERE "pro_id" = %s;',
                (pro_id,))

        for test_idx,test_conf in enumerate(conf['test']):
            metadata = {
                'data':test_conf['data'],
                'weight':test_conf['weight']
            } 
            yield cur.execute(('INSERT INTO "test_config" '
                '("pro_id","test_idx","compile_type","score_type","check_type",'
                '"timelimit","memlimit","metadata") '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s);'),
                (pro_id,test_idx,comp_type,score_type,check_type,
                    timelimit,memlimit,json.dumps(metadata)))

        return (None,None)

class ProsetHandler(RequestHandler):
    @reqenv
    def get(self):
        err,prolist = yield from ProService.inst.list_pro(
                self.acct,state = True)

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

        testl = list()
        for test_idx,test_conf in pro['testm_conf'].items():
            testl.append({
                'test_idx':test_idx,
                'timelimit':test_conf['timelimit'],
                'memlimit':test_conf['memlimit'],
                'weight':test_conf['metadata']['weight'],
                'rate':2000
            })

        cur = yield self.db.cursor()

        yield cur.execute(('SELECT "test_idx","rate" FROM "test_valid_rate" '
            'WHERE "pro_id" = %s ORDER BY "test_idx" ASC;'),
            (pro_id,))
        
        countmap = {}
        for test_idx,count in cur:
            countmap[test_idx] = count

        for test in testl:
            if test['test_idx'] in countmap:
                test['rate'] = math.floor(countmap[test['test_idx']])

        self.render('pro',pro = {
            'pro_id':pro['pro_id'],
            'name':pro['name'],
            'status':pro['status']
        },testl = testl)
        return

class SubmitHandler(RequestHandler):
    @reqenv
    def get(self,pro_id):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('Esign')
            return

        pro_id = int(pro_id)
        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        self.render('submit',pro = pro)
        return

    @reqenv
    def post(self):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('Esign')
            return

        reqtype = self.get_argument('reqtype')
        if reqtype == 'submit':
            pro_id = int(self.get_argument('pro_id'))
            code = self.get_argument('code')

            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

            err,chal_id = yield from ChalService.inst.add_chal(
                    pro_id,self.acct['acct_id'],code)
            if err:
                self.finish(err)
                return

        elif (reqtype == 'rechal' and
                self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL):

            chal_id = int(self.get_argument('chal_id'))

            err,ret = yield from ChalService.inst.reset_chal(chal_id)
            err,chal = yield from ChalService.inst.get_chal(chal_id,self.acct)

            pro_id = chal['pro_id']
            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

        else:
            self.finish('Eparam')
            return

        err,ret = yield from ChalService.inst.emit_chal(
                chal_id,
                pro_id,
                pro['testm_conf'],
                os.path.abspath('code/%d/main.cpp'%chal_id),
                os.path.abspath('problem/%d/res'%pro_id))
        if err:
            self.finish(err)
            return

        self.finish(json.dumps(chal_id))
        return

class ChalListHandler(RequestHandler):
    @reqenv
    def get(self):
        try:
            off = int(self.get_argument('off'))

        except tornado.web.HTTPError:
            off = 0

        err,chalstat = yield from ChalService.inst.get_stat(
                min(self.acct['acct_type'],UserService.ACCTTYPE_MEMBER))
        err,challist = yield from ChalService.inst.list_chal(
                off,20,min(self.acct['acct_type'],UserService.ACCTTYPE_MEMBER))

        self.render('challist',chalstat = chalstat,challist = challist)
        return

    @reqenv
    def psot(self):
        pass

class ChalHandler(RequestHandler):
    @reqenv
    def get(self,chal_id):
        chal_id = int(chal_id)

        err,chal = yield from ChalService.inst.get_chal(chal_id,self.acct)
        if err:
            self.finish(err)
            return

        err,pro = yield from ProService.inst.get_pro(chal['pro_id'],self.acct)
        if err:
            self.finish(err)
            return

        if self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
            rechal = True

        else:
            rechal = False

        self.render('chal',pro = pro,chal = chal,rechal = rechal)
        return

    @reqenv
    def post(self):
        reqtype = self.get_argument('reqtype')
        self.finish('Eunk')
        return
