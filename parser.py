#!/usr/bin/env python
import logging

__all__ = ['parse']

ints = lambda l: map(int, l)
floats = lambda l: map(float, l)
same = lambda _:_

class Parser(object):
    def __init__(self):
        self.settings = {}
        self.frames = {0:{'acts':{}}}
        self._frame = 0

    def parse_made_with(self, line):
        if line.startswith('with '):
            self.settings['made_with'] = line[5:]
    def parse_score(self, line):
        self.settings['score'] = ints(line.split())
    def parse_win(self, line):
        self.settings['win'] = line.split()
    def parse_version(self, line):
        self.settings['version'] = int(line)
    def parse_fightname(self, line):
        self.settings['fightname'] = unicode(line[3:], errors='replace')
    def parse_bout(self, line):
        pl, name = line.split('; ')
        self.settings.setdefault('players', ['',''])
        self.settings['players'][int(pl)] = unicode(name, errors='replace')
    def parse_fight(self, line):
        p = line[3:].split(None, 2)
        self.settings['fightname'] = unicode(p[0], errors='replace')
        self.settings['players'] = [unicode(pl, errors='replace') for pl in p[1:]]
    def parse_author(self, line):
        self.settings['author'] = unicode(line[3:], errors='replace')
    def parse_engage(self, line):
        pl, line = line.split('; ')
        p = line.split()
        self.settings.setdefault('engage', {})
        self.settings['engage'][pl] = {'pos':floats(p[0:3]), 'rot':floats(p[3:6])}

    GAME_PARAMS = {0: ('match_frames', same), 
                   1: ('turn_frames', same),
                   5: ('flags', int),
                   6: ('engage_distance', int),
                   7: ('damage', int),
                   9: ('mod', same),
                   14: ('engage_height', int),
                   19: ('engage_rotation', int),
                   21: ('engage_space', int),
                   25: ('gravity_x', float),
                   26: ('gravity_y', float),
                   27: ('gravity_z', float),
                   }
    def parse_newgame(self, line):
        line = line[2:]
        p = line.split()
        self.settings.update(dict([(lambda n, f: (n, f(p)))(*self.GAME_PARAMS[i]) 
                                   for i, p in enumerate(line.split()) if i in self.GAME_PARAMS]))

    def parse_frame(self, line):
        frame, line = line.split(';')
        frame = int(frame)
        self.frames.setdefault(frame, {'acts':{}})
        self._frame = frame
        if line.strip():
            self.frames[frame]['score'] = ints(line.strip().split()[1::-1])
    def parse_joint(self, line):
        pl, line = line.split('; ')
        p = ints(line.split(' '))
        pl = int(pl)
        self.frames[self._frame]['acts'].setdefault(pl, {})
        self.frames[self._frame]['acts'][pl]['joints'] = zip(p[::2], p[1::2])
    def parse_crush(self, line):
        pl, line = line.split('; ')
        pl = int(pl)
        self.frames[self._frame]['acts'].setdefault(pl, {})
        self.frames[self._frame]['acts'][pl]['crush'] = ints(line.split(' '))
    def parse_grip(self, line):
        pl, line = line.split('; ')
        pl = int(pl)
        self.frames[self._frame]['acts'].setdefault(pl, {})
        self.frames[self._frame]['acts'][pl]['grip'] = ints(line.split(' '))

    PARSERS = {'#made': parse_made_with,
#               '#SCORE': parse_score,
               '#WIN': parse_win,
               'VERSION': parse_version,
               'FIGHTNAME': parse_fightname,
               'BOUT': parse_bout,
               'FIGHT': parse_fight,
               'AUTHOR': parse_author,
               'ENGAGE': parse_engage,
               'NEWGAME': parse_newgame,
               'FRAME': parse_frame,
               'JOINT': parse_joint,
               'GRIP': parse_grip,
               }
    IGNORE = ('POS', 'QAT', 'LINVEL', 'ANGVEL', 'EMOTE', 'EPOS', 'EQAT', 'ELINVEL', 'EANGVEL', 
              'CRUSH', 'FRACT', 'ITEM', 'BODCOL', 'GRADCOL1', 'GRADCOL2',
              '#!/usr/bin/toribash',
              '#SCORE',
              )

    def parse(self, file):
        for line in file:
            line = line.strip("\r\n")
            if not line:
                continue
            p = line.split(None, 1)
            cmd, line = p[0], p[1:] and p[1] or ''
            if cmd not in self.IGNORE:
                if cmd in self.PARSERS:
                    self.PARSERS[cmd](self, line)
                else:
                    logging.warning("Unknown command: '%s %s'" % (cmd, line))
        
        # Set score to score of last frame
        self.settings['score'] = self.frames[max(self.frames.keys())].get('score')

def parse(file):
    p = Parser()
    p.parse(file) 
    return p.settings, p.frames


if __name__ == '__main__':
    import sys, traceback
    if len(sys.argv) < 2:
        print 'usage: parse.py <replay> [replay]'
        exit()

    for path in sys.argv[1:]:    
        try:
            s,f = parse(file(path))
            #print 'Settings', s
            #print 'Frames', f
        except KeyboardInterrupt:
            raise
        except:
            print path
            #print sys.exc_info()[:2]
            traceback.print_exception(*sys.exc_info())
