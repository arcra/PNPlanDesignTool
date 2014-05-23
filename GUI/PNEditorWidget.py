# -*- coding: utf-8 -*-
"""
@author: Adrián Revuelta Cuauhtli
"""

import re
import Tkinter
import tkMessageBox

from PetriNets import Place, PlaceTypes, Vec2, Transition, TransitionTypes, PetriNet

class PNEditor(Tkinter.Canvas):
    
    """
    Tk widget for editing Petri Net diagrams.
    
    Subclass of the Tkinter.Canvas Widget class. Handles several GUI interactions
    and provides some basic API methods to edit the Petri Net without the GUI events.
    """
    
    _GRID_SIZE = 100
    _GRID_SIZE_FACTOR = 3
    _LINE_WIDTH = 2.0
    
    _MARKING_REGEX = re.compile('^[0-9][1-9]*$')
    _TOKEN_RADIUS = 3
    
    _PLACE_RADIUS = 25
    _PLACE_LABEL_PADDING = _PLACE_RADIUS + 10
    
    _PLACE_CONFIG = {PlaceTypes.ACTION: {
                                   'prefix' : 'a',
                                   'fill': '#00CC00',
                                   'outline': '#008800',
                                   'regex': re.compile('^a\.[A-Za-z][A-Za-z0-9_-]*$')
                                   },
                     PlaceTypes.PREDICATE: {
                                      'prefix' : 'p',
                                       'fill': '#0000CC',
                                       'outline': '#000088',
                                       'regex': re.compile('^p\.[A-Za-z][A-Za-z0-9_-]*$')
                                      },
                     PlaceTypes.TASK: {
                                      'prefix' : 't',
                                       'fill': '#CCCC00',
                                       'outline': '#888800',
                                       'regex': re.compile('^t\.[A-Za-z][A-Za-z0-9_-]*$')
                                      },
                     PlaceTypes.GENERIC: {
                                      'prefix' : 'g',
                                       'fill': 'white',
                                       'outline': '#777777'
                                      }
               }
    
    _TRANSITION_HALF_LARGE = 40
    _TRANSITION_HALF_SMALL = 7.5
    _TRANSITION_HORIZONTAL_LABEL_PADDING = _TRANSITION_HALF_SMALL + 10
    _TRANSITION_VERTICAL_LABEL_PADDING = _TRANSITION_HALF_LARGE + 10
    
    '''
    _IMMEDIATE_TRANSITION_FILL = 
    _IMMEDIATE_TRANSITION_OUTLINE = 
    _IMMEDIATE_TRANSITION_REGEX = 
    
    _STOCHASTIC_TRANSITION_FILL = 
    _STOCHASTIC_TRANSITION_OUTLINE = 
    _STOCHASTIC_TRANSITION_REGEX = 
    '''
    
    _TRANSITION_CONFIG = {
                          TransitionTypes.IMMEDIATE: {
                                   'prefix' : 'i',
                                   'fill': '#888888',
                                   'outline': '#888888',
                                   'regex': re.compile('^i\.[A-Za-z][A-Za-z0-9_-]*$')
                                   },
                          TransitionTypes.TIMED_STOCHASTIC: {
                                   'prefix' : 'i',
                                   'fill': '#FFFFFF',
                                   'outline': '#888888',
                                   'regex': re.compile('^s\.[A-Za-z][A-Za-z0-9_-]*$')
                                   }
                          }
    
    def __init__(self, parent, *args, **kwargs):
        """
        PNEditor Class' constructor.
        
        Besides the usual Canvas parameters, it should receive at least either
        a Petri Net object or a name for the new Petri Net to be created.
        
        Keyword Arguments:
        PetriNet -- Petri Net object to load for viewing/editing.
        name -- In case no Petri Net object is specified, a name must be
                specified for the new Petri Net to be created.
        grid -- (Default True) Boolean that specifies whether to draw a square grid.
        """
        
        if not 'bg' in kwargs:
            kwargs['bg'] = 'white'
            
        self._grid = kwargs.pop('grid', True)
        self._petri_net = kwargs.pop('PetriNet', None)
        petri_net_name = kwargs.pop('name', None)
        
        if not (petri_net_name or self._petri_net):
            raise Exception('Either a PetriNet object or a name must be passed to the Petri Net Editor.')
        
        if not self._petri_net:
            self._petri_net = PetriNet(petri_net_name)
        
        Tkinter.Canvas.__init__(self, *args, **kwargs)
        
        self._canvas_menu = Tkinter.Menu(self, tearoff = 0)
        self._canvas_menu.add_command(label = 'Add Action Place', command = self._create_action_place)
        self._canvas_menu.add_command(label = 'Add Predicate Place', command = self._create_predicate_place)
        self._canvas_menu.add_command(label = 'Add Task Place', command = self._create_task_place)
        self._canvas_menu.add_separator()
        self._canvas_menu.add_command(label = 'Add Immediate Transition', command = self._create_immediate_transition)
        self._canvas_menu.add_command(label = 'Add Stochastic Transition', command = self._create_stochastic_transition)
        
        self._place_menu = Tkinter.Menu(self, tearoff = 0)
        self._place_menu.add_command(label = 'Rename Place', command = self._rename_place)
        self._place_menu.add_command(label = 'Set Initial Marking', command = self._set_initial_marking)
        self._place_menu.add_separator()
        self._place_menu.add_command(label = 'Remove Place', command = self._remove_place)
        self._place_menu.add_separator()
        self._place_menu.add_command(label = 'Connect to...')
        
        self._transition_menu = Tkinter.Menu(self, tearoff = 0)
        self._transition_menu.add_command(label = 'Rename Transition')
        self._transition_menu.add_command(label = 'Switch orientation', command = self._switch_orientation)
        self._transition_menu.add_separator()
        self._transition_menu.add_command(label = 'Remove Transition', command = self._remove_transition)
        self._transition_menu.add_separator()
        self._transition_menu.add_command(label = 'Connect to...')
        
        
        self._place_count = 0
        self._transition_count = 0
        
        self._last_point = Vec2()
        
        self._anchor_tag = 'all'
        self._anchor_set = False
        
        self._popped_up_menu = None
        
        self._current_grid_size = PNEditor._GRID_SIZE
        
        self._draw_petri_net()
        
        ################################
        #        EVENT BINDINGs
        ################################
        self.bind('<Button-1>', self._set_anchor)
        self.bind('<B1-Motion>', self._dragCallback)
        self.bind('<ButtonRelease-1>', self._change_cursor_back)
        #Windows and MAC OS:
        self.bind('<MouseWheel>', self._scale_canvas)
        #UNIX/Linux:
        self.bind('<Button-4>', self._scale_up)
        self.bind('<Button-5>', self._scale_down)
        
        self.bind('<KeyPress-c>', self._center_diagram)
        
        #MAC OS:
        if (self.tk.call('tk', 'windowingsystem')=='aqua'):
            self.bind('<2>', self._popup_menu)
            self.bind('<Control-1>', self._popup_menu)
        #Windows / UNIX / Linux:
        else:
            self.bind('<3>', self._popup_menu)
    
    @property
    def petri_net(self):
        return self._petri_net
    
    def set_petri_net(self, newPN):
        """Loads a new Petri Net object to be viewed/edited."""
        
        '''
        #TODO (Possibly):
        Check PetriNet saved attribute, before changing the Petri Net
        or destroying the widget.
        '''
        
        self._petri_net = newPN
        self._draw_petri_net()
    
    def add_place(self, p, overwrite = False):
        """Adds a place to the Petri Net and draws it.
        
        Note that it uses the PetriNet Class' instance method
        for adding the place and so it will remove any arc information
        it contains for the sake of maintaining consistency. 
        """
        
        if self._petri_net.add_place(p, overwrite):
            self._draw_place(p)
    
    def remove_place(self, p):
        """Removes the place from the Petri Net.
        
        p should be either a Place object, or
        a string representation of a place [i. e. str(place_object)]
        """
        
        p = self._petri_net.remove_place(p)
        
        self.delete('place_' + str(p))
        self.delete('source_' + str(p))
        self.delete('target_' + str(p))
        
    
    def add_transition(self, t, overwrite = False):
        """Adds a transition to the Petri Net and draws it.
        
        Note that it uses the PetriNet Class' instance method
        for adding the transition and so it will remove any arc information
        it contains for the sake of maintaining consistency.
        """
        
        if self._petri_net.add_transition(t, overwrite):
            self._draw_transition(t)
    
    def remove_transition(self, t):
        """Removes the transition from the Petri Net.
        
        t should be either a Transition object, or
        a string representation of a transition [i. e. str(transition_object)]
        """
        
        t = self._petri_net.remove_transition(t)
        
        self.delete('transition_' + str(t))
        self.delete('source_' + str(t))
        self.delete('target_' + str(t))
    
    def add_arc(self, source, target, weight = 1):
        self._petri_net.add_arc(source, target, weight)
        self._draw_arc(source, target, weight)
    
    def _draw_petri_net(self):
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
        minx = 1000000000
        maxx = -1000000000
        miny = 1000000000
        maxy = -1000000000
        
        padding = PNEditor._TRANSITION_HALF_LARGE * 2 * self._current_scale
        
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
        canvas_width = int(self.config()['width'][4])
        canvas_height = int(self.config()['height'][4])
        
        #canvas might not be squared:
        w_ratio = canvas_width/w
        h_ratio = canvas_height/h
        if w_ratio < h_ratio:
            #scale horizontally, center vertically
            scale_factor = w_ratio
            offset = Vec2(-minx, -miny + (canvas_height - h*w_ratio)/2)
        else:
            #scale vertically, center horizontally
            scale_factor = h_ratio
            offset = Vec2(-minx + (canvas_width - w*h_ratio)/2, -miny)
        
        for p in self._petri_net.places.itervalues():
            p.position = (p.position + offset)*scale_factor
        
        for t in self._petri_net.transitions.itervalues():
            t.position = (t.position + offset)*scale_factor
        
        self._current_scale *= scale_factor
        self._petri_net.scale = self._current_scale
        
        self._draw_petri_net()
    
    def _draw_grid(self):
        
        self.delete('grid')
        
        if not self._grid:
            return
        
        if self._current_grid_size * self._current_scale <= PNEditor._GRID_SIZE / PNEditor._GRID_SIZE_FACTOR:
            self._current_grid_size = self._current_grid_size * PNEditor._GRID_SIZE_FACTOR
        
        if self._current_grid_size / PNEditor._GRID_SIZE_FACTOR * self._current_scale >= PNEditor._GRID_SIZE:
            self._current_grid_size = int(self._current_grid_size / PNEditor._GRID_SIZE_FACTOR)
        
        conf = self.config()
        width = int(conf['width'][4])
        height = int(conf['height'][4])
        
        startx = int(self._grid_offset.x - self._current_grid_size * self._current_scale)
        step = int(self._current_grid_size * self._current_scale / PNEditor._GRID_SIZE_FACTOR)
        
        for x in xrange(startx, width, step):
            self.create_line(x, 0, x, height, fill = '#BBBBFF', tags='grid')
        
        starty = int(self._grid_offset.y - self._current_grid_size * self._current_scale)
        for y in xrange(starty, height, step):
            self.create_line(0, y, width, y, fill = '#BBBBFF', tags='grid')
        
        step *= PNEditor._GRID_SIZE_FACTOR
        
        for x in xrange(startx, width, step):
            self.create_line(x, 0, x, height, fill = '#7777FF', width = 1.4, tags='grid')
        
        for y in xrange(starty, height, step):
            self.create_line(0, y, width, y, fill = '#7777FF', width = 1.4, tags='grid')
            
        self.tag_lower('grid')
    
    def _adjust_grid_offset(self):
        currentGridSize = int(self._current_grid_size * self._current_scale)
        while self._grid_offset.x < 0:
            self._grid_offset.x += currentGridSize
        while self._grid_offset.x > currentGridSize:
            self._grid_offset.x -= currentGridSize
            
        while self._grid_offset.y < 0:
            self._grid_offset.y += currentGridSize
        while self._grid_offset.y > currentGridSize:
            self._grid_offset.y -= currentGridSize
    
    def _draw_all_arcs(self):
        
        self.delete('arc')
        
        for p in self._petri_net.places.itervalues():
            target = p
            for arc in p.incoming_arcs.iterkeys():
                source = self._petri_net.transitions[arc]
                self._draw_arc(source, target)
            source = p
            for arc in p.outgoing_arcs.iterkeys():
                target = self._petri_net.transitions[arc]
                self._draw_arc(source, target)
    
    def _draw_item_arcs(self, obj):
        
        arc_dict = self._petri_net.transitions
        if isinstance(obj, Transition):
            arc_dict = self._petri_net.places
        
        self.delete('source_' + str(obj))
        self.delete('target_' + str(obj))
        target = obj
        for arc in obj.incoming_arcs.iterkeys():
            source = arc_dict[arc]
            self._draw_arc(source, target)
        source = obj
        for arc in obj.outgoing_arcs.iterkeys():
            target = arc_dict[arc]
            self._draw_arc(source, target)
    
    def _draw_place(self, p):
        
        place_id = self._draw_generic_place(place = p)
        self._draw_marking(place_id, p)
        self.create_text(p.position.x,
                       p.position.y + PNEditor._PLACE_LABEL_PADDING*self._current_scale,
                       tags = ('label', 'place_' + str(p)) + self.gettags(place_id),
                       text = str(p)
                       )
        
        return place_id
    
    def _remove_place(self):
        tags = self.gettags(self._last_clicked)
        
        if 'place' not in tags:
            return
        
        for t in tags:
            if t[:6] == 'place_':
                name = t[6:]
                break
        
        self.remove_place(name)
    
    def _set_initial_marking(self):
        tags = self.gettags(self._last_clicked)
        
        if 'place' not in tags:
            return
        
        for t in tags:
            if t[:6] == 'place_':
                name = t[6:]
                break
        
        p = self._petri_net.places[name]
        
        self._set_marking_entry(self._last_clicked, p)
        
    def _set_marking_entry(self, canvas_id, p):
        
        txtbox = Tkinter.Entry(self)
        txtbox.insert(0, str(p.init_marking))
        txtbox.selection_range(0, Tkinter.END)
        txtbox_id = self.create_window(p.position.x, p.position.y, height= 20, width = 20, window = txtbox)
        txtbox.grab_set()
        txtbox.focus_set()
        
        callback = self._get_marking_callback(txtbox, txtbox_id, canvas_id, p)
        
        txtbox.bind('<KeyPress-Return>', callback)
    
    def _get_marking_callback(self, txtbox, txtbox_id, canvas_id, p):
        
        def txtboxCallback(event):
            txt = txtbox.get()
            if not PNEditor._MARKING_REGEX.match(txt):
                msg = ('Please input a positive integer number for the marking.')
                tkMessageBox.showerror('Invalid Marking', msg)
                return
            p.init_marking = int(txt)
            self._draw_marking(canvas_id, p)
            txtbox.destroy()
            self.delete(txtbox_id)
            
        return txtboxCallback
    
    def _draw_marking(self, canvas_id, p):
        
        tag = 'mark_' + str(p)
        
        self.delete(tag)
        
        if p.init_marking == 0:
            return
        tags = ('marking', tag) + self.gettags(canvas_id)
        if p.init_marking == 1:
            self.create_oval(p.position.x - PNEditor._TOKEN_RADIUS,
                             p.position.y - PNEditor._TOKEN_RADIUS,
                             p.position.x + PNEditor._TOKEN_RADIUS,
                             p.position.y + PNEditor._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black'
                             )
            self.scale(tag, p.position.x, p.position.y, self._current_scale, self._current_scale)
            return
        if p.init_marking == 2:
            self.create_oval(p.position.x - 3*PNEditor._TOKEN_RADIUS,
                             p.position.y - PNEditor._TOKEN_RADIUS,
                             p.position.x - PNEditor._TOKEN_RADIUS,
                             p.position.y + PNEditor._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black'
                             )
            self.create_oval(p.position.x + PNEditor._TOKEN_RADIUS,
                             p.position.y - PNEditor._TOKEN_RADIUS,
                             p.position.x + 3*PNEditor._TOKEN_RADIUS,
                             p.position.y + PNEditor._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black'
                             )
            self.scale(tag, p.position.x, p.position.y, self._current_scale, self._current_scale)
            return
        if p.init_marking == 3:
            self.create_oval(p.position.x + PNEditor._TOKEN_RADIUS,
                             p.position.y + PNEditor._TOKEN_RADIUS,
                             p.position.x + 3*PNEditor._TOKEN_RADIUS,
                             p.position.y + 3*PNEditor._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black'
                             )
            self.create_oval(p.position.x - 3*PNEditor._TOKEN_RADIUS,
                             p.position.y + PNEditor._TOKEN_RADIUS,
                             p.position.x - PNEditor._TOKEN_RADIUS,
                             p.position.y + 3*PNEditor._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black'
                             )
            self.create_oval(p.position.x - PNEditor._TOKEN_RADIUS,
                             p.position.y - 3*PNEditor._TOKEN_RADIUS,
                             p.position.x + PNEditor._TOKEN_RADIUS,
                             p.position.y - PNEditor._TOKEN_RADIUS,
                             tags = tags,
                             fill = 'black'
                             )
            self.scale(tag, p.position.x, p.position.y, self._current_scale, self._current_scale)
            return
        self.create_text(p.position.x, p.position.y, text = str(p.init_marking), tags=tags)
    
    def _rename_place(self):
        pass
    
    def _create_action_place(self):
        
        placeType = PlaceTypes.ACTION
        self._create_place(placeType)
    
    def _create_predicate_place(self):
        
        placeType = PlaceTypes.PREDICATE
        self._create_place(placeType)
    
    def _create_task_place(self):
        
        placeType = PlaceTypes.TASK
        self._create_place(placeType)
        
    def _create_place(self, placeType):
        
        item = self._draw_generic_place(self._last_point, placeType)
        p = Place('p' + '%02d' % self._place_count, placeType, self._last_point)
        regex = PNEditor._PLACE_CONFIG[placeType]['regex']
        self._set_label_entry(item, regex, p)
    
    def _draw_generic_place(self, point = Vec2(), placeType = PlaceTypes.GENERIC, place = None):
        self._hide_menu()
        place_tag = ''
        if place:
            point = place.position
            place_tag = 'place_' + str(place)
            placeType = place.type
            
        
        item = self.create_oval(point.x - PNEditor._PLACE_RADIUS,
                         point.y - PNEditor._PLACE_RADIUS,
                         point.x + PNEditor._PLACE_RADIUS,
                         point.y + PNEditor._PLACE_RADIUS,
                         tags = ('place', placeType, place_tag),
                         width = PNEditor._LINE_WIDTH,
                         fill = PNEditor._PLACE_CONFIG[placeType]['fill'],
                         outline = PNEditor._PLACE_CONFIG[placeType]['outline'])
        self.addtag_withtag('p_' + str(item), item)
        self.scale(item, point.x, point.y, self._current_scale, self._current_scale)
        self._place_count += 1
        return item
    
    def _draw_transition(self, t):
        trans_id = self._draw_generic_transition(transition = t)
        
        if t.isHorizontal:
            padding = PNEditor._TRANSITION_HORIZONTAL_LABEL_PADDING
        else:
            padding = PNEditor._TRANSITION_VERTICAL_LABEL_PADDING
        
        self.create_text(t.position.x,
                       t.position.y + padding*self._current_scale,
                       tags = ('label', 'transition_' + str(t)) + self.gettags(trans_id),
                       text = str(t)
                       )
        
        return trans_id
    
    def _remove_transition(self):
        tags = self.gettags(self._last_clicked)
        
        if 'transition' not in tags:
            return
        
        for t in tags:
            if t[:11] == 'transition_':
                name = t[11:]
                break
        
        self.remove_transition(name)
    
    def _draw_generic_transition(self, point = Vec2(), transitionType = TransitionTypes.IMMEDIATE, transition = None):
        self._hide_menu()
        
        transition_tag = ''
        if transition:
            point = transition.position
            transition_tag = 'transition_' + str(transition)
            transitionType = transition.type
        
        x0 = point.x - PNEditor._TRANSITION_HALF_SMALL
        y0 = point.y - PNEditor._TRANSITION_HALF_LARGE
        x1 = point.x + PNEditor._TRANSITION_HALF_SMALL
        y1 = point.y + PNEditor._TRANSITION_HALF_LARGE
        
        if transition and transition.isHorizontal:
            x0 = point.x - PNEditor._TRANSITION_HALF_LARGE
            y0 = point.y - PNEditor._TRANSITION_HALF_SMALL
            x1 = point.x + PNEditor._TRANSITION_HALF_LARGE
            y1 = point.y + PNEditor._TRANSITION_HALF_SMALL
        
        item = self.create_rectangle(x0, y0, x1, y1,
                         tags = ('transition', transitionType, transition_tag),
                         width = PNEditor._LINE_WIDTH,
                         fill = PNEditor._TRANSITION_CONFIG[transitionType]['fill'],
                         outline = PNEditor._TRANSITION_CONFIG[transitionType]['outline']
                         )
        
        self.addtag_withtag('t_' + str(item), item)
        self.scale(item, point.x, point.y, self._current_scale, self._current_scale)
        self._transition_count += 1
        return item
    
    def _create_immediate_transition(self):
        
        transitionType = TransitionTypes.IMMEDIATE
        self._create_transition(self, transitionType)
    
    def _create_stochastic_transition(self):
        
        transitionType = TransitionTypes.TIMED_STOCHASTIC
        self._create_transition(self, transitionType)
    
    def _create_transition(self, transitionType):
        item = self._draw_generic_transition(self._last_point, transitionType)
        t = Transition('t' + '%02d' % self._transition_count, transitionType, self._last_point)
        regex = PNEditor._TRANSITION_CONFIG[transitionType]['regex']
        self._set_label_entry(item, regex, t)
        
    def _switch_orientation(self):
        
        tags = self.gettags(self._last_clicked)
        
        if 'transition' not in tags:
            return
        
        for t in tags:
            if t[:11] == 'transition_':
                name = t[11:]
                break
        
        t = self._petri_net.transitions[name]
        t.isHorizontal = not t.isHorizontal
        
        self.delete('source_' + name)
        self.delete('target_' + name)
        self.delete('transition_' + name)
        
        self._draw_transition(t)
        self._draw_item_arcs(t)
        
        
        
    
    def _set_label_entry(self, canvas_id, regex, obj):
        
        txtbox = Tkinter.Entry(self)
        txtbox.insert(0, str(obj))
        txtbox.selection_range(2, Tkinter.END)
        #extra padding because entry position refers to the center, not the corner
        if isinstance(obj, Place):
            label_padding = PNEditor._PLACE_LABEL_PADDING + 10
        else:
            if obj.isHorizontal:
                label_padding = PNEditor._TRANSITION_HORIZONTAL_LABEL_PADDING + 10
            else:
                label_padding = PNEditor._TRANSITION_VERTICAL_LABEL_PADDING + 10
        
        txtbox_id = self.create_window(obj.position.x, obj.position.y + label_padding*self._current_scale, height= 20, width = 60, window = txtbox)
        txtbox.grab_set()
        txtbox.focus_set()
        
        callback = self._get_txtbox_callback(txtbox, txtbox_id, canvas_id, regex, obj)
        
        txtbox.bind('<KeyPress-Return>', callback)
    
    def _get_txtbox_callback(self, txtbox, txtbox_id, canvas_id, regex, obj):
        
        isPlace = isinstance(obj, Place)
        def txtboxCallback(event):
            txt = txtbox.get()
            if not regex.match(txt):
                if isPlace:
                    msg = ('A place name must begin with the first letter of its type and a dot, ' +
                    'followed by an alphabetic character and then any number of ' +
                    'alphanumeric characters, dashes or underscores. \
                     \
                    Examples: a.my_Action, t.task1')
                else:
                    msg = ("A transition name must begin with an 'i' and a dot if it's an immediate transition " +
                           "or an 's' and a dot if it's a timed_stochastic transition, " + 
                           "followed by an alphabetic character and then any number of " +
                           "alphanumeric characters, dashes or underscores. \
                           \
                           Example: i.transition1, s.t-2")
                tkMessageBox.showerror('Invalid Name', msg)
                return
            if isPlace:
                if txt in self._petri_net.places:
                    tkMessageBox.showerror('Duplicate name', 'A place of the same type with that name already exists in the Petri Net.')
                    return
            else:
                if txt in self._petri_net.transitions:
                    tkMessageBox.showerror('Duplicate name', 'A transition with that name already exists in the Petri Net.')
                    return
            newObj = obj.__class__(txt[2:], obj.type, obj.position)
            if isPlace:
                label_padding = PNEditor._PLACE_LABEL_PADDING
                if not self._petri_net.add_place(newObj):
                    tkMessageBox.showerror('Insertion failed', 'Failed to add place to the Petri Net.')
                    return
                self.addtag_withtag('place_' + str(newObj), canvas_id)
            else:
                if obj.isHorizontal:
                    label_padding = PNEditor._TRANSITION_HORIZONTAL_LABEL_PADDING
                else:
                    label_padding = PNEditor._TRANSITION_VERTICAL_LABEL_PADDING
                if not self._petri_net.add_transition(newObj):
                    tkMessageBox.showerror('Insertion failed', 'Failed to add transition to the Petri Net.')
                    return
                self.addtag_withtag('transition_' + str(newObj), canvas_id)
            tags = ('label', 'lbl_' + str(newObj)) + self.gettags(canvas_id)
            self.create_text(newObj.position.x,
                             newObj.position.y + label_padding*self._current_scale,
                             text = str(newObj),
                             tags=tags
                             )
            txtbox.destroy()
            self.delete(txtbox_id)
        return txtboxCallback
    
    def _draw_arc(self, source, target, weight = 1):
        
        if isinstance(source, Place):
            p = source
            t = target
        else:
            p = target
            t = source
        
        place_vec = t.position - p.position
        trans_vec = -place_vec
        place_point = p.position + place_vec.unit*PNEditor._PLACE_RADIUS*self._current_scale
        transition_point = self._find_intersection(t, trans_vec)
        
        if isinstance(source, Place):
            src_point = place_point
            trgt_point = transition_point
        else:
            src_point = transition_point
            trgt_point = place_point
        
        tags = ('arc', 'source_' + str(source), 'target_' + str(target))
        
        self.create_line(src_point.x,
                         src_point.y,
                         trgt_point.x,
                         trgt_point.y,
                         tags = tags,
                         width = PNEditor._LINE_WIDTH,
                         arrow= Tkinter.LAST,
                         arrowshape = (10,12,5)
                         )
        
        
    def _find_intersection(self, t, vec):
        #NOTE: vec is a vector from the transition's center
        
        if t.isHorizontal:
            half_width = PNEditor._TRANSITION_HALF_LARGE
            half_height = PNEditor._TRANSITION_HALF_SMALL
        else:
            half_width = PNEditor._TRANSITION_HALF_SMALL
            half_height = PNEditor._TRANSITION_HALF_LARGE
        
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
    
    def _popup_menu(self, event):
        
        ids = self.find_withtag('current')
        
        self._last_point = Vec2(event.x, event.y)
        self._popped_up_menu = self._canvas_menu
        if len(ids) > 0:
            tags = self.gettags(ids[0])
            self._last_clicked = ids[0]
            if 'place' in tags:
                self._popped_up_menu = self._place_menu
            elif 'transition' in tags:
                self._popped_up_menu = self._transition_menu
        
        self._popped_up_menu.post(event.x_root, event.y_root)
    
    def _hide_menu(self):
        if self._popped_up_menu:
            self._popped_up_menu.unpost()
            self._popped_up_menu = None
            return True
        return False
    
    def _scale_up(self, event):
        e = Vec2(event.x, event.y)
        scale_factor = 1.11111111
        self.scale('all', e.x, e.y, scale_factor, scale_factor)
        self._current_scale = round(self._current_scale * scale_factor, 8)
        self._petri_net.scale = self._current_scale
        for p in self._petri_net.places.itervalues():
            p.position = e + (p.position - e)*scale_factor
        for t in self._petri_net.transitions.itervalues():
            t.position = e + (t.position - e)*scale_factor
        self._draw_all_arcs()
        if self._grid:
            self._grid_offset = (e + (self._grid_offset - e)*scale_factor).int
            self._adjust_grid_offset()
            self._draw_grid()
    
    def _scale_down(self, event):
        e = Vec2(event.x, event.y)
        scale_factor = 0.9
        self.scale('all', e.x, e.y, scale_factor, scale_factor)
        self._current_scale = round(self._current_scale * scale_factor, 8)
        self._petri_net.scale = self._current_scale
        for p in self._petri_net.places.itervalues():
            p.position = e + (p.position - e)*scale_factor
        for t in self._petri_net.transitions.itervalues():
            t.position = e + (t.position - e)*scale_factor
        self._draw_all_arcs()
        if self._grid:
            self._grid_offset = (e + (self._grid_offset - e)*scale_factor).int
            self._adjust_grid_offset()
            self._draw_grid()
    
    def _scale_canvas(self, event):
        if event.delta > 0:
            self._scale_up(event)
        else:
            self._scale_down(event)
    
    def _set_anchor(self, event):
        
        self.focus_set()
        
        if self._hide_menu():
            return
        
        self._anchor_tag = 'all';
        currentTags = self.gettags('current')
        if 'place' in currentTags:
            for t in currentTags:
                if t[:2] == 'p_':
                    self._anchor_tag = t
                    break
        elif 'transition' in currentTags:
            for t in currentTags:
                if t[:2] == 't_':
                    self._anchor_tag = t
                    break
        self._last_point = Vec2(event.x, event.y)
        self._anchor_set = True
        self.config(cursor = 'fleur')
    
    def _dragCallback(self, event):
        if not self._anchor_set:
            return
        
        e = Vec2(event.x, event.y)
        
        dif = e - self._last_point
        self.move(self._anchor_tag, dif.x, dif.y)
        
        if self._anchor_tag != 'all':
            name = ''
            item_dict = self._petri_net.places
            item = self.find_withtag(self._anchor_tag)[0]
            for t in self.gettags(item):
                if t[:6] == 'place_':
                    name = t[6:]
                    break
                elif t[:11] == 'transition_':
                    name = t[11:]
                    item_dict = self._petri_net.transitions
                    break
            if name != '':
                item_dict[name].position += dif #/self._current_scale
                self._draw_item_arcs(item_dict[name])
        
        if self._anchor_tag == 'all':
            self._draw_all_arcs()
            for p in self._petri_net.places.itervalues():
                p.position += dif
            for t in self._petri_net.transitions.itervalues():
                t.position += dif
            if self._grid:
                self._grid_offset = (self._grid_offset + dif).int
                self._adjust_grid_offset()
                self._draw_grid()
                
        self._set_anchor(event)
        
        
    def _change_cursor_back(self, event):
        self.config(cursor = 'arrow')
        self._anchor_set = False