# -*- coding: utf-8 -*-
"""
@author: Adrián Revuelta Cuauhtli
"""

import copy
import io
import os
#import xml.etree.ElementTree as ET
import lxml.etree as ET

from nodes import Place, Transition, _Arc, _get_treeElement,\
    RuleTransition, SequenceTransition, TaskStatusPlace, TaskPlace,\
    FactPlace, StructuredFactPlace, CommandPlace, FunctionCallPlace
from utils import Vec2

class BasicPetriNet(object):
    
    '''
    #TODO (Possibly):
    Add a 'saved' attribute, to know when some attribute has changed and
    saving is necessary before the object is destroyed.
    '''
    
    def __init__(self, name, _net = None):
        """Petri Net Class' constuctor."""
        
        super(BasicPetriNet, self).__init__()
        
        if not name:
            raise Exception("PetriNet 'name' must be a non-empty string.")
        
        self.name = name
        self.places = {}
        self.transitions = {}
        self.scale = 1.0
        
        self._place_counter = 0
        self._transition_counter = 0
        
        root_el = ET.Element('pnml', {'xmlns': 'http://www.pnml.org/version-2009/grammar/pnml'})
        self._tree = ET.ElementTree(root_el)
        page = None
        if _net is not None:
            root_el.append(_net)
            try:
                self.scale = float(_net.find('toolspecific[@tool="PNLab"]/scale/text').text)
            except:
                pass
            page = _net.find('page')
        else:
            _net = ET.SubElement(root_el, 'net', {'id': name,
                                           'type': 'http://www.pnml.org/version-2009/grammar/ptnet'
                                           })
        
        tmp = _get_treeElement(_net, 'name')
        tmp = _get_treeElement(tmp)
        tmp.text = name
        if page is None:
            ET.SubElement(_net, 'page', {'id': 'PNLab_top_lvl'})
    
    def add_place(self, p):
        """Adds a place from the Petri Net.
        
        Clears the arcs from the place object and adds it to the Petri Net.
        
        Arguments:
        p -- A Place object to insert
        
        """
        
        self._place_counter += 1
        p._id = "P{:0>3d}".format(self._place_counter)
        
        p._incoming_arcs = {}
        p._outgoing_arcs = {}
        self.places[repr(p)] = p
        
        p.petri_net = self
    
    def add_transition(self, t):
        """Adds a transition from the Petri Net.
        
        Clears the arcs from the transition object and adds it to the Petri Net.
        
        Arguments:
        t -- A Transition object to insert
        """
        
        self._transition_counter += 1
        t._id = "T{:0>3d}".format(self._transition_counter)
        
        t._incoming_arcs = {}
        t._outgoing_arcs = {}
        self.transitions[repr(t)] = t
        
        t.petri_net = self
    
    def remove_place(self, place):
        """Removes a place from the Petri Net.
        
        Argument 'place' should be either a Place object,
        or a representation of a Place object [i. e. repr(place_obj)].
        
        Returns the removed object. 
        """
        
        if isinstance(place, Place): 
            key = repr(place)
        else:
            key = place
        if key not in self.places:
            return None
        p = self.places[key]
        
        for t in p._incoming_arcs.keys() :
            self.remove_arc(self.transitions[t], p)
        
        for t in p._outgoing_arcs.keys():
            self.remove_arc(p, self.transitions[t])
        
        for ref in p._references:
            el = self._tree.find('//*[@id="' + ref + '"]')
            el.getparent().remove(el)
        
        el = self._tree.find('//place[@id="' + key + '"]')
        if el is not None:
            el.getparent().remove(el)
        
        p = self.places.pop(key)
        p._references.clear()
        p.hasTreeElement = False
        p.petri_net = None
        
        return p
    
    def remove_transition(self, transition):
        """Removes a transition from the Petri Net.
        
        Argument 'transition' should be either a Transition object,
        or a representation of a Transition object [i. e. str(transition_obj)].
        
        Returns the removed object. 
        """
        if isinstance(transition, Transition): 
            key = repr(transition)
        else:
            key = transition
        if key not in self.transitions:
            return
        t = self.transitions[key]
        
        for p in t._incoming_arcs.keys():
            self.remove_arc(self.places[p], t)
        
        for p in t._outgoing_arcs.keys():
            self.remove_arc(t, self.places[p])
        
        for ref in t._references:
            el = self._tree.find('//*[@id="' + ref + '"]')
            el.getparent().remove(el)
        
        el = self._tree.find('//transition[@id="' + key + '"]')
        if el is not None:
            el.getparent().remove(el)
        
        t = self.transitions.pop(key)
        t._references.clear()
        t.hasTreeElement = False
        t.petri_net = None
        
        return t
    
    def _can_connect(self, source, target, weight):
        
        if weight < 0:
            raise Exception('An arc cannot have a negative weight.')
    
    def add_arc(self, source, target, weight = 1, _treeElement = None):
        """
        Adds an arc from 'source' to 'target' with weight 'weight'.
        
        Source and target should  be instances of the Place and Transition classes,
        one of each.
        
        If weight is zero, this arc becomes an inhibitor.
        If weight is zero and target is a place, an exception is raised.
        
        _treeElement is an internal field for maintaining a reference to the tree element when read from a pnml file.
        """
        
        # Assert:
        source.can_connect_to(target, weight)
        
        # Assert:
        self._can_connect(source, target, weight)
        
        if repr(target) in source._outgoing_arcs:
            raise Exception('There already exists an arc between these nodes.')
        
        arc = _Arc(source, target, weight, _treeElement)
        
        src = repr(source)
        trgt = repr(target)
        
        if isinstance(source, Place):
            self.places[src]._outgoing_arcs[trgt] = arc
            self.transitions[trgt]._incoming_arcs[src] = arc
        else:
            self.transitions[src]._outgoing_arcs[trgt] = arc
            self.places[trgt]._incoming_arcs[src] = arc
        
        return arc
    
    def remove_arc(self, source, target):
        """
        Removes an arc from 'source' to 'target'.
        
        source and target should  be instances of the Place and Transition classes,
        one of each.
        """
        
        src = repr(source)
        trgt = repr(target)
        if isinstance(source, Place):
            arc = self.places[src]._outgoing_arcs.pop(trgt, None)
            self.transitions[trgt]._incoming_arcs.pop(src, None)
        else:
            arc = self.transitions[src]._outgoing_arcs.pop(trgt, None)
            self.places[trgt]._incoming_arcs.pop(src, None)
        
        if arc and arc.hasTreeElement:
            arc_el = self._tree.find('//arc[@id="' + arc._treeElement + '"]')
            if arc_el is None:
                print 'Something is not right!'
            else:
                arc_el.getparent().remove(arc_el)
    
    @classmethod
    def _get_consecutive_letter_generator(cls):
        
        text = 'a'
        length = 1
        
        while True:
            yield text
            index = length - 1
            while index > -1:
                if text[index] == 'z':
                    text = text[:index] + 'a' + text[index+1:]
                    index -= 1
                else:
                    text = text[:index] + chr(ord(text[index])+1) + text[index+1:]
                    break
            if index == -1:
                text = 'a' + text
                length += 1

    @classmethod
    def from_ElementTree(cls, et, name = None, PetriNetClass = None, task = None):
        
        pnets = []
        root = et.getroot()
        for net in root.findall('net'):
            if name is None:
                try:
                    name = net.find('name').findtext('text')
                except:
                    name = net.get('id')
            
            #print 'Loading Petri Net: ' + name + '...'
            
            if PetriNetClass == None:
                PetriNetClass = BasicPetriNet
            
            if task:
                t = None
                for current_t in net.findall('page//transition'):
                    if current_t.find('name/text').text.startswith(RuleTransition.PREFIX + '.'):
                        t = current_t
                        break
                
                if t is not None:
                    transition_id = t.get('id')
                    p = None
                    l = len(TaskPlace.PREFIX) + 1
                    for current_arc in net.findall("page//arc[@target='"+ transition_id +"']"):
                        place_id = current_arc.get('source')
                        current_p = net.find('page//place[@id="' + place_id + '"]')
                        p_name = current_p.find('name').findtext('text')
                        if p_name[:l] == TaskPlace.PREFIX + '.':
                            p = current_p
                            break
                    if p is None:
                        print 'WARNING: TaskPlace not found!'
                    else:
                        p.find('name/text').text = p_name[:l] + task
                
                pn = PetriNetClass(name, task, _net = net, initialize = False)
            else:
                pn = PetriNetClass(name, _net = net)
            
            try:
                scale = float(net.find('toolspecific[@tool="PNLab"]/scale/text').text)
                pn.scale = scale
            except:
                pass
            
            generator = BasicPetriNet._get_consecutive_letter_generator()
            
            queue = [net]
            
            #Since name clashes can occur, all nodes must be renamed after reading the file
            # (i. e. after creating all nodes AND ARCS correctly).
            renaming_places_dict = {}
            renaming_places_dict_2 = {}
            renaming_transitions_dict = {}
            renaming_transitions_dict_2 = {}
            
            ### GET PLACES AND TRANSITIONS, AS WELL AS THEIR REFERENCES, AND GET THEIR NEW IDS
            while queue:
                current = queue.pop(0)
                
                for p_el in current.findall('place'):
                    p = Place.fromETreeElement(p_el)
                    pn.add_place(p)
                    if p.name == task:
                        pn._main_place = p
                    
                    temp_key = next(generator)
                    renaming_places_dict[p_el.get('id')] = temp_key
                    renaming_places_dict_2[temp_key] = repr(p)
                    
                for t_el in current.findall('transition'):
                    t = Transition.fromETreeElement(t_el)
                    pn.add_transition(t)
                    if t.__class__ == RuleTransition:
                        pn._main_transition = t
                    
                    temp_key = next(generator)
                    renaming_transitions_dict[t_el.get('id')] = temp_key
                    renaming_transitions_dict_2[temp_key] = repr(t)
                
                pages = current.findall('page')
                if pages:
                    queue += pages
            
            for ref in net.findall('.//referencePlace'):
                reference = ref
                try:
                    while reference.tag[:9] == 'reference':
                        reference = net.find('.//*[@id="' + reference.get('ref') + '"]')
                except:
                    raise Exception("Referenced node '" + ref.get('ref') + "' was not found.")
                
                place_id = ref.get('id')
                pn._place_counter += 1
                new_id = 'P{:0>3d}'.format(pn._place_counter)
                
                temp_key = next(generator)
                renaming_places_dict[place_id] = temp_key
                renaming_places_dict_2[temp_key] = new_id
                
                temp_key = renaming_places_dict[reference.get('id')]
                pn.places[renaming_places_dict_2[temp_key]]._references.add(new_id)
            
            for ref in net.findall('.//referenceTransition'):
                reference = ref
                try:
                    while reference.tag[:9] == 'reference':
                        reference = net.find('.//*[@id="' + reference.get('ref') + '"]')
                except:
                    raise Exception("Referenced node '" + ref.get('ref') + "' was not found.")
                
                transition_id = ref.get('id')
                pn._transition_counter += 1
                new_id = 'T{:0>3d}'.format(pn._transition_counter)
                
                temp_key = next(generator)
                renaming_transitions_dict[transition_id] = temp_key
                renaming_transitions_dict_2[temp_key] = new_id
                
                temp_key = renaming_transitions_dict[reference.get('id')]
                pn.transitions[renaming_transitions_dict_2[temp_key]]._references.add(new_id)
            
            ### RENAME PLACES AND TRANSITIONS, AS WELL AS THEIR REFERENCES, AND SUBSTITUTE ANY REFERENCE TO THEM
            
            for key, new_key in renaming_places_dict.iteritems():
                p_el = net.find('.//place[@id="' + key + '"]')
                for e in net.findall('.//referencePlace[@ref="' + key + '"]'):
                    e.set('ref', new_key)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', new_key)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', new_key)
                p_el.set('id', new_key)
            
            for key, new_key in renaming_places_dict_2.iteritems():
                p_el = net.find('.//place[@id="' + key + '"]')
                for e in net.findall('.//referencePlace[@ref="' + key + '"]'):
                    e.set('ref', new_key)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', new_key)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', new_key)
                p_el.set('id', new_key)
            
            
            for key, new_key in renaming_transitions_dict.iteritems():
                t_el = net.find('.//transition[@id="' + key + '"]')
                for e in net.findall('.//referenceTransition[@ref="' + key + '"]'):
                    e.set('ref', new_key)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', new_key)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', new_key)
                t_el.set('id', new_key)
            
            for key, new_key in renaming_transitions_dict_2.iteritems():
                t_el = net.find('.//transition[@id="' + key + '"]')
                for e in net.findall('.//referenceTransition[@ref="' + key + '"]'):
                    e.set('ref', new_key)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', new_key)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', new_key)
                t_el.set('id', new_key)
            
            ### GET ARC INFO TO THE PN AND UPDATE ARC INFO IN THE TE
            
            for arc in current.findall('arc'):
                
                source = net.find('.//*[@id="' + arc.get('source') + '"]')
                try:
                    while source.tag[:9] == 'reference':
                        source = net.find('.//*[@id="' + source.get('ref') + '"]')
                except:
                    raise Exception("Referenced node '" + arc.get('source') + "' was not found.")
                
                target = net.find('.//*[@id="' + arc.get('target') + '"]')
                try:
                    while target.tag[:9] == 'reference':
                        target = net.find('.//*[@id="' + target.get('ref') + '"]')
                except:
                    raise Exception("Referenced node '" + arc.get('target') + "' was not found.")
                
                source_id = source.get('id')
                target_id = target.get('id')
                
                if source.tag == 'place':
                    source = pn.places[source_id]
                    target = pn.transitions[target_id]
                else:
                    source = pn.transitions[source_id]
                    target = pn.places[target_id]
                try:
                    weight = int(arc.find('inscription/text').text)
                except:
                    weight = 1
                new_arc_id = source_id + '_' + target_id
                arc.set('id', new_arc_id)
                pn.add_arc(source, target, weight, new_arc_id)
            
            pnets.append(pn)
        
        return pnets
        
    
    def to_ElementTree(self):
        
        net = self._tree.find('net')
        
        tmp = _get_treeElement(net, 'name')
        tmp = _get_treeElement(tmp)
        tmp.text = self.name
        
        page = net.find('page')
        
        toolspecific = net.find('toolspecific[@tool="PNLab"]')
        if toolspecific is None:
            toolspecific = ET.SubElement(net, 'toolspecific', {'tool' : 'PNLab'})
        tmp = _get_treeElement(toolspecific, 'scale')
        tmp = _get_treeElement(tmp, 'text')
        tmp.text = str(self.scale)
        
        for p in self.places.itervalues():
            if p.hasTreeElement:
                p._merge_treeElement()
            else:
                page.append(p._build_treeElement())
        
        for t in self.transitions.itervalues():
            if t.hasTreeElement:
                t._merge_treeElement()
            else:
                page.append(t._build_treeElement())
        
        for p in self.places.itervalues():
            for arc in p._incoming_arcs.itervalues():
                if arc.hasTreeElement:
                    arc._merge_treeElement()
                else:
                    page.append(arc._build_treeElement())

            for arc in p._outgoing_arcs.itervalues():
                if arc.hasTreeElement:
                    arc._merge_treeElement()
                else:
                    page.append(arc._build_treeElement())
        
        return copy.deepcopy(self._tree)
    
    @classmethod
    def from_pnml_file(cls, filename, PetriNetClass = None, task = None):
        et = ET.parse(filename)
        # http://wiki.tei-c.org/index.php/Remove-Namespaces.xsl
        xslt='''<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
        <xsl:output method="xml" indent="no"/>
        
        <xsl:template match="/|comment()|processing-instruction()">
            <xsl:copy>
              <xsl:apply-templates/>
            </xsl:copy>
        </xsl:template>
        
        <xsl:template match="*">
            <xsl:element name="{local-name()}">
              <xsl:apply-templates select="@*|node()"/>
            </xsl:element>
        </xsl:template>
        
        <xsl:template match="@*">
            <xsl:attribute name="{local-name()}">
              <xsl:value-of select="."/>
            </xsl:attribute>
        </xsl:template>
        </xsl:stylesheet>
        '''
        xslt_doc=ET.parse(io.BytesIO(xslt))
        transform=ET.XSLT(xslt_doc)
        et=transform(et)
        filename = os.path.basename(filename)
        if '.' in filename:
            filename = filename[:filename.find('.')]
        
        if PetriNetClass is None:
            PetriNetClass = BasicPetriNet
        
        return PetriNetClass.from_ElementTree(et, name = filename, task = task, PetriNetClass = PetriNetClass)
    
    def to_pnml_file(self, file_name):
        et = self.to_ElementTree()
        et.write(file_name, encoding = 'utf-8', xml_declaration = True, pretty_print = True)

class RulePN(BasicPetriNet):
    
    def __init__(self, name, _net = None, **kwargs):
        
        self._main_transition_ = None
        self._to_delete = []
        self._deleted_fact_count = 0
        
        self._preconditions_handlers = {'task': self._handle_task,
                                        'fact': self._handle_fact,
                                        'sfact': self._handle_sfact,
                                        'delete': self._handle_delete,
                                        'cmp': self._handle_cmp,
                                        'or' : self._handle_or,
                                        'and' : self._handle_and,
                                        'not' : self._handle_not,
                                        'task_status' : lambda x: '(task_status ?pnpdt_task__ ' + x[2] + ')',
                                        'active_task' : lambda x: '(active_task ?pnpdt_task__)',
                                        'cancel_active_tasks' : lambda x: '(cancel_active_tasks)'
                                    }
        
        self._effects_handlers = {
                                  'fact': self._handle_fact_effect,
                                  'sfact': self._handle_sfact_effect,
                                  'task': self._handle_task_effect,
                                  'command': self._handle_command,
                                  'fncCall': self._handle_fncCall,
                                  'task_status' : self._handle_task_status_effect
                                  }
        
        super(RulePN, self).__init__(name, _net)
        
        
        if kwargs.pop('initialize', True):
            self._initialize()
    
    def _initialize(self):
        self._main_transition = RuleTransition('Rule', Vec2(350, 300))
        self.add_transition(self._main_transition)
    
    @property
    def _main_transition(self):
        
        if self._main_transition_:
            return self._main_transition_
        
        for t in self.transitions.itervalues():
            if t.__class__ is RuleTransition:
                self._main_transition_ = t
                return self._main_transition_
        
        raise Exception('Main Transition was not found!')
    
    @_main_transition.setter
    def _main_transition(self, val):
        
        if not isinstance(val, Transition):
            raise Exception("Main Transition must be an object from Transition Class or derived.")
        
        self._main_transition_ = val
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        return BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls)
    
    def add_arc(self, source, target, weight = 1, _treeElement = None):
        
        if isinstance(target, SequenceTransition):
            raise Exception('A generic Rule PN cannot have arcs to SEQUENCE transitions.')
        
        return super(RulePN, self).add_arc(source, target, weight, _treeElement)
    
    def get_dependency_tasks(self):
        
        dependencies = set()
        
        for p in self.places.values():
            if p.__class__ is not TaskPlace or p.name == self.task:
                continue
            name = p.name
            par = name.find('(')
            if par >= 0:
                name = name[:par]
            dependencies.add(name)
            
        return dependencies
                    
    
    def get_clips_code(self, is_cancelation = False):
        
        '''
        (rule <task_name>-<rule_name>
            <salience>
            <preconditions>
            =>
            (retract <vars>)
            (assert
                <new_facts>
                <task facts>
            )
            <commands>
            (send-command "ex_command" symbol "params" timeout attempts)
        )
        '''
        
        self._deleted_fact_count = 0
        self._to_delete = []
        
        try:
            preconditions = self._main_transition._get_preconditions(is_cancelation)
            facts, tasks, functions = self._get_effects()
        except Exception as e:
            raise Exception(str(e) + '\nError occurred in PN: ' + self.task + ' - ' + self.name + '.')
        
        task = self.task
        pos = self.task.find('(')
        if pos > -1:
            task = task[:pos]
        
        rule = ['(defrule ' + task + '-' + self.name]
        if self._main_transition.priority != 0:
            rule += self._indent('(declare (salience ' + str(self._main_transition.priority) + '))')
        for el in preconditions:
            rule += self._indent(self._preconditions_handlers[el[0]](el))
        rule += self._indent('=>')
        if self._to_delete:
            rule += self._indent('(retract ' + ' '.join(self._to_delete) + ')')
        if facts or tasks:
            rule += self._indent('(assert')
            for f in facts:
                rule += self._indent(self._effects_handlers[f[0]](f), 2)
            for t in tasks:
                rule += self._indent(self._effects_handlers[t[0]](t), 2)
            rule += self._indent(')')
        for f in functions:
            rule += self._indent(self._effects_handlers[f[0]](f))
        rule += [')']
        
        return '\n'.join(rule)
    
    def _indent(self, text, times = 1):
        
        if isinstance(text, basestring):
            return ['\t'*times + text]

        for i in range(len(text)):
            text[i] = '\t'*times + text[i]
        
        return text
    
    def _get_func_text(self, func_dict, lst):
        text = '(' + lst[0]
        
        for arg in lst[1:]:
            if arg in func_dict:
                arg = self._get_func_text(func_dict, func_dict[arg])
            text += ' ' + arg
        
        text += ')'
        
        return text
    
    def _handle_task(self, lst):
        
        text = ''
        
        func_dict = lst[1]
        
        for arg in lst[3]:
            if arg in func_dict:
                arg = '=' + self._get_func_text(func_dict, func_dict[arg])
            text += ' ' + arg
        
        if not text:
            text = ' ""'
        
        return '(task (id ?pnpdt_task__) (plan ?pnpdt_planName__) (action_type {0}) (params{1}) (step $?pnpdt_steps__) )'.format(lst[2], text)
    
    def _handle_fact(self, lst):
        text = ''
        
        func_dict = lst[1]
        
        for arg in lst[3]:
            if arg in func_dict:
                arg = '=' + self._get_func_text(func_dict, func_dict[arg])
            text += ' ' + arg 
        
        return '({0}{1})'.format(lst[2], text)
    
    def _handle_sfact(self, lst):
        text = ''
        
        func_dict = lst[1]
        
        for p in lst[3]:
            text += ' (' + p[0]
            for arg in p[1]:
                if arg in func_dict:
                    arg = '=' + self._get_func_text(func_dict, func_dict[arg])
                text += ' ' + arg
            text += ')'
        
        return '({0}{1})'.format(lst[2], text)
    
    def _handle_delete(self, lst):
        el = lst[1]
        self._deleted_fact_count += 1
        var = '?pnpdt_f' + str(self._deleted_fact_count) + '__'
        self._to_delete.append(var)
        
        fact_text = self._preconditions_handlers[el[0]](el)
        return var + ' <-' + fact_text
    
    def _handle_cmp(self, lst):
        
        func_dict = lst[1]
        
        el = lst[2]
        op1 = el[1]
        if op1 in func_dict:
            op1 = self._get_func_text(func_dict, func_dict[op1])
        op2 = el[2]
        if op2 in func_dict:
            op2 = self._get_func_text(func_dict, func_dict[op2])
        
        return '(test ({0} {1} {2}))'.format(el[0], op1, op2)
    
    def _handle_or(self, lst):
        text = ['(or']
        for el in lst[1]:
            text += self._indent(self._preconditions_handlers[el[0]](el))
        text += [')']
        
        return text
    
    def _handle_and(self, lst):
        text = ['(and']
        for el in lst[1]:
            text += self._indent(self._preconditions_handlers[el[0]](el))
        text += [')']
        
        return text
    
    def _handle_not(self, lst):
        el = lst[1]
        
        if el[0] == 'not':
            el = el[1]
            return self._preconditions_handlers[el[0]](el)
        
        text = ['(not']
        text += self._indent(self._preconditions_handlers[el[0]](el))
        text += [')']
        
        return text
    
    def _handle_fact_effect(self, lst):
        text = ''
        
        for arg in lst[2]:
            if arg in self._main_transition._func_dict:
                arg = self._get_func_text(self._main_transition._func_dict, self._main_transition._func_dict[arg])
            elif arg in ['?', '$?']:
                raise Exception('Produced facts cannot have wildcards in them, they must be bound variables.')
            text += ' ' + arg 
        
        return '({0}{1})'.format(lst[1], text)
                                  
    def _handle_sfact_effect(self, lst):
        text = ''
        
        for p in lst[2]:
            text += ' (' + p[0]
            for arg in p[1]:
                if arg in self._main_transition._func_dict:
                    arg = self._get_func_text(self._main_transition._func_dict, self._main_transition._func_dict[arg])
                elif arg in ['?', '$?']:
                    raise Exception('Produced facts cannot have wildcards in them, they must be bound variables.')
                text += ' ' + arg
            text += ')'
        
        return '({0}{1})'.format(lst[1], text)
                                  
    def _handle_task_effect(self, lst):
        text = ''
        
        for arg in lst[2]:
            if arg in self._main_transition._func_dict:
                arg = self._get_func_text(self._main_transition._func_dict, self._main_transition._func_dict[arg])
            text += ' ' + arg 
        
        if not text:
            text = ' ""'
        
        parent = '?pnpdt_task__'
        step = str(lst[3])
        
        return '(task (plan ?pnpdt_planName__) (action_type {0}) (params{1}) (step {2} $?pnpdt_steps__) (parent {3}) )'.format(lst[1], text, step, parent)
                                  
    def _handle_command(self, lst):
        
        params = lst[2][0]
        symbol = lst[2][1]
        
        if params in self._main_transition._func_dict:
            params = self._get_func_text(self._main_transition._func_dict, self._main_transition._func_dict[params])
        
        if symbol in self._main_transition._func_dict:
            symbol = self._get_func_text(self._main_transition._func_dict, self._main_transition._func_dict[symbol])
        
        return '(send-command "{0}" {1} {2})'.format(lst[1], symbol, params)
    
    def _handle_fncCall(self, lst):
        
        params = []
        
        for p in lst[2]:
            if p in self._main_transition._func_dict:
                p = self._get_func_text(self._main_transition._func_dict, self._main_transition._func_dict[p])
            params.append(p)
        
        return '({0} {1})'.format(lst[1], ' '.join(params))
    
    def _handle_task_status_effect(self, lst):
        
        if lst[1] == '?':
            raise Exception('A TASK STATUS Place that is an effect of a rule cannot have a wildcard as a parameter.')
        
        return '(task_status ?pnpdt_task__ {0})'.format(lst[1])
    
    def _get_effects(self):
        
        outgoing_arcs = self._main_transition._outgoing_arcs.values()
        
        facts = []
        tasks = []
        functions = []
        unbound_vars = set()
        
        for arc in outgoing_arcs:
            
            if repr(arc.target) in self._main_transition._incoming_arcs:
                continue
            
            unbound_vars |= (arc.target._get_unbound_vars() - self._main_transition._bound_vars)
            
            if arc.target.__class__ is TaskPlace:
                tasks += self._get_task_effects(arc)
            elif arc.target.__class__ in [FactPlace, StructuredFactPlace, TaskStatusPlace]:
                facts.append(arc.target._get_description())
            elif arc.target.__class__ in [CommandPlace, FunctionCallPlace] :
                functions.append(arc.target._get_description())
            else:
                print 'Place was not parsed: ' + str(arc.target)
        
        if unbound_vars:
            raise Exception('The following unbound variables were found: ' + ', '.join(unbound_vars) + '.')
        
        return (facts, tasks, functions)
    
    def _get_task_effects(self, arc):
        
        offset = 0
        
        arcs = [arc]
        tasks = []
        
        while arcs:
            offset += 1
            for arc in arcs:
                t = arc.target._get_description()
                t.append(offset)
                tasks.append(t)
            arcs2 = []
            for arc in arcs:
                #There should be only ONE sequence transition next to each task.
                t = arc.target._outgoing_arcs.values()[0].target
                arcs2 += t._outgoing_arcs.values()
            arcs = arcs2
        
        return tasks

class PlanningRulePN(RulePN):
    
    def __init__(self, name, task = None, **kwargs):
        
        self._task = task
        
        super(PlanningRulePN, self).__init__(name, **kwargs)
        
        # Notice the underscore at the end.
        self._main_place_ = None
    
    def _initialize(self):
        
        super(PlanningRulePN, self)._initialize()
        
        self._main_place = TaskPlace(self.task, Vec2(150, 300))
        self.add_place(self._main_place)
        self.add_arc(self._main_place, self._main_transition)
        self.add_arc(self._main_transition, self._main_place)
    
    @property
    def task(self):
        return self._task
    
    @task.setter
    def task(self, val):
        if not val:
            raise Exception('Task name cannot be an empty string.')
        
        place = None
        for p in self.places.itervalues():
            if p.name == self.task:
                place = p
                break
        
        if not place:
            raise Exception('Parent Task Place was not found.')
        
        place.name = val
        
        self._task = val
    
    @property
    def _main_place(self):
        
        if self._main_place_:
            return self._main_place_
        
        for p in self.places.itervalues():
            if p.name == self.task:
                self._main_place_ = p
                return self._main_place_
        
        raise Exception('Main Place was not found!')
    
    @_main_place.setter
    def _main_place(self, val):
        
        if not isinstance(val, Place):
            raise Exception("Main Place must be an object from Place Class or derived.")
        
        self._main_place_ = val
    
    def add_arc(self, source, target, weight = 1, _treeElement = None):
        
        if isinstance(target, SequenceTransition) and len(target._incoming_arcs) > 0:
            raise Exception('A Sequence Transition cannot have more than one task connected to it.\n\
            If synchronization is needed, two hierarchy levels must be created.')
        
        return super(RulePN, self).add_arc(source, target, weight, _treeElement)

class DexecPN(PlanningRulePN):
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        return BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls, task = task)

class FinalizationPN(PlanningRulePN):
    
    def _initialize(self):
        
        super(FinalizationPN, self)._initialize()
        
        t = self._main_transition
        p = TaskStatusPlace('task_status(?)', t.position + Vec2(-200, -100))
        self.add_place(p)
        self.add_arc(p, t)
        self.add_arc(t, p)
    
    def _can_connect(self, source, target, weight):
        
        if source.__class__ is TaskStatusPlace and weight == 0:
            raise Exception("Finalization rules must have a TaskStatus place as precondition (i. e. its arc's weight must be one)")
        
        super(FinalizationPN, self)._can_connect(source, target, weight)
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        return BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls, task = task)

class CancelationPN(PlanningRulePN):
    
    def get_CLIPS_code(self):
        return super(CancelationPN, self).get_clips_code(is_cancelation = True)
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        return BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls, task = task)
