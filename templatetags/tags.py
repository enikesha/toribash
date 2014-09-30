from copy import deepcopy
from google.appengine.ext.webapp import template

register = template.create_template_register()


COMMON = ('','Contracting','Extending','Holding','Relaxing')
REVERSE = ('','Extending','Contracting','Holding','Relaxing')
LUMBAR = ('','Right Bending', 'Left Bending', 'Holding', 'Relaxing')
CHEST = ('','Right Rotating', 'Left Rotating', 'Holding', 'Relaxing')
SHOULDER = ('','Lowering', 'Raising', 'Holding', 'Relaxing')

ACTIONS = (REVERSE, CHEST, LUMBAR, COMMON, REVERSE, SHOULDER, REVERSE, REVERSE, SHOULDER, REVERSE,
           REVERSE, REVERSE, COMMON, COMMON, COMMON, COMMON, REVERSE, REVERSE, COMMON, COMMON)
GRIP = ('Ungrip', 'Grip', 'Ungrip')
HANDS = ('Left Hand', 'Right Hand')

JOINTS = ('Neck',
          'Chest',
          'Lumbar',
          'Abs',

          'Right Pecs',
          'Right Shoulder',
          'Right Elbow',
          'Left Pecs',
          'Left Shoulder',
          'Left Elbow',

          'Right Wrist',
          'Left Wrist',

          'Right Glute',
          'Left Glute',

          'Right Hip',
          'Left Hip',

          'Right Knee',
          'Left Knee',

          'Right Ankle',
          'Left Ankle')

class FramesNode(template.django.template.Node):
    def __init__(self, frames, node_list):
        self.frames = frames
        self.node_list = node_list

    def render(self, context):
        frames = self.frames.resolve(context)

        def get_joints(new, old):
            hold = ['Hold all']
            diff = []
            relax = ['Relax all']
            for joint, state in new.items():
                action = '%s %s' % (ACTIONS[joint][state], JOINTS[joint])
                if state != 3:
                    hold.append(action)
                if state != 4:
                    relax.append(action)
                if old[joint] != state:
                    diff.append(action)
            return min((hold, diff, relax), key=len)

        def get_frames():
            joints = {0: dict(enumerate([4]*20)),
                      1: dict(enumerate([4]*20))}
            grips = {0: dict(enumerate([0,0])),
                     1: dict(enumerate([0,0]))}
            for time in sorted(frames):
                actions = {}
                new_grips = deepcopy(grips)
                new_joints = deepcopy(joints)
                for pl, acts in frames[time]['acts'].items():
                    actions[pl] = {}
                    if 'grip' in acts:
                        new_grips[pl] = acts['grip']
                        actions[pl]['grip'] = ['%s %s' % (GRIP[new_grips[pl][hand]], HANDS[hand]) for hand in (0, 1)
                                                                                                  if new_grips[pl][hand] != grips[pl][hand]]
                    if 'joints' in acts:
                        new_joints[pl].update(acts['joints'])
                        actions[pl]['joints'] = get_joints(new_joints[pl], joints[pl])

                joints, grips = new_joints, new_grips
                if sum([len(actions[pl].get(i, [])) for pl in actions for i in ('grip','joints')]) > 0:
                    yield {'time': time,
                           'score': frames[time]['score'],
                           'actions': actions}

        return ''.join(self.node_list.render(template.Context({'frame':frame})) for frame in get_frames())


FLAGS = {1: 'Disqualifications',
         2: 'Dismemberment',
         4: 'No gripping',
         8: 'Fracture'}

class FlagsNode(template.django.template.Node):
    def __init__(self, flags, node_list):
        self.flags = flags
        self.node_list = node_list

    def render(self, context):
        flags = self.flags.resolve(context)

        def get_flags():
            for i, flag in FLAGS.items():
                if flags & i != 0:
                    yield flag

        return ''.join(self.node_list.render(template.Context({'flag':flag})) for flag in get_flags())


@register.tag
def forframe(parser, token):
    bits = token.split_contents()
    if len(bits) != 3 or bits[1] != 'in':
        raise template.TemplateSyntaxError('"%s" takes one argument: frames dictionary' % bits[0])
    node_list = parser.parse('end' + bits[0])
    parser.delete_first_token()
    return FramesNode(parser.compile_filter(bits[2]), node_list)

@register.tag
def flags(parser, token):
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError('"%s" takes one argument: flags field' % bits[0])
    node_list = parser.parse('end' + bits[0])
    parser.delete_first_token()
    return FlagsNode(parser.compile_filter(bits[1]), node_list)

@register.inclusion_tag('actions.html')
def actions(acts, player):
  return {'actions':acts.get(player)}
