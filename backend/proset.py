from req import RequestHandler
from req import reqenv

class ProsetHandler(RequestHandler):
    @reqenv
    def get(self,page = None):
        self.render('proset')

    @reqenv
    def psot(self):
        pass
