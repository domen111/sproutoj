import os
import json
import math
import datetime
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
        yield cur.execute(('SELECT "name","status","class","expire" '
            'FROM "problem" WHERE "pro_id" = %s AND "status" <= %s;'),
            (pro_id,max_status))

        if cur.rowcount != 1:
            return ('Enoext',None)

        name,status,clas,expire = cur.fetchone()
        clas = clas[0]
        if expire == datetime.date.max:
            expire = None

        yield cur.execute(('SELECT "test_idx","compile_type","score_type",'
            '"check_type","timelimit","memlimit","weight","metadata" '
            'FROM "test_config" WHERE "pro_id" = %s ORDER BY "test_idx" ASC;'),
            (pro_id,))

        testm_conf = OrderedDict()
        for (test_idx,comp_type,score_type,check_type,timelimit,memlimit,weight,
                metadata) in cur:
            testm_conf[test_idx] = {
                'comp_type':comp_type,
                'score_type':score_type,
                'check_type':check_type,
                'timelimit':timelimit,
                'memlimit':memlimit,
                'weight':weight,
                'metadata':json.loads(metadata,'utf-8')
            }

        return (None,{
            'pro_id':pro_id,
            'name':name,
            'status':status,
            'expire':expire,
            'class':clas,
            'testm_conf':testm_conf
        })

    def list_pro(self,acct,state = False,clas = None):
        cur = yield self.db.cursor()

        max_status = self._get_acct_limit(acct)

        if clas == None:
            clas = [1,2]

        else:
            clas = [clas]

        if state == False:
            yield cur.execute(('SELECT "pro_id","name","status","expire",NULL '
                'FROM "problem" WHERE "status" <= %s AND "class" && %s '
                'ORDER BY "pro_id" ASC;'),
                (max_status,clas))

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
                'WHERE "problem"."status" <= %s AND "problem"."class" && %s '
                'GROUP BY "problem"."pro_id" '
                'ORDER BY "pro_id" ASC;'),
                (acct['acct_id'],max_status,clas))

        prolist = list()
        for pro_id,name,status,expire,state in cur:
            if expire == datetime.datetime.max:
                expire = None

            prolist.append({
                'pro_id':pro_id,
                'name':name,
                'status':status,
                'expire':expire,
                'state':state,
                'rate':2000
            })
        
        yield cur.execute(('SELECT "problem"."pro_id",'
            'SUM("test_config"."weight") AS "weight",'
            'SUM("test_valid_rate"."rate" * "test_config"."weight") AS "rate" '
            'FROM "test_valid_rate" '
            'INNER JOIN "test_config" '
            'ON "test_valid_rate"."pro_id" = "test_config"."pro_id" '
            'AND "test_valid_rate"."test_idx" = "test_config"."test_idx" '
            'INNER JOIN "problem" '
            'ON "test_valid_rate"."pro_id" = "problem"."pro_id" '
            'WHERE "problem"."status" <= %s '
            'GROUP BY "problem"."pro_id" '
            'ORDER BY "pro_id" ASC;'),
            (max_status,))

        ratemap = {}
        for pro_id,weight,rate in cur:
            ratemap[pro_id] = math.floor((rate + (100 - weight) * 2000) / 100)

        for pro in prolist:
            pro_id = pro['pro_id']
            if pro_id in ratemap:
                pro['rate'] = ratemap[pro_id]

        return (None,prolist)

    def add_pro(self,name,status,clas,expire,pack_token = None):
        if len(name) < ProService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)
        if clas not in [1,2]:
            return ('Eparam',None)

        if expire == None:
            expire = datetime.datetime.max

        cur = yield self.db.cursor()
        yield cur.execute(('INSERT INTO "problem" '
            '("name","status","class","expire") '
            'VALUES (%s,%s,%s,%s) RETURNING "pro_id";'),
            (name,status,[clas],expire))

        if cur.rowcount != 1:
            return ('Eunk',None)
        
        pro_id = cur.fetchone()[0]

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_token)
            if err:
                return (err,None)

        return (None,pro_id)

    def update_pro(self,pro_id,name,status,clas,expire,pack_token = None):
        if len(name) < ProService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)
        if clas not in [1,2]:
            return ('Eparam',None)

        if expire == None:
            expire = datetime.datetime.max

        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "problem" '
            'SET "name" = %s,"status" = %s,"class" = %s,"expire" = %s '
            'WHERE "pro_id" = %s;'),
            (name,status,[clas],expire,pro_id))

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
                'data':test_conf['data']
            } 
            yield cur.execute(('INSERT INTO "test_config" '
                '("pro_id","test_idx","compile_type","score_type","check_type",'
                '"timelimit","memlimit","weight","metadata") '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);'),
                (pro_id,test_idx,comp_type,score_type,check_type,
                    timelimit,memlimit,test_conf['weight'],
                    json.dumps(metadata)))

        return (None,None)

class ProsetHandler(RequestHandler):
    @reqenv
    def get(self):
        try:
            clas = int(self.get_argument('class'))

        except tornado.web.HTTPError:
            clas = None

        err,prolist = yield from ProService.inst.list_pro(
                self.acct,state = True,clas = clas)

        self.render('proset',prolist = prolist,clas = clas)
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
                'weight':test_conf['weight'],
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
                min(self.acct['acct_type'],UserService.ACCTTYPE_USER))
        err,challist = yield from ChalService.inst.list_chal(
                off,20,min(self.acct['acct_type'],UserService.ACCTTYPE_USER))

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
