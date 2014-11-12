# -*- coding: utf-8 -*-
'''
@author: Adrián Revuelta Cuauhtli
'''

import sys
import os
import tkMessageBox
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import Tkinter as tk
import ttk
import tkFileDialog
import tkFont

import zipfile
import tempfile

from PetriNets import PetriNet, PetriNetTypes
from GUI.TabManager import TabManager
from GUI.PNEditor import PNEditor
from GUI.AuxDialogs import InputDialog

class PNPDT(object):
    
    WORKSPACE_WIDTH = 600
    WORKSPACE_HEIGHT = 600
    
    EXPLORER_WIDTH = 250
    
    def __init__(self):
        super(PNPDT, self).__init__()
        
        self.root = tk.Tk()
        self.root.wm_title('PNPlanDesignTool')
        self.root.protocol("WM_DELETE_WINDOW", self.exit)
        #Necessary in order for the children to expand to the real size of the window if resized:
        self.root.rowconfigure(1, weight = 1)
        self.root.columnconfigure(2, weight = 1)
        
        toolbar_frame = tk.Frame(self.root)
        toolbar_frame.grid(row = 0, column = 2, sticky = tk.E)
        
        '''
        mode_label = tk.Label(toolbar_frame, text = 'mode: ')
        mode_label.grid(row = 0, column = 0, sticky = tk.E)
        
        self.mode_var = tk.StringVar()
        mode_combo = ttk.Combobox(toolbar_frame,
                                  values = ['Editor', 'Simulation', 'Execution'],
                                  textvariable = self.mode_var,
                                  state = 'readonly')
        self.mode_var.set('Editor')
        mode_combo.grid(row = 0, column = 1, sticky = tk.E)
        '''
        
        project_frame = tk.Frame(self.root, width = PNPDT.EXPLORER_WIDTH)
        project_frame.grid(row = 1, column = 0, sticky = tk.NSEW)
        project_frame.rowconfigure(0, weight = 1)
        
        sep = ttk.Separator(self.root, orient = tk.VERTICAL)
        sep.grid(row = 1, column = 1, sticky = tk.NS)
        
        workspace_frame = tk.Frame(self.root, width = PNPDT.WORKSPACE_WIDTH, height = PNPDT.WORKSPACE_HEIGHT)
        workspace_frame.grid(row = 1, column = 2, sticky = tk.NSEW)
        #Necessary in order for the children to expand to the real size of the window if resized:
        workspace_frame.rowconfigure(0, weight = 1)
        workspace_frame.columnconfigure(0, weight = 1)
        
        self.status_bar = tk.Frame(self.root, height = 20)
        self.status_bar.grid(row = 2, columnspan=3, sticky = tk.EW)
        
        self.status_var = tk.StringVar()
        self.status_var.set('Ready.')
        
        self.status_label = tk.Label(self.status_bar, textvariable = self.status_var)
        self.status_label.grid(row = 0, column = 0, sticky = tk.EW)
        
        self.project_tree = ttk.Treeview(project_frame, height = int((PNPDT.WORKSPACE_HEIGHT - 20)/20), selectmode = 'browse')
        self.project_tree.heading('#0', text='Project Explorer', anchor=tk.W)
        self.project_tree.grid(row = 0, column = 0, sticky = tk.NSEW)
        
        #ysb = ttk.Scrollbar(project_frame, orient='vertical', command=self.project_tree.yview)
        xsb = ttk.Scrollbar(project_frame, orient='horizontal', command=self.project_tree.xview)
        self.project_tree.configure(xscroll = xsb.set)#, yscroll = ysb.set)
        #ysb.grid(row = 0, column = 1, sticky = tk.NS)
        xsb.grid(row = 1, column = 0, sticky = tk.EW)
        
        self.folder_img = tk.PhotoImage('folder_img', file = os.path.join(os.path.dirname(__file__), 'GUI', 'img', 'TreeView_Folder.gif'))
        self.petri_net_img = tk.PhotoImage('petri_net_img', file = os.path.join(os.path.dirname(__file__), 'GUI', 'img', 'doc.gif'))
        self.project_tree.tag_configure('folder', image = self.folder_img)
        self.project_tree.tag_configure('petri_net', image = self.petri_net_img)
        
        
        self.project_tree.insert('', 'end', 'Primitive_Actions/', text = 'Primitive Actions/', tags = ['folder', 'primitive_action', 'top_level'], open = True)
        self.project_tree.insert('', 'end', 'Non_Primitive_Actions/', text = 'Non-Primitive Actions/', tags = ['folder', 'non_primitive_action', 'top_level'], open = True)
        
        self.tab_manager = TabManager(workspace_frame,
                                     width = PNPDT.WORKSPACE_WIDTH,
                                     height = PNPDT.WORKSPACE_HEIGHT)
        self.tab_manager.grid(row = 0, column = 0, sticky = tk.NSEW)
        
        self.tab_manager.bind('<<NotebookTabChanged>>', self._set_string_var)
        
        menubar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menubar, tearoff = False)
        file_menu.add_command(label = 'Open', command = self.open)
        file_menu.add_command(label="Save", command = self.save, accelerator = 'Ctrl+s')
        file_menu.add_command(label="Save As...", command = self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command = self.exit, accelerator = 'Ctrl+q', foreground = 'red', activeforeground = 'white', activebackground = 'red')
        
        menubar.add_cascade(label = 'File', menu = file_menu)
        
        self.root.config(menu = menubar)
        
        self.popped_up_menu = None
        self.petri_nets = {}
        self.file_path = None
        
        self.task_folder_menu = tk.Menu(self.root, tearoff = 0)
        self.task_folder_menu.add_command(label = 'Add Task', command = self.create_task)
        self.task_folder_menu.add_command(label = 'Import Task', command = self.import_task)
        
        self.subfolder_menu = tk.Menu(self.root, tearoff = 0)
        self.subfolder_menu.add_command(label = 'Add Rule', command = self.create_petri_net)
        self.subfolder_menu.add_command(label = 'Import Rule from PNML file', command = self.import_from_PNML)
        
        self.petri_net_menu = tk.Menu(self.root, tearoff = 0)
        self.petri_net_menu.add_command(label = 'Open', command = self.open_petri_net)
        self.petri_net_menu.add_command(label = 'Rename', command = self.rename_petri_net)
        self.petri_net_menu.add_command(label = 'Delete', command = self.delete_petri_net)
        self.petri_net_menu.add_command(label = 'Export Task', command = self.export_to_PNML)
        
        #MAC OS:
        if (self.root.tk.call('tk', 'windowingsystem')=='aqua'):
            self.project_tree.tag_bind('top_level', '<2>', self.popup_task_folder_menu)
            self.project_tree.tag_bind('top_level', '<Control-1>', self.popup_task_folder_menu)
        #Windows / UNIX / Linux:
        else:
            self.project_tree.tag_bind('top_level', '<3>', self.popup_task_folder_menu)
        
        #MAC OS:
        if (self.root.tk.call('tk', 'windowingsystem')=='aqua'):
            self.project_tree.tag_bind('subfolder', '<2>', self.popup_subfolder_menu)
            self.project_tree.tag_bind('subfolder', '<Control-1>', self.popup_subfolder_menu)
        #Windows / UNIX / Linux:
        else:
            self.project_tree.tag_bind('subfolder', '<3>', self.popup_subfolder_menu)
            
        #MAC OS:
        if (self.root.tk.call('tk', 'windowingsystem')=='aqua'):
            self.project_tree.tag_bind('petri_net', '<2>', self.popup_petri_net_menu)
            self.project_tree.tag_bind('petri_net', '<Control-1>', self.popup_petri_net_menu)
        #Windows / UNIX / Linux:
        else:
            self.project_tree.tag_bind('petri_net', '<3>', self.popup_petri_net_menu)
        
        
        self.project_tree.tag_bind('petri_net', '<Double-1>', self.open_callback)
        self.root.bind('<Button-1>', self._hide_menu)
        self.root.bind('<Control-s>', self.save)
        self.root.bind('<Control-q>', self.exit)
    
    
    #######################################################
    #        TREE WIDGET, PNs AND TABS INTERACTIONS
    #######################################################
    def _set_string_var(self, event):
        try:
            tab_id = self.tab_manager.select()
            if not tab_id:
                return
        except:
            return
        
        pne = self.tab_manager.widget_dict[tab_id]
        self.status_label.configure(textvariable = pne.status_var)
        pne.focus_set()
    
    def popup_task_folder_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.task_folder_menu
        self.task_folder_menu.post(event.x_root, event.y_root)
    
    def popup_subfolder_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.subfolder_menu
        self.subfolder_menu.post(event.x_root, event.y_root)
    
    def popup_petri_net_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.petri_net_menu
        self.petri_net_menu.post(event.x_root, event.y_root)
    
    def _hide_menu(self, event):
        """Hides a popped-up menu."""
        if self.popped_up_menu:
            self.popped_up_menu.unpost()
            self.popped_up_menu = None
            return True
        return False
    
    def _adjust_width(self, text, item_id):
        
        font = tkFont.Font()
        measure = font.measure(text) + self._find_depth(item_id)*20
        current_width = self.project_tree.column('#0', 'minwidth')
        if measure > current_width:
            self.project_tree.column('#0', minwidth = measure, stretch = True)
            
    def _find_depth(self, item):
        
        count = 0
        while item != '':
            item = self.project_tree.parent(item)
            count += 1
        return count
    
    def _add_pne(self, item_id, **kwargs):
        
        open_tab = kwargs.pop('open_tab', True)
        pn = kwargs.pop('pn_object', None)
        pn_name = kwargs.pop('pn_name', None)
        pn_type = kwargs.pop('pn_type', None)
        task = kwargs.pop('task', None)
        
        if not ((pn_name and pn_type and task) or pn):
            raise Exception('Either a PetriNet object or a name and a type must be passed to the Petri Net Editor.') 
        
        if pn:
            pne = PNEditor(self.tab_manager, PetriNet = pn)
        else:
            pne = PNEditor(self.tab_manager, name = pn_name, pn_type = pn_type, task = task)
        self.petri_nets[item_id] = pne
        if open_tab:
            self.tab_manager.add(pne, text = pne.name)
            self.tab_manager.select(pne)
        return pne
    
    def create_task(self, name = None):
        
        if name is None:
            dialog = InputDialog('Task name',
                                 'Please input a Task name, preferably composed only of alphanumeric characters.',
                                 'Name',
                                 entry_length = 25)
            dialog.window.transient(self.root)
            self.root.wait_window(dialog.window)
            if not dialog.value_set:
                return
            name = dialog.input_var.get()
        
        item_id = self.clicked_element + name
        
        try:
            item_tags = ['task', 'folder', 'task_' + name]
            is_primitive_action = self.project_tree.tag_has('primitive_action', self.clicked_element)
            
            item_tags.append('primitive_action' if is_primitive_action else 'non_primitive_action')
            self.project_tree.insert(self.clicked_element, 'end', item_id, text = name, tags = item_tags, open = True)
            self._adjust_width(name, item_id)
            
            
            sub_tags = item_tags + ['subfolder']
            sub_tags.remove('task')
            
            sub_name = 'Executing rules/' if is_primitive_action else 'Decomposing rules/'
            sub_id = item_id + ('Executing_rules/' if is_primitive_action else 'Decomposing_Rules/')
            self.project_tree.insert(item_id, 'end', sub_id, text = sub_name, tags = sub_tags + ['dexec'])
            self._adjust_width(sub_name, sub_id)
            
            sub_name = 'Finalizing rules/'
            sub_id = item_id + 'Finalizing_rules/'
            self.project_tree.insert(item_id, 'end', sub_id, text = sub_name, tags = sub_tags + ['Finalizing'])
            self._adjust_width(sub_name, sub_id)
            
            sub_name = 'Canceling rules/'
            sub_id = item_id + 'Canceling_rules/'
            self.project_tree.insert(item_id, 'end', sub_id, text = sub_name, tags = sub_tags + ['canceling'])
            self._adjust_width(sub_name, sub_id)
            
        except Exception as e:
            tkMessageBox.showerror('ERROR', 'A Task could not be inserted in the selected node, possible duplicate name.\n\n' + str(e))
            return
    
    def create_petri_net(self):
        dialog = InputDialog('Rule name',
                             'Please input a rule name, preferably composed only of alphabetic characters, dashes and underscores.',
                             'Name',
                             entry_length = 25)
        dialog.window.transient(self.root)
        self.root.wait_window(dialog.window)
        if not dialog.value_set:
            return
        name = dialog.input_var.get()
        item_id = self.clicked_element + name
        
        item_tags = list(self.project_tree.item(self.clicked_element, "tags")) + ['petri_net']
        item_tags.remove('subfolder')
        item_tags.remove('folder')
        
        if self.project_tree.tag_has('dexec', self.clicked_element):
            if self.project_tree.tag_has('primitive_action', self.clicked_element):
                pn_type = PetriNetTypes.PRIMITIVE_TASK
            else:
                pn_type = PetriNetTypes.NON_PRIMITIVE_TASK
        elif self.project_tree.tag_has('finalizing', self.clicked_element):
            pn_type = PetriNetTypes.FINALIZING
        elif self.project_tree.tag_has('canceling', self.clicked_element):
            pn_type = PetriNetTypes.CANCELING
        
        try:
            self.project_tree.insert(self.clicked_element, 'end', item_id, text = name, tags = item_tags)
            self._adjust_width(name, item_id)
        except Exception as e:
            tkMessageBox.showerror('ERROR', 'The Petri Net could not be inserted in the selected node, possible duplicate name.\n\n' + str(e))
            return
        
        task = None
        for t in self.project_tree.item(self.clicked_element, "tags"):
            if t[:5] == 'task_':
                task = t[5:]
                break
        
        if not task:
            raise Exception('Task tag was not found!')
        
        self._add_pne(item_id, pn_name = name, pn_type = pn_type, task = task)
    
    def open_callback(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.open_petri_net()
    
    def open_petri_net(self):
        pne = self.petri_nets[self.clicked_element]
        try:
            self.tab_manager.add(pne, text = pne.name)
        except:
            pass
        
        self.tab_manager.select(pne)
    
    def import_task(self):
        
        zip_filename = tkFileDialog.askopenfilename(
                                              defaultextension = '.tsk',
                                              filetypes=[('PNPDT Task file', '*.tsk')],
                                              title = 'Open PNPDT Task file...',
                                              initialdir = os.path.expanduser('~/Desktop')
                                              )
        if not zip_filename:
            return
        
        zip_file = zipfile.ZipFile(zip_filename, 'r')
        
        
        tmp_dir = tempfile.mkdtemp()
        
        # Check file with task name
        # self.create_task(task_name)
        task_name = 'placebo'
        
        for x in [f for f in zip_file.infolist() if x[-4:] == '.tsk']:
            
            # Create content from files in each folder
            
            '''Check "open" function, in case any of that code is useful.
            
                file_path = os.path.join(tmp_dir, filename)
                f = open(file_path, 'w')
                data = zip_file.read(x)
                f.write(data)
                f.close()
                self._import_from_pnml(file_path, parent)
                os.remove(file_path)
            '''
            pass
        os.rmdir(tmp_dir)
        zip_file.close()
        
        self.status_var.set('Imported task: ' + task_name)
    
    def import_from_PNML(self):
        filename = tkFileDialog.askopenfilename(
                                              defaultextension = '.pnml',
                                              filetypes=[('Standard PNML file', '*.pnml'), ('Standard PNML file', '*.pnml.xml')],
                                              title = 'Open Standard PNML file...',
                                              initialdir = os.path.expanduser('~/Desktop')
                                              )
        if not filename:
            return
        
        item_id = self._import_from_pnml(filename, self.clicked_element)
        pne = self.petri_nets[item_id]
        self.tab_manager.add(pne, text = pne.name)
        self.tab_manager.select(pne)
        
    def _import_from_pnml(self, filename, parent):
        try:
            
            petri_nets = PetriNet.from_pnml_file(filename)
        except Exception as e:
            tkMessageBox.showerror('Error reading PNML file.', 'An error occurred while reading the PNML file.\n\n' + str(e))
            return
        
        if len(petri_nets) > 1:
            print 'warning: More than 1 petri net read, only 1 loaded.'
        
        try:
            pn = petri_nets[0]
        except Exception as e:
            tkMessageBox.showerror('Error loading PetriNet.', 'An error occurred while loading the PetriNet object.\n\n' + str(e))
        
        name = pn.name
        item_id = parent + name
        
        try:
            self.project_tree.insert(parent, 'end', item_id, text = name, tags = ['petri_net'])
            self._adjust_width(name, item_id)
        except Exception as e:
            tkMessageBox.showerror('ERROR', 'Petri Net could not be inserted in the selected node, possible duplicate name.\n\n' + str(e))
            return
        
        pne = self._add_pne(item_id, open_tab = False, pn_object = pn)
        pne.edited = False
        return item_id
    
    def rename_petri_net(self):
        old_name = self.project_tree.item(self.clicked_element, 'text')
        dialog = InputDialog('Petri Net name',
                             'Please input a Petri Net name, preferably composed only of alphabetic characters.',
                             'Name',
                             value = old_name,
                             entry_length = 25)
        dialog.window.transient(self.root)
        self.root.wait_window(dialog.window)
        if not dialog.value_set:
            return
        name = dialog.input_var.get()
        parent = self.project_tree.parent(self.clicked_element)
        
        self._move_petri_net(self.clicked_element, parent, parent, old_name, name)
    
    def _move_petri_net(self, old_id, old_parent, parent, old_name, name):
        item_id = parent + name
        pne = self.petri_nets.pop(old_id)
        try:
            self.project_tree.insert(parent, 'end', item_id, text = name, tags = ['petri_net'])
            self.project_tree.delete(old_id)
            self._adjust_width(name, item_id)
            pne.name = name
            self.petri_nets[item_id] = pne
        except Exception as e:
            tkMessageBox.showerror('ERROR', 'Item could not be inserted in the selected node, possible duplicate name.\n\nERROR: ' + str(e))
            try:
                self.project_tree.insert(old_parent, 'end', old_id, text = old_name, tags = ['petri_net'])
            except:
                pass
            self.petri_nets[old_id] = pne
            return
        
        try:
            self.tab_manager.tab(pne, text = pne.name)
        except:
            pass
    
    def delete_petri_net(self, item = None):
        if not item:
            item = self.clicked_element
        pne = self.petri_nets.pop(item, None)
        try:
            self.tab_manager.forget(pne)
        except:
            pass
        self.project_tree.delete(item)
    
    def export_to_PNML(self):
        filename = tkFileDialog.asksaveasfilename(
                                                  defaultextension = '.pnml',
                                                  filetypes=[('Standard PNML file', '*.pnml')],
                                                  title = 'Save as Standard PNML file...',
                                                  initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
                                                  initialfile = os.path.basename(self.clicked_element) + '.pnml'
                                                  )
        if not filename:
            return
        
        try:
            self.petri_nets[self.clicked_element].petri_net.to_pnml_file(filename)
        except Exception as e:
            tkMessageBox.showerror('Error saving PNML file.', 'An error occurred while saving the PNML file.\n\n' + str(e))
    
    #######################################################
    #                FILE MENU ACTIONS
    #######################################################
    def open(self):
        zip_filename = tkFileDialog.askopenfilename(
                                                  defaultextension = '.rpnp',
                                                  filetypes=[('Robotic Petri Net Plan file', '*.rpnp')],
                                                  title = 'Open RPNP file...',
                                                  initialdir = os.path.expanduser('~/Desktop')
                                                  )
        if not zip_filename:
            return
        
        items = self.project_tree.get_children('Actions/') \
        + self.project_tree.get_children('CommActions/') \
        + self.project_tree.get_children('Tasks/') \
        + self.project_tree.get_children('Environment/')
        
        for i in items:
            self.delete_petri_net(i)
        
        self.file_path = zip_filename
        
        zip_file = zipfile.ZipFile(self.file_path, 'r')
        tmp_dir = tempfile.mkdtemp()
        
        for x in zip_file.infolist():
            prev_sep = -1
            sep_index = x.filename.find('/', 0)
            while sep_index > -1:
                current_dir = x.filename[:sep_index + 1]
                parent = x.filename[:prev_sep + 1]
                if not self.project_tree.exists(current_dir):
                    name = current_dir[current_dir[:-1].rfind('/') + 1:]
                    self.project_tree.insert(parent, 'end', current_dir, text = name, tags = ['folder'], open = True)
                    self._adjust_width(name, current_dir)
                prev_sep = sep_index
                sep_index = x.filename.find('/', sep_index + 1)
            if x.filename[-5:] == '.pnml':
                last_sep = x.filename.rfind('/') + 1
                filename = x.filename[last_sep:]
                parent = x.filename[:last_sep]
                file_path = os.path.join(tmp_dir, filename)
                f = open(file_path, 'w')
                data = zip_file.read(x)
                f.write(data)
                f.close()
                self._import_from_pnml(file_path, parent)
                os.remove(file_path)
            
        os.rmdir(tmp_dir)
        zip_file.close()
        
        self.status_var.set('Opened: ' + self.file_path)
    
    def save(self, event = None):
        if not self.file_path:
            self.save_as()
            return
        
        try:
            zip_file = zipfile.ZipFile(self.file_path, "w")
        except:
            tkMessageBox.showerror('Error opening file.', 'A problem ocurred while opening a file for writing, make sure the file is not open by other program before saving.')
            return
        tmp_dir = tempfile.mkdtemp()
        
        folders = ('Actions/', 'CommActions/', 'Tasks/', 'Environment/')
        
        for f in folders:
            children = self.project_tree.get_children(f)
            if not children:
                file_path = os.path.join(tmp_dir, f)
                os.mkdir(file_path)
                zip_file.write(file_path, f)
                os.rmdir(file_path)
                continue
            for current in children:
                path = current + '.pnml'
                pne = self.petri_nets[current]
                file_name = os.path.basename(path)
                file_path = os.path.join(tmp_dir, file_name)
                pne._petri_net.to_pnml_file(file_path)
                zip_file.write(file_path, path)
                pne.edited = False
                os.remove(file_path)
        
        os.rmdir(tmp_dir)
        zip_file.close()
        
        try:
            tab_id = self.tab_manager.select()
            if not tab_id:
                raise Exception()
        except:
            self.status_label.configure(textvariable = self.status_var)
            self.status_var.set('File saved: ' + self.file_path)
            return
        
        pne = self.tab_manager.widget_dict[tab_id]
        pne.status_var.set('File saved: ' + self.file_path)
    
    def save_as(self):
        zip_filename = tkFileDialog.asksaveasfilename(
                                                  defaultextension = '.rpnp',
                                                  filetypes=[('Robotic Petri Net Plan file', '*.rpnp')],
                                                  title = 'Save as RPNP file...',
                                                  initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
                                                  initialfile = os.path.basename(self.file_path) if self.file_path is not None else ''
                                                  )
        if not zip_filename:
            return
        
        self.file_path = zip_filename
        
        self.save()
        
    
    def exit(self, event = None):
        
        edited = False
        for pne in self.petri_nets.itervalues():
            if pne.edited:
                edited = True
                break
        
        if edited:
            if not tkMessageBox.askokcancel('Exit without saving?', 'Are you sure you want to quit without saving any changes?', default = tkMessageBox.CANCEL):
                return
        
        self.root.destroy()

if __name__ == '__main__':
    w = PNPDT()
    
    tk.mainloop()
