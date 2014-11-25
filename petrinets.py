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
    def from_ElementTree(cls, et, name = None, PetriNetClass = None):
        
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
                
            pn = PetriNetClass(name, _net = net)
            
            try:
                scale = float(net.find('toolspecific[@tool="PNLab"]/scale/text').text)
                pn.scale = scale
            except:
                pass
            
            first_queue = [net]
            second_queue = []
            
            while first_queue:
                current = first_queue.pop()
                second_queue.append(current)
                
                for p_el in current.findall('place'):
                    p = Place.fromETreeElement(p_el)
                    pn.add_place(p)
                    place_id = p_el.get('id')
                    for e in net.findall('.//referencePlace[@ref="' + place_id + '"]'):
                        e.set('ref', repr(p))
                    for e in net.findall('.//arc[@source="' + place_id + '"]'):
                        e.set('source', repr(p))
                    for e in net.findall('.//arc[@target="' + place_id + '"]'):
                        e.set('target', repr(p))
                    p_el.set('id', repr(p))
                for t_el in current.findall('transition'):
                    t = Transition.fromETreeElement(t_el)
                    pn.add_transition(t)
                    transition_id = t_el.get('id')
                    for e in net.findall('.//referenceTransition[@ref="' + transition_id + '"]'):
                        e.set('ref', repr(t))
                    for e in net.findall('.//arc[@source="' + transition_id + '"]'):
                        e.set('source', repr(t))
                    for e in net.findall('.//arc[@target="' + transition_id + '"]'):
                        e.set('target', repr(t))
                    t_el.set('id', repr(t))
                
                pages = current.findall('page')
                if pages:
                    first_queue += pages
            
            while second_queue:
                current = second_queue.pop()
                
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
                    pn.places[reference.get('id')]._references.add(new_id)
                
                for ref in net.findall('.//referenceTransition'):
                    reference = ref
                    try:
                        while reference.tag[:9] == 'reference':
                            reference = net.find('.//*[@id="' + reference.get('ref') + '"]')
                    except:
                        raise Exception("Referenced node '" + ref.get('ref') + "' was not found.")
                    
                    transition_id = ref.get('id')
                    pn._transition_counter += 1
                    new_id = 'P{:0>3d}'.format(pn._transition_counter)
                    for e in net.findall('.//referenceTransition[@ref="' + transition_id + '"]'):
                        e.set('ref', new_id)
                    for e in net.findall('.//arc[@source="' + transition_id + '"]'):
                        e.set('source', new_id)
                    for e in net.findall('.//arc[@target="' + transition_id + '"]'):
                        e.set('target', new_id)
                    ref.set('id', new_id)
                    pn.places[reference.get('id')]._references.add(new_id)
                
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
                        source = pn.places[source.get('id')]
                        target = pn.transitions[target.get('id')]
                    else:
                        source = pn.transitions[source.get('id')]
                        target = pn.places[target.get('id')]
                        
                    try:
                        weight = int(arc.find('inscription/text').text)
                    except:
                        weight = 1
                    pn.add_arc(source, target, weight, arc.get('id'))
                
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
    def from_pnml_file(cls, filename, PetriNetClass = None):
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
        if '.pnml.xml' in filename:
            filename = filename[:filename.rfind('.pnml.xml')]
        elif '.pnml' in filename: 
            filename = filename[:filename.rfind('.pnml')]
        elif '.' in filename:
            filename = filename[:filename.rfind('.')]
        
        if PetriNetClass is None:
            PetriNetClass = BasicPetriNet
        
        return PetriNetClass.from_ElementTree(et, name = filename, PetriNetClass = PetriNetClass)
    
    def to_pnml_file(self, file_name):
        et = self.to_ElementTree()
        et.write(file_name, encoding = 'utf-8', xml_declaration = True, pretty_print = True)

class RulePN(BasicPetriNet):
    
    def __init__(self, name, task, is_primitive_task, _net = None):
        
        super(RulePN, self).__init__(name, _net)
        
        self._task = task
        self._initialize()
        
        if is_primitive_task:
            self._main_place = PrimitiveTaskPlace(self.task, Vec2(150, 300))
        else:
            self._main_place = NonPrimitiveTaskPlace(self.task, Vec2(150, 300))
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
        
        for p in self.places.itervalues():
            if p.name == self.task:
                break
        
        if not p:
            raise Exception('Parent Task Place was not found.')
        
        p.name = val
        
        self._task = val
    
    def _initialize(self):
        self._main_transition = RuleTransition('Rule', Vec2(350, 300))
        self.add_transition(self._main_transition)

class NonPrimitiveTaskPN(RulePN):
    
    def __init__(self, name, task, is_primitive_task, _net = None):
        super(NonPrimitiveTaskPN, self).__init__(name, task, is_primitive_task, _net)
    
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
    def from_pnml_file(cls, filename):
        BasicPetriNet.from_pnml_file(filename, cls)
    
    def add_arc(self, source, target, weight = 1, _treeElement = None):
        
        #Assert
        if isinstance(target, SequenceTransition) and len(target._incoming_arcs) > 0:
            raise Exception('A Sequence Transition cannot have more than one tasks connected to it.\n\
            If synchronization is needed, two hierarchy levels must be created.')
        
        return super(NonPrimitiveTaskPN, self).add_arc(source, target, weight, _treeElement)

class PrimitiveTaskPN(RulePN):
    
    def __init__(self, name, task, is_primitive_task, _net = None):
        
        super(PrimitiveTaskPN, self).__init__(name, task, is_primitive_task, _net)
    
    @classmethod
    def from_pnml_file(cls, filename):
        BasicPetriNet.from_pnml_file(filename, cls)

class FinalizingPN(RulePN):
    
    def __init__(self, name, task, is_primitive_task, _net = None):
        
        super(FinalizingPN, self).__init__(name, task, is_primitive_task, _net)
    
    def _initialize(self):
        
        super(FinalizingPN, self)._initialize()
        
        t = self._main_transition
        p = TaskStatusPlace('task_status(?)', t.position + Vec2(-200, -100))
        self.add_place(p)
        self.add_arc(p, t)
        self.add_arc(t, p)
    
    @classmethod
    def from_pnml_file(cls, filename):
        BasicPetriNet.from_pnml_file(filename, cls)