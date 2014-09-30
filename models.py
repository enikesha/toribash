import zlib
import hashlib 
from StringIO import StringIO

from google.appengine.ext import db

import parser

__all__ = ['Replay']

def dumps(dict):
    return zlib.compress(repr(dict), 9)
def loads(str):
    return eval(zlib.decompress(str))

class ReplayParse(db.Model):
    b_settings = db.BlobProperty()
    b_frames = db.BlobProperty()

    @staticmethod
    def create(key, settings, frames):
        ret = ReplayParse(key=key,
                          b_settings=dumps(settings),
                          b_frames=dumps(frames))
        ret._settings = settings
        ret._frames = frames
        return ret

    @property
    def settings(self):
        if getattr(self, '_settings', None) is None:
            self._settings = loads(self.b_settings)
        return self._settings

    @property
    def frames(self):
        if getattr(self, '_frames', None) is None:
            self._frames = loads(self.b_frames)
        return self._frames
    
class ReplayContent(db.Model):
    b_content = db.BlobProperty()

    @staticmethod 
    def create(key, content):
        return ReplayContent(key=key, b_content=zlib.compress(content, 9))

    @property
    def content(self):
        return zlib.decompress(self.b_content)


class Replay(db.Model):
    filename = db.StringProperty(required=True)
    added = db.DateTimeProperty(auto_now_add=True)
    hash = db.StringProperty()

    #
    fightname = db.StringProperty()
    author = db.StringProperty()
    players = db.StringListProperty()
    score = db.ListProperty(long, default=None)

    content = db.ReferenceProperty(ReplayContent)
    parsed = db.ReferenceProperty(ReplayParse)
   

    @staticmethod
    def parse(data, filename, save=False):
        hash = hashlib.sha1(data).hexdigest()
        repl = Replay.all().filter('hash =', hash).get()
        if repl is not None:
            return repl, Replay.parsed.get_value_for_datastore(repl), None

        settings, frames = parser.parse(StringIO(data))
        parsed_key = db.Key.from_path('ReplayParse', hash)
        parsed = ReplayParse.create(parsed_key, settings, frames)
        content_key = db.Key.from_path('ReplayContent', hash)
        content = ReplayContent.create(content_key, data)

        params = {'filename': filename, 
                  'hash': hash,
                  'content': content_key,
                  'parsed': parsed_key}
        params.update([(key, settings[key]) for key in ('fightname', 'author', 'players', 'score') if settings.get(key) is not None])
        replay = Replay(**params)
        if save:
            db.put((replay, parsed, content))

        return replay, parsed_key, parsed
