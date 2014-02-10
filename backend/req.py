import types
import tornado.template
import tornado.gen
import tornado.web
import tornado.websocket

from user import UserService

class RequestHandler(tornado.web.RequestHandler):
    def __init__(self,*args,**kwargs):
        self.db = kwargs.pop('db')
        self.mc = kwargs.pop('mc')

        super().__init__(*args,**kwargs)
        
    def render(self,templ,**kwargs):
        tpldr = tornado.template.Loader('templ')

        if self.acct['acct_id'] != UserService.ACCTID_GUEST:
            kwargs['acct_id'] = self.acct['acct_id']
        
        else:
            kwargs['acct_id'] = ''

        self.finish(tpldr.load(templ + '.templ').generate(**kwargs))
        return

def reqenv(func):
    @tornado.gen.coroutine
    def wrap(self,*args,**kwargs):
        err,acct_id = yield from UserService.inst.getsign(self)
        if err == None:
            err,acct = yield from UserService.inst.getinfo(acct_id)
            self.acct = acct

        else:
            self.acct = {
                'acct_id':0,
                'acct_type':UserService.ACCTTYPE_USER,
                'mail':'',
                'name':''
            }

        ret = func(self,*args,**kwargs)
        if isinstance(ret,types.GeneratorType):
            ret = yield from ret

        return ret

    return wrap

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def __init__(self,*args,**kwargs):
        self.db = kwargs.pop('db')
        self.mc = kwargs.pop('mc')

        super().__init__(*args,**kwargs)
