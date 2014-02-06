import json
import uuid

from req import WebSocketHandler

class PackHandler(WebSocketHandler):
    STATE_HDR = 0
    STATE_DATA = 1
    CHUNK_MAX = 4194304

    def open(self):
        self.state = PackHandler.STATE_HDR
        self.output = None

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
            pack_token = str(uuid.UUID(hdr['pack_token']))
            pack_size = hdr['pack_size']

            self.remain = pack_size
            self.output = open('tmp/%s.tar.xz'%pack_token,'wb')
            self.state = PackHandler.STATE_DATA

            self.write_message('S')
            return

    def on_close(self):
        if self.output != None:
            self.output.close()

class PackService():
    def __init__(self,db,mc):
        self.db = db
        self.mc = mc

        PackService.inst = self

    def gen_token(self):
        pack_token = str(uuid.uuid1())
        yield self.mc.set('PACK_TOKEN@%s'%pack_token,0)

        return pack_token
