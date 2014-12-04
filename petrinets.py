# -*- coding: utf-8 -*-
"""
@author: Adrián Revuelta Cuauhtli
"""

import copy
import io
import os
#import xml.etree.ElementTree as ET
import lxml.etree as ET

from nodes import Place, Transition, PreconditionsTransition, _Arc, _get_treeElement,\
    RuleTransition, SequenceTransition, TaskStatusPlace, NonPrimitiveTaskPlace,\
    PrimitiveTaskPlace
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
        
        p = self.places.pop(key)
        p._references.clear()
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
        
        t = self.transitions.pop(key)
        t._references.clear()
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
            return None
        
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
            arc_el = arc.petri_net._tree.find('//*[@id="' + arc._treeElement + '"]')
            arc_el.getparent().remove(arc_el)

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
            
            if PetriNetClass == None:
                PetriNetClass = BasicPetriNet
            
            if task:
                t = None
                for current_t in net.findall('page//transition'):
                    if current_t.find('name/text').text.startswith(PreconditionsTransition.PREFIX + '.'):
                        t = current_t
                        break
                    if current_t.find('name/text').text.startswith(RuleTransition.PREFIX + '.'):
                        t = current_t
                        break
                
                if t is not None:
                    transition_id = t.get('id')
                    p = None
                    for current_arc in net.findall("page//arc[@target='"+ transition_id +"']"):
                        place_id = current_arc.get('source')
                        current_p = net.find('page//place[@id="' + place_id + '"]')
                        p_name = current_p.find('name').findtext('text')
                        l = len(PrimitiveTaskPlace.PREFIX) + 1
                        if p_name[:l] == PrimitiveTaskPlace.PREFIX + '.':
                            p = current_p
                            break
                        l = len(NonPrimitiveTaskPlace.PREFIX) + 1
                        if p_name[:l] == NonPrimitiveTaskPlace.PREFIX + '.':
                            p = current_p
                            break
                    if p is None:
                        print 'WARNING: TaskPlace not found!'
                    else:
                        p.find('name/text').text = p_name[:l] + task
                
                pn = PetriNetClass(name, task, _net = net)
            else:
                pn = PetriNetClass(name, _net = net)
            
            try:
                scale = float(net.find('toolspecific[@tool="PNLab"]/scale/text').text)
                pn.scale = scale
            except:
                pass
            
            first_queue = [net]
            second_queue = []
            
            #Since name clashes can occur, all nodes must be renamed after reading the file
            # (i. e. after creating all nodes AND ARCS correctly).
            renaming_places_dict = {}
            renaming_transitions_dict = {}
            
            while first_queue:
                current = first_queue.pop(0)
                second_queue.append(current)
                
                for p_el in current.findall('place'):
                    p = Place.fromETreeElement(p_el)
                    pn.add_place(p)
                    
                    renaming_places_dict[p_el.get('id')] = repr(p)
                    
                for t_el in current.findall('transition'):
                    t = Transition.fromETreeElement(t_el)
                    pn.add_transition(t)
                    
                    renaming_transitions_dict[t_el.get('id')] = repr(t)
                
                pages = current.findall('page')
                if pages:
                    first_queue += pages
            
            while second_queue:
                current = second_queue.pop(0)
                
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
                    for e in net.findall('.//referencePlace[@ref="' + place_id + '"]'):
                        e.set('ref', new_id)
                    for e in net.findall('.//arc[@source="' + place_id + '"]'):
                        e.set('source', new_id)
                    for e in net.findall('.//arc[@target="' + place_id + '"]'):
                        e.set('target', new_id)
                    ref.set('id', new_id)
                    #Translate old_id to new_id to set references correctly before renaming main node.
                    pn.places[renaming_places_dict[reference.get('id')]]._references.add(new_id)
                
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
                    for e in net.findall('.//referenceTransition[@ref="' + transition_id + '"]'):
                        e.set('ref', new_id)
                    for e in net.findall('.//arc[@source="' + transition_id + '"]'):
                        e.set('source', new_id)
                    for e in net.findall('.//arc[@target="' + transition_id + '"]'):
                        e.set('target', new_id)
                    ref.set('id', new_id)
                    #Translate old_id to new_id to set references correctly before renaming main node.
                    pn.transitions[renaming_transitions_dict[reference.get('id')]]._references.add(new_id)
                
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
                    
                    if source.tag == 'place':
                        source = pn.places[renaming_places_dict[source.get('id')]]
                        target = pn.transitions[renaming_transitions_dict[target.get('id')]]
                    else:
                        source = pn.transitions[renaming_transitions_dict[source.get('id')]]
                        target = pn.places[renaming_places_dict[target.get('id')]]
                        
                    try:
                        weight = int(arc.find('inscription/text').text)
                    except:
                        weight = 1
                    pn.add_arc(source, target, weight, arc.get('id'))
            
            renaming_places = renaming_places_dict.items()
            key = val = 'placebo'
            while renaming_places and key == val:
                key, val = renaming_places.pop(0)
                renaming_places_dict.pop(key)
            
            if key != val:
                new_key = val
                while new_key in renaming_places_dict:
                    new_key += 'a'
                
                renaming_places.append((new_key, val))
                renaming_places_dict[new_key] = val
                
                p_el = net.find('.//place[@id="' + key + '"]')
                for e in net.findall('.//referencePlace[@ref="' + key + '"]'):
                    e.set('ref', new_key)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', new_key)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', new_key)
                p_el.set('id', new_key)
            
            while renaming_places:
                
                key, val = renaming_places.pop(0)
                if key == val:
                    del renaming_places_dict[key]
                    continue
                
                if val in renaming_places_dict:
                    renaming_places.append((key, val))
                    continue
                
                p_el = net.find('.//place[@id="' + key + '"]')
                for e in net.findall('.//referencePlace[@ref="' + key + '"]'):
                    e.set('ref', val)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', val)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', val)
                p_el.set('id', val)
                
                del renaming_places_dict[key]
                
            
            renaming_transitions = renaming_transitions_dict.items()
            key = val = 'placebo'
            while renaming_transitions and key == val:
                key, val = renaming_transitions.pop(0)
                renaming_transitions_dict.pop(key)
            
            if key != val:
                new_key = val
                while new_key in renaming_transitions_dict:
                    new_key += 'a'
                
                renaming_transitions.append((new_key, val))
                renaming_transitions_dict[new_key] = val
                
                t_el = net.find('.//transition[@id="' + key + '"]')
                for e in net.findall('.//referenceTransition[@ref="' + key + '"]'):
                    e.set('ref', new_key)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', new_key)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', new_key)
                t_el.set('id', new_key)
            
            while renaming_transitions:
                
                key, val = renaming_transitions.pop(0)
                if key == val:
                    del renaming_transitions_dict[key]
                    continue
                
                if val in renaming_transitions_dict:
                    renaming_transitions.append((key, val))
                    continue
                
                t_el = net.find('.//transition[@id="' + key + '"]')
                for e in net.findall('.//referenceTransition[@ref="' + key + '"]'):
                    e.set('ref', val)
                for e in net.findall('.//arc[@source="' + key + '"]'):
                    e.set('source', val)
                for e in net.findall('.//arc[@target="' + key + '"]'):
                    e.set('target', val)
                t_el.set('id', val)
                
                del renaming_transitions_dict[key]
            
            pnets.append(pn)
        
        return pnets
        
    
    def to_ElementTree(self):
        
        net = self._tree.find('net')
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
    
    def __init__(self, name, task, is_primitive_task = None, _net = None):
        
        self._main_transition_ = None
        self._main_place_ = None
        self._to_delete = []
        self._deleted_fact_count = 0
        
        self._preconditions_handlers = {'task': self._handle_task,
                                        'fact': self._handle_fact,
                                        'sfact': self._handle_sfact,
                                        'delete': self._handle_delete,
                                        'cmp': self._handle_cmp,
                                        'or' : self._handle_or,
                                        'not' : self._handle_not,
                                        'task_status' : lambda x: '(task_status ?pnpdt_task__ ' + x[1] + ')',
                                        'active_task' : lambda x: '(active_task ?pnpdt_task__)',
                                        'cancel_active_tasks' : lambda x: '(cancel_active_tasks)'
                                    }
        
        super(RulePN, self).__init__(name, _net)
        
        self._task = task
        if is_primitive_task is not None:
            self._initialize()
            if is_primitive_task:
                self._main_place = PrimitiveTaskPlace(self.task, Vec2(150, 300))
            else:
                self._main_place = NonPrimitiveTaskPlace(self.task, Vec2(150, 300))
            self.add_place(self._main_place)
            self.add_arc(self._main_place, self._main_transition)
            self.add_arc(self._main_transition, self._main_place)
    
    def _initialize(self):
        self._main_transition = RuleTransition('Rule', Vec2(350, 300))
        self.add_transition(self._main_transition)
    
    @property
    def task(self):
        return self._task
    
    @task.setter
    def task(self, val):
        if not val:
            raise Exception('Task name cannot be an empty string.')
        
        for p in self.places.itervalues():
            if p.name == self.task:
                break
        
        if not p:
            raise Exception('Parent Task Place was not found.')
        
        p.name = val
        
        self._task = val
    
    @property
    def _main_transition(self):
        
        if self._main_transition_:
            return self._main_transition_
        
        for t in self.transitions.itervalues():
            if t.__class__ is PreconditionsTransition or t.__class__ is RuleTransition:
                self._main_transition_ = t
                return self._main_transition_
        
        raise Exception('Main Transition was not found!')
    
    @_main_transition.setter
    def _main_transition(self, val):
        
        if not isinstance(val, Transition):
            raise Exception("Main Transition must be an object from Transition Class or derived.")
        
        self._main_transition_ = val
    
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
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls, task = task)
    
    def get_clips_code(self):
        
        '''
        (rule task_name-rule_name
            <preconditions>
            =>
            (retract <vars>)
            (assert
                <new_facts>
                <task facts>
            )
            (send-command "command" symbol "params" timeout attempts)
        '''
        
        self._deleted_fact_count = 0
        self._to_delete = []
        
        preconditions = self._main_transition._get_preconditions()
        #facts, tasks, commands = self._main_transition._get_effects()
        
        task = self.task
        pos = self.task.find('(')
        if pos > -1:
            task = task[:pos]
        
        rule = ['(defrule ' + task + '-' + self.name]
        for el in preconditions:
            rule += self._indent(self._preconditions_handlers[el[0]](el))
        rule += self._indent('=>')
        rule += [')']
        
        return '\n'.join(rule)
    
    def _indent(self, text):
        
        if isinstance(text, basestring):
            return ['\t' + text]

        for i in range(len(text)):
            text[i] = '\t' + text[i]
        
        return text
    
    def _get_func_text(self, lst):
        text = '(' + lst[0]
        
        for arg in lst[1:]:
            if arg in self._main_transition._func_dict:
                arg = self._get_func_text(self._main_transition._func_dict[arg])
            text += ' ' + arg
        
        text += ')'
    
    def _handle_task(self, lst):
        
        text = ''
        
        for arg in lst[2]:
            if arg in self._main_transition._func_dict:
                arg = self._get_func_text(self._main_transition._func_dict[arg])
            text += ' ' + arg 
        
        return '?pnpdt_task__ <-(task (plan ?pnpdt_planName__) (action_type {0}) (params{1}) (step ?pnpdt_step__ $?pnpdt_steps__) (parent ?pnpdt_p__)'.format(lst[1], text)
    
    def _handle_fact(self, lst):
        text = ''
        
        for arg in lst[2]:
            if arg in self._main_transition._func_dict:
                arg = self._get_func_text(self._main_transition._func_dict[arg])
            text += ' ' + arg 
        
        return '({0}{1})'.format(lst[1], text)
    
    def _handle_sfact(self, lst):
        text = ''
        
        for p in lst[2]:
            text = ' (' + p[0]
            for arg in p[1]:
                if arg in self._main_transition._func_dict:
                    arg = self._get_func_text(self._main_transition._func_dict[arg])
                text += ' ' + arg
            text += ')'
         
        
        return '({0}{1})'.format(lst[1], text)
    
    def _handle_delete(self, lst):
        el = lst[1]
        self._deleted_fact_count += 1
        var = '?pnpdt_f' + str(self._deleted_fact_count) + '__'
        self._to_delete.append(var)
        
        fact_text = self._preconditions_handlers[el[0]](el)
        return var + ' <-' + fact_text
    
    def _handle_cmp(self, lst):
        el = lst[1]
        op1 = el[1]
        if op1 in self._main_transition._func_dict:
            op1 = self._get_func_text(self._main_transition._func_dict[op1])
        op2 = el[2]
        if op2 in self._main_transition._func_dict:
            op2 = self._get_func_text(self._main_transition._func_dict[op2])
        
        return '(test ({0} {1} {2}))'.format(el[0], op1, op2)
    
    def _handle_or(self, lst):
        el = lst[1]
        text = ['(or']
        text += self._indent(self._preconditions_handlers[el[0]](el))
        text += [')']
        
        return text
    
    def _handle_not(self, lst):
        el = lst[1]
        text = ['(not']
        text += self._indent(self._preconditions_handlers[el[0]](el))
        text += [')']
        
        return text
    

class DecompositionPN(RulePN):
    
    def __init__(self, name, task, is_primitive_task = None, _net = None):
        super(DecompositionPN, self).__init__(name, task, is_primitive_task, _net)
    
    def _initialize(self):
        self._main_transition = PreconditionsTransition('Preconditions', Vec2(350, 300))
        self.add_transition(self._main_transition)
    
    '''
    @BasicPetriNet.task.setter
    def task(self, val):
        
        BasicPetriNet.task.setter(val)
        
        for p in self.places.itervalues():
            if p.name == self.task:
                break
        
        if not p:
            raise Exception('Parent Task Place was not found.')
        
        p.name = val
    '''
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        
        return BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls, task = task)
    
    def add_arc(self, source, target, weight = 1, _treeElement = None):
        
        #Assert
        if isinstance(target, SequenceTransition) and len(target._incoming_arcs) > 0:
            raise Exception('A Sequence Transition cannot have more than one tasks connected to it.\n\
            If synchronization is needed, two hierarchy levels must be created.')
        
        return super(DecompositionPN, self).add_arc(source, target, weight, _treeElement)

class ExecutionPN(RulePN):
    
    def __init__(self, name, task, is_primitive_task = None, _net = None):
        
        super(ExecutionPN, self).__init__(name, task, is_primitive_task, _net)
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        return BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls, task = task)

class FinalizationPN(RulePN):
    
    def __init__(self, name, task, is_primitive_task = None, _net = None):
        
        super(FinalizationPN, self).__init__(name, task, is_primitive_task, _net)
    
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

class CancelationPN(RulePN):
    
    def get_CLIPS_code(self):
        
        preconditions = self._main_transition._get_precondtions(is_cancelation = True)
    
    @classmethod
    def from_pnml_file(cls, filename, task):
        return BasicPetriNet.from_pnml_file(filename, PetriNetClass = cls, task = task)
