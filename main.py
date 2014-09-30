import cgi
import sys
import logging
import traceback
import struct
from datetime import datetime
from base64 import urlsafe_b64encode as b64encode, urlsafe_b64decode as b64decode

from google.appengine.api.datastore_errors import *
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from models import Replay, ReplayParse, ReplayContent

webapp.template.register_template_library('templatetags')

class BaseHandler(webapp.RequestHandler):
    def respond(self, templatename, params=None):
        if params is None:
            params = {}

        if not templatename.endswith('.html'):
            templatename += '.html'
        templatename = 'templates/' + templatename

        self.response.out.write(template.render(templatename, params))

    def not_found(self):
        self.error(404)
        return self.respond('404')

ON_PAGE = 20

class MainPage(BaseHandler):
    def dump_bookmark(self, ord, replay):
        if ord == 'a':
            added = map(replay.added.__getattribute__,('year', 'month','day','hour','minute','second','microsecond'))
            next = struct.pack("H5BI", *added)
        elif ord == 'f':
            next = replay.filename.encode('utf-8')
            
        return b64encode('%s|%s|%s' % (ord, b64encode(next), replay.key().id()))
        
    def load_bookmark(self, bookmark):
        ord, next, key = b64decode(bookmark.encode('utf-8')).split('|')    
        if ord == 'a':
            filter = datetime(*struct.unpack("H5BI", b64decode(next)))
        elif ord == 'f':
            filter = b64decode(next).decode('utf-8')
        key = db.Key.from_path('Replay', int(key))
        return ord, filter, key
            
    SORT = {'a':('-added', 'added =', 'added <'),
            'f':('filename', 'filename =', 'filename >')}

    def get(self):
        ord = self.request.get('o', 'a')
        if ord not in ('a','f'):
            ord = 'a'
        next = None
        # Paging by http://google-appengine.googlegroups.com/web/efficient_paging_using_key_instead_of_a_dedicated_unique_property.txt
        bookmark = self.request.get('from')
        if bookmark:
            try:
                ord, first, key = self.load_bookmark(bookmark)
            except (ValueError, TypeError):
                return self.redirect("/")

            replays = Replay.all(keys_only=True).filter(self.SORT[ord][1], first).filter('__key__ >=', key).order('__key__').fetch(ON_PAGE+1)
            if len(replays) < ON_PAGE + 1:
                replays.extend(Replay.all(keys_only=True).filter(self.SORT[ord][2], first).order(self.SORT[ord][0]).order('__key__').fetch(ON_PAGE+1-len(replays)))
        else:
            replays = Replay.all(keys_only=True).order(self.SORT[ord][0]).order('__key__').fetch(ON_PAGE+1)
        
        replays = Replay.get(replays)
         
        if len(replays) == ON_PAGE+1:
            next = self.dump_bookmark(ord, replays[ON_PAGE])
            replays = replays[:-1]

        self.respond('main', {'title':'browse replays',
                              'replays': replays,
                              'next': next})
class SearchPage(BaseHandler):
    def load_bookmark(self, bookmark):
        type, search, value, key = b64decode(bookmark.encode('utf-8')).split('|')
        search, value = [b64decode(v).decode('utf-8') for v in (search, value)]
        key = db.Key.from_path('Replay', int(key))
        return {'f':'filename', 'p':'players'}[type], search, value, key
    def dump_bookmark(self, type, search, replay):
        if type=='players':
            try:
                value = (p for p in replay.players if search <= p < search + u'\ufffd').next()
            except StopIteration:
                value = replay.players[0]
        else:
            value = getattr(next, type)
        search, value = [b64encode(v.encode('utf-8')) for v in (search, value)]
        return b64encode('|'.join([type[0], search, value, str(replay.key().id())]))
    
    def get(self):
        next = None
        # Paging by http://google-appengine.googlegroups.com/web/efficient_paging_using_key_instead_of_a_dedicated_unique_property.txt
        bookmark = self.request.get('from')
        if bookmark:
            try:
                type, search, value, key = self.load_bookmark(bookmark)
            except (ValueError, TypeError):
                return self.redirect("/")

            replays = Replay.all(keys_only=True).filter('%s =' % type, value).filter('__key__ >=', key).order('__key__').fetch(ON_PAGE+1)
            if len(replays) < ON_PAGE + 1:
                replays.extend(Replay.all(keys_only=True).filter('%s >' % type, value).filter('%s <' % type, search + u'\ufffd').order(type).order('__key__').fetch(ON_PAGE+1-len(replays)))
        else:
            if self.request.get('player'):
                type = 'players'
                search = self.request.get('player')
            elif self.request.get('file'):
                type = 'filename'
                search = self.request.get('file')
            else:
                return self.redirect('/')
            replays = Replay.all(keys_only=True).filter('%s >=' % type, search).filter('%s <' % type, search + u'\ufffd').order(type).order('__key__').fetch(ON_PAGE+1)
        
        replays = Replay.get(replays)
         
        if len(replays) == ON_PAGE+1:
            next = self.dump_bookmark(type, search, replays[ON_PAGE])
            replays = replays[:-1]

        self.respond('main', {'title': "%s search results for '%s'" % (type, search),
                              'replays': replays,
                              'next': next})

class ViewReplay(BaseHandler):
    def post(self):
        if isinstance(self.request.POST.get('replay', None), cgi.FieldStorage):
            try:
                filename = self.request.POST['replay'].filename
                if not filename.lower().endswith('.rpl'):
                    raise ValueError('Not a replay file! (%s)' % filename)
                replay, key, parsed = Replay.parse(self.request.get('replay'), filename, 'save' in self.request.POST)
                if 'view' in self.request.POST:
                    if parsed is None:
                        parsed = ReplayParse.get(key)
                    return self.respond('view', {'settings': parsed.settings,
                                                 'frames': parsed.frames,
                                                 'parsed': parsed})
            except:
                traceback.print_exception(*sys.exc_info())
                self.respond('error_parse', {})
            else:
                self.redirect('/view?id=%s' % key.name())
        else:
            self.redirect('/')

    def get(self):
        if 'id' in self.request.GET:
            key = self.request.get('id')
            parsed = ReplayParse.get_by_key_name(key)
        elif 'name' in self.request.GET:
            replay = Replay.all().filter('filename =', self.request.get('name')).get()
            if replay is None:
                return self.not_found()
            return self.redirect('/view?id=%s' % Replay.parsed.get_value_for_datastore(replay).name(), permanent=True)
        else:
            return self.redirect("/")
        
        if parsed is None:
            return self.not_found()

        self.respond('view', {'settings': parsed.settings,
                              'frames': parsed.frames,
                              'parsed': parsed})

class DownloadReplay(BaseHandler):
    def get(self):
        if 'id' in self.request.GET:
            try:
                replay = Replay.get_by_id(int(self.request.get('id')))
            except ValueError: 
                replay = None
        elif 'name' in self.request.GET:
            replay = Replay.all().filter('filename =', self.request.get('name')).get()
            if replay is None:
                return self.not_found()
            return self.redirect('/down?id=%s' % replay.key().id(), permanent=True)
        elif 'hash' in self.request.GET:
            replay = Replay.all().filter('hash = ', self.request.get('hash')).get()

        if replay is None:
            return self.not_found()

        filename = replay.filename        
        content = replay.content.content

        self.response.headers['Content-Type'] = "application/octet-stream" 
        self.response.headers['Content-Disposition'] = 'attachment; filename="%s"' % filename
        self.response.out.write(content)

#import db_log
#db_log.patch_appengine()

application = webapp.WSGIApplication(
    [('/', MainPage),
     ('/search', SearchPage),
     ('/view', ViewReplay),
     ('/down', DownloadReplay),
     ],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__=='__main__':
    main()
