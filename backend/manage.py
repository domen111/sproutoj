import os
import json
import datetime

from req import RequestHandler
from req import reqenv
from user import UserService
from pack import PackService
from pro import ProService
from chal import ChalService

class ManageHandler(RequestHandler):
    @reqenv
    def get(self,page = 'dash'):
        if self.acct['acct_type'] != UserService.ACCTTYPE_KERNEL:
            self.finish('Eacces')
            return

        if page == 'dash':
            self.render('manage-dash',page = page)
            return

        elif page == 'pro':
            err,prolist = yield from ProService.inst.list_pro(
                    ProService.STATUS_OFFLINE)

            self.render('manage-pro',page = page,prolist = prolist)
            return

        elif page == 'addpro':
            self.render('manage-pro-add',page = page)
            return

        elif page == 'updatepro':
            pro_id = int(self.get_argument('proid'))

            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

            self.render('manage-pro-update',page = page,pro = pro)
            return

    @reqenv
    def post(self,page):
        if self.acct['acct_type'] != UserService.ACCTTYPE_KERNEL:
            self.finish('Eacces')
            return

        if page == 'pack':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'gettoken':
                err,pack_token = yield from PackService.inst.gen_token()
                self.finish(json.dumps(pack_token))
                return

        elif page == 'pro':
            reqtype = self.get_argument('reqtype')
            
            if reqtype == 'addpro':
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                pack_token = self.get_argument('pack_token')

                err,pro_id = yield from ProService.inst.add_pro(
                        name,status,pack_token)
                if err:
                    self.finish(err)
                    return

                self.finish(json.dumps(pro_id))
                return

            elif reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                expire = self.get_argument('expire')
                pack_token = self.get_argument('pack_token')

                if expire == '':
                    expire = None

                else:
                    try:
                        expire = datetime.datetime.strptime(expire,
                                '%Y-%m-%dT%H:%M:%S.%fZ')

                    except ValueError:
                        self.finish('Eexpire')
                        return

                if pack_token == '':
                    pack_token = None

                err,ret = yield from ProService.inst.update_pro(
                        pro_id,name,status,expire,pack_token)
                if err:
                    self.finish(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'rechal':
                pro_id = int(self.get_argument('pro_id'))

                err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
                if err:
                    self.finish(err)
                    return

                cur = yield self.db.cursor()
                yield cur.execute(('SELECT "chal_id" FROM "challenge" '
                    'WHERE "pro_id" = %s'),
                    (pro_id,))

                for chal_id, in cur:
                    err,ret = yield from ChalService.inst.reset_chal(chal_id)
                    err,ret = yield from ChalService.inst.emit_chal(
                            chal_id,
                            pro_id,
                            pro['testm_conf'],
                            os.path.abspath('code/%d/main.cpp'%chal_id),
                            os.path.abspath('problem/%d/res'%pro_id))

                self.finish('S')
                return

        self.finish('Eunk')
        return
