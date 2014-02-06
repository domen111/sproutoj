import json

from req import RequestHandler
from req import reqenv
from pack import PackService
from pro import ProService

class ManageHandler(RequestHandler):
    @reqenv
    def get(self,page = 'dash'):
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

    @reqenv
    def post(self,page):
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

                self.finish(json.dumps(pro_id))
                return

            elif reqtype == 'updatepro':
                pro_id = self.get_argument('pro_id')
                name = self.get_argument('name')
                status = int(self.get_argument('status'))

                try:
                    pack_token = self.get_argument('pack_token')

                except tornado.web.HTTPError:
                    pack_token = None

                err,ret = yield from ProService.inst.update_pro(
                        pro_id,name,status,pack_token)
                if err:
                    self.finish(err)

                self.finish('S')
                return

            self.finish('Eunk')
            return
