# -*- coding: utf-8 -*-
"""
@author: Adrián Revuelta Cuauhtli
"""

import abc
import copy
import lxml.etree as ET

from utils import Vec2
from settings import *
from settings import __version__, _UPDATE_LABEL_OFFSET

def _get_treeElement(parent, tag = 'text', attr = None):
    """Aux function to search or create a certain ElementTree element."""
    
    el = parent.find(tag)
    if el is None:
        if attr is None:
            el = ET.SubElement(parent, tag)
        else:
            el = ET.SubElement(parent, tag, attr)
    return el

class Node(object):
    """PetriNets Node class, which is extended by Place and Transition Classes.
        NOTICE: Arc does not extend from this class.
    """
    
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, name, position):
        """Node constructor
        
            Sets the name and position of a node.
            
            Positional Arguments:
            name -- Any string (preferably only alphanumeric characters, daches and underscores).
            position -- An instance of the Vec2 utility class.
            """
        
        if not name:
            raise Exception('A Node name must be a non-empty string.')
        
        self._name = name
        self.petri_net = None
        self.position = Vec2(position)
        self._incoming_arcs = {}
        self._outgoing_arcs = {}
        self.hasTreeElement = False
        self._references = set()
        self._id = name.replace(' ', '_').replace('(', '__').replace(')', '__').replace(',', '_')
    
    @property
    def name(self):
        """Returns the name of the node."""
        return self._name
    
    @name.setter
    def name(self, value):
        """Sets the name of the node. Throws an exception if name is None or an empty string."""
        
        self.validate_name(value)
        
        self._name = value
    
    @property
    def full_name(self):
        """Returns the name of the node, with its class prefix."""
        return self.PREFIX + '.' + self._name
    
    def validate_name(self, val):
        
        if not val:
            raise Exception('A Node name must be a non-empty string.')
    
    @property
    def incoming_arcs(self):
        """Read-only property. Deepcopy of the incoming arcs as a dictionaty with source
            transition/place string representations as keys and weights as values. 
        """
        return copy.deepcopy(self._incoming_arcs)
    
    @property
    def outgoing_arcs(self):
        """Read-only property. Deepcopy of the outgoing arcs as a dictionaty with target
            transition/place string representations as keys and weights as values. 
        """
        return copy.deepcopy(self._outgoing_arcs)
    
    @abc.abstractmethod
    def _merge_treeElement(self):
        """Merges the current ElementTree element information with the previously loaded info."""
        return
    
    @abc.abstractmethod
    def _build_treeElement(self):
        """Builds the ElementTree element from the node's information."""
        return

    def __repr__(self):
        """ String representation of a Node object. It is the id of the node.
        
        If the id is created by PNLab tool, then it is formed with 
        the first letter of the node type, a dot and the node name with spaces replaced by an underscore.
        """
        return self._id
    
    def __str__(self):
        """ Printable name of a Node object. It is the id of the node.
        
        If the id is created by PNLab tool, then it is formed with 
        the first letter of the node type, a dot and the node name.
        """
        return self.name

class Place(Node):
    """Petri Net Place Class."""
    
    FILL_COLOR = 'white'
    OUTLINE_COLOR = 'black'
    PREFIX = 'regular'
    
    def __init__(self, name, position = Vec2(), init_marking = 0, capacity = 1):
        """Place constructor
        
            Sets the name, type, position and initial marking of a place.
            
            Positional Arguments:
            name -- Any string (preferably only alphanumeric characters, daches and underscores).
                    
            Keyword Arguments:
            position -- An instance of the Vec2 utility class.
            initial_marking -- An integer specifying the initial marking for this place.
        """
        
        super(Place, self).__init__(name, position)
        
        self.init_marking = init_marking
        self.capacity = capacity
        self.current_marking = self.init_marking
        
    def can_connect_to(self, target, weight):
        
        if not self.petri_net or repr(self) not in self.petri_net.places or repr(target) not in self.petri_net.transitions:
            raise Exception('Arcs should go either from a place to a transition or vice versa and they should exist in the PN.')
        
        if repr(target) in self._outgoing_arcs:
            raise Exception('There already exists an arc between these nodes.')
    
    @classmethod
    def fromETreeElement(cls, element):
        """Method for parsing xml nodes as an ElementTree object."""
        if element.tag != 'place':
            raise Exception('Wrong eTree seed element for place.')
        
        place_id = element.get('id')
        place_name = element.find('name')
        if place_name is not None:
            name = place_name.findtext('text')
        else:
            name = place_id
        
        PlaceClass = Place
        
        for pc in PLACE_CLASSES:
            l = len(pc.PREFIX) + 1
            if name[:l] == pc.PREFIX + '.':
                name = name[l:]
                PlaceClass = pc
                break
        
        if not name:
            raise Exception('Place name cannot be an empty string.')
        
        try:
            position_el = element.find('graphics/position')
            position = Vec2(float(position_el.get('x')), float(position_el.get('y')))
        except:
            position = Vec2()
        
        initMarking = 0
        place_initMarking = element.find('initialMarking')
        if place_initMarking is not None:
            initMarking = int(place_initMarking.findtext('text'))
        
        toolspecific_el = element.find('toolspecific[@tool="PNLab"]')
        
        try:
            capacity = int(toolspecific_el.find('capacity/text').text)
        except:
            capacity = 0
        
        #NOTE: PNML renaming (of references?) is done by the PetriNet procedure where this node is created.
        p = PlaceClass(name, position, initMarking, capacity)
        p.hasTreeElement = True
        return p
    
    def _build_treeElement(self):
        
        place = ET.Element('place', {'id': self.__repr__()})
        
        place_name = ET.SubElement(place, 'name')
        tmp = ET.SubElement(place_name, 'text')
        tmp.text = self.full_name
        tmp = ET.SubElement(place_name, 'graphics')
        ET.SubElement(tmp, 'offset', {'x': str(0.0), 'y': str(PLACE_LABEL_PADDING)})
            
        tmp = ET.SubElement(place, 'initialMarking')
        tmp = ET.SubElement(tmp, 'text')
        tmp.text = str(self.init_marking)
        
        place_toolspecific = ET.SubElement(place, 'toolspecific', {'tool': 'PNLab', 'version': __version__})
        
        tmp = ET.SubElement(place_toolspecific, 'capacity')
        tmp = ET.SubElement(tmp, 'text')
        tmp.text = str(int(self.capacity))
        
        tmp = ET.SubElement(place, 'graphics')
        ET.SubElement(tmp, 'position', {'x': str(self.position.x), 'y': str(self.position.y)})
        scale = 1.0
        if self.petri_net:
            scale = self.petri_net.scale
        ET.SubElement(tmp, 'dimension', {'x': str(PLACE_RADIUS*scale), 'y': str(PLACE_RADIUS*scale)})
        ET.SubElement(tmp, 'fill', {'color': self.FILL_COLOR})
        ET.SubElement(tmp, 'line', {
                                    'color': self.OUTLINE_COLOR,
                                    'width': str(LINE_WIDTH),
                                    'style': 'solid'})
        
        self.hasTreeElement = True
        return place
    
    def _merge_treeElement(self):
        
        place = self.petri_net._tree.find('//*[@id="' + self.__repr__() + '"]')
        
        place_name = _get_treeElement(place, 'name')
        tmp = _get_treeElement(place_name)
        tmp.text = self.full_name
        
        if _UPDATE_LABEL_OFFSET:
            place_name_graphics = _get_treeElement(place_name, 'graphics') 
            tmp = _get_treeElement(place_name_graphics, 'offset')
            tmp.set('x', str(0.0))
            tmp.set('y', str(PLACE_LABEL_PADDING))
        
        place_initMarking = _get_treeElement(place, 'initialMarking')
        tmp = _get_treeElement(place_initMarking)
        tmp.text = str(self.init_marking)
        
        
        place_toolspecific = _get_treeElement(place, 'toolspecific[@tool="PNLab"]', {'tool': 'PNLab', 'version': __version__})
        
        place_capacity = _get_treeElement(place_toolspecific, 'capacity')
        tmp = _get_treeElement(place_capacity)
        tmp.text = str(self.capacity)
        
        place_graphics = _get_treeElement(place, 'graphics')
        tmp = _get_treeElement(place_graphics, 'position')
        tmp.set('x', str(self.position.x))
        tmp.set('y', str(self.position.y))
        
        scale = 1.0
        if self.petri_net:
            scale = self.petri_net.scale
        
        tmp = _get_treeElement(place_graphics, 'dimension')
        tmp.set('x', str(PLACE_RADIUS*scale))
        tmp.set('y', str(PLACE_RADIUS*scale))
        
        tmp = place_graphics.find('fill')
        if tmp is None:
            tmp = ET.SubElement(place_graphics, 'fill', {'color': self.FILL_COLOR})
        
        tmp = place_graphics.find('line')
        if tmp is None:
            tmp = ET.SubElement(place_graphics, 'line', {
                                                         'color': self.OUTLINE_COLOR,
                                                         'width': str(LINE_WIDTH)
                                                         }
                                )

class NonPrimitiveTaskPlace(Place):
    
    FILL_COLOR = '#EEEE00'
    OUTLINE_COLOR = '#AAAA00'
    PREFIX = 'npt'
    
    def __init__(self, name, position=Vec2(), init_marking=0, capacity=1):
        super(NonPrimitiveTaskPlace, self).__init__(name, position=position, init_marking=init_marking, capacity=capacity)
    
    def can_connect_to(self, target, weight):
        super(NonPrimitiveTaskPlace, self).can_connect_to(target, weight)
        if target.__class__ != SequenceTransition:
            raise Exception('TASK places cannot connect to a transition that is not of type SEQUENCE.')
        
        if weight == 0:
            raise Exception('TASK places cannot connect with an inhibitor arc (weight == 0).')

class PrimitiveTaskPlace(Place):
    
    FILL_COLOR = '#FF6600'
    OUTLINE_COLOR = '#DD4400'
    PREFIX = 'pt'
    
    def __init__(self, name, position=Vec2(), init_marking=0, capacity=1):
        super(PrimitiveTaskPlace, self).__init__(name, position=position, init_marking=init_marking, capacity=capacity)
    
    def can_connect_to(self, target, weight):
        super(PrimitiveTaskPlace, self).can_connect_to(target, weight)
        if target.__class__ != SequenceTransition:
            raise Exception('TASK places cannot connect to a transition that is not of type SEQUENCE.')
        
        if weight == 0:
            raise Exception('TASK places cannot connect with an inhibitor arc (weight == 0).')

class CommandPlace(Place):
    
    FILL_COLOR = '#99FF66'
    OUTLINE_COLOR = '#77DD44'
    PREFIX = 'cmd'
    
    def __init__(self, name, position=Vec2(), init_marking=0, capacity=1):
        super(CommandPlace, self).__init__(name, position=position, init_marking=init_marking, capacity=capacity)
    
    def can_connect_to(self, target, weight):
        super(CommandPlace, self).can_connect_to(target, weight)
        raise Exception('COMMAND places cannot connect to any transition.')
    
class FactPlace(Place):
    
    FILL_COLOR = '#4444FF'
    OUTLINE_COLOR = '#0000BB'
    PREFIX = 'fact'
    
    def __init__(self, name, position=Vec2(), init_marking=0, capacity=1):
        super(FactPlace, self).__init__(name, position=position, init_marking=init_marking, capacity=capacity)
    
    def can_connect_to(self, target, weight):
        super(FactPlace, self).can_connect_to(target, weight)
        
        if target.__class__ == SequenceTransition:
            raise Exception('FACT and STRUCTURED_FACT PLACES cannot be connected to SEQUENCE transitions.')
    
class StructuredFactPlace(Place):
    
    FILL_COLOR = '#CC0099'
    OUTLINE_COLOR = '#AA0077'
    PREFIX = 'sfact'
    
    def __init__(self, name, position=Vec2(), init_marking=0, capacity=1):
        super(StructuredFactPlace, self).__init__(name, position=position, init_marking=init_marking, capacity=capacity)
    
    def can_connect_to(self, target, weight):
        super(StructuredFactPlace, self).can_connect_to(target, weight)
        
        if target.__class__ == SequenceTransition:
            raise Exception('FACT and STRUCTURED_FACT PLACES cannot be connected to SEQUENCE transitions.')
    
class OrPlace(Place):
    
    FILL_COLOR = '#88DDFF'
    OUTLINE_COLOR = '#66BBDD'
    PREFIX = 'or'
    
    def __init__(self, name, position=Vec2(), init_marking=0, capacity=1):
        super(OrPlace, self).__init__(name, position=position, init_marking=init_marking, capacity=capacity)
    
    def can_connect_to(self, target, weight):
        super(OrPlace, self).can_connect_to(target, weight)
        
        if target.__class__ == SequenceTransition:
            raise Exception('OR places cannot connect to a SEQUENCE transition.')
    
class TaskStatusPlace(Place):
    
    FILL_COLOR = '#00EE00'
    OUTLINE_COLOR = '#00AA00'
    PREFIX = 'ts'
    
    def __init__(self, name, position=Vec2(), init_marking=0, capacity=1):
        super(TaskStatusPlace, self).__init__(name, position=position, init_marking=init_marking, capacity=capacity)
    
    def can_connect_to(self, target, weight):
        super(TaskStatusPlace, self).can_connect_to(target, weight)
        raise Exception('TASK_STATUS places cannot connect to any transition.')

PLACE_CLASSES = (Place,
                 NonPrimitiveTaskPlace,
                 PrimitiveTaskPlace,
                 CommandPlace,
                 FactPlace,
                 StructuredFactPlace,
                 OrPlace,
                 TaskStatusPlace)

class Transition(Node):
    
    """Petri Net Transition Class."""
    
    FILL_COLOR = '#444444'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'regular'
    
    def __init__(self, name, position = Vec2(), isHorizontal = False, rate = 1.0, priority = 1):
        
        """Transition constructor
        
            Sets the name, type, position, orientation and rate of a transition.
            
            Positional Arguments:
            name -- name -- Any string (preferably only alphanumeric characters, daches and underscores).
                    
            Keyword Arguments:
            position -- An instance of the Vec2 utility class.
            isHorizontal -- A boolean specifying whether the transition
                            should be drawn as a vertical bar or as a horizontal bar.
            rate -- For timed_stochastic transitions, the rate used to determine
                    the firing of a transition.
        """
        
        super(Transition, self).__init__(name, position)
        
        self.isHorizontal = isHorizontal
        
        #For stochastic_timed transitions:
        self.rate = rate
        self.priority = priority
    
    @property
    def type(self):
        """Returns the type of the transition. Should be a value from one of the constants in TransitionTypes class."""
        return self._type
    
    @type.setter
    def type(self, value):
        """Sets the type of the transition. Should be a value from one of the constants in TransitionTypes class."""
        self._type = value
    
    def can_connect_to(self, target, weight):
        
        
        if not self.petri_net or repr(self) not in self.petri_net.transitions or repr(target) not in self.petri_net.places:
            raise Exception('Arcs should go either from a place to a transition or vice versa and they should exist in the PN.')
        
        if weight < 1:
            raise Exception('Transitions cannot connect to places with inhibitor arcs (weight == 0).')
        
        if repr(target) in self._outgoing_arcs:
            raise Exception('There already exists an arc between these nodes.')
    
    @classmethod
    def fromETreeElement(cls, element):
        """Method for parsing xml nodes as an ElementTree object."""
        if element.tag != 'transition':
            raise Exception('Wrong eTree seed element for transition.')
        
        transition_id = element.get('id')
        transition_name = element.find('name')
        if transition_name is not None:
            name = transition_name.findtext('text')
        else:
            name = transition_id
        
        TransitionClass = Transition
        
        for tc in TRANSITION_CLASSES:
            l = len(tc.PREFIX) + 1
            if name[:l] == tc.PREFIX + '.':
                name = name[l:]
                TransitionClass = tc
                break
          
        if not name:
            raise Exception('Transition name cannot be an empty string.')
        
        
        try:
            position_el = element.find('graphics/position')
            position = Vec2(float(position_el.get('x')), float(position_el.get('y')))
        except:
            position = Vec2()
        
        toolspecific_el = element.find('toolspecific[@tool="PNLab"]')
        
        try:
            isHorizontal = bool(int(toolspecific_el.find('isHorizontal/text').text))
        except:
            isHorizontal = False
        
        try:
            rate = float(toolspecific_el.find('rate/text').text)
        except:
            rate = 1.0
        
        try:
            priority = int(toolspecific_el.find('priority/text').text)
        except:
            priority = 1
        
        #NOTE: PNML renaming is done by the PetriNet procedure where this node is created.
        
        t = TransitionClass(name, position, isHorizontal, rate, priority)
        t.hasTreeElement = True
        return t
    
    def _build_treeElement(self):
        
        transition = ET.Element('transition', {'id': self.__repr__()})
        
        transition_name = ET.SubElement(transition, 'name')
        tmp = ET.SubElement(transition_name, 'text')
        tmp.text = self.full_name
        tmp = ET.SubElement(transition_name, 'graphics')
        if self.isHorizontal:
            ET.SubElement(tmp, 'offset', {'x': str(0.0), 'y': str(TRANSITION_HORIZONTAL_LABEL_PADDING)})
        else:
            ET.SubElement(tmp, 'offset', {'x': str(0.0), 'y': str(TRANSITION_VERTICAL_LABEL_PADDING)})
        
        transition_toolspecific = ET.SubElement(transition, 'toolspecific', {'tool': 'PNLab', 'version': __version__})
        '''
        tmp = ET.SubElement(transition_toolspecific, 'type')
        tmp = ET.SubElement(tmp, 'text')
        tmp.text = self.type
        '''
        
        tmp = ET.SubElement(transition_toolspecific, 'isHorizontal')
        tmp = ET.SubElement(tmp, 'text')
        tmp.text = str(int(self.isHorizontal))
        
        tmp = ET.SubElement(transition_toolspecific, 'rate')
        tmp = ET.SubElement(tmp, 'text')
        tmp.text = str(self.rate)
        
        tmp = ET.SubElement(transition_toolspecific, 'priority')
        tmp = ET.SubElement(tmp, 'text')
        tmp.text = str(self.priority)
        
        tmp = ET.SubElement(transition, 'graphics')
        ET.SubElement(tmp, 'position', {'x': str(self.position.x), 'y': str(self.position.y)})
        scale = 1.0
        if self.petri_net:
            scale = self.petri_net.scale
        if self.isHorizontal:
            width = TRANSITION_HALF_LARGE
            height = TRANSITION_HALF_SMALL
        else:
            width = TRANSITION_HALF_SMALL
            height = TRANSITION_HALF_LARGE
        ET.SubElement(tmp, 'dimension', {'x': str(width*scale), 'y': str(height*scale)})
        ET.SubElement(tmp, 'fill', {'color': self.FILL_COLOR})
        ET.SubElement(tmp, 'line', {
                                    'color': self.OUTLINE_COLOR,
                                    'width': str(LINE_WIDTH),
                                    'style': 'solid'})
        
        self.hasTreeElement = True
        return transition
    
    def _merge_treeElement(self):
        
        transition = self.petri_net._tree.find('//*[@id="' + self.__repr__() + '"]')
        
        transition_name = _get_treeElement(transition, 'name')
        tmp = _get_treeElement(transition_name)
        tmp.text = self.full_name
        
        if _UPDATE_LABEL_OFFSET:
            transition_name_graphics = _get_treeElement(transition_name, 'graphics') 
            tmp = _get_treeElement(transition_name_graphics, 'offset')
            tmp.set('x', str(0.0))
            if self.isHorizontal:
                tmp.set('y', str(TRANSITION_HORIZONTAL_LABEL_PADDING))
            else:
                tmp.set('y', str(TRANSITION_VERTICAL_LABEL_PADDING))
        
        transition_toolspecific = _get_treeElement(transition, 'toolspecific[@tool="PNLab"]', {'tool': 'PNLab', 'version': __version__})
        
        transition_isHorizontal = _get_treeElement(transition_toolspecific, 'isHorizontal')
        tmp = _get_treeElement(transition_isHorizontal)
        tmp.text = str(int(self.isHorizontal))
        
        transition_rate = _get_treeElement(transition_toolspecific, 'rate')
        tmp = _get_treeElement(transition_rate)
        tmp.text = str(self.rate)
        
        transition_priority = _get_treeElement(transition_toolspecific, 'priority')
        tmp = _get_treeElement(transition_priority)
        tmp.text = str(self.priority)
        
        transition_graphics = _get_treeElement(transition, 'graphics')
        tmp = _get_treeElement(transition_graphics, 'position')
        tmp.set('x', str(self.position.x))
        tmp.set('y', str(self.position.y))
        
        scale = 1.0
        if self.petri_net:
            scale = self.petri_net.scale
        
        tmp = _get_treeElement(transition_graphics, 'dimension')
        if self.isHorizontal:
            width = TRANSITION_HALF_LARGE
            height = TRANSITION_HALF_SMALL
        else:
            width = TRANSITION_HALF_SMALL
            height = TRANSITION_HALF_LARGE
        tmp.set('x', str(width*scale))
        tmp.set('y', str(height*scale))
        
        tmp = transition_graphics.find('fill')
        if tmp is None:
            tmp = ET.SubElement(transition_graphics, 'fill', {'color': self.FILL_COLOR})
        
        tmp = transition_graphics.find('line')
        if tmp is None:
            tmp = ET.SubElement(transition_graphics, 'line', {
                                                         'color': self.OUTLINE_COLOR,
                                                         'width': str(LINE_WIDTH)
                                                         }
                                )

class PreconditionsTransition(Transition):
    
    FILL_COLOR = '#444444'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'p'
    
    def __init__(self, name, position = Vec2(), isHorizontal = False, rate = 1.0, priority = 1):
        super(PreconditionsTransition, self).__init__(name, position, isHorizontal, rate, priority)
        
    def can_connect_to(self, target, weight):
        super(PreconditionsTransition, self).can_connect_to(target, weight)
        if target.__class__ in [CommandPlace, OrPlace]:
            raise Exception('PRECONDITIONS transitions cannot connect to a COMMAND or an OR place.')

class RuleTransition(Transition):
    
    FILL_COLOR = '#444444'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'r'
    
    def __init__(self, name, position = Vec2(), isHorizontal = False, rate = 1.0, priority = 1):
        super(RuleTransition, self).__init__(name, position, isHorizontal, rate, priority)
    
    def can_connect_to(self, target, weight):
        super(RuleTransition, self).can_connect_to(target, weight)
        if target.__class__ == OrPlace:
            raise Exception('RULE transitions cannot connect to OR places.')
    
class AndTransition(Transition):
    
    FILL_COLOR = '#444444'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'and'
    
    def __init__(self, name, position = Vec2(), isHorizontal = False, rate = 1.0, priority = 1):
        super(AndTransition, self).__init__(name, position, isHorizontal, rate, priority)
    
    def can_connect_to(self, target, weight):
        super(AndTransition, self).can_connect_to(target, weight)
        if target.__class__ != OrPlace:
            raise Exception('AND transitions cannot connect to a place that is not an OR place.')

class SequenceTransition(Transition):
    
    FILL_COLOR = '#FFFFFF'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'seq'
    
    def __init__(self, name, position = Vec2(), isHorizontal = False, rate = 1.0, priority = 1):
        super(SequenceTransition, self).__init__(name, position, isHorizontal, rate, priority)
    
    def can_connect_to(self, target, weight):
        super(SequenceTransition, self).can_connect_to(target, weight)
        if target.__class__ not in [NonPrimitiveTaskPlace, PrimitiveTaskPlace]:
            raise Exception('SEQUENCE transitions cannot connect to places that are not TASK places.')

TRANSITION_CLASSES = (Transition,
                 PreconditionsTransition,
                 RuleTransition,
                 AndTransition,
                 SequenceTransition)

class _Arc(object):
    
    def __init__(self, source, target, weight = 1, treeElement = None):
        
        self.source = source
        self.target = target
        self.weight = weight
        self._treeElement = treeElement
        self.petri_net = source.petri_net
    
    def __str__(self):
        return repr(self.source) + '_' + repr(self.target)
    
    def __repr__(self):
        return self.__str__()
    
    @property
    def hasTreeElement(self):
        return self._treeElement is not None
    
    def _build_treeElement(self):
        
        arc = ET.Element('arc', {'id': self.__repr__(),
                                 'source': repr(self.source),
                                 'target': repr(self.target),
                                 })
        tmp = ET.SubElement(arc, 'inscription')
        tmp = ET.SubElement(tmp, 'text')
        tmp.text = str(self.weight)
        
        self._treeElement = self.__repr__()
        
        return arc
    
    def _merge_treeElement(self):
        
        el = self.petri_net._tree.find('//*[@id="' + self._treeElement + '"]')
        if el is None:
            print 'DEBUG - TE: ' + self._treeElement + ' - TreeName: ' + self.petri_net.name
            return
        el.set('id', self.__repr__())
        weight = _get_treeElement(el, 'inscription')
        _get_treeElement(weight).text = str(self.weight)
