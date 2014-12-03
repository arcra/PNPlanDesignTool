# -*- coding: utf-8 -*-
"""
@author: Adrián Revuelta Cuauhtli
"""

import re
import Tkinter
import tkFont
import tkMessageBox

from copy import deepcopy
from petrinets import BasicPetriNet, DecompositionPN, ExecutionPN,\
    FinalizationPN, CancelationPN, RulePN
from nodes import Place, Transition, TRANSITION_CLASSES, PLACE_CLASSES,\
    PreconditionsTransition, NonPrimitiveTaskPlace, SequenceTransition,\
    PrimitiveTaskPlace, FactPlace, StructuredFactPlace, OrPlace, AndTransition,\
    RuleTransition, TaskStatusPlace, CommandPlace
from settings import *
from utils import Vec2
from auxdialogs import PositiveIntDialog, NonNegativeFloatDialog, NonNegativeIntDialog

class BasicPNEditor(Tkinter.Canvas):
    """
    Tk widget for editing Petri Net diagrams.
    
    Subclass of the Tkinter.Canvas Widget class. Handles several GUI interactions
    and provides some basic API methods to edit the Petri Net without the GUI events.
    """
    
    _GRID_SIZE = 100.0
    _GRID_SIZE_FACTOR = 3
    SMALL_GRID_COLOR = '#BBBBFF'
    BIG_GRID_COLOR = '#7777FF'
    
    _MARKING_REGEX = re.compile('^[0-9]+$')
    _NAME_REGEX = re.compile('^[a-zA-Z][a-zA-Z0-9_ -]*$')
    #_NAME_REGEX = re.compile('^[a-zA-Z][a-zA-Z0-9_ -]*( ?\([a-zA-Z0][a-zA-Z0-9_ -]*(, ?[a-zA-Z0][a-zA-Z0-9_ -]*)*\))?$')
    _TOKEN_RADIUS = 3
    
    PetriNetClass = BasicPetriNet
    
    def __init__(self, parent, *args, **kwargs):
        """
        BasePNEditor constructor.
        
        Besides the usual Canvas parameters, it should receive at least either
        a Petri Net object or a name for the new Petri Net to be created
        and a task name.
        
        Keyword Arguments:
        PetriNet -- BasicPetriNet object to load for viewing/editing.
        name -- In case no Petri Net object is specified, a name must be
                specified for the new Petri Net to be created.
        task -- In case no Petri Net object is specified, a task name must be
                specified for the new Petri Net to be created.
        grid -- (Default True) Boolean that specifies whether to draw a square grid.
        """
        
        if not 'bg' in kwargs:
            kwargs['bg'] = 'white'
        
        self._grid = kwargs.pop('grid', True)
        self._label_transitions = kwargs.pop('label_transitions', False)
        
        self._create_petri_net(kwargs)
        
        Tkinter.Canvas.__init__(self, parent, *args, **kwargs)
        
        self._create_menus()
        
        ################
        # INIT VARS
        ################
        self._last_point = Vec2()
        
        self._offset = Vec2()
        
        self.text_font = tkFont.Font(family = "Helvetica", size = 12)
        self._anchor_tag = 'all'
        self._anchor_set = False
        self._valid_click = False
        
        self._popped_up_menu = None
        self._state = 'normal'
        self._connecting_double = False
        self._connecting_inhibitor = False
        self.status_var = Tkinter.StringVar()
        self.status_var.set('Ready')
        
        self._current_grid_size = self._GRID_SIZE
        
        self.set_petri_net(self._petri_net)
        
        ################################
        #        EVENT BINDINGs
        ################################
        self.bind('<Button-1>', self._dispatch_left_click)
        self.bind('<B1-Motion>', self._dragCallback)
        self.bind('<ButtonRelease-1>', self._change_cursor_back)
        self.bind('<KeyPress-c>', self._center_diagram)
        self.bind('<KeyPress-C>', self._center_diagram)
        self.bind('<Control-z>', self._undo)
        self.bind('<Control-y>', self._redo)
        self.bind('<Escape>', self._escape)
        
        ##########################################
        #    BINDING MOUSE WHEEL SCROLL
        ##########################################
        #Windows and MAC OS:
        self.bind('<MouseWheel>', self._scale_canvas)
        #UNIX/Linux:
        self.bind('<Button-4>', self._scale_up)
        self.bind('<Button-5>', self._scale_down)
        
        self.bind('<Configure>', self._resize)
        
        ##########################################
        #    BINDING RIGHT CLICK
        ##########################################
        #MAC OS:
        if (self.tk.call('tk', 'windowingsystem')=='aqua'):
            self.bind('<2>', self._popup_menu)
            self.bind('<Control-1>', self._popup_menu)
        #Windows / UNIX / Linux:
        else:
            self.bind('<3>', self._popup_menu)
        
        self.bind('<Double-1>', self._set_connecting)
        #self.bind('<Double-1>', self._test)
        self.bind('<Shift-Double-1>', self._set_connecting_double)
    
    '''
    def _test(self, event):
        item = self._get_current_item(event)
        print [item] + list(self.gettags(item))
    '''
    
    def _create_petri_net(self, kwargs):
        
        self._petri_net = kwargs.pop('PetriNet', None)
        petri_net_name = kwargs.pop('name', None)
        
        if not (petri_net_name or self._petri_net):
            raise Exception('Either a PetriNet object or a name must be passed to the Petri Net Editor.')
        
        if not self._petri_net:
            if not petri_net_name:
                raise Exception('The PetriNet name cannot be an empty string.')
            self._petri_net = BasicPetriNet(petri_net_name)
    
    def _create_menus(self):
        
        self._menus_options_sets_dict = {
                                       'canvas' : [
                                                   ('Add Place', self._create_regular_place),
                                                   ('Add Transition', self._create_regular_place)
                                                ],
                                       'pneditor_widget_options' : [
                                                                    ('Toggle grid', self._toggle_grid),
                                                                    ("Toggle transition's labels", self._toggle_transitions_labels)
                                                                ],
                                       'generic_place_properties' : [
                                                          ('Rename Place', self._rename_place)
                                                          #,
                                                          #('Set Initial Marking', self._set_initial_marking),
                                                          #('Set Capacity', self._set_capacity)
                                                        ],
                                       'generic_place_operations' : [
                                                          ('Remove Place', self._remove_place),
                                                        ],
                                       'generic_place_connections' : [
                                                          ('Connect to...', self._connect_place_to, '(Double click)'),
                                                          ('Connect to...(bidirectional)', self._connect_place_to_bidirectional, '(Shift+Double click)')
                                                        ],
                                       'generic_transition_properties' : [
                                                               ('Rename Transition', self._rename_transition),
                                                               ('Switch orientation', self._switch_orientation)
                                                               #,
                                                               #('Set Rate', self._set_rate),
                                                               #('Set Priority', self._set_priority)
                                                            ],
                                       'generic_transition_operations' : [
                                                               ('Remove Transition', self._remove_transition)
                                                            ],
                                       'generic_transition_connections' : [
                                                               ('Connect to...', self._connect_transition_to, '(Double click)'),
                                                               ('Connect to...(bidirectional)', self._connect_transition_to_bidirectional, '(Shift+Double click)')
                                                            ],
                                       'generic_arc_properties' : [
                                                        ('Set Weight', self._set_weight)
                                                    ],
                                       'generic_arc_operations' : [
                                                        ('Remove arc', self._remove_arc)
                                                    ]
                                }
        
        self._configure_menus()
        self._menus_dict['canvas'].append('pneditor_widget_options')
        self._build_menus()
    
    def _configure_menus(self):
        
        self._menus_dict = {
                            'canvas' : ['canvas'],
                            'place' : ['generic_place_properties', 'generic_place_operations', 'generic_place_connections'],
                            'transition' : ['generic_transition_properties', 'generic_transition_operations', 'generic_transition_connections'],
                            'arc' : ['generic_arc_properties', 'generic_arc_operations']
                            }
    
    def _build_menus(self):
        
        for menu, components in self._menus_dict.iteritems():
            if not components:
                continue
            current_menu = Tkinter.Menu(self, tearoff = 0)
            current_component = components[0]
            for el in self._menus_options_sets_dict[current_component]:
                if len(el) > 2:
                    current_menu.add_command(label = el[0], command = el[1], accelerator = el[2])
                else:
                    current_menu.add_command(label = el[0], command = el[1])
            for current_component in components[1:]:
                current_menu.add_separator()
                for el in self._menus_options_sets_dict[current_component]:
                    if len(el) > 2:
                        current_menu.add_command(label = el[0], command = el[1], accelerator = el[2])
                    else:
                        current_menu.add_command(label = el[0], command = el[1])
            
            self._menus_dict[menu] = current_menu
    
    def _toggle_grid(self):
        self._grid = not self._grid
        self._draw_petri_net()
    
    def _toggle_transitions_labels(self):
        self._label_transitions = not self._label_transitions
        self._draw_petri_net() 
    
    def _set_connecting(self, event):
        
        self.focus_set()
        
        if self._state != 'normal':
            return
        
        if event.x < 0 or event.y < 0:
            return
        
        item = self._get_current_item(event)
        
        self._last_point = Vec2(event.x, event.y)
        self._last_clicked_id = item
        
        if item:
            tags = self.gettags(item)
            if 'place' in tags:
                self._connect_place_to()
            elif 'transition' in tags:
                self._connect_transition_to()
    
    def _set_connecting_double(self, event):
        
        if self._state != 'normal':
            return
        
        if event.x < 0 or event.y < 0:
            return
        
        self._connecting_double = True
        self._set_connecting(event)
    
    def _connect_place_to(self):
        """Menu callback to connect clicked place to a transition."""
        self._hide_menu()
        self._state = 'connecting_place'
        self.grab_set()
        self.itemconfig('place', state = Tkinter.DISABLED)
        self.itemconfig('transition&&!label', outline = '#FFFF00', width = 5)
        place_id = self._get_place_id()
        self._source = self._petri_net.places[place_id]
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_place, '+')
    
    def _connect_place_to_bidirectional(self):
        self._connecting_double = True
        self._connect_place_to()
    
    def _connect_place_to_inhibitor(self):
        self._connecting_inhibitor = True
        self._connect_place_to()
    
    def _connecting_place(self, event):
        """Event callback to draw an arc when connecting a place."""
        
        item = self._get_current_item(event)
        self.delete('connecting')
        
        if item and 'transition' in self.gettags(item):
            transition_id = self._get_transition_id(item)
            target = self._petri_net.transitions[transition_id]
            target_point = self._find_intersection(target, self._source.position)
            
            if self._connecting_inhibitor:
                radius = 6
                origin = target_point
                
                side = self._get_intersection_side(target, self._source.position)
                if side == 'top':
                    origin.y -= radius
                elif side == 'bottom':
                    origin.y += radius
                elif side == 'left':
                    origin.x -= radius            
                else:
                    origin.x += radius
                
                target_point = origin + radius*(self._source.position - origin).unit
            
        else:
            target_point = Vec2(event.x, event.y)
            
            if self._connecting_inhibitor:
                radius = 6
                origin = target_point
                
                target_point = origin + radius*(self._source.position - origin).unit
        
        place_vec = target_point - self._source.position
        place_point = self._source.position + place_vec.unit*PLACE_RADIUS*self._current_scale
        
        if self._connecting_inhibitor:
            self.create_line(place_point.x,
                         place_point.y,
                         target_point.x,
                         target_point.y,
                         tags = ('connecting',),
                         width = LINE_WIDTH )
            
            self.create_oval(origin.x - radius,
                             origin.y - radius,
                             origin.x + radius,
                             origin.y + radius,
                             tags = ('connecting',),
                             width = LINE_WIDTH)
        else:
            arrow = Tkinter.BOTH if self._connecting_double else Tkinter.LAST
            
            self.create_line(place_point.x,
                     place_point.y,
                     target_point.x,
                     target_point.y,
                     tags = ('connecting',),
                     width = LINE_WIDTH,
                     arrow= arrow,
                     arrowshape = (10,12,5) )
    
    def _connect_transition_to(self):
        """Menu callback to connect clicked transition to a place."""
        self._hide_menu()
        self._state = 'connecting_transition'
        self.grab_set()
        self.itemconfig('transition', state = Tkinter.DISABLED)
        self.itemconfig('place&&!label&&!token', outline = '#FFFF00', width = 5)
        transition_id = self._get_transition_id()
        self._source = self._petri_net.transitions[transition_id]
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_transition, '+')
    
    def _connect_transition_to_bidirectional(self):
        self._connecting_double = True
        self._connect_transition_to()
        
    def _connecting_transition(self, event):
        """Event callback to draw an arc when connecting a transition."""
        
        item = self._get_current_item(event)
            
        self.delete('connecting')
        
        if item and 'place' in self.gettags(item):
            place_id = self._get_place_id(item)
            target = self._petri_net.places[place_id]
            place_vec = self._source.position - target.position
            target_point = target.position + place_vec.unit*PLACE_RADIUS*self._current_scale
        else:
            target_point = Vec2(event.x, event.y)
        
        transition_point = self._find_intersection(self._source, target_point)
        
        arrow = Tkinter.BOTH if self._connecting_double else Tkinter.LAST
        
        self.create_line(transition_point.x,
                     transition_point.y,
                     target_point.x,
                     target_point.y,
                     tags = ('connecting',),
                     width = LINE_WIDTH,
                     arrow= arrow,
                     arrowshape = (10,12,5) )
    
    def _undo(self, event):
        
        if not self._undo_queue:
            return
        
        action = self._undo_queue.pop()
        self.status_var.set('Undo: ' + action[1])
        if action[0] == 'create_place':
            self.remove_place(action[2])
            action[-2] = Vec2(self._offset)
            action[-1] = self._current_scale
        elif action[0] == 'create_transition':
            self.remove_transition(action[2])
            action[-2] = Vec2(self._offset)
            action[-1] = self._current_scale
        elif action[0] == 'create_arc':
            self.remove_arc(action[2], action[3])
        elif action[0] == 'remove_place':
            old_offset = action[-2]
            old_scale = action[-1]
            p = action[2]
            p.position = self._offset + (p.position - old_offset)/old_scale*self._current_scale
            self.add_place(p)
            action[-2] = self._offset
            action[-1] = self._current_scale
            for arc in action[3].itervalues():
                src = self._petri_net.transitions[repr(arc.source)]
                trgt = self._petri_net.places[repr(arc.target)]
                self.add_arc(src, trgt, arc.weight, _treeElement = arc._treeElement)
            for arc in action[4].itervalues():
                src = self._petri_net.places[repr(arc.source)]
                trgt = self._petri_net.transitions[repr(arc.target)]
                self.add_arc(src, trgt, arc.weight, _treeElement = arc._treeElement)
        elif action[0] == 'remove_transition':
            old_offset = action[-2]
            old_scale = action[-1]
            t = action[2]
            t.position = self._offset + (t.position - old_offset)/old_scale*self._current_scale
            self.add_transition(t)
            action[-2] = self._offset
            action[-1] = self._current_scale
            for arc in action[3].itervalues():
                src = self._petri_net.places[repr(arc.source)]
                trgt = self._petri_net.transitions[repr(arc.target)]
                self.add_arc(src, trgt, arc.weight, _treeElement = arc._treeElement)
            for arc in action[4].itervalues():
                src = self._petri_net.transitions[repr(arc.source)]
                trgt = self._petri_net.places[repr(arc.target)]
                self.add_arc(src, trgt, arc.weight, _treeElement = arc._treeElement)
        elif action[0] == 'remove_arc':
            if isinstance(action[2].source, Place):
                src = self._petri_net.places[repr(action[2].source)]
                trgt = self._petri_net.transitions[repr(action[2].target)]
            else:
                src = self._petri_net.transitions[repr(action[2].source)]
                trgt = self._petri_net.places[repr(action[2].target)]
            self.add_arc(src, trgt, action[2].weight, _treeElement = action[2]._treeElement)
        elif action[0] == 'rename_place':
            old_tag = 'place_' + repr(action[2])
            self.delete('label&&' + old_tag)
            p = self._petri_net.places[repr(action[2])]
            old_name = p.name
            tags = ('label',) + self.gettags(old_tag)
            self.delete('source_' + repr(p))
            self.delete('target_' + repr(p))
            
            try:
                p.name = action[3]
                action[2] = p
                action[3] = old_name
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
            
            self._draw_item_arcs(p)
            self.create_text(p.position.x,
                             p.position.y + PLACE_LABEL_PADDING*self._current_scale,
                             text = str(p),
                             tags=tags,
                             font = self.text_font )
        elif action[0] == 'rename_transition':
            old_tag = 'transition_' + repr(action[2])
            self.delete('label&&' + old_tag)
            t = self._petri_net.transitions[repr(action[2])]
            old_name = t.name
            tags = ('label',) + self.gettags(old_tag)
            self.delete('source_' + repr(t))
            self.delete('target_' + repr(t))
            
            try:
                t.name = action[3]
                action[2] = t
                action[3] = old_name
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
            
            if t.isHorizontal:
                label_padding = TRANSITION_HORIZONTAL_LABEL_PADDING + 10
            else:
                label_padding = TRANSITION_VERTICAL_LABEL_PADDING + 10
            
            self._draw_item_arcs(t)
            if self._label_transitions:
                self.create_text(t.position.x,
                                 t.position.y + label_padding*self._current_scale,
                                 text = str(t),
                                 tags=tags,
                                 font = self.text_font )
        elif action[0] == 'move_node':
            move_vec = -action[3]/action[-1]*self._current_scale
            if isinstance(action[2], Place):
                node = self._petri_net.places[repr(action[2])]
                self.move('place_' + repr(action[2]), move_vec.x, move_vec.y)
            else:
                node = self._petri_net.transitions[repr(action[2])]
                self.move('transition_' + repr(action[2]), move_vec.x, move_vec.y)
            node.position += move_vec
            self._draw_item_arcs(node)
        elif action[0] == 'switch_orientation':
            name = action[2]
            t = self._petri_net.transitions[name]
            t.isHorizontal = not t.isHorizontal
            
            self.delete('source_' + name)
            self.delete('target_' + name)
            self.delete('transition_' + name)
            
            self._draw_transition(t)
            self._draw_item_arcs(t)
        elif action[0] == 'set_init_marking':
            p = self._petri_net.places[action[2]]
            m = p.init_marking
            p.init_marking = action[3]
            canvas_id = self.find_withtag('!label&&place_' + action[2])
            self._draw_marking(canvas_id, p)
            action[3] = m
        elif action[0] == 'set_capacity':
            p = self._petri_net.places[action[2]]
            c = p.capacity
            p.capacity = action[3]
            action[3] = c
        elif action[0] == 'set_rate':
            t = self._petri_net.transitions[action[2]]
            r = t.rate
            t.rate = action[3]
            action[3] = r
        elif action[0] == 'set_priority':
            t = self._petri_net.transitions[action[2]]
            p = t.priority
            t.priority = action[3]
            action[3] = p
        elif action[0] == 'set_weight':
            w = action[2].weight
            action[2].weight = action[3]
            action[3] = w
            self._draw_arc(action[2])
                
        
        self._redo_queue.append(action)
    
    def _redo(self, event):
        
        if not self._redo_queue:
            return
        
        action = self._redo_queue.pop()
        self.status_var.set('Redo: ' + action[1])
        if action[0] == 'create_place':
            old_offset = action[-2]
            old_scale = action[-1]
            p = action[2]
            p.position = self._offset + (p.position - old_offset)/old_scale*self._current_scale
            self.add_place(p)
        elif action[0] == 'create_transition':
            old_offset = action[-2]
            old_scale = action[-1]
            t = action[2]
            t.position = self._offset + (t.position - old_offset)/old_scale*self._current_scale
            self.add_transition(t)
        elif action[0] == 'create_arc':
            self.add_arc(action[2], action[3])
        elif action[0] == 'remove_place':
            self.remove_place(action[2])
            action[-2] = Vec2(self._offset)
            action[-1] = self._current_scale
        elif action[0] == 'remove_transition':
            self.remove_transition(action[2])
            action[-2] = Vec2(self._offset)
            action[-1] = self._current_scale
        elif action[0] == 'remove_arc':
            if isinstance(action[2].source, Place):
                src = self._petri_net.places[repr(action[2].source)]
                trgt = self._petri_net.transitions[repr(action[2].target)]
            else:
                src = self._petri_net.transitions[repr(action[2].source)]
                trgt = self._petri_net.places[repr(action[2].target)]
            self.remove_arc(src, trgt)
        elif action[0] == 'rename_place':
            
            old_tag = 'place_' + repr(action[2])
            self.delete('label&&' + old_tag)
            p = self._petri_net.places[repr(action[2])]
            old_name = p.name
            tags = ('label',) + self.gettags(old_tag)
            self.delete('source_' + repr(p))
            self.delete('target_' + repr(p))
            
            try:
                p.name = action[3]
                action[2] = p
                action[3] = old_name
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
            
            self._draw_item_arcs(p)
            self.create_text(p.position.x,
                             p.position.y + PLACE_LABEL_PADDING*self._current_scale,
                             text = str(p),
                             tags=tags,
                             font = self.text_font )
        elif action[0] == 'rename_transition':
            old_tag = 'transition_' + repr(action[2])
            self.delete('label&&' + old_tag)
            t = self._petri_net.transitions[repr(action[2])]
            old_name = t.name
            tags = ('label',) + self.gettags(old_tag)
            self.delete('source_' + repr(t))
            self.delete('target_' + repr(t))
            
            try:
                t.name = action[3]
                action[2] = t
                action[3] = old_name
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
            
            if t.isHorizontal:
                label_padding = TRANSITION_HORIZONTAL_LABEL_PADDING + 10
            else:
                label_padding = TRANSITION_VERTICAL_LABEL_PADDING + 10
            
            self._draw_item_arcs(t)
            if self._label_transitions:
                self.create_text(t.position.x,
                                 t.position.y + label_padding*self._current_scale,
                                 text = str(t),
                                 tags=tags,
                                 font = self.text_font )
        elif action[0] == 'move_node':
            move_vec = action[3]/action[-1]*self._current_scale
            if isinstance(action[2], Place):
                node = self._petri_net.places[repr(action[2])]
                self.move('place_' + repr(action[2]), move_vec.x, move_vec.y)
            else:
                node = self._petri_net.transitions[repr(action[2])]
                self.move('transition_' + repr(action[2]), move_vec.x, move_vec.y)
            node.position += move_vec
            self._draw_item_arcs(node)
        elif action[0] == 'switch_orientation':
            name = action[2]
            t = self._petri_net.transitions[name]
            t.isHorizontal = not t.isHorizontal
            
            self.delete('source_' + name)
            self.delete('target_' + name)
            self.delete('transition_' + name)
            
            self._draw_transition(t)
            self._draw_item_arcs(t)
        elif action[0] == 'set_init_marking':
            p = self._petri_net.places[action[2]]
            m = p.init_marking
            p.init_marking = action[3]
            canvas_id = self.find_withtag('!label&&place_' + action[2])
            self._draw_marking(canvas_id, p)
            action[3] = m
        elif action[0] == 'set_capacity':
            p = self._petri_net.places[action[2]]
            c = p.capacity
            p.capacity = action[3]
            action[3] = c
        elif action[0] == 'set_rate':
            t = self._petri_net.transitions[action[2]]
            r = t.rate
            t.rate = action[3]
            action[3] = r
        elif action[0] == 'set_priority':
            t = self._petri_net.transitions[action[2]]
            p = t.priority
            t.priority = action[3]
            action[3] = p
        elif action[0] == 'set_weight':
            w = action[2].weight
            action[2].weight = action[3]
            action[3] = w
            self._draw_arc(action[2])
        
        self._undo_queue.append(action)
    
    def _add_to_undo(self, action):
        self._undo_queue.append(action)
        self.status_var.set(action[1])
        if len(self._undo_queue) > 50:
            self._undo_queue.pop(0)
        self._redo_queue = []
    
    @property
    def petri_net(self):
        """Read-only propery. Deepcopy of the petri net object."""
        return deepcopy(self._petri_net)
    
    @property
    def name(self):
        return self._petri_net.name
    
    def disable(self):
        self._state = 'disabled'
        self.config(background = 'gray')
        self.SMALL_GRID_COLOR = '#DDDDDD'
        self.BIG_GRID_COLOR = '#FFFFFF'
    
    def enable(self):
        self._state = 'normal'
        self.SMALL_GRID_COLOR = '#BBBBFF'
        self.BIG_GRID_COLOR = '#7777FF'
    
    def set_petri_net(self, newPN):
        """Loads a new Petri Net object to be viewed/edited."""
        
        '''
        #TODO (Possibly):
        Check PetriNet saved attribute, before changing the Petri Net
        or destroying the widget.
        '''
        self._petri_net = newPN
        self.edited = True
        self._undo_queue = []
        self._redo_queue = []
        
        self._draw_petri_net()
    
    def set_pn_task(self, val):
        
        self._petri_net.task = val
        self._draw_petri_net()
    
    def add_place(self, p):
        """Adds a place to the Petri Net and draws it.
        
        Note that it uses the PetriNet Class' instance method
        for adding the place and so it will remove any arc information
        it contains for the sake of maintaining consistency. 
        """
        
        self._petri_net.add_place(p)
        self._draw_place(p)
        
        self.edited = True
    
    def add_transition(self, t):
        """Adds a transition to the Petri Net and draws it.
        
        Note that it uses the PetriNet Class' instance method
        for adding the transition and so it will remove any arc information
        it contains for the sake of maintaining consistency.
        """
        
        self._petri_net.add_transition(t)
        self._draw_transition(t)
        
        self.edited = True
    
    def add_arc(self, source, target = None, weight = 1, **kwargs):
        """Adds an arc to the PetriNet object and draws it."""
        
        arc = self._petri_net.add_arc(source, target, weight, kwargs.pop('_treeElement', None))
        
        self._draw_arc(arc)
        self.edited = True
    
    def remove_place(self, p):
        """Removes the place from the Petri Net.
        
        p should be either a Place object, or
        a representation of a place [i. e. repr(place_object)]
        
        Returns the removed object.
        """
        
        p = self._petri_net.remove_place(p)
        
        self.delete('place_' + repr(p))
        self.delete('source_' + repr(p))
        self.delete('target_' + repr(p))
        self.edited = True
        return p
    
    def remove_transition(self, t):
        """Removes the transition from the Petri Net.
        
        t should be either a Transition object, or
        a representation of a transition [i. e. repr(transition_object)]
        
        Returns the removed object.
        """
        
        t = self._petri_net.remove_transition(t)
        
        self.delete('transition_' + repr(t))
        self.delete('source_' + repr(t))
        self.delete('target_' + repr(t))
        self.edited = True
        return t
    
    def remove_arc(self, source, target):
        """Removes an arc from the PetriNet object and from the canvas widget.""" 
        self._petri_net.remove_arc(source, target)
        self.delete('source_' + repr(source) + '&&' + 'target_' + repr(target))
        self.edited = True
    
    def _resize(self, event):
        self._draw_grid()
    
    def _draw_petri_net(self):
        """Draws an entire PetriNet.
        """ 
        self._current_scale = self._petri_net.scale
        self._grid_offset = Vec2()
        
        self.delete('all')
        
        self._draw_grid()
        
        for p in self._petri_net.places.itervalues():
            self._draw_place(p)
        
        for t in self._petri_net.transitions.itervalues():
            self._draw_transition(t)
            
        self._draw_all_arcs()
    
    def _center_diagram(self, event):
        """Center all elements in the PetriNet inside the canvas current width and height."""
        
        if self._state != 'normal':
            return
        
        if len(self._petri_net.places) + len(self._petri_net.transitions) == 0:
            return
        
        minx = 1000000000
        maxx = -1000000000
        miny = 1000000000
        maxy = -1000000000
        
        padding = TRANSITION_HALF_LARGE * 2 * self._current_scale
        
        for p in self._petri_net.places.itervalues():
            if p.position.x - padding < minx:
                minx = p.position.x - padding
            if p.position.x + padding > maxx:
                maxx = p.position.x + padding
            if p.position.y - padding < miny:
                miny = p.position.y - padding
            if p.position.y + padding > maxy:
                maxy = p.position.y + padding
        
        for t in self._petri_net.transitions.itervalues():
            if t.position.x - padding < minx:
                minx = t.position.x - padding
            if t.position.x + padding > maxx:
                maxx = t.position.x + padding
            if t.position.y - padding < miny:
                miny = t.position.y - padding
            if t.position.y + padding > maxy:
                maxy = t.position.y + padding
        
        w = maxx - minx
        h = maxy - miny
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()
        
        if canvas_width == 1:
            canvas_width = self.winfo_reqwidth()
            canvas_height = self.winfo_reqheight()
        
        offset = Vec2(-minx, -miny)
        
        #canvas might not be squared:
        w_ratio = canvas_width/w
        h_ratio = canvas_height/h
        if w_ratio < h_ratio:
            #scale horizontally, center vertically
            scale_factor = w_ratio
            center_offset = Vec2(0, (canvas_height - h*scale_factor)/2)
        else:
            #scale vertically, center horizontally
            scale_factor = h_ratio
            center_offset = Vec2((canvas_width - w*scale_factor)/2, 0)
        
        # (new_pos - (0, 0))*scale_factor
        for p in self._petri_net.places.itervalues():
            p.position = (p.position + offset)*scale_factor + center_offset
        
        for t in self._petri_net.transitions.itervalues():
            t.position = (t.position + offset)*scale_factor + center_offset
        
        self._offset = (self._offset + offset)*scale_factor + center_offset
        
        self._petri_net.scale = self._current_scale*scale_factor
        
        self.edited = True
        self._draw_petri_net()
    
    def _draw_grid(self):
        """Draws the grid on the background."""
        self.delete('grid')
        
        if not self._grid:
            return
        
        self._adjust_grid_offset()
        
        width = self.winfo_width()
        height = self.winfo_height()
        if width == 1:
            width = self.winfo_reqwidth()
            height = self.winfo_reqheight()
        
        startx = int(self._grid_offset.x - self._current_grid_size * self._current_scale)
        step = int(self._current_grid_size * self._current_scale / self._GRID_SIZE_FACTOR)
        
        for x in xrange(startx, width, step):
            self.create_line(x, 0, x, height, fill = self.SMALL_GRID_COLOR, tags='grid')
        
        starty = int(self._grid_offset.y - self._current_grid_size * self._current_scale)
        for y in xrange(starty, height, step):
            self.create_line(0, y, width, y, fill = self.SMALL_GRID_COLOR, tags='grid')
        
        step *= self._GRID_SIZE_FACTOR
        
        for x in xrange(startx, width, step):
            self.create_line(x, 0, x, height, fill = self.BIG_GRID_COLOR, width = 1.4, tags='grid')
        
        for y in xrange(starty, height, step):
            self.create_line(0, y, width, y, fill = self.BIG_GRID_COLOR, width = 1.4, tags='grid')
        
        self.tag_lower('grid')
    
    def _adjust_grid_offset(self):
        """Adjusts the grid offset caused by panning the workspace."""
        
        #current_grid_size is smaller than the small grid
        while self._current_grid_size * self._current_scale < self._GRID_SIZE / self._GRID_SIZE_FACTOR + 1:
            self._current_grid_size *= self._GRID_SIZE_FACTOR
        
        #small grid size is bigger than the current_grid_size
        while self._current_grid_size * self._current_scale >= self._GRID_SIZE * self._GRID_SIZE_FACTOR - 1:
            self._current_grid_size /= self._GRID_SIZE_FACTOR
        
        currentGridSize = int(self._current_grid_size * self._current_scale)
        
        while self._grid_offset.x < 0:
            self._grid_offset.x += currentGridSize
        while self._grid_offset.x >= currentGridSize:
            self._grid_offset.x -= currentGridSize
            
        while self._grid_offset.y < 0:
            self._grid_offset.y += currentGridSize
        while self._grid_offset.y >= currentGridSize:
            self._grid_offset.y -= currentGridSize
    
    def _get_current_item(self, event):
        
        halo = 10
        item = ''
        #ids = self.find_closest(event.x, event.y, halo) #This doesn't work when there is no grid.
        ids = self.find_overlapping(event.x - halo, event.y - halo, event.x + halo, event.y + halo)
        ids = [x for x in ids if 'grid' not in self.gettags(x)]
        if ids:
            item = ids[0]
        
        return item
    
    def _get_place_id(self, item = None):
        """Get place name of the specified canvas item or the last clicked item if None given."""
        if not item:
            item = self._last_clicked_id
        
        tags = self.gettags(item)
        
        for tag in tags:
            if tag[:6] == 'place_':
                return tag[6:]
        
        raise Exception('Place name not found!')
    
    def _get_transition_id(self, item = None):
        """Get transition name of the specified canvas item or the last clicked item if None given."""
        if not item:
            item = self._last_clicked_id
        
        tags = self.gettags(item)
        
        for tag in tags:
            if tag[:11] == 'transition_':
                return tag[11:]
        
        raise Exception('Transition name not found!')
    
    def _draw_all_arcs(self):
        """(Re-)Draws all arcs in the PetriNet object.""" 
        self.delete('arc')
        
        for p in self._petri_net.places.itervalues():
            for arc in p._incoming_arcs.itervalues():
                self._draw_arc(arc)
            for arc in p._outgoing_arcs.itervalues():
                self._draw_arc(arc)
    
    def _draw_item_arcs(self, obj):
        """Draws the arcs of one node from the PetriNet object."""
        
        self.delete('source_' + repr(obj))
        self.delete('target_' + repr(obj))
        for arc in obj.incoming_arcs.itervalues():
            self._draw_arc(arc)
        for arc in obj.outgoing_arcs.itervalues():
            self._draw_arc(arc)
    
    def _draw_place(self, p):
        """Draws a place object in the canvas widget."""
        
        self.delete('place_' + repr(p))
        
        place_id = self._draw_place_item(place = p)
        self._draw_marking(place_id, p)
        self.create_text(p.position.x,
                       p.position.y + PLACE_LABEL_PADDING*self._current_scale,
                       tags = ('label',) + self.gettags(place_id),
                       text = str(p),
                       font = self.text_font )
        
        return place_id
    
    def _draw_transition(self, t):
        """Draws a transition object in the canvas widget."""
        
        self.delete('transition_' + repr(t))
        
        trans_id = self._draw_transition_item(transition = t)
        if self._label_transitions:
            if t.isHorizontal:
                padding = TRANSITION_HORIZONTAL_LABEL_PADDING
            else:
                padding = TRANSITION_VERTICAL_LABEL_PADDING
            
            self.create_text(t.position.x,
                           t.position.y + padding*self._current_scale,
                           tags = ('label',) + self.gettags(trans_id),
                           text = str(t),
                           font = self.text_font )
        
        return trans_id
    
    def _remove_place(self):
        """Menu callback to remove clicked place."""
        self._hide_menu()
        place_id = self._get_place_id()
        p = self._petri_net.places[place_id]
        incoming_arcs = p.incoming_arcs
        outgoing_arcs = p.outgoing_arcs
        self.remove_place(place_id)
        self._add_to_undo(['remove_place', 'Remove Place.', p, incoming_arcs, outgoing_arcs, Vec2(self._offset), self._current_scale])
    
    def _remove_transition(self):
        """Menu callback to remove clicked transition."""
        self._hide_menu()
        transition_id = self._get_transition_id()
        t = self._petri_net.transitions[transition_id]
        incoming_arcs = t.incoming_arcs
        outgoing_arcs = t.outgoing_arcs
        self.remove_transition(transition_id)
        self._add_to_undo(['remove_transition', 'Remove Transition.', t, incoming_arcs, outgoing_arcs, Vec2(self._offset), self._current_scale])
    
    def _remove_arc(self):
        """Menu callback to remove clicked arc."""
        self._hide_menu()
        
        tags = self.gettags(self._last_clicked_id)
        
        if 'arc' not in tags:
            return None
        
        source_name = ''
        target_name = ''
        
        for tag in tags:
            if tag[:7] == 'source_':
                source_name = tag[7:]
            elif tag[:7] == 'target_':
                target_name = tag[7:]
        
        if not source_name or not target_name:
            raise Exception('No source and target specified!')
        
        if source_name in self._petri_net.places:
            source = self._petri_net.places[source_name]
            target = self._petri_net.transitions[target_name]
            arc = self._petri_net.places[source_name]._outgoing_arcs[target_name]
        else:
            source = self._petri_net.transitions[source_name]
            target = self._petri_net.places[target_name]
            arc = self._petri_net.transitions[source_name]._outgoing_arcs[target_name]
        
        self.remove_arc(source, target)
        self._add_to_undo(['remove_arc', 'Remove Arc.', arc])
    
    def _rename_place(self):
        """Menu callback to rename clicked place.
            
            Removes the clicked place and creates a new one with the same properties,
            then sets the entry widget for entering the new name.
        """
        self._hide_menu()
        place_id = self._get_place_id()
        
        #Adjust height when label is occluded
        #h = int(self.config()['height'][4])
        h = self.winfo_height()
        if h == 1:
            h = self.winfo_reqheight()
        entry_y = self._last_point.y + (PLACE_LABEL_PADDING + 10)*self._current_scale + 10
        if entry_y > h:
            diff = Vec2(0.0, h - entry_y)
            self.move('all', diff.x, diff.y)
            for p in self._petri_net.places.itervalues():
                p.position += diff
            for t in self._petri_net.transitions.itervalues():
                t.position += diff
            self._draw_all_arcs()
            if self._grid:
                self._grid_offset = (self._grid_offset + diff).int
                self._draw_grid()
        
        p = self._petri_net.places[place_id]
        
        self.delete('label&&place_' + repr(p))
        canvas_id = self.find_withtag('place_' + repr(p))[0]
        
        txtbox = Tkinter.Entry(self)
        txtbox.insert(0, str(p))
        txtbox.selection_range(0, Tkinter.END)
        
        #extra padding because entry position refers to the center, not the corner
        label_padding = PLACE_LABEL_PADDING + 10
        
        txtbox_id = self.create_window(p.position.x, p.position.y + label_padding*self._current_scale, height= 20, width = 85, window = txtbox)
        txtbox.wait_visibility()
        txtbox.grab_set()
        txtbox.focus_set()
        
        callback = self._get_rename_place_callback(txtbox, txtbox_id, canvas_id, p)
        
        escape_callback = self._get_cancel_rename_place_callback(txtbox, txtbox_id, canvas_id, p)
        
        txtbox.bind('<KeyPress-Return>', callback)
        txtbox.bind('<KeyPress-Escape>', escape_callback)
        
    def _rename_transition(self):
        """Menu callback to rename clicked transition.
            
            Removes the clicked transition and creates a new one with the same properties,
            then sets the entry widget for entering the new name.  
        """
        self._hide_menu()
        transition_id = self._get_transition_id()
        
        #Adjust height when label is occluded
        #h = int(self.config()['height'][4])
        h = self.winfo_height()
        if h == 1:
            h = self.winfo_reqheight()
        entry_y = self._last_point.y + (TRANSITION_VERTICAL_LABEL_PADDING + 10)*self._current_scale + 10
        if entry_y > h:
            #old_t.position.y -= entry_y - h
            diff = Vec2(0.0, h - entry_y)
            self.move('all', diff.x, diff.y)
            for p in self._petri_net.places.itervalues():
                p.position += diff
            for t in self._petri_net.transitions.itervalues():
                t.position += diff
            self._draw_all_arcs()
            if self._grid:
                self._grid_offset = (self._grid_offset + diff).int
                self._draw_grid()
        
        t = self._petri_net.transitions[transition_id]
        
        self.delete('label&&transition_' + repr(t))
        canvas_id = self.find_withtag('transition_' + repr(t))[0]
        
        txtbox = Tkinter.Entry(self)
        txtbox.insert(0, str(t))
        txtbox.selection_range(0, Tkinter.END)
        
        #extra padding because entry position refers to the center, not the corner
        if t.isHorizontal:
            label_padding = TRANSITION_HORIZONTAL_LABEL_PADDING + 10
        else:
            label_padding = TRANSITION_VERTICAL_LABEL_PADDING + 10
        
        txtbox_id = self.create_window(t.position.x, t.position.y + label_padding*self._current_scale, height= 20, width = 85, window = txtbox)
        txtbox.wait_visibility()
        txtbox.grab_set()
        txtbox.focus_set()
        
        callback = self._get_rename_transition_callback(txtbox, txtbox_id, canvas_id, t)
        
        escape_callback = self._get_cancel_rename_transition_callback(txtbox, txtbox_id, canvas_id, t)
        
        txtbox.bind('<KeyPress-Return>', callback)
        txtbox.bind('<KeyPress-Escape>', escape_callback)
    
    def _switch_orientation(self):
        """Menu callback to switch clicked transition's orientation."""
        self._hide_menu()
        transition_id = self._get_transition_id()
        
        t = self._petri_net.transitions[transition_id]
        t.isHorizontal = not t.isHorizontal
        
        self.delete('source_' + transition_id)
        self.delete('target_' + transition_id)
        self.delete('transition_' + transition_id)
        
        self._draw_transition(t)
        self._draw_item_arcs(t)
        
        self._add_to_undo(['switch_orientation', "Switch transition's orientation.", repr(t)])
        self.edited = True
        
    def _set_initial_marking(self):
        """Menu callback to set the initial marking of a Place."""
        self._hide_menu()
        place_id = self._get_place_id()
        p = self._petri_net.places[place_id]
        
        txtbox = Tkinter.Entry(self)
        txtbox.insert(0, str(p.init_marking))
        txtbox.selection_range(0, Tkinter.END)
        txtbox_id = self.create_window(p.position.x, p.position.y, height= 20, width = 20, window = txtbox)
        txtbox.wait_visibility()
        txtbox.grab_set()
        txtbox.focus_set()
        
        callback = self._get_marking_callback(txtbox, txtbox_id, self._last_clicked_id, p)
        
        txtbox.bind('<KeyPress-Return>', callback)
    
    def _set_capacity(self):
        """Menu callback to set the capacity of a Place."""
        self._hide_menu()
        place_id = self._get_place_id()
        p = self._petri_net.places[place_id]
        
        dialog = PositiveIntDialog('Set place capacity', 'Write a positive number for \nthe capacity of place: ' + str(p), 'Capacity', init_value = p.capacity)
        dialog.window.transient(self)
        self.wait_window(dialog.window)
        if dialog.value_set and p.capacity != int(dialog.input_var.get()):
            self._add_to_undo(['set_capacity', 'Set Place capacity.', repr(p), p.capacity])
            p.capacity = int(dialog.input_var.get())
            self.edited = True
    
    def _set_rate(self):
        """Menu callback to set the rate of a Transition."""
        self._hide_menu()
        transition_id = self._get_transition_id()
        t = self._petri_net.transitions[transition_id]
        
        dialog = NonNegativeFloatDialog("Set transition's rate", 'Write a positive decimal number for \nthe rate of transition: ' + str(t), 'Rate', init_value = t.rate)
        dialog.window.transient(self)
        self.wait_window(dialog.window)
        if dialog.value_set and t.rate != float(dialog.input_var.get()):
            self._add_to_undo(['set_rate', 'Set Transition Rate.', repr(t), t.rate])
            t.rate = float(dialog.input_var.get())
            self.edited = True
    
    def _set_priority(self):
        """Menu callback to set the priority of a Transition."""
        self._hide_menu()
        transition_id = self._get_transition_id()
        t = self._petri_net.transitions[transition_id]
        
        dialog = PositiveIntDialog("Set transition's priority", 'Write a positive integer for \nthe priority of transition: ' + str(t), 'Priority', init_value = t.priority)
        dialog.window.transient(self)
        self.wait_window(dialog.window)
        if dialog.value_set and t.priority != int(dialog.input_var.get()):
            self._add_to_undo(['set_priority', 'Set Transition priority.', repr(t), t.priority])
            t.priority = int(dialog.input_var.get())
            self.edited = True
    
    def _set_weight(self, new_weight = None):
        """Menu callback to set the weight of an arc."""
        self._hide_menu()
        
        tags = self.gettags(self._last_clicked_id)
        
        if 'arc' not in tags:
            return None
        
        source_name = ''
        target_name = ''
        
        for tag in tags:
            if tag[:7] == 'source_':
                source_name = tag[7:]
            elif tag[:7] == 'target_':
                target_name = tag[7:]
        
        if not source_name or not target_name:
            raise Exception('No source and target specified!')
        
        if 'place_' + source_name in tags:
            arc = self._petri_net.places[source_name]._outgoing_arcs[target_name] 
        else:
            arc = self._petri_net.places[target_name]._incoming_arcs[source_name]
        
        if new_weight is None:
            new_weight = self._get_weight(arc)
            if not new_weight:
                return
        try:
            arc.source.can_connect_to(arc.target, new_weight)
            self._petri_net._can_connect(arc.source, arc.target, new_weight)
        except Exception as e:
            tkMessageBox.showerror('Invalid weight.', str(e))
            return
        
        self._add_to_undo(['set_weight', 'Set Arc weight.', arc, arc.weight])
        arc.weight = new_weight
        self._draw_arc(arc)
        self.edited = True
    
    def _get_weight(self, arc):
        dialog = PositiveIntDialog("Set arc's weight", 'Write a positive integer for \nthe weight of arc: ' + str(arc), 'Weight', init_value = arc.weight)
        dialog.window.transient(self)
        self.wait_window(dialog.window)
        if dialog.value_set and arc.weight != int(dialog.input_var.get()):
            return int(dialog.input_var.get())
        return None
        
    
    def _get_marking_callback(self, txtbox, txtbox_id, canvas_id, p):
        """Callback factory function for the marking entry widget."""
        def txtboxCallback(event):
            txt = txtbox.get()
            if not self._MARKING_REGEX.match(txt):
                msg = ('Please input a positive integer number for the marking.')
                tkMessageBox.showerror('Invalid Marking', msg)
                return
            new_val = int(txt)
            if new_val > p.capacity:
                new_val = p.capacity
                msg = ('Marking cannot exceed the capacity. Value will be truncated.')
                tkMessageBox.showerror('Invalid Marking', msg)
            if p.init_marking != new_val:
                self._add_to_undo(['set_init_marking', 'Set initial marking.', repr(p), p.init_marking])
                self.edited = True
            p.init_marking = new_val
            self._draw_marking(canvas_id, p)
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
        
        return txtboxCallback
    
    def _draw_marking(self, canvas_id, p):
        """Draws the marking of the given place."""
        tag = 'token_' + repr(p)
        
        self.delete(tag)
        
        if p.init_marking == 0:
            return
        tags = ('token', tag) + self.gettags(canvas_id)
        if p.init_marking == 1:
            self.create_oval(p.position.x - self._TOKEN_RADIUS,
                             p.position.y - self._TOKEN_RADIUS,
                             p.position.x + self._TOKEN_RADIUS,
                             p.position.y + self._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black' )
            self.scale(tag, p.position.x, p.position.y, self._current_scale, self._current_scale)
            return
        if p.init_marking == 2:
            self.create_oval(p.position.x - 3*self._TOKEN_RADIUS,
                             p.position.y - self._TOKEN_RADIUS,
                             p.position.x - self._TOKEN_RADIUS,
                             p.position.y + self._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black' )
            self.create_oval(p.position.x + self._TOKEN_RADIUS,
                             p.position.y - self._TOKEN_RADIUS,
                             p.position.x + 3*self._TOKEN_RADIUS,
                             p.position.y + self._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black' )
            self.scale(tag, p.position.x, p.position.y, self._current_scale, self._current_scale)
            return
        if p.init_marking == 3:
            self.create_oval(p.position.x + self._TOKEN_RADIUS,
                             p.position.y + self._TOKEN_RADIUS,
                             p.position.x + 3*self._TOKEN_RADIUS,
                             p.position.y + 3*self._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black' )
            self.create_oval(p.position.x - 3*self._TOKEN_RADIUS,
                             p.position.y + self._TOKEN_RADIUS,
                             p.position.x - self._TOKEN_RADIUS,
                             p.position.y + 3*self._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black' )
            self.create_oval(p.position.x - self._TOKEN_RADIUS,
                             p.position.y - 3*self._TOKEN_RADIUS,
                             p.position.x + self._TOKEN_RADIUS,
                             p.position.y - self._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black' )
            self.scale(tag, p.position.x, p.position.y, self._current_scale, self._current_scale)
            return
        
        self.create_text(p.position.x,
                         p.position.y,
                         text = str(p.init_marking),
                         tags=tags,
                         fill = 'black',
                         font = self.text_font )
    
    def _create_regular_place(self):
        """Menu callback to create a REGULAR place."""
        self._hide_menu()
        self._create_place(PlaceClass = Place)
        
    def _create_place(self, PlaceClass, point = None, afterFunction = None, afterCancelFunction = None):
        """Creates a Place object, draws it and sets the label entry for entering the name."""
        
        if not point:
            point = self._last_point
        
        #Adjust height when label is occluded
        #h = int(self.config()['height'][4])
        h = self.winfo_height()
        if h == 1:
            h = self.winfo_reqheight()
        entry_y = point.y + (PLACE_LABEL_PADDING + 10)*self._current_scale + 10
        if entry_y > h:
            diff = Vec2(0.0, h - entry_y)
            self.move('all', diff.x, diff.y)
            for p in self._petri_net.places.itervalues():
                p.position += diff
            for t in self._petri_net.transitions.itervalues():
                t.position += diff
            self._draw_all_arcs()
            if self._grid:
                self._grid_offset = (self._grid_offset + diff).int
                self._draw_grid()
            
            point += diff
        
        canvas_id = self._draw_place_item(point, PlaceClass = PlaceClass)
        p = PlaceClass('P{0:0>3d}'.format(self._petri_net._place_counter + 1), point)
        
        txtbox = Tkinter.Entry(self)
        txtbox.insert(0, str(p))
        txtbox.selection_range(0, Tkinter.END)
        #extra padding because entry position refers to the center, not the corner
        label_padding = PLACE_LABEL_PADDING + 10
        
        txtbox_id = self.create_window(p.position.x, p.position.y + label_padding*self._current_scale, height= 20, width = 85, window = txtbox)
        txtbox.wait_visibility()
        txtbox.grab_set()
        txtbox.focus_set()
        
        callback = self._get_create_place_callback(txtbox, txtbox_id, canvas_id, p, afterFunction = afterFunction)
        
        escape_callback = self._get_cancel_create_callback(txtbox, txtbox_id, canvas_id, p, afterCancelFunction = afterCancelFunction)
        
        txtbox.bind('<KeyPress-Return>', callback)
        txtbox.bind('<KeyPress-Escape>', escape_callback)
    
    def _create_regular_transition(self):
        """Menu callback to create a REGULAR transition."""
        self._hide_menu()
        self._create_transition(Transition)
    
    def _create_transition(self, TransitionClass):
        """Creates a Transition object, draws it and sets the label entry for entering the name."""
        
        #Adjust height when label is occluded
        #h = int(self.config()['height'][4])
        h = self.winfo_height()
        if h == 1:
            h = self.winfo_reqheight()
        entry_y = self._last_point.y + (TRANSITION_VERTICAL_LABEL_PADDING + 10)*self._current_scale + 10
        if entry_y > h:
            diff = Vec2(0.0, h - entry_y)
            self.move('all', diff.x, diff.y)
            for p in self._petri_net.places.itervalues():
                p.position += diff
            for t in self._petri_net.transitions.itervalues():
                t.position += diff
            self._draw_all_arcs()
            if self._grid:
                self._grid_offset = (self._grid_offset + diff).int
                self._draw_grid()
            self._last_point += diff
        
        canvas_id = self._draw_transition_item(self._last_point, TransitionClass)
        t = TransitionClass('{0:0>3d}'.format(self._petri_net._transition_counter + 1), self._last_point)
        
        txtbox = Tkinter.Entry(self)
        txtbox.insert(0, str(t))
        txtbox.selection_range(0, Tkinter.END)
        #extra padding because entry position refers to the center, not the corner
        if t.isHorizontal:
            label_padding = TRANSITION_HORIZONTAL_LABEL_PADDING + 10
        else:
            label_padding = TRANSITION_VERTICAL_LABEL_PADDING + 10
        
        txtbox_id = self.create_window(t.position.x, t.position.y + label_padding*self._current_scale, height= 20, width = 85, window = txtbox)
        txtbox.wait_visibility()
        txtbox.grab_set()
        txtbox.focus_set()
        
        callback = self._get_create_transition_callback(txtbox, txtbox_id, canvas_id, t)
        
        escape_callback = self._get_cancel_create_callback(txtbox, txtbox_id, canvas_id, t)
        
        txtbox.bind('<KeyPress-Return>', callback)
        txtbox.bind('<KeyPress-Escape>', escape_callback)
    
    def _draw_place_item(self, point = None, PlaceClass = Place, place = None):
        """Draws a place item, with the attributes corresponding to the place class.
        
            Returns the id generated by the canvas widget.
        """
        self._hide_menu()
        place_tag = ''
        if place:
            point = place.position
            place_tag = 'place_' + repr(place)
            PlaceClass = place.__class__
        elif not (point and PlaceClass):
            raise Exception('Neither location nor place class was specified.')
            
        item = self.create_oval(point.x - PLACE_RADIUS,
                         point.y - PLACE_RADIUS,
                         point.x + PLACE_RADIUS,
                         point.y + PLACE_RADIUS,
                         tags = ('place', PlaceClass.__name__, place_tag),
                         width = LINE_WIDTH,
                         fill = PlaceClass.FILL_COLOR,
                         outline = PlaceClass.OUTLINE_COLOR,
                         disabledfill = '#888888',
                         disabledoutline = '#888888' )
        self.addtag_withtag('p_' + str(item), item)
        self.scale(item, point.x, point.y, self._current_scale, self._current_scale)
        return item
    
    def _draw_transition_item(self, point = None, TransitionClass = Transition, transition = None):
        """Draws a transition item, with the attributes corresponding to the transition class.
        
            Returns the id generated by the canvas widget.
        """
        self._hide_menu()
        
        transition_tag = ''
        if transition:
            point = transition.position
            transition_tag = 'transition_' + repr(transition)
            TransitionClass = transition.__class__
        elif not (point and TransitionClass):
            raise Exception('Neither location nor transition class was specified.')
        
        x0 = point.x - TRANSITION_HALF_SMALL
        y0 = point.y - TRANSITION_HALF_LARGE
        x1 = point.x + TRANSITION_HALF_SMALL
        y1 = point.y + TRANSITION_HALF_LARGE
        
        if transition and transition.isHorizontal:
            x0 = point.x - TRANSITION_HALF_LARGE
            y0 = point.y - TRANSITION_HALF_SMALL
            x1 = point.x + TRANSITION_HALF_LARGE
            y1 = point.y + TRANSITION_HALF_SMALL
        
        item = self.create_rectangle(x0, y0, x1, y1,
                         tags = ('transition', TransitionClass.__name__, transition_tag),
                         width = LINE_WIDTH,
                         fill = TransitionClass.FILL_COLOR,
                         outline = TransitionClass.OUTLINE_COLOR,
                         disabledfill = '#888888',
                         disabledoutline = '#888888' )
        
        self.addtag_withtag('t_' + str(item), item)
        self.scale(item, point.x, point.y, self._current_scale, self._current_scale)
        return item
    
    def _get_create_place_callback(self, txtbox, txtbox_id, canvas_id, p, afterFunction = None):
        """Callback factory function for the <KeyPress-Return> event of the 'create place' entry widget."""
        def txtboxCallback(event):
            txt = txtbox.get()
            
            try:
                p.name = txt
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
                return
            
            label_padding = PLACE_LABEL_PADDING
            
            self._petri_net.add_place(p)
            self._add_to_undo(['create_place', 'Create Place.', p, Vec2(self._offset), self._current_scale])
            
            self.addtag_withtag('place_' + repr(p), canvas_id)
            tags = ('label',) + self.gettags(canvas_id)
            self.create_text(p.position.x,
                             p.position.y + label_padding*self._current_scale,
                             text = str(p),
                             tags=tags,
                             font = self.text_font )
            
            self.edited = True
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
            
            if afterFunction:
                afterFunction(p)
            
        return txtboxCallback
    
    def _get_create_transition_callback(self, txtbox, txtbox_id, canvas_id, t):
        """Callback factory function for the <KeyPress-Return> event of the 'create transition' entry widget."""
        def txtboxCallback(event):
            txt = txtbox.get()
            
            try:
                t.name = txt
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
                return
            
            if t.isHorizontal:
                label_padding = TRANSITION_HORIZONTAL_LABEL_PADDING
            else:
                label_padding = TRANSITION_VERTICAL_LABEL_PADDING
                
            self._petri_net.add_transition(t)
            
            self.addtag_withtag('transition_' + repr(t), canvas_id)
            tags = ('label',) + self.gettags(canvas_id)
            if self._label_transitions:
                self.create_text(t.position.x,
                                 t.position.y + label_padding*self._current_scale,
                                 text = str(t),
                                 tags=tags,
                                 font = self.text_font )
            self._add_to_undo(['create_transition', 'Create Transition.', t, Vec2(self._offset), self._current_scale])
            self.edited = True
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
        return txtboxCallback
    
    def _get_cancel_create_callback(self, txtbox, txtbox_id, canvas_id, obj, afterCancelFunction = None):
        """Callback factory function for the <KeyPress-Escape> event of the 'create' entry widget."""
        def escape_callback(event):
            
            if afterCancelFunction:
                afterCancelFunction()
            
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
            self.delete(canvas_id)
        return escape_callback
    
    def _get_rename_place_callback(self, txtbox, txtbox_id, canvas_id, p):
        """Callback factory function for the <KeyPress-Return> event of the 'rename place' entry widget."""
        def txtboxCallback(event):
            old_name = p.name
            txt = txtbox.get()
            
            try:
                p.name = txt
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
                return
                        
            tags = ('label',) + self.gettags(canvas_id)
            self.create_text(p.position.x,
                             p.position.y + PLACE_LABEL_PADDING*self._current_scale,
                             text = str(p),
                             tags=tags,
                             font = self.text_font )
            self._add_to_undo(['rename_place', 'Rename Place', p, old_name])
            self.edited = True
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
        return txtboxCallback
    
    def _get_rename_transition_callback(self, txtbox, txtbox_id, canvas_id, t):
        """Callback factory function for the <KeyPress-Return> event of the 'rename transition' entry widget."""
        def txtboxCallback(event):
            old_name = t.name
            txt = txtbox.get()
            
            try:
                t.name = txt
            except Exception as e:
                tkMessageBox.showerror('Invalid Name', e)
                return
            
            if t.isHorizontal:
                label_padding = TRANSITION_HORIZONTAL_LABEL_PADDING + 10
            else:
                label_padding = TRANSITION_VERTICAL_LABEL_PADDING + 10
            tags = ('label',) + self.gettags(canvas_id)
            if self._label_transitions:
                self.create_text(t.position.x,
                                 t.position.y + label_padding*self._current_scale,
                                 text = str(t),
                                 tags=tags,
                                 font = self.text_font )
            self._add_to_undo(['rename_transition', 'Rename Transition.', t, old_name])
            self.edited = True
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
        return txtboxCallback
    
    def _get_cancel_rename_place_callback(self, txtbox, txtbox_id, canvas_id, p):
        """Callback factory function for the <KeyPress-Escape> event of the 'rename place' entry widget."""
        def escape_callback(event):
            label_padding = PLACE_LABEL_PADDING
            tags = ('label',) + self.gettags(canvas_id)
            self.create_text(p.position.x,
                             p.position.y + label_padding*self._current_scale,
                             text = str(p),
                             tags=tags,
                             font = self.text_font )
            self._draw_item_arcs(p)
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
        return escape_callback
    
    def _get_cancel_rename_transition_callback(self, txtbox, txtbox_id, canvas_id, t):
        """Callback factory function for the <KeyPress-Escape> event of the 'rename transition' entry widget."""
        def escape_callback(event):
            if t.isHorizontal:
                label_padding = TRANSITION_HORIZONTAL_LABEL_PADDING
            else:
                label_padding = TRANSITION_VERTICAL_LABEL_PADDING
            tags = ('label',) + self.gettags(canvas_id)
            if self._label_transitions:
                self.create_text(t.position.x,
                                 t.position.y + label_padding*self._current_scale,
                                 text = str(t),
                                 tags=tags,
                                 font = self.text_font )
            txtbox.grab_release()
            txtbox.destroy()
            self.focus_set()
            self.delete(txtbox_id)
        return escape_callback
    
    def _draw_arc(self, arc):
        """Internal method. Draws the specified arc object."""
        if isinstance(arc.source, Place):
            p = arc.source
            t = arc.target
        else:
            p = arc.target
            t = arc.source
        
        self.delete('source_' + repr(arc.source) + '&&target_' + repr(arc.target))
        
        place_vec = t.position - p.position
        place_point = p.position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(t, p.position)
        
        if isinstance(arc.source, Place):
            src_point = place_point
            trgt_point = transition_point
        else:
            src_point = transition_point
            trgt_point = place_point
        
        tags = ('arc', 'source_' + repr(arc.source), 'target_' + repr(arc.target))
        
        if arc.weight > 0:
            self.create_line(src_point.x,
                         src_point.y,
                         trgt_point.x,
                         trgt_point.y,
                         tags = tags,
                         width = LINE_WIDTH,
                         arrow= Tkinter.LAST,
                         arrowshape = (10,12,5) )
        else:
            
            radius = 6
            origin = trgt_point
            
            side = self._get_intersection_side(t, p.position)
            if side == 'top':
                origin.y -= radius
            elif side == 'bottom':
                origin.y += radius
            elif side == 'left':
                origin.x -= radius
            else:
                origin.x += radius
            
            trgt_point = origin + radius*(src_point - origin).unit
            
            
            self.create_line(src_point.x,
                         src_point.y,
                         trgt_point.x,
                         trgt_point.y,
                         tags = tags,
                         width = LINE_WIDTH )
            
            self.create_oval(origin.x - radius,
                             origin.y - radius,
                             origin.x + radius,
                             origin.y + radius,
                             tags = tags,
                             width = LINE_WIDTH)
            
        
        if arc.weight > 1:
            arc_vec = arc.target.position - arc.source.position
            offset = Vec2(arc_vec.unit.y, -arc_vec.unit.x)*PLACE_RADIUS/2
            text_pos = (src_point + trgt_point)/2 + offset
            self.create_text(text_pos.x,
                             text_pos.y,
                             tags = tags + ('label',),
                             text = str(arc.weight),
                             font = self.text_font
                             )
    
    def _find_intersection(self, t, point):
        """This is used to compute the point where an arc hits an edge
            of a transition's graphic representation (rectangle)."""
        
        if t.isHorizontal:
            half_width = TRANSITION_HALF_LARGE
            half_height = TRANSITION_HALF_SMALL
        else:
            half_width = TRANSITION_HALF_SMALL
            half_height = TRANSITION_HALF_LARGE
        
        half_width *= self._current_scale
        half_height *= self._current_scale
        
        vec = point - t.position
        
        if vec.x < 0:
            half_width *= -1
        if vec.y < 0:
            half_height *= -1
        
        pos = t.position + Vec2(half_width*min(abs(vec.x)/300,1), half_height*min(abs(vec.y)/300,1))
        
        vec = point - pos
        
        #vec2 = "closest corner from vector from t to p" - pos
        vec2 = t.position + Vec2(half_width, half_height) - pos
        
        #vector is vertical => m is infinity
        if vec.x == 0:
            return Vec2(pos.x, t.position.y + half_height)
        
        # i. e. pos is on the edge (place is further away than 300 from transition... because of how pos is calculated)
        if vec2.x == 0:
            return pos
        
        #Test vertical side:
        m1 = vec.y/vec.x
        m2 = vec2.y/vec2.x
        if abs(m1) <= abs(m2):
            x = vec2.x
            y = m1*x #x0 = y0 = b0 = 0
            return pos + Vec2(x, y)
        
        #Test horizontal side:
        y = vec2.y
        x = y/m1 #x0 = y0 = b0 = 0 
        return pos + Vec2(x, y)
    
    '''
    def _find_intersection(self, t, vec):
        """This is used to compute the point where an arc hits an edge
            of a transition's graphic representation (rectangle)."""
        #NOTE: vec is a vector from the transition's center
        
        if t.isHorizontal:
            half_width = TRANSITION_HALF_LARGE
            half_height = TRANSITION_HALF_SMALL
        else:
            half_width = TRANSITION_HALF_SMALL
            half_height = TRANSITION_HALF_LARGE
        
        half_width *= self._current_scale
        half_height *= self._current_scale
        
        if vec.x < 0:
            half_width = -half_width
        if vec.y < 0:
            half_height = -half_height
        
        #vector is vertical => m is infinity
        if vec.x == 0:
            return Vec2(t.position.x, t.position.y + half_height)
        
        m = vec.y/vec.x
        if abs(m) <= abs(half_height/half_width):
            #Test vertical side:
            x = half_width
            y = m*x #x0 = y0 = b0 = 0
            return t.position + Vec2(x, y)
        
        #Test horizontal side:
        y = half_height
        x = y/m #x0 = y0 = b0 = 0 
        return t.position + Vec2(x, y)
    '''
    
    def _get_intersection_side(self, t, point):
        """This is used to compute the side where an arc hits an edge
            of a transition's graphic representation (rectangle).
            
            It is useful for adding an offset to the circle of an inhibitor arc (and the arc's end).
        """
        
        if t.isHorizontal:
            half_width = TRANSITION_HALF_LARGE
            half_height = TRANSITION_HALF_SMALL
        else:
            half_width = TRANSITION_HALF_SMALL
            half_height = TRANSITION_HALF_LARGE
        
        half_width *= self._current_scale
        half_height *= self._current_scale
        
        vec = point - t.position
        
        if vec.x < 0:
            half_width *= -1
        if vec.y < 0:
            half_height *= -1
        
        pos = t.position + Vec2(half_width*min(abs(vec.x)/300,1), half_height*min(abs(vec.y)/300,1))
        
        vec = point - pos
        
        #vec2 = "closest corner" - pos
        vec2 = t.position + Vec2(half_width, half_height) - pos
        
        #vector is vertical => m is infinity
        if vec.x == 0:
            if vec.y > 0:
                return 'bottom'
            else:
                return 'top'
        
        #pos is on the edge of the transition
        if vec2.x == 0:
            if vec.x > 0:
                return 'right'
            else:
                return 'left'
        
        #Test vertical side:
        m1 = vec.y/vec.x
        m2 = vec2.y/vec2.x
        if abs(m1) <= abs(m2):
            if vec.x > 0:
                return 'right'
            else:
                return 'left'
        
        #Test horizontal side:
        if vec.y > 0:
            return 'bottom'
        else:
            return 'top'
    
    def _popup_menu(self, event):
        """Determines whether the event ocurred over an existing item and which one to
            pop up the correct menu."""
        
        self.focus_set()
        
        if self._state != 'normal':
            return
        
        item = self._get_current_item(event)
        
        self._last_point = Vec2(event.x, event.y)
        self._popped_up_menu = self._menus_dict['canvas']
        if item:
            
            try:
                place_id = self._get_place_id(item)
                p = self._petri_net.places[place_id]
                if p.petri_net.task == p.name:
                    return
            except:
                pass
            
            tags = self.gettags(item)
            self._last_clicked_id = item
            
            for tag in self._menus_dict:
                if tag in tags:
                    self._popped_up_menu = self._menus_dict[tag]
                    break
        
        self._popped_up_menu.post(event.x_root, event.y_root)
    
    def _hide_menu(self):
        """Hides a popped-up menu."""
        if self._popped_up_menu:
            self._popped_up_menu.unpost()
            self._popped_up_menu = None
            return True
        return False
    
    def _scale_up(self, event):
        """Callback for the wheel-scroll to scale the canvas elements to look like a zoom-in."""
        
        if self._state != 'normal':
            return
        
        e = Vec2(event.x, event.y)
        scale_factor = 1.11111111
        self.scale('all', e.x, e.y, scale_factor, scale_factor)
        self._current_scale = round(self._current_scale * scale_factor, 8)
        self._petri_net.scale = self._current_scale
        for p in self._petri_net.places.itervalues():
            p.position = e + (p.position - e)*scale_factor
        for t in self._petri_net.transitions.itervalues():
            t.position = e + (t.position - e)*scale_factor
        self._offset = e + (self._offset - e)*scale_factor
        self._draw_all_arcs()
        if self._grid:
            self._grid_offset = (e + (self._grid_offset - e)*scale_factor).int
            self._draw_grid()
        self.edited = True
    
    def _scale_down(self, event):
        """Callback for the wheel-scroll to scale the canvas elements to look like a zoom-out."""
        
        if self._state != 'normal':
            return
        
        e = Vec2(event.x, event.y)
        scale_factor = 0.9
        self.scale('all', e.x, e.y, scale_factor, scale_factor)
        self._current_scale = round(self._current_scale * scale_factor, 8)
        self._petri_net.scale = self._current_scale
        for p in self._petri_net.places.itervalues():
            p.position = e + (p.position - e)*scale_factor
        for t in self._petri_net.transitions.itervalues():
            t.position = e + (t.position - e)*scale_factor
        self._offset = e + (self._offset - e)*scale_factor
        self._draw_all_arcs()
        if self._grid:
            self._grid_offset = (e + (self._grid_offset - e)*scale_factor).int
            self._draw_grid()
        self.edited = True
    
    def _scale_canvas(self, event):
        """Callback for handling the wheel-scroll event in different platforms."""
        if event.delta > 0:
            self._scale_up(event)
        else:
            self._scale_down(event)
    
    def _dispatch_left_click(self, event):
        """Callback for the left-click event.
        
            It determines what to do depending
            on the current state (normal, connecting_place or connecting_transition).
        """
        
        self.focus_set()
        self._left_click(event)
    
    def _left_click(self, event):
        
        if self._hide_menu():
            return
        
        if event.x < 0 or event.y < 0:
            return
        
        self._valid_click = True
        
        if self._left_click_handlers(event):
            self._state = 'normal'
    
    def _left_click_handlers(self, event):
        
        if self._state == 'normal':
            self._set_anchor(event)
            return True
        
        #Prevent left click to trigger when cursor is outside of the workspace
        if event.x < 0 or event.y < 0:
            return True
        
        if self._state == 'connecting_place':
            self._finish_connect_place(event)
            return True
        
        if self._state == 'connecting_transition':
            self._finish_connect_transition(event)
            return True
    
    def _escape(self, event):
        
        if self._hide_menu():
            return
        
        if self._state == 'normal':
            return
        
        if self._escape_handlers(event):
            self._state = 'normal'
    
    def _escape_handlers(self, event):
        
        if self._state == 'connecting_place':
            self._finish_connect_place(event, True)
            return True
        
        if self._state == 'connecting_transition':
            self._finish_connect_transition(event, True)
            return True
    
    def _set_anchor(self, event):
        """When in "normal" mode (see _left_click), determines whether a movable element or the
            canvas "background" was clicked, to either move the element or pan
            the work area.
        """
        self._anchor_tag = 'all';
        self._last_point = Vec2(event.x, event.y)
        self._anchor_set = True
        self._moved_vec = Vec2()
        self._anchor_node = None
        self.config(cursor = 'fleur')
        
        item = self._get_current_item(event)
        
        if not item:
            return
            
        currentTags = self.gettags(item)
        
        if 'place' in currentTags:
            for t in currentTags:
                if t[:6] == 'place_':
                    self._anchor_tag = t
                    self._anchor_node = self._petri_net.places[t[6:]]
                    break
        elif 'transition' in currentTags:
            for t in currentTags:
                if t[:11] == 'transition_':
                    self._anchor_tag = t
                    self._anchor_node = self._petri_net.transitions[t[11:]]
                    break
    
    def _finish_connect_place(self, event, canceled = None):
        self._state = 'normal'
        self.grab_release()
        self.itemconfig('place', state = Tkinter.NORMAL)
        
        for tc in TRANSITION_CLASSES:
            self.itemconfig('transition&&' + tc.__name__ + '&&!label', outline = tc.OUTLINE_COLOR, width = LINE_WIDTH)
        
        self.unbind('<Motion>', self._connecting_node_fn_id)
        self.delete('connecting')
        
        if canceled:
            self._connecting_inhibitor = False
            self._connecting_double = False
            return
        
        item = self._get_current_item(event)
    
        if item and 'transition' in self.gettags(item):
            name = self._get_transition_id(item)
            target = self._petri_net.transitions[name]
            if self._connecting_inhibitor:
                weight = 0
            else:
                weight = 1
            try:
                self.add_arc(self._source, target, weight)
                self._add_to_undo(['create_arc', 'Create Arc.', self._source, target, weight])
            except Exception as e:
                tkMessageBox.showerror('Cannot create arc', str(e))
            
            if self._connecting_double:
                try:
                    self.add_arc(target, self._source, weight)
                    self._add_to_undo(['create_arc', 'Create Arc.', target, self._source, weight])
                except Exception as e:
                    tkMessageBox.showerror('Cannot create arc', str(e))
        
        self._connecting_inhibitor = False
        self._connecting_double = False
    
    def _finish_connect_transition(self, event, canceled = None):
        self._state = 'normal'
        self.grab_release()
        self.itemconfig('transition', state = Tkinter.NORMAL)
        
        for pc in PLACE_CLASSES:
            self.itemconfig('place&&' + pc.__name__ + '&&!label&&!token', outline = pc.OUTLINE_COLOR, width = LINE_WIDTH)
        
        self.unbind('<Motion>', self._connecting_node_fn_id)
        self.delete('connecting')
        
        if canceled:
            self._connecting_inhibitor = False
            self._connecting_double = False
            return
        
        item = self._get_current_item(event)
    
        if item and 'place' in self.gettags(item):
            name = self._get_place_id(item)
            target = self._petri_net.places[name]
            try:
                self.add_arc(self._source, target)
                self._add_to_undo(['create_arc', 'Create Arc.', self._source, target])
            except Exception as e:
                tkMessageBox.showerror('Cannot create arc', str(e))
            
            if self._connecting_double:
                try:
                    self.add_arc(target, self._source)
                    self._add_to_undo(['create_arc', 'Create Arc.', target, self._source])
                except Exception as e:
                    tkMessageBox.showerror('Cannot create arc', str(e))
        
        self._connecting_inhibitor = False
        self._connecting_double = False
    
    def _dragCallback(self, event):
        """<B1-Motion> callback for moving an element or panning the work area."""
        if not self._anchor_set:
            return
        
        e = Vec2(event.x, event.y)
        
        diff = e - self._last_point
        self.move(self._anchor_tag, diff.x, diff.y)
        if self._anchor_tag == 'all':
            for p in self._petri_net.places.itervalues():
                p.position += diff
            for t in self._petri_net.transitions.itervalues():
                t.position += diff
            self._offset += diff
            #self._draw_all_arcs()
            if self._grid:
                self._grid_offset = (self._grid_offset + diff).int
                self._draw_grid()
        elif self._anchor_tag != 'selection':
            self._anchor_node.position += diff
            self._moved_vec += diff
            self._draw_item_arcs(self._anchor_node)
        
        self.edited = True
        self._last_point = Vec2(event.x, event.y)
        
        
    def _change_cursor_back(self, event):
        """Callback for when the left click is released after panning or moving an item."""
        
        if not self._anchor_set:
            return
        
        if not self._valid_click:
            return
        
        self._valid_click = False 
        
        self.config(cursor = 'arrow')
        self._anchor_set = False
        
        if self._anchor_tag not in ['all', 'selection'] and \
                (abs(self._moved_vec.x) > 2.0 or abs(self._moved_vec.y) > 2.0) :
            
            self._add_to_undo(['move_node', 'Move.', self._anchor_node, Vec2(self._moved_vec), self._current_scale])

class RegularPNEditor(BasicPNEditor):
    
    def __init__(self, parent, *args, **kwargs):
        
        BasicPNEditor.__init__(self, parent, *args, **kwargs)
        
    def _configure_menus(self):
        
        self._menus_options_sets_dict['generic_place_connections'].append(
                            ('Connect to...(inhibitor)', self._connect_place_to_inhibitor, "(Control+Double click)")
                        )
        
        self._menus_options_sets_dict['generic_arc_properties'] += [
                            ('Make inhibitor (weight = 0)', self._make_arc_inhibitor),
                            ('Make ordinary (weight = 1)', self._make_arc_ordinary)
                        ]
                    
        self._menus_dict = {
                            'canvas' : ['canvas'],
                            'Place' : ['generic_place_properties', 'generic_place_operations', 'generic_place_connections'],
                            'Transition' : ['generic_transition_properties', 'generic_transition_operations', 'generic_transition_connections'],
                            'arc' : ['generic_arc_properties', 'generic_arc_operations']
                            }
        
        self.bind('<Control-Double-1>', self._set_connecting_inhibitor)
    
    def _set_connecting_inhibitor(self, event):
        
        self.focus_set()
        
        if self._state != 'normal':
            return
        
        if event.x < 0 or event.y < 0:
            return
        
        item = self._get_current_item(event)
        
        self._last_point = Vec2(event.x, event.y)
        self._last_clicked_id = item
        
        if item:
            tags = self.gettags(item)
            if 'place' in tags:
                self._connecting_inhibitor = True
                self._connect_place_to()
    
    def _make_arc_inhibitor(self):
        self._set_weight(0)
    
    def _make_arc_ordinary(self):
        self._set_weight(1)
    
    def _get_weight(self, arc):
        dialog = NonNegativeIntDialog("Set arc's weight", 'Write a non-negative integer for \nthe weight of arc: ' + str(arc), 'Weight', init_value = arc.weight)
        dialog.window.transient(self)
        self.wait_window(dialog.window)
        if dialog.value_set and arc.weight != int(dialog.input_var.get()):
            return int(dialog.input_var.get())
        return None
    
class RulePNEditor(RegularPNEditor):
    
    PetriNetClass = RulePN
    
    def __init__(self, parent, *args, **kwargs):
        
        kwargs['PetriNetClass'] = self.PetriNetClass
        
        RegularPNEditor.__init__(self, parent, *args, **kwargs)
    
    def _create_petri_net(self, kwargs):
        
        self._petri_net = kwargs.pop('PetriNet', None)
        petri_net_name = kwargs.pop('name', None)
        petri_net_task = kwargs.pop('task', None)
        petri_net_class = kwargs.pop('PetriNetClass', None)
        is_primitive_task = kwargs.pop('is_primitive_task', False)
        
        if not ((petri_net_name and petri_net_task and petri_net_class) or self._petri_net):
            raise Exception('Either a PetriNet object or a name, a task name and a Petri Net class must be passed to the Petri Net Editor.')
        
        if not self._petri_net:
            self._petri_net = petri_net_class(petri_net_name, petri_net_task, is_primitive_task)
    
    def _configure_menus(self):
        
        RegularPNEditor._configure_menus(self)
        
        #override self._menus_options_sets_dict['canvas'] or self._menus_dict['canvas']
        self._menus_dict['canvas'] = []
        
        #ADD options
        
        self._menus_options_sets_dict['preconditions_operations'] = [
                                                             ('Add Fact Precondition', self._add_fact_precondition),
                                                             ('Add NEGATAED Fact Precondition', self._add_negated_fact),
                                                             ('Add Structured Fact Precondition', self._add_structured_fact),
                                                             ('Add NEGATED Structured Fact Precondition', self._add_negated_structured_fact),
                                                             ('Add NAND Precondition', self._add_nand),
                                                             ('Add OR Precondition', self._add_or),
                                                             ('Add NOR Precondition', self._add_nor)
                                                            ]
        self._menus_options_sets_dict['fact_operations'] = [
                                                             ('Add Fact', self._add_fact),
                                                             ('Add Structured Fact', self._add_structured_fact)
                                                            ]
        
        self._menus_options_sets_dict['task_operations'] = [
                                                             ('Add Non-Primitive Task', self._add_non_primitive_task),
                                                             ('Add Primitive Task', self._add_primitive_task)
                                                            ]
        self._menus_options_sets_dict['or_operations'] = [
                                                             ('Add AND Transition', self._add_transition)
                                                            ]
        self._menus_options_sets_dict['command_operations'] = [
                                                             ('Add Command', self._add_command)
                                                            ]
        
        self._menus_dict[RuleTransition.__name__] = ['preconditions_operations', 'fact_operations', 'task_operations', 'generic_transition_properties', 'generic_transition_connections']  # @UndefinedVariable
        self._menus_dict[SequenceTransition.__name__] = ['task_operations', 'generic_transition_properties', 'generic_transition_operations', 'generic_transition_connections']  # @UndefinedVariable
        self._menus_dict[AndTransition.__name__] = ['preconditions_operations', 'generic_transition_properties', 'generic_transition_operations', 'generic_transition_connections']  # @UndefinedVariable
        self._menus_dict[NonPrimitiveTaskPlace.__name__] = ['generic_place_properties', 'generic_place_operations', 'generic_place_connections']  # @UndefinedVariable
        self._menus_dict[PrimitiveTaskPlace.__name__] = ['generic_place_properties', 'generic_place_operations', 'generic_place_connections']  # @UndefinedVariable
        self._menus_dict[FactPlace.__name__] = ['generic_place_properties', 'generic_place_operations', 'generic_place_connections']  # @UndefinedVariable
        self._menus_dict[StructuredFactPlace.__name__] = ['generic_place_properties', 'generic_place_operations', 'generic_place_connections']  # @UndefinedVariable
        self._menus_dict[OrPlace.__name__] = ['or_operations', 'generic_place_operations']  # @UndefinedVariable
        self._menus_dict[CommandPlace.__name__] = ['generic_place_properties', 'generic_place_operations']  # @UndefinedVariable
    
    def _left_click_handlers(self, event):
        
        if RegularPNEditor._left_click_handlers(self, event):
            return True
        
        self.grab_release()
        
        #Call other left_click handlers
        
        if self._state == 'adding_task':
            self._finish_adding_task(event)
            return True
        
        if self._state == 'adding_fact_precondition':
            self._finish_adding_fact_precondition(event)
            return True
        
        if self._state == 'adding_negated_fact':
            self._finish_adding_negated_fact(event)
            return True
        
        if self._state == 'adding_fact':
            self._finish_adding_fact(event)
            return True
        
        if self._state == 'adding_nand':
            self._finish_adding_nand(event)
            return True
        
        if self._state == 'adding_or':
            self._finish_adding_or(event)
            return True
        
        if self._state == 'adding_nor':
            self._finish_adding_nor(event)
            return True
        
        if self._state == 'adding_transition':
            self._finish_adding_transition(event)
            return True
        
        if self._state == 'adding_command':
            self._finish_adding_command(event)
            return True
    
    def _escape_handlers(self, event):
        
        if RegularPNEditor._escape_handlers(self, event):
            return True
        
        self.grab_release()
        self._cancel_creation()
        return True
        
        '''
        if self._state in ['adding_task',
                           'adding_fact_precondition',
                           'adding_negated_fact',
                           'adding_fact',
                           'adding_or',
                           'adding_nor',
                           'adding_transition',
                           'adding_command']:
            self._cancel_creation()
            return True
        '''
    
    def _cancel_creation(self):
        self.delete('selection')
        self.delete('connecting_arc')
        self.unbind('<Motion>', self._connecting_node_fn_id)
        self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _add_non_primitive_task(self):
        self._add_task(NonPrimitiveTaskPlace)
    
    def _add_primitive_task(self):
        self._add_task(PrimitiveTaskPlace)
        
    def _add_task(self, PlaceClass):
        self._state = 'adding_task'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawing of place
        p_position = self._last_point
        t_position = p_position +Vec2(100, 0)
        dummy_transition = SequenceTransition('dummy', t_position)
        npt_id = self._draw_place_item(p_position, PlaceClass)
        t_id = self._draw_transition_item(transition = dummy_transition)
        
        place_vec = t_position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        dummy_transition = SequenceTransition('dummy', t_position)
        transition_point = self._find_intersection(dummy_transition, p_position)
        
        arc_id = self.create_line(place_point.x,
                     place_point.y,
                     transition_point.x,
                     transition_point.y,
                     tags = ['selection'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
        
        self.addtag_withtag('selection', npt_id)
        self.addtag_withtag('selection', t_id)
        self.addtag_withtag('selection', arc_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        
        self._connecting_t = self._petri_net.transitions[transition_id]
        self._place_class = PlaceClass
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_transition_to_place, '+')
    
    def _add_fact_precondition(self):
        self._add_fact_place_precondition(FactPlace)
    
    def _add_structured_fact_precondition(self):
        self._add_fact_place_precondition(StructuredFactPlace)
        
    def _add_fact_place_precondition(self, PlaceClass):
        self._state = 'adding_fact_precondition'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawing of place
        p_position = self._last_point
        fact_id = self._draw_place_item(p_position, PlaceClass)
        self.addtag_withtag('selection', fact_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        
        self._connecting_t = self._petri_net.transitions[transition_id]
        self._place_class = PlaceClass
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_place_to_transition, '+')
    
    def _add_fact(self):
        self._add_fact_place(FactPlace)
    
    def _add_structured_fact(self):
        self._add_fact_place(StructuredFactPlace)
        
    def _add_fact_place(self, PlaceClass):
        self._state = 'adding_fact'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawing of place
        p_position = self._last_point
        fact_id = self._draw_place_item(p_position, PlaceClass)
        self.addtag_withtag('selection', fact_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        
        self._connecting_t = self._petri_net.transitions[transition_id]
        self._place_class = PlaceClass
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_transition_to_place, '+')
    
    def _add_negated_fact(self):
        self._add_negated_fact_place(FactPlace)
    
    def _add_negated_structured_fact(self):
        self._add_negated_fact_place(StructuredFactPlace)
    
    def _add_negated_fact_place(self, PlaceClass):
        self._state = 'adding_negated_fact'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawing of place
        p_position = self._last_point
        fact_id = self._draw_place_item(p_position, PlaceClass)
        self.addtag_withtag('selection', fact_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        
        self._connecting_t = self._petri_net.transitions[transition_id]
        self._place_class = PlaceClass
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_negated_place_to_transition, '+')
    
    def _add_or(self):
        self._state = 'adding_or'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawings (selection)
        p_position = self._last_point
        t1_position = p_position + Vec2(-80, -50)
        t2_position = p_position + Vec2(-80, 50)
        dummy_transition_1 = AndTransition('dummy1', t1_position)
        dummy_transition_2 = AndTransition('dummy2', t2_position)
        
        place_vec = dummy_transition_1.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(dummy_transition_1, p_position)
        
        arc1_id = self.create_line(transition_point.x,
                     transition_point.y,
                     place_point.x,
                     place_point.y,
                     tags = ['selection'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
        
        place_vec = dummy_transition_2.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(dummy_transition_2, p_position)
        
        arc2_id = self.create_line(transition_point.x,
                     transition_point.y,
                     place_point.x,
                     place_point.y,
                     tags = ['selection'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
        
        t1_id = self._draw_transition_item(transition = dummy_transition_1)
        t2_id = self._draw_transition_item(transition = dummy_transition_2)
        place_id = self._draw_place_item(p_position, OrPlace)
        
        label_id = self.create_text(p_position.x,
                         p_position.y + PLACE_LABEL_PADDING*self._current_scale,
                         text = 'OR',
                         tags=['selection'],
                         font = self.text_font )
        
        self.addtag_withtag('selection', t1_id)
        self.addtag_withtag('selection', t2_id)
        self.addtag_withtag('selection', place_id)
        self.addtag_withtag('selection', arc1_id)
        self.addtag_withtag('selection', arc2_id)
        self.addtag_withtag('selection', label_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        self._connecting_t = self._petri_net.transitions[transition_id]
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_place_to_transition, '+')
        
    def _add_nor(self):
        self._state = 'adding_nor'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawings (selection)
        p_position = self._last_point
        t1_position = p_position + Vec2(-80, -50)
        t2_position = p_position + Vec2(-80, 50)
        dummy_transition_1 = AndTransition('dummy1', t1_position)
        dummy_transition_2 = AndTransition('dummy2', t2_position)
        
        place_vec = dummy_transition_1.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(dummy_transition_1, p_position)
        
        arc1_id = self.create_line(transition_point.x,
                     transition_point.y,
                     place_point.x,
                     place_point.y,
                     tags = ['selection'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
        
        place_vec = dummy_transition_2.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(dummy_transition_2, p_position)
        
        arc2_id = self.create_line(transition_point.x,
                     transition_point.y,
                     place_point.x,
                     place_point.y,
                     tags = ['selection'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
        
        t1_id = self._draw_transition_item(transition = dummy_transition_1)
        t2_id = self._draw_transition_item(transition = dummy_transition_2)
        place_id = self._draw_place_item(p_position, OrPlace)
        
        label_id = self.create_text(p_position.x,
                         p_position.y + PLACE_LABEL_PADDING*self._current_scale,
                         text = 'OR',
                         tags=['selection'],
                         font = self.text_font )
        
        self.addtag_withtag('selection', t1_id)
        self.addtag_withtag('selection', t2_id)
        self.addtag_withtag('selection', place_id)
        self.addtag_withtag('selection', arc1_id)
        self.addtag_withtag('selection', arc2_id)
        self.addtag_withtag('selection', label_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        self._connecting_t = self._petri_net.transitions[transition_id]
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_negated_place_to_transition, '+')
    
    def _add_nand(self):
        self._state = 'adding_nand'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawings (selection)
        p_position = self._last_point
        t_position = p_position + Vec2(-80, 0)
        dummy_transition = AndTransition('dummy1', t_position)
        
        place_vec = dummy_transition.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(dummy_transition, p_position)
        
        arc_id = self.create_line(transition_point.x,
                     transition_point.y,
                     place_point.x,
                     place_point.y,
                     tags = ['selection'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
        
        t_id = self._draw_transition_item(transition = dummy_transition)
        place_id = self._draw_place_item(p_position, OrPlace)
        
        label_id = self.create_text(p_position.x,
                         p_position.y + PLACE_LABEL_PADDING*self._current_scale,
                         text = 'NAND',
                         tags=['selection'],
                         font = self.text_font )
        
        self.addtag_withtag('selection', t_id)
        self.addtag_withtag('selection', place_id)
        self.addtag_withtag('selection', arc_id)
        self.addtag_withtag('selection', label_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        self._connecting_t = self._petri_net.transitions[transition_id]
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_negated_place_to_transition, '+')
    
    def _add_transition(self):
        self._state = 'adding_transition'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawings (selection)
        t_id = self._draw_transition_item(self._last_point, AndTransition)
        self.addtag_withtag('selection', t_id)
        
        place_id = self._get_place_id(self._last_clicked_id)
        self._connecting_p = self._petri_net.places[place_id]
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_transition_to_or_place, '+')
    
    def _add_command(self):
        self._state = 'adding_command'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawing of place
        p_position = self._last_point
        place_id = self._draw_place_item(p_position, CommandPlace)
        
        self.addtag_withtag('selection', place_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        
        self._connecting_t = self._petri_net.transitions[transition_id]
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_transition_to_place, '+')
    
    def _connecting_transition_to_place(self, event):
        
        self.delete('connecting_arc')
        
        t = self._connecting_t
        p_position = Vec2(event.x, event.y)
        
        place_vec = t.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(t, p_position)
        
        self.create_line(transition_point.x,
                     transition_point.y,
                     place_point.x,
                     place_point.y,
                     tags = ['connecting_arc'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
    
    def _connecting_transition_to_or_place(self, event):
        
        self.delete('connecting_arc')
        
        t_position = Vec2(event.x, event.y)
        dummy_transition = AndTransition('dummy', t_position)
        p = self._connecting_p
        
        place_vec = t_position - p.position
        place_point = p.position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(dummy_transition, p.position)
        
        self.create_line(transition_point.x,
                     transition_point.y,
                     place_point.x,
                     place_point.y,
                     tags = ['connecting_arc'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
    
    def _connecting_place_to_transition(self, event):
        
        self.delete('connecting_arc')
        
        t = self._connecting_t
        p_position = Vec2(event.x, event.y)
        place_vec = t.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(t, p_position)
        
        self.create_line(place_point.x,
                     place_point.y,
                     transition_point.x,
                     transition_point.y,
                     tags = ['connecting_arc'],
                     width = LINE_WIDTH,
                     arrow= Tkinter.LAST,
                     arrowshape = (10,12,5) )
    
    def _connecting_negated_place_to_transition(self, event):
        
        self.delete('connecting_arc')
        
        t = self._connecting_t
        p_position = Vec2(event.x, event.y)
        place_vec = t.position - p_position
        place_point = p_position + place_vec.unit*PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(t, p_position)
        
        radius = 6
        origin = transition_point
        
        side = self._get_intersection_side(t, p_position)
        if side == 'top':
            origin.y -= radius
        elif side == 'bottom':
            origin.y += radius
        elif side == 'left':
            origin.x -= radius
        else:
            origin.x += radius
        
        trgt_point = origin + radius*(place_point - origin).unit
        
        
        self.create_line(place_point.x,
                     place_point.y,
                     trgt_point.x,
                     trgt_point.y,
                     tags = ['connecting_arc'],
                     width = LINE_WIDTH )
        
        self.create_oval(origin.x - radius,
                         origin.y - radius,
                         origin.x + radius,
                         origin.y + radius,
                         tags = ['connecting_arc'],
                         width = LINE_WIDTH)
            
    def _finish_adding_task(self, event):        
        try:
            self._create_place(self._place_class, afterFunction = self._add_task_arc, afterCancelFunction = self._cancel_create_place)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_fact_precondition(self, event):
        try:
            self._create_place(self._place_class, afterFunction = self._add_fact_precondition_arc, afterCancelFunction = self._cancel_create_place)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_negated_fact(self, event):
        try:
            self._create_place(self._place_class, afterFunction = self._add_negated_fact_arc, afterCancelFunction = self._cancel_create_place)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_fact(self, event):
        try:
            self._create_place(self._place_class, afterFunction = self._add_simple_place_arc, afterCancelFunction = self._cancel_create_place)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_or(self, event):
        try:
            self.delete('selection')
            self.delete('connecting_arc')
            
            p = OrPlace('OR', self._last_point)
            t1 = AndTransition('or_t1', p.position + Vec2(-80, -50))
            t2 = AndTransition('or_t2', p.position + Vec2(-80, 50))
            self.add_place(p)
            self.add_transition(t1)
            self.add_transition(t2)
            
            self.add_arc(t1, p)
            self.add_arc(t2, p)
            self.add_arc(p, self._connecting_t)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_nor(self, event):
        try:
            self.delete('selection')
            self.delete('connecting_arc')
            
            p = OrPlace('OR', self._last_point)
            t1 = AndTransition('or_t1', p.position + Vec2(-80, -50))
            t2 = AndTransition('or_t2', p.position + Vec2(-80, 50))
            self.add_place(p)
            self.add_transition(t1)
            self.add_transition(t2)
            
            self.add_arc(t1, p)
            self.add_arc(t2, p)
            self.add_arc(p, self._connecting_t, 0)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_nand(self, event):
        try:
            self.delete('selection')
            self.delete('connecting_arc')
            
            p = OrPlace('NAND', self._last_point)
            t = AndTransition('nand_t', p.position + Vec2(-80, 0))
            self.add_place(p)
            self.add_transition(t)
            
            self.add_arc(t, p)
            self.add_arc(p, self._connecting_t, 0)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_transition(self, event):
        try:
            self.delete('selection')
            self.delete('connecting_arc')
            
            p = self._connecting_p
            t_position = Vec2(event.x, event.y)
            
            t = AndTransition('AndT{0}'.format(self._petri_net._transition_counter + 1), t_position)
            
            self.add_transition(t)
            self.add_arc(t, p)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _finish_adding_command(self, event):
        try:
            self._create_place(CommandPlace, afterFunction = self._add_simple_place_arc, afterCancelFunction = self._cancel_create_place)
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _add_task_arc(self, p):
        self.delete('selection')
        self.delete('connecting_arc')
        
        t = SequenceTransition('SeqT{0}'.format(self._petri_net._transition_counter + 1), p.position + Vec2(100, 0))
        self.add_transition(t)
        self.add_arc(p, t)
        self.add_arc(self._connecting_t, p)
    
    def _add_fact_precondition_arc(self, p):
        self.delete('selection')
        self.delete('connecting_arc')
        self.add_arc(p, self._connecting_t)
        self.add_arc(self._connecting_t, p)
    
    def _add_negated_fact_arc(self, p):
        self.delete('selection')
        self.delete('connecting_arc')
        self.add_arc(p, self._connecting_t, 0)
    
    def _add_simple_place_arc(self, p):
        self.delete('selection')
        self.delete('connecting_arc')
        self.add_arc(self._connecting_t, p)
    
    def _cancel_create_place(self):
        self.delete('selection')
        self.delete('connecting_arc')

class DecompositionPNEditor(RulePNEditor):
    
    PetriNetClass = DecompositionPN
    
    def __init__(self, parent, *args, **kwargs):
        
        kwargs['is_primitive_task'] = False
        
        RulePNEditor.__init__(self, parent, *args, **kwargs)
    
    def _configure_menus(self):
        RulePNEditor._configure_menus(self)
        
        self._menus_dict[PreconditionsTransition.__name__] = ['preconditions_operations', 'fact_operations', 'task_operations', 'generic_transition_properties', 'generic_transition_connections']  # @UndefinedVariable
    
class CancelationPNEditor(RulePNEditor):
    
    PetriNetClass = CancelationPN
    
    def _configure_menus(self):
        RulePNEditor._configure_menus(self)
        
        self._menus_options_sets_dict['task_status_operations'] = [
                                                             ('Make Successful', self._make_successful),
                                                             ('Make Failed', self._make_failed)
                                                        ]
        self._menus_options_sets_dict['task_status_effect_operations'] = [
                                                                          ('Add Successful Place', self._add_successful),
                                                                          ('Add Failed Place', self._add_failed)
                                                                        ]
        self._menus_dict[RuleTransition.__name__] = ['preconditions_operations', 'fact_operations', 'task_operations', 'command_operations', 'task_status_effect_operations', 'generic_transition_properties', 'generic_transition_connections']  # @UndefinedVariable
        self._menus_dict[TaskStatusPlace.__name__] = ['task_status_operations']  # @UndefinedVariable
    
    
    def _left_click_handlers(self, event):
        
        if RulePNEditor._left_click_handlers(self, event):
            return True
        
        #Call other left_click handlers
        
        if self._state == 'adding_task_status':
            self._finish_adding_task_status(event)
            return True
    
    def _add_successful(self):
        self._add_task_status(True)
    
    def _add_failed(self):
        self._add_task_status(False)
    
    def _add_task_status(self, is_successful):
        self._state = 'adding_task_status'
        self.grab_set()
        self._anchor_set = True
        self._anchor_tag = 'selection'
        
        #Create drawing of place
        p_position = self._last_point
        place_id = self._draw_place_item(p_position, TaskStatusPlace)
        self.addtag_withtag('selection', place_id)
        
        transition_id = self._get_transition_id(self._last_clicked_id)
        
        self._connecting_t = self._petri_net.transitions[transition_id]
        self._is_successful = is_successful
        
        self._adding_node_fn_id = self.bind('<Motion>', self._dragCallback, '+')
        self._connecting_node_fn_id = self.bind('<Motion>', self._connecting_transition_to_place, '+')
    
    def _finish_adding_task_status(self, event):
        try:
            self._create_place(TaskStatusPlace, afterFunction = self._add_simple_place_arc, afterCancelFunction = self._cancel_create_place)
            
            pos = Vec2(event.x, event.y)
            
            status = 'failed'
            if self._is_successful:
                status = 'successful'
            p = TaskStatusPlace('task_status(' + status + ')', pos)
            self.add_place(p)
            self.add_arc(self._connecting_t, p)
            
        except Exception as e:
            tkMessageBox.showerror('Creation Error', str(e))
        finally:
            self.unbind('<Motion>', self._connecting_node_fn_id)
            self.unbind('<Motion>', self._adding_node_fn_id)
    
    def _make_successful(self):
        self._change_task_status('successful')
    
    def _make_failed(self):
        self._change_task_status('failed')
    
    def _change_task_status(self, status):
        
        place_id = self._get_place_id(self._last_clicked_id)
        p = self._petri_net.places[place_id]
        p.name = 'task_status(' + status + ')'
        self._draw_place(p)

class ExecutionPNEditor(CancelationPNEditor):
    
    PetriNetClass = ExecutionPN
    
    def __init__(self, parent, *args, **kwargs):
        
        kwargs['is_primitive_task'] = True
        
        CancelationPNEditor.__init__(self, parent, *args, **kwargs)

class FinalizationPNEditor(CancelationPNEditor):
    
    PetriNetClass = FinalizationPN
    
    def _configure_menus(self):
        CancelationPNEditor._configure_menus(self)
        
        self._menus_options_sets_dict['task_status_operations'].append(
                                                             ('Make Generic Task Status', self._make_generic_task_status)
                                                            )
        
        self._menus_dict[RuleTransition.__name__] = ['preconditions_operations', 'fact_operations', 'task_operations', 'generic_transition_properties', 'generic_transition_connections']  # @UndefinedVariable
    
    def _make_generic_task_status(self):
        self._change_task_status('?')