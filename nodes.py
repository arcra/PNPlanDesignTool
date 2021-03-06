# -*- coding: utf-8 -*-
"""
@author: Adrián Revuelta Cuauhtli
"""

import abc
import copy
import re
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
            name = self._get_new_node_name()
        
        self.name = name
        self.petri_net = None
        self.position = Vec2(position)
        self._incoming_arcs = {}
        self._outgoing_arcs = {}
        self.hasTreeElement = False
        self._references = set()
        self._id = name.replace(' ', '_').replace('(', '__').replace(')', '__').replace(',', '_')
    
    @classmethod
    def _get_new_node_name(cls):
        return 'new_node'
    
    @classmethod
    def _get_display_name(cls):
        return cls._get_new_node_name()
    
    @property
    def name(self):
        """Returns the name of the node."""
        return self._name
    
    @name.setter
    def name(self, value):
        """Sets the name of the node. Throws an exception if name is None or an empty string."""
        
        self._validate_name(value)
        
        self._name = value
    
    @property
    def full_name(self):
        """Returns the name of the node, with its class prefix."""
        return self.PREFIX + '.' + self._name
    
    def _validate_name(self, val):
        
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

class BaseFactPlace(Place):
    
    __metaclass__ = abc.ABCMeta
    
    REGEX = re.compile(r'(?P<name>[a-zA-Z][a-zA-Z0-9_-]*)\s*(?P<parenthesis>(\(\s*(([-]?[0-9]+(\.[0-9]+)?)|(\$?\?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))(\s*,\s*(([-]?[0-9]+(\.[0-9]+)?)|(\$?\?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))*\s*\))?)')
    PARAMS_REGEX = re.compile(r'[^\s,][^\s,]*')
    VARS_REGEX = re.compile(r'\?[a-zA-Z][a-zA-Z0-9_-]*')
    
    def _get_vars(self):
        m = self.REGEX.match(self.name)
        
        parenthesis = m.group('parenthesis')
        if not parenthesis:
            return set()
        return set(self.VARS_REGEX.findall(parenthesis[1:-1]))
    
    def _get_bound_vars(self):
        return self._get_vars()
    
    def _get_unbound_vars(self):
        return set()
    

class FactPlace(BaseFactPlace):
    
    FILL_COLOR = '#4444FF'
    OUTLINE_COLOR = '#0000BB'
    PREFIX = 'fact'
    
    def can_connect_to(self, target, weight):
        super(FactPlace, self).can_connect_to(target, weight)
        
        if target.__class__ is SequenceTransition:
            raise Exception(self.name + ' - ' + target.name + ' - ' + 'FACT and STRUCTURED_FACT PLACES cannot be connected to SEQUENCE transitions.')
    
    def _validate_name(self, val):
        #Assert
        if not self.REGEX.match(val):
            raise Exception("A FactPlace should be a command name, followed by parameters that can either be a constant value or a bound variable.")
    
    def _get_description(self):
        
        m = self.REGEX.match(self.name)
        
        name = m.group('name')
        parenthesis = m.group('parenthesis')
        params = []
        if parenthesis:
            params = self.PARAMS_REGEX.findall(parenthesis[1:-1])
        return ['fact', name, params]
    
    def _get_effects(self):
        return self._get_description()
    
class StructuredFactPlace(FactPlace):
    
    FILL_COLOR = '#CC0099'
    OUTLINE_COLOR = '#AA0077'
    PREFIX = 'sfact'
    STRUTURED_PARAMS_REGEX = re.compile(r'(?P<name>[a-zA-Z][a-zA-Z0-9_-]*)\s*:\s*(' + 
                                    '(?P<single>(([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))|' + 
                                    '(?P<multi>\(' +
                                        '((\$?\?)|([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))' +  
                                        '(\s*,\s*((\$?\?)|([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))*' +  
                                    '\))' + 
                                ')')
    #I've created a MONSTER!!!!
    
    #name of deftemplate
    REGEX = re.compile(r'(?P<name>[a-zA-Z][a-zA-Z0-9_-]*)\s*(?P<parenthesis>(\(' +
                       # name of field / slot
                       '\s*[a-zA-Z][a-zA-Z0-9_-]*\s*:' +
                       # value of field / slot
                       '\s*(' + 
                            # number, variable (multi or single), constant or string
                            '(([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))|' +
                            # nested parenthesis 
                            '(\(' +
                                # wildcard, number, variable (multi or single), constant or string
                                '((\$?\?)|([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))' +
                                # coma and some other param
                                '(\s*,\s*((\$?\?)|([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))*' +  
                            '\))' + 
                        ')' + 
                        # name of field / slot
                        '(\s*,\s*[a-zA-Z][a-zA-Z0-9_-]*\s*:' +
                        # value of field / slot 
                       '\s*(' +
                            # number, variable (multi or single), constant or string 
                            '(([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))|' +
                            # nested parenthesis  
                            '(\(' +
                                # number, variable (multi or single), constant or string
                                '((\$?\?)|([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))' +  
                                # coma and some other param
                                '(\s*,\s*((\$?\?)|([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))*' +  
                            '\))' + 
                        '))*' + 
                        '\s*\)))?')
    
    def _get_description(self):
        
        m = self.REGEX.match(self.name)
        
        name = m.group('name')
        parenthesis = m.group('parenthesis')
        params = []
        if parenthesis:
            for m in self.STRUTURED_PARAMS_REGEX.finditer(parenthesis[1:-1]):
                param_name = m.group('name')
                if m.group('single'):
                    params.append([param_name, [m.group('single')]])
                else:
                    params.append([param_name, self.PARAMS_REGEX.findall(m.group('multi')[1:-1])])
        return ['sfact', name, params]
    
    def _get_effects(self):
        return self._get_description()

class TaskPlace(BaseFactPlace):
    
    FILL_COLOR = '#FF6600'
    OUTLINE_COLOR = '#DD4400'
    PREFIX = 't'
    
    def can_connect_to(self, target, weight):
        super(TaskPlace, self).can_connect_to(target, weight)
        if target.__class__ not in [SequenceTransition, RuleTransition]:
            raise Exception('TASK places cannot connect to a transition that is not of type SEQUENCE.')
        
        if target.__class__ is RuleTransition and self.petri_net.task != self.name:
            raise Exception('Only the TASK place corresponding to the task this rule belongs to is allowed to connect to a PRECONDITIONS or RULE Transition.')
        
        if weight == 0:
            raise Exception('TASK places cannot connect with an inhibitor arc (weight == 0).')
    
    def _get_description(self):
        
        pos = self.name.find('(')
        if pos < 0:
            return ['task', self.name, ""]
        
        name = self.name[:pos]
        params = [p.strip() for p in self.name[pos+1:-1].split(',')]
        return ['task', name, params]

class CommandPlace(BaseFactPlace):
    
    FILL_COLOR = '#99FF66'
    OUTLINE_COLOR = '#77DD44'
    PREFIX = 'cmd'
    REGEX = re.compile(r'(?P<name>[a-zA-Z][a-zA-Z0-9_]*)\s*(?P<parenthesis>(\(\s*((\?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))\s*,\s*(\??[a-zA-Z][a-zA-Z0-9_-]*)(\s*,\s*((\?[a-zA-Z][a-zA-Z0-9_-]*)|([0-9]+))){0,2}\s*\)))')
    
    @classmethod
    def _get_new_node_name(cls):
        return 'new_command("args", symbol)'
    
    def can_connect_to(self, target, weight):
        super(CommandPlace, self).can_connect_to(target, weight)
        raise Exception('COMMAND places cannot connect to any transition.')
    
    def _validate_name(self, val):
        #Assert
        if not self.REGEX.match(val):
            raise Exception("A CommandPlace name should be a command name, followed by a string of parameters or a bound variable, and by a symbol.")
    
    def _get_description(self):
        
        m = self.REGEX.match(self.name)
        
        name = m.group('name')
        parenthesis = m.group('parenthesis')
        params = self.PARAMS_REGEX.findall(parenthesis[1:-1])
        if len(params) < 2:
            raise Exception("Command with too few arguments found!")
        return ['command', name, params]
    
    def _get_vars(self):
        m = self.REGEX.match(self.name)
        parenthesis = m.group('parenthesis')
        return set(self.VARS_REGEX.findall(parenthesis[1:-1]))
    
    def _get_bound_vars(self):
        return set()
    
    def _get_unbound_vars(self):
        return self._get_vars()
        
class TaskStatusPlace(BaseFactPlace):
    
    FILL_COLOR = '#994400'
    OUTLINE_COLOR = '#550000'
    PREFIX = 'ts'
    REGEX = re.compile(r'task_status\(((successful)|(failed)|(\?)|(\?[a-z-A-Z][a-z-A-Z0-9_-]*))\)')
    
    @classmethod
    def _get_new_node_name(cls):
        return 'task_status(?)'
    
    def _validate_name(self, val):
        #Assert
        if not self.REGEX.match(val):
            raise Exception("A Task Status Place should have as parameter either one of the constants 'successful' and 'failed', or a variable.")
    
    def can_connect_to(self, target, weight):
        super(TaskStatusPlace, self).can_connect_to(target, weight)
        
        if target.__class__ != RuleTransition:
            raise Exception('TASK_STATUS places cannot connect to any transition other than a RULE Transition.')
    
    def _get_description(self):
        
        return ['task_status', self.name[self.name.find('(') + 1:-1]]
    
    def _get_bound_vars(self):
        return set()
    
    def _get_unbound_vars(self):
        return set()

class FunctionPlace(BaseFactPlace):
    
    FILL_COLOR = '#66AA00'
    OUTLINE_COLOR = '#447700'
    PREFIX = 'fnc'
    REGEX = re.compile(r'fnc\s*\(\s*(?P<func>[^\s,]+)(?P<args>(\s*,\s*(([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))+)\s*,\s*(?P<result>(\?[a-zA-Z][a-zA-Z0-9_-]*))\s*\)')
    
    @classmethod
    def _get_new_node_name(cls):
        return 'fnc(func_name, op1, op2, ?result)'
    
    def can_connect_to(self, target, weight):
        super(FunctionPlace, self).can_connect_to(target, weight)
        
        if weight == 0:
            raise Exception('FUNCTION Places cannot connect with inhibitor arcs.')
        
        if target.__class__ is SequenceTransition:
            raise Exception('FUNCTION Places cannot connect to SEQUENCE Transitions.')
    
    def _validate_name(self, val):
        #Assert
        if not self.REGEX.match(val):
            raise Exception("A FUNCTION Place must be named fnc(<function_name>, <operand1>, ..., <operandN>, ?<result_var>).")
    
    def _get_bound_vars(self):
        m = self.REGEX.match(self.name)
        
        return set([m.group('result')])
    
    def _get_unbound_vars(self):
        m = self.REGEX.match(self.name)
        args = m.group('args')
        return set(self.VARS_REGEX.findall(args))
    
    def _get_func_substitution(self):
        m = self.REGEX.match(self.name)
        args = m.group('args')
        return (m.group('result'), [m.group('func')] + self.PARAMS_REGEX.findall(args))

class FunctionCallPlace(BaseFactPlace):
    
    FILL_COLOR = '#EEEE00'
    OUTLINE_COLOR = '#AAAA00'
    PREFIX = 'fncCall'
    REGEX = re.compile(r'(?P<func>[a-zA-Z][a-zA-Z0-9_-]+)\s*(\(\s*(?P<args>(([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*"))(\s*,\s*(([-]?[0-9]+(\.[0-9]+)?)|((\$?\?)?[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))*)\s*\))?')
    
    @classmethod
    def _get_new_node_name(cls):
        return 'func_name(?op1, ?op2)'
    
    @classmethod
    def _get_display_name(cls):
        return 'func_name(op1, ...)'
    
    def can_connect_to(self, target, weight):
        raise Exception('FUNCTION CALL Places cannot connect to anything.')
    
    def _validate_name(self, val):
        #Assert
        if not self.REGEX.match(val):
            raise Exception("A FUNCTION CALL Place must be named fncCall(<function_name>, <operand1>, ..., <operandN>).")
    
    def _get_bound_vars(self):
        return set()
    
    def _get_unbound_vars(self):
        m = self.REGEX.match(self.name)
        args = m.group('args')
        if args is None:
            args = ''
        return set(self.VARS_REGEX.findall(args))
    
    def _get_description(self):
        
        m = self.REGEX.match(self.name)
        func = m.group('func')
        args = self.PARAMS_REGEX.findall(m.group('args'))
        if args is None:
            args = ''
        return ['fncCall', func, args]

class ComparisonPlace(BaseFactPlace):
    
    FILL_COLOR = '#EE0000'
    OUTLINE_COLOR = '#AA0000'
    PREFIX = 'cmp'
    #NOTE: if regex (list of operators) changes, change exception messages.
    REGEX = re.compile(r'cmp\s*\(\s*(?P<operator>((>)|(>=)|(<)|(<=)|(=)|(<>)|(eq)|(neq)))\s*,\s*(?P<op1>(([-]?[0-9]+(\.[0-9]+)?)|(\??[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))\s*,\s*(?P<op2>(([-]?[0-9]+(\.[0-9]+)?)|(\??[a-zA-Z][a-zA-Z0-9_-]*)|("([^\\"]|\\.)*")))\s*\)')
    
    @classmethod
    def _get_new_node_name(cls):
        return 'cmp(neq, ?op1, ?op2)'
    
    @classmethod
    def _get_display_name(cls):
        return 'cmp(operator, op1, op2)'
    
    def can_connect_to(self, target, weight):
        super(ComparisonPlace, self).can_connect_to(target, weight)
        
        if target.__class__ is SequenceTransition:
            raise Exception('COMPARISON Places cannot connect to SEQUENCE Transitions.')
    
    def _validate_name(self, val):
        #Assert
        if not self.REGEX.match(val):
            raise Exception("A COMPARISON Place must be named cmp(<operator>, <operand1>, <operand2>), where operator is one of: '>', '>=', '<', '<=', '=', '<>', 'eq' or 'neq' without the quotes.")
    
    def _get_description(self):
        
        m = self.REGEX.match(self.name)
        
        return ['cmp', [m.group('operator'), m.group('op1'), m.group('op2')]]
    
    def _get_bound_vars(self):
        return set()
    
    def _get_unbound_vars(self):
        
        m = self.REGEX.match(self.name)
        
        return set(self.VARS_REGEX.findall(m.group('op1')) + self.VARS_REGEX.findall(m.group('op2')))

class OrPlace(BaseFactPlace):
    
    FILL_COLOR = '#88DDFF'
    OUTLINE_COLOR = '#66BBDD'
    PREFIX = 'or'
    
    def can_connect_to(self, target, weight):
        super(OrPlace, self).can_connect_to(target, weight)
        
        if target.__class__ == SequenceTransition:
            raise Exception('OR places cannot connect to a SEQUENCE transition.')
    
    def _validate_name(self, val):
        if val != 'OR':
            raise Exception('An OR Place must be named "OR".')
    
    def _get_description(self, prev_transition):
        
        incoming_arcs = self._incoming_arcs.values()
        params = []
        
        for arc in incoming_arcs:
            if arc.weight == 0:
                params.append(['not', arc.source._get_description(prev_transition)])
            else:
                params.append(arc.source._get_description(prev_transition))
        
        return ['or', params]
    
    def _get_bound_vars(self):
        
        incoming_arcs = self._incoming_arcs.values()
        
        arc = incoming_arcs.pop()
        bound_vars = arc.source._get_bound_vars()
        
        for arc in incoming_arcs:
            bound_vars &= arc.source._get_bound_vars()
        
        return bound_vars
    
    def _get_unbound_vars(self):
        return set()
    
class NandPlace(BaseFactPlace):
    
    FILL_COLOR = '#88DDFF'
    OUTLINE_COLOR = '#66BBDD'
    PREFIX = 'nand'
    
    def can_connect_to(self, target, weight):
        super(NandPlace, self).can_connect_to(target, weight)
        
        if target.__class__ == SequenceTransition:
            raise Exception('NAND places cannot connect to a SEQUENCE transition.')
    
    def _validate_name(self, val):
        if val != 'NAND':
            raise Exception('A NAND Place must be named "NAND".')
    
    def _get_description(self, prev_transition):
        
        #NAND places should only have one transition connected to them.
        return self._incoming_arcs.values()[0].source._get_description(prev_transition)
    
    def _get_bound_vars(self):
        return set()
    
    def _get_unbound_vars(self):
        return set()

PLACE_CLASSES = (Place,
                 FactPlace,
                 StructuredFactPlace,
                 TaskPlace,
                 CommandPlace,
                 FunctionPlace,
                 FunctionCallPlace,
                 ComparisonPlace,
                 OrPlace,
                 NandPlace,
                 TaskStatusPlace)

class Transition(Node):
    
    """Petri Net Transition Class."""
    
    FILL_COLOR = '#444444'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'regular'
    
    def __init__(self, name, position = Vec2(), isHorizontal = False, rate = 1.0, priority = 0):
        
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

class BaseRuleTransition(Transition):
    
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, *args, **kwargs):
        self._bound_vars = set()
        self._unbound_vars = set()
        self._func_dict = {}
        super(BaseRuleTransition, self).__init__(*args, **kwargs)

class RuleTransition(BaseRuleTransition):
    
    PREFIX = 'r'
    
    def can_connect_to(self, target, weight):
        super(RuleTransition, self).can_connect_to(target, weight)
        if target.__class__ in [OrPlace, NandPlace, FunctionPlace, ComparisonPlace]:
            raise Exception('RULE transitions cannot connect to OR, NAND, Function or Comparison places.')
    
    def _get_preconditions(self, is_cancelation = False):
        
        self._func_vars = set()
        self._bound_vars = set(['?pnpdt_task__', '?pnpdt_planName__', '?pnpdt_steps__'])
        self._unbound_vars = set()
        
        incoming_arcs = self._incoming_arcs.values()
        or_arcs = []
        not_arcs = []
        
        cancelation_precondition = ['not', ['cancel_active_tasks']]
        if is_cancelation:
            cancelation_precondition = ['cancel_active_tasks']
        
        first_arcs = [['active_task'], cancelation_precondition]
        preconditions = []
        
        task_status = False
        initial = None
        edited = False
        
        # GET FUNCTION NAMES
        while incoming_arcs:
            
            arc = incoming_arcs.pop(0)
            
            if arc.source.__class__ is not FunctionPlace:
                continue
            
            func_vars = arc.source._get_bound_vars()
            # Check if result variable was already used in another function.
            if not func_vars - self._func_vars:
                raise Exception('A function with the result variable name "' + func_vars.pop() + '" already exists!')
            self._func_vars |= func_vars
        
        incoming_arcs = self._incoming_arcs.values()
        
        # PROCESS "POSITIVE" NODES
        while incoming_arcs:
            
            arc = incoming_arcs.pop(0)
            
            if arc.weight == 0:
                not_arcs.append(arc)
                continue
            
            unbound_vars = None
            
            if arc.source.__class__ is TaskPlace:
                node_bound_vars = arc.source._get_bound_vars()
                node_unbound_vars = arc.source._get_unbound_vars()
                bound_vars = node_bound_vars - (self._func_vars - self._bound_vars)
                unbound_vars = (node_unbound_vars | (node_bound_vars - bound_vars))  - self._bound_vars
                if not unbound_vars:
                    desc = arc.source._get_description()
                    desc = [desc[0]] + [self._func_dict] + desc[1:]
                    first_arcs.insert(0, desc)
                    edited = True
                    self._bound_vars |= bound_vars
            elif arc.source.__class__ is TaskStatusPlace:
                node_bound_vars = arc.source._get_bound_vars()
                node_unbound_vars = arc.source._get_unbound_vars()
                bound_vars = node_bound_vars - (self._func_vars - self._bound_vars)
                unbound_vars = (node_unbound_vars | (node_bound_vars - bound_vars))  - self._bound_vars
                if not unbound_vars:
                    desc = arc.source._get_description()
                    desc = [desc[0]] + [self._func_dict] + desc[1:]
                    if repr(arc.source) not in self._outgoing_arcs:
                        first_arcs.append(['delete', desc])
                    else:
                        first_arcs.append(desc)
                    edited = True
                    task_status = True
                    self._bound_vars |= bound_vars
            elif arc.source.__class__ in [FactPlace, StructuredFactPlace]:
                node_bound_vars = arc.source._get_bound_vars()
                node_unbound_vars = arc.source._get_unbound_vars()
                bound_vars = node_bound_vars - (self._func_vars - self._bound_vars)
                unbound_vars = (node_unbound_vars | (node_bound_vars - bound_vars))  - self._bound_vars
                if not unbound_vars:
                    desc = arc.source._get_description()
                    desc = [desc[0]] + [self._func_dict] + desc[1:]
                    if repr(arc.source) not in self._outgoing_arcs:
                        preconditions.append(['delete', desc])
                    else:
                        preconditions.append(desc)
                    edited = True
                    self._bound_vars |= bound_vars
            elif arc.source.__class__ is OrPlace:
                node_bound_vars = arc.source._get_bound_vars()
                node_unbound_vars = arc.source._get_unbound_vars()
                bound_vars = node_bound_vars - (self._func_vars - self._bound_vars)
                unbound_vars = (node_unbound_vars | (node_bound_vars - bound_vars))  - self._bound_vars
                if not unbound_vars:
                    or_arcs.append(arc)
                    edited = True
                    self._bound_vars |= bound_vars
            elif arc.source.__class__ is ComparisonPlace:
                unbound_vars = arc.source._get_unbound_vars() - self._bound_vars
                if not unbound_vars:
                    desc = arc.source._get_description()
                    desc = [desc[0]] + [self._func_dict] + desc[1:]
                    preconditions.append(desc)
                    edited = True
                    self._bound_vars |= arc.source._get_bound_vars()
            elif arc.source.__class__ is FunctionPlace:
                unbound_vars = arc.source._get_unbound_vars() - self._bound_vars
                if not unbound_vars:
                    key, val = arc.source._get_func_substitution()
                    self._func_dict[key] = val
                    edited = True
                    self._bound_vars |= arc.source._get_bound_vars()
            else:
                print 'Place was not parsed: ' + str(arc.source)
            
            #If arc was not processed/added:
            if unbound_vars:
                # Enqueue to process later
                incoming_arcs.append(arc)
                self._unbound_vars |= unbound_vars
                
                #Marc initial arc, if this arc is reached again and no other place was processed:
                #then this place cannot be processed, i. e. it has unbound variables.
                if initial not in incoming_arcs:
                    initial = arc
                elif initial is arc:
                    if edited:
                        edited = False
                    else:
                        self._unbound_vars -= self._bound_vars
                        raise Exception('The following unbound variables were found: ' + ', '.join(self._unbound_vars) + '.')
        
        if not task_status:
            first_arcs.append(['not', ['task_status', {}, '?']])
        
        # PROCESS "OR" NODES RECURSIVELY (AFTER ALL FUNCTION PLACES WERE PROCESSED)
        for arc in or_arcs:
            preconditions.append(arc.source._get_description(self))
        
        # PROCESS "NEGATIVE" ARCS
        while not_arcs:
            arc = not_arcs.pop(0)
            
            if arc.source.__class__ in [FactPlace, StructuredFactPlace, ComparisonPlace]:
                desc = arc.source._get_description()
                desc = [desc[0]] + [self._func_dict] + desc[1:]
                preconditions.append(['not', desc])
            elif arc.source.__class__ in [OrPlace, NandPlace]:
                preconditions.append(['not', arc.source._get_description(self)])
            else:
                print 'Place was not parsed: ' + str(arc.source)
        
        return first_arcs + preconditions
    
class AndTransition(BaseRuleTransition):
    
    FILL_COLOR = '#444444'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'and'
    
    def can_connect_to(self, target, weight):
        super(AndTransition, self).can_connect_to(target, weight)
        
        if target.__class__ not in [OrPlace, NandPlace, FactPlace,
                                    StructuredFactPlace, TaskPlace, TaskStatusPlace]:
            raise Exception('AND transitions can only connect to an OR place, a NAND place, or a precondition Fact, Task or TaskStatus places.')
    
    def _get_description(self, prev_transition):
        
        self._func_vars = set(prev_transition._func_vars)
        self._bound_vars = set(prev_transition._bound_vars)
        
        self._func_dict = copy.copy(prev_transition._func_dict)
        
        incoming_arcs = self._incoming_arcs.values()
        or_arcs = []
        not_arcs = []
        
        preconditions = []
        
        initial = None
        edited = False
        
        # GET FUNCTION NAMES
        while incoming_arcs:
            
            arc = incoming_arcs.pop(0)
            
            if arc.source.__class__ is not FunctionPlace:
                continue
            
            func_vars = arc.source._get_bound_vars()
            # Check if result variable was already used in another function.
            if not func_vars - self._func_vars:
                raise Exception('A function with the result variable name "' + func_vars.pop() + '" already exists!')
            self._func_vars |= func_vars
        
        incoming_arcs = self._incoming_arcs.values()
        
        # PROCESS "POSITIVE" NODES
        while incoming_arcs:
            
            arc = incoming_arcs.pop(0)
            
            if arc.weight == 0:
                not_arcs.append(arc)
                continue
            
            unbound_vars = None
            
            if arc.source.__class__ in [FactPlace, StructuredFactPlace]:
                node_bound_vars = arc.source._get_bound_vars()
                node_unbound_vars = arc.source._get_unbound_vars()
                bound_vars = node_bound_vars - (self._func_vars - self._bound_vars)
                unbound_vars = (node_unbound_vars | (node_bound_vars - bound_vars))  - self._bound_vars
                if not unbound_vars:
                    desc = arc.source._get_description()
                    desc = [desc[0]] + [self._func_dict] + desc[1:]
                    preconditions.append(desc)
                    edited = True
                    self._bound_vars |= bound_vars
            elif arc.source.__class__ is OrPlace:
                node_bound_vars = arc.source._get_bound_vars()
                node_unbound_vars = arc.source._get_unbound_vars()
                bound_vars = node_bound_vars - (self._func_vars - self._bound_vars)
                unbound_vars = (node_unbound_vars | (node_bound_vars - bound_vars))  - self._bound_vars
                if not unbound_vars:
                    #preconditions.append(arc.source._get_description(self))
                    or_arcs.append(arc)
                    edited = True
                    self._bound_vars |= bound_vars
            elif arc.source.__class__ is ComparisonPlace:
                unbound_vars = (arc.source._get_unbound_vars() - self._bound_vars)
                if not unbound_vars:
                    desc = arc.source._get_description()
                    desc = [desc[0]] + [self._func_dict] + desc[1:]
                    preconditions.append(desc)
                    edited = True
                    self._bound_vars |= arc.source._get_bound_vars()
            elif arc.source.__class__ is FunctionPlace:
                
                unbound_vars = arc.source._get_unbound_vars() - self._bound_vars
                if not unbound_vars:
                    key, val = arc.source._get_func_substitution()
                    self._func_dict[key] = val
                    edited = True
                    self._bound_vars |= arc.source._get_bound_vars()
            else:
                print 'Place was not parsed: ' + str(arc.source)
                
            #If arc was not processed/added:
            if unbound_vars:
                # Enqueue to process later
                incoming_arcs.append(arc)
                
                #Marc initial arc, if this arc is reached again and no other place was processed:
                #then this place cannot be processed, i. e. it has unbound variables.
                if initial not in incoming_arcs:
                    initial = arc
                elif initial is arc:
                    if edited:
                        edited = False
                    else:
                        raise Exception('Something wrong happened. Unbound variables found while getting AND preconditions.')
        
        # PROCESS OR NODES RECURSIVELY (AFTER ALL FUNCTION PLACES WERE PROCESSED)
        for arc in or_arcs:
            preconditions.append(arc.source._get_description(self))
        
        # PROCESS "NEGATIVE" NODES
        for arc in not_arcs:
            
            if arc.source.__class__ in [FactPlace, StructuredFactPlace, ComparisonPlace]:
                desc = arc.source._get_description()
                desc = [desc[0]] + [self._func_dict] + desc[1:]
                preconditions.append(['not', desc])
            elif arc.source.__class__ in [OrPlace, NandPlace]:
                desc = arc.source._get_description(self)
                #desc = [desc[0]] + [self._func_dict] + desc[1:]
                preconditions.append(['not', desc])
            else:
                print 'Place was not parsed: ' + str(arc.source)
        
        if len(preconditions) == 1:
            return preconditions[0]
        
        return ['and', preconditions]
    
    def _get_bound_vars(self):
        
        self._bound_vars = set()
        
        incoming_arcs = self._incoming_arcs.values()
        
        for arc in incoming_arcs:
            
            if arc.weight == 0:
                continue
            
            if arc.source.__class__ in [FactPlace, StructuredFactPlace,
                                        ComparisonPlace, FunctionPlace,
                                        OrPlace]:
                self._bound_vars |= arc.source._get_bound_vars()
        
        return self._bound_vars
    
    def _get_unbound_vars(self):
        
        self._bound_vars = self._get_bound_vars()
        unbound_vars = set()
        
        incoming_arcs = self._incoming_arcs.values()
        
        for arc in incoming_arcs:
            
            if arc.weight == 0 or arc.source.__class__ not in [ComparisonPlace, FunctionPlace]:
                continue
            
            if arc.source.__class__ is ComparisonPlace:
                unbound_vars |= (arc.source._get_unbound_vars() - self._bound_vars)
            else:
                unbound_vars |= (arc.source._get_unbound_vars() - self._bound_vars)
        
        return unbound_vars

class SequenceTransition(BaseRuleTransition):
    
    FILL_COLOR = '#FFFFFF'
    OUTLINE_COLOR = '#444444'
    PREFIX = 'seq'
    
    def can_connect_to(self, target, weight):
        super(SequenceTransition, self).can_connect_to(target, weight)
        if target.__class__ is not TaskPlace:
            raise Exception('SEQUENCE transitions cannot connect to places that are not TASK places.')

TRANSITION_CLASSES = (Transition,
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
        
        el = self.petri_net._tree.find('//arc[@id="' + self._treeElement + '"]')
        if el is None:
            print 'DEBUG - TE: ' + self._treeElement + ' - TreeName: ' + self.petri_net.name
            return
        weight = _get_treeElement(el, 'inscription')
        _get_treeElement(weight).text = str(self.weight)
        el.set('id', self.__repr__())
        self._treeElement = self.__repr__()
