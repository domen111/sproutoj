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

        self.rs.delete('rate@kernel_True')
        self.rs.delete('rate@kernel_False')

        return (None,None)

    def running(self):
        err,meta = self.get()

        if meta['status'] == ContestConst.STATUS_OFFLINE:
            return (None,False)

        now = datetime.datetime.now().replace(
                tzinfo = datetime.timezone(datetime.timedelta(hours = 8)))
        if meta['start'] > now or meta['end'] <= now:
            return (None,False)

        return (None,True)

class BoardHandler(RequestHandler):
    @reqenv
    def get(self):
        err,meta = Service.Contest.get()
        if err:
            self.error(err)
            return

        if meta['status'] == ContestConst.STATUS_OFFLINE:
            self.error('Eacces')
            return

        if (meta['status'] == ContestConst.STATUS_HIDDEN and
                self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL):
            self.error('Eacces')
            return

        clas = meta['class']

        err,prolist = yield from Service.Pro.list_pro(acct = self.acct,
                clas = clas)
        err,acctlist = yield from Service.Rate.list_rate(acct = self.acct,
                clas = clas)
        err,ratemap = yield from Service.Rate.map_rate(clas = clas)

        rank = 0
        last_rate = None
        for acct in acctlist:
            if acct['rate'] != last_rate:
                rank += 1
                last_rate = acct['rate']

            acct['rank'] = rank

        self.render('board',
                prolist = prolist,
                acctlist = acctlist,
                ratemap = ratemap)
        return
