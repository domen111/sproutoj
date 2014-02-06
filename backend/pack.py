import os
import json
import uuid
import tornado.concurrent

from req import WebSocketHandler

class PackHandler(WebSocketHandler):
    STATE_HDR = 0
    STATE_DATA = 1
    CHUNK_MAX = 65536

    def open(self):
        self.state = PackHandler.STATE_HDR
        self.output = None
        self.remain = 0

    def on_message(self,msg):
        if self.state == PackHandler.STATE_DATA:
            size = len(msg)
            if size > PackHandler.CHUNK_MAX or size > self.remain:
                self.write_message('Echunk')
                return

            self.output.write(msg)
        
            self.remain -= size
            self.write_message('S')
            return

        elif self.state == PackHandler.STATE_HDR:
            hdr = json.loads(msg,'utf-8')

            self.pack_token = str(uuid.UUID(hdr['pack_token']))
            self.remain = hdr['pack_size']
            self.output = open('tmp/%s.tar.xz'%self.pack_token,'wb')
            self.state = PackHandler.STATE_DATA

            self.write_message('S')
            return

    def on_close(self):
        if self.output != None:
            self.output.close()

        if self.remain > 0:
            os.remove('tmp/%s.tar.xz'%self.pack_token)

class PackService():
    def __init__(self,db,mc):
        self.db = db
        self.mc = mc

        PackService.inst = self

    def gen_token(self):
        pack_token = str(uuid.uuid1())
        yield self.mc.set('PACK_TOKEN@%s'%pack_token,0)

        return (None,pack_token)

    @tornado.concurrent.return_future
    def unpack(self,pack_token,dst,clean = False,callback = None):
        def _rm_cb(code):
            os.makedirs(dst,0o700)
            _tar()

        def _tar():
            sub = tornado.process.Subprocess(
                    ['/bin/tar','-Jxf','tmp/%s.tar.xz'%pack_token,'-C',dst])
            sub.set_exit_callback(_tar_cb)

        def _tar_cb(code):
            if code != 0:
                callback(('Eunk',None))

            callback((None,None))

        if clean == False:
            _tar()

        else:
            sub = tornado.process.Subprocess(
                    ['/bin/rm','-Rf',dst])
            sub.set_exit_callback(_rm_cb)
