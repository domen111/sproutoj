import msgpack
import math
import datetime

from user import UserConst
from pro import ProConst
from req import RequestHandler
from req import reqenv
from req import Service

class ContestConst:
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

class ContestService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs

    def get(self):
        data = self.rs.get('contest')
        if data == None:
            return (None,{
                'class':0,
                'status':ContestConst.STATUS_OFFLINE,
                'start':datetime.datetime.now().replace(
                    tzinfo = datetime.timezone(
                    datetime.timedelta(hours = 8))),
                'end':datetime.datetime.now().replace(
                    tzinfo = datetime.timezone(
                    datetime.timedelta(hours = 8))),
            })

        meta = msgpack.unpackb(data,encoding = 'utf-8')

        start = datetime.datetime.fromtimestamp(meta['start'])
        meta['start'] = start.replace(tzinfo = datetime.timezone(
            datetime.timedelta(hours = 8)))

        end = datetime.datetime.fromtimestamp(meta['end'])
        meta['end'] = end.replace(tzinfo = datetime.timezone(
            datetime.timedelta(hours = 8)))

        return (None,meta)

    def set(self,clas,status,start,end):
        def _mp_encoder(obj):
            if isinstance(obj,datetime.datetime):
                return obj.astimezone(datetime.timezone.utc).timestamp()

            return obj

        self.rs.set('contest',msgpack.packb({
            'class':clas,
            'status':status,
            'start':start,
            'end':end
        },default = _mp_encoder))

        return (None,None)

class BoardHandler(RequestHandler):
    @reqenv
    def get(self):
        self.render('board')
        return
