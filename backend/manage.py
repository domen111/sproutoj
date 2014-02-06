import json
import uuid

from req import RequestHandler
from req import reqenv
from pack import PackService

class ManageHandler(RequestHandler):
    @reqenv
    def get(self,page = 'dash'):
        if page == 'pro':
            self.render('manage-pro',page = page)

    @reqenv
    def post(self,page):
        if page == 'pro':
            reqtype = self.get_argument('reqtype')
            if reqtype == 'addpro':
                pack_token = yield from PackService.inst.gen_token()

                self.finish(json.dumps({
                    'pro_id':1,
                    'pack_token':pack_token
                }))
                return

            self.finish('Eunk')
            return
