#!/usr/bin/python3

import redis
import tornado.ioloop
import tornado.netutil
import tornado.process
import tornado.httpserver
import tornado.web
from tornado.web import RequestHandler
from tornado.gen import coroutine

class PackHandler(RequestHandler):
    @coroutine
    def get(self):
        self.finish('Test Online Judge Lab')
        return

if __name__ == '__main__':
    httpsock = tornado.netutil.bind_sockets(8000)

    rs = redis.StrictRedis(host = 'localhost',port = 6379,db = 2)

    app = tornado.web.Application([
        #('/pack',PackHandler,args),
    ],autoescape = 'xhtml_escape')

    httpsrv = tornado.httpserver.HTTPServer(app)
    httpsrv.add_sockets(httpsock)
    
    tornado.ioloop.IOLoop.instance().start()
