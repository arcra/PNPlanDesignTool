# -*- coding: utf-8 -*-
'''
@author: Adrián Revuelta Cuauhtli
'''

import os

import Tkinter as tk
import ttk
import tkFileDialog
import tkFont
import tkMessageBox

import zipfile
import tempfile

from gui.tabmanager import TabManager
from gui.pneditors import NonPrimitiveTaskPNEditor,\
    PrimitiveTaskPNEditor, FinalizingPNEditor, RulePNEditor
from gui.auxdialogs import InputDialog
from nodes import FactPlace

class PNPDT(object):
    
    WORKSPACE_WIDTH = 600
    WORKSPACE_HEIGHT = 600
    
    EXPLORER_WIDTH = 400
    
    def __init__(self):
        super(PNPDT, self).__init__()
        
        self.root = tk.Tk()
        self.root.wm_title('PNPlanDesignTool')
        self.root.protocol("WM_DELETE_WINDOW", self.exit)
        #Necessary in order for the children to expand to the real size of the window if resized:
        self.root.rowconfigure(1, weight = 1)
        self.root.columnconfigure(0, weight = 1)
        self.root.columnconfigure(2, weight = 4)
        
        self.project_frame = tk.Frame(self.root, width = PNPDT.EXPLORER_WIDTH)
        self.project_frame.grid(row = 1, column = 0, sticky = tk.NSEW)
        self.project_frame.rowconfigure(0, weight = 1)
        self.project_frame.columnconfigure(0, weight = 1)
        
        sep = ttk.Separator(self.root, orient = tk.VERTICAL)
        sep.grid(row = 1, column = 1, sticky = tk.NS)
        
        self.workspace_frame = tk.Frame(self.root, width = PNPDT.WORKSPACE_WIDTH, height = PNPDT.WORKSPACE_HEIGHT)
        self.workspace_frame.grid(row = 1, column = 2, sticky = tk.NSEW)
        #Necessary in order for the children to expand to the real size of the window if resized:
        self.workspace_frame.rowconfigure(0, weight = 1)
        self.workspace_frame.columnconfigure(0, weight = 1)
        
        self.status_bar = tk.Frame(self.root, height = 20)
        self.status_bar.grid(row = 2, columnspan=3, sticky = tk.EW)
        
        self.status_var = tk.StringVar()
        self.status_var.set('Ready.')
        
        self.status_label = tk.Label(self.status_bar, textvariable = self.status_var)
        self.status_label.grid(row = 0, column = 0, sticky = tk.EW)
        
        self.project_tree = ttk.Treeview(self.project_frame, height = int((PNPDT.WORKSPACE_HEIGHT - 20)/20), selectmode = 'browse')
        self.project_tree.heading('#0', text='Project Explorer', anchor=tk.W)
        self.project_tree.grid(row = 0, column = 0, sticky = tk.NSEW)
        
        #ysb = ttk.Scrollbar(project_frame, orient='vertical', command=self.project_tree.yview)
        xsb = ttk.Scrollbar(self.project_frame, orient='horizontal', command=self.project_tree.xview)
        self.project_tree.configure(xscroll = xsb.set)#, yscroll = ysb.set)
        #ysb.grid(row = 0, column = 1, sticky = tk.NS)
        xsb.grid(row = 1, column = 0, sticky = tk.EW)
        
        self.folder_img = tk.PhotoImage('folder_img', file = os.path.join(os.path.dirname(__file__), 'gui', 'img', 'TreeView_Folder.gif'))
        self.petri_net_img = tk.PhotoImage('petri_net_img', file = os.path.join(os.path.dirname(__file__), 'gui', 'img', 'doc.gif'))
        self.project_tree.tag_configure('folder', image = self.folder_img)
        self.project_tree.tag_configure('petri_net', image = self.petri_net_img)
        
        
        self.project_tree.insert('', 'end', 'Primitive_Tasks/', text = 'Primitive Tasks', tags = ['folder', 'top_level', 'primitive_folder', 'primitive_task'], open = True)
        self.project_tree.insert('', 'end', 'Non_Primitive_Tasks/', text = 'Non-Primitive Tasks', tags = ['folder', 'top_level', 'non_primitive_folder', 'non_primitive_task'], open = True)
        
        self.tab_manager = TabManager(self.workspace_frame,
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
        
        self.non_primitive_task_folder_menu = tk.Menu(self.root, tearoff = 0)
        self.non_primitive_task_folder_menu.add_command(label = 'Add Task', command = self.create_non_primitive_task)
        self.non_primitive_task_folder_menu.add_command(label = 'Import Task', command = self.import_non_primitive_task)
        
        self.primitive_task_folder_menu = tk.Menu(self.root, tearoff = 0)
        self.primitive_task_folder_menu.add_command(label = 'Add Task', command = self.create_primitive_task)
        self.primitive_task_folder_menu.add_command(label = 'Import Task', command = self.import_primitive_task)
        
        self.task_folder_menu = tk.Menu(self.root, tearoff = 0)
        self.task_folder_menu.add_command(label = 'Rename', command = self.rename_task)
        self.task_folder_menu.add_command(label = 'Export Task', command = self.export_task)
        
        self.non_primitive_task_menu = tk.Menu(self.root, tearoff = 0)
        self.non_primitive_task_menu.add_command(label = 'Add Rule', command = self.create_non_primitive_task_pn)
        self.non_primitive_task_menu.add_command(label = 'Import Rule from PNML file', command = self.import_from_PNML)
        
        self.primitive_task_menu = tk.Menu(self.root, tearoff = 0)
        self.primitive_task_menu.add_command(label = 'Add Rule', command = self.create_primitive_task_pn)
        self.primitive_task_menu.add_command(label = 'Import Rule from PNML file', command = self.import_from_PNML)
        
        self.finalizing_menu = tk.Menu(self.root, tearoff = 0)
        self.finalizing_menu.add_command(label = 'Add Rule', command = self.create_finalizing)
        self.finalizing_menu.add_command(label = 'Import Rule from PNML file', command = self.import_from_PNML)
        
        self.canceling_menu = tk.Menu(self.root, tearoff = 0)
        self.canceling_menu.add_command(label = 'Add Rule', command = self.create_canceling)
        self.canceling_menu.add_command(label = 'Import Rule from PNML file', command = self.import_from_PNML)
        
        self.petri_net_menu = tk.Menu(self.root, tearoff = 0)
        self.petri_net_menu.add_command(label = 'Open', command = self.open_petri_net)
        self.petri_net_menu.add_command(label = 'Rename', command = self.rename_petri_net)
        self.petri_net_menu.add_command(label = 'Delete', command = self.delete_petri_net)
        self.petri_net_menu.add_command(label = 'Export Rule to PNML', command = self.export_to_PNML)
        
        right_click_tag_bindings = {
                        'non_primitive_folder' : self.popup_non_primitive_task_folder_menu,
                        'primitive_folder' : self.popup_primitive_task_folder_menu,
                        'task' : self.popup_task_folder_menu,
                        'decomposing_folder' : self.popup_non_primitive_task_menu,
                        'executing_folder' : self.popup_primitive_task_menu,
                        'finalizing_folder' : self.popup_finalizing_menu,
                        'canceling_folder' : self.popup_canceling_menu,
                        'petri_net' : self.popup_petri_net_menu
                        }
        
        for tag, handler in right_click_tag_bindings.iteritems():
            #MAC OS:
            if (self.root.tk.call('tk', 'windowingsystem')=='aqua'):
                self.project_tree.tag_bind(tag, '<2>', handler)
                self.project_tree.tag_bind(tag, '<Control-1>', handler)
            #Windows / UNIX / Linux:
            else:
                self.project_tree.tag_bind(tag, '<3>', handler)
        
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
    
    def popup_non_primitive_task_folder_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.non_primitive_task_folder_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
    
    def popup_primitive_task_folder_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.primitive_task_folder_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
    
    def popup_task_folder_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.task_folder_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
    
    def popup_non_primitive_task_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.non_primitive_task_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
        
    def popup_primitive_task_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.primitive_task_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
    
    def popup_finalizing_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.finalizing_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
        
    def popup_canceling_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.canceling_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
    
    def popup_petri_net_menu(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.popped_up_menu = self.petri_net_menu
        self.popped_up_menu.post(event.x_root, event.y_root)
    
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
    
    def _get_ext_and_filetype(self, element):
        
        item_tags = self.project_tree.item(element, 'tags')
        
        extension = ''
        filetype = ''
        
        if 'executing' in item_tags:
            extension = '.pt'
            filetype = 'Primitive Task '
        elif 'decomposing' in item_tags:
            extension = '.npt'
            filetype = 'Non-Primitive Task '
        elif 'finalizing' in item_tags:
            if 'primitive_task' in item_tags:
                extension = '.pt.f'
                filetype = 'Finalizing Primitive Task '
            elif 'non_primitive_task' in item_tags:
                extension = '.npt.f'
                filetype = 'Finalizing Non-Primitive Task '
        elif 'canceling' in item_tags:
            if 'primitive_task' in item_tags:
                extension = '.pt.c'
                filetype = 'Canceling Primitive Task '
            elif 'non_primitive_task' in item_tags:
                extension = '.npt.c'
                filetype = 'Canceling Non-Primitive Task '
        
        return extension, filetype
    
    def _add_pne(self, item_id, PNEditorClass = RulePNEditor, **kwargs):
        
        open_tab = kwargs.pop('open_tab', True)
        pne = kwargs.pop('pne_object', None)
        
        if not pne:
            pne = PNEditorClass(self.tab_manager, **kwargs)
        self.petri_nets[item_id] = pne
        if open_tab:
            self.tab_manager.add(pne, text = pne.name)
            self.tab_manager.select(pne)
        return pne
    
    def create_non_primitive_task(self):
        self.create_task(is_primitive_task = False)
    
    def create_primitive_task(self):
        self.create_task(is_primitive_task = True)
    
    def create_task(self, name = None, is_primitive_task = True, open = True):
        
        if name is None:
            dialog = InputDialog('Task name',
                                 'Please input a Task name, preferably composed only of alphanumeric characters.',
                                 'Name',
                                 entry_length = 25,
                                 regex = FactPlace.REGEX
                                 )
            dialog.window.transient(self.root)
            self.root.wait_window(dialog.window)
            if not dialog.value_set:
                return
            name = dialog.input_var.get()
        
        item_id = self.clicked_element + name + '/'
        
        try:
            tags = ['folder', 'task_' + name]
            tags.append('primitive_task' if is_primitive_task else 'non_primitive_task')
            item_tags = tags + ['task']
            self.project_tree.insert(self.clicked_element, 'end', item_id, text = name, tags = item_tags, open = open)
            self._adjust_width(name, item_id)
            
            sub_name = 'Executing rules' if is_primitive_task else 'Decomposing rules'
            sub_id = item_id + ('Executing_Rules/' if is_primitive_task else 'Decomposing_Rules/')
            sub_tag = 'executing' if is_primitive_task else 'decomposing'
            self.project_tree.insert(item_id, 'end', sub_id, text = sub_name, tags = tags +  [sub_tag, sub_tag + '_folder'], open = open)
            self._adjust_width(sub_name, sub_id)
            
            sub_name = 'Finalizing rules'
            sub_id = item_id + 'Finalizing_Rules/'
            self.project_tree.insert(item_id, 'end', sub_id, text = sub_name, tags = tags + ['finalizing', 'finalizing_folder'], open = open)
            self._adjust_width(sub_name, sub_id)
            
            sub_name = 'Canceling rules'
            sub_id = item_id + 'Canceling_Rules/'
            self.project_tree.insert(item_id, 'end', sub_id, text = sub_name, tags = tags + ['canceling', 'canceling_folder'], open = open)
            self._adjust_width(sub_name, sub_id)
            
        except Exception as e:
            tkMessageBox.showerror('ERROR', 'A Task could not be inserted in the selected node, possible duplicate name.\n\n' + str(e))
            return None
        
        return item_id
    
    def create_non_primitive_task_pn(self):
        self.create_petri_net(PNEditorClass = NonPrimitiveTaskPNEditor, is_primitive_task = False)
    
    def create_primitive_task_pn(self):
        self.create_petri_net(PNEditorClass = PrimitiveTaskPNEditor, is_primitive_task = True)
    
    def create_finalizing(self):
        
        item_tags = self.project_tree.item(self.clicked_element, 'tags')
        ipt = 'primitive_task' in item_tags
        
        self.create_petri_net(PNEditorClass = FinalizingPNEditor, is_primitive_task = ipt)
    
    def create_canceling(self):
        
        item_tags = self.project_tree.item(self.clicked_element, 'tags')
        ipt = 'primitive_task' in item_tags
        
        self.create_petri_net(PNEditorClass = RulePNEditor, is_primitive_task = ipt)
    
    def create_petri_net(self, pne_object = None, PNEditorClass = RulePNEditor, is_primitive_task = False):
        
        if pne_object:
            name = pne_object.name
        else:
            dialog = InputDialog('Rule name',
                                 'Please input a rule name, preferably composed only of alphabetic characters, dashes and underscores.',
                                 'Name',
                                 entry_length = 25)
            dialog.window.transient(self.root)
            self.root.wait_window(dialog.window)
            if not dialog.value_set:
                return
            name = dialog.input_var.get()
            
            task = None
            for t in self.project_tree.item(self.clicked_element, "tags"):
                if t[:5] == 'task_':
                    task = t[5:]
                    break
            
            if not task:
                raise Exception('Task tag was not found!')
            
        
        item_id = self.clicked_element + name
        
        item_tags = list(self.project_tree.item(self.clicked_element, "tags")) + ['petri_net']
        item_tags.remove('folder')
        try:
            item_tags.remove('decomposing_folder')
        except:
            try:
                item_tags.remove('executing_folder')
            except:
                try:
                    item_tags.remove('finalizing_folder')
                except:
                    item_tags.remove('canceling_folder')
        
        
        try:
            if pne_object:
                self._add_pne(item_id, pne_object = pne_object, open_tab = False)
            else:
                pne_object = self._add_pne(item_id, PNEditorClass = PNEditorClass, name = name, task = task, is_primitive_task = is_primitive_task)
            pne_object.edited = True
        except Exception as e:
            tkMessageBox.showerror('ERROR', str(e))
            return
            
        try:
            self.project_tree.insert(self.clicked_element, 'end', item_id, text = name, tags = item_tags)
            self._adjust_width(name, item_id)
        except Exception as e:
            del self.petri_nets[item_id]
            tkMessageBox.showerror('ERROR', 'The Petri Net could not be inserted in the selected node, possible duplicate name.\n\n' + str(e))
            return
    
    def rename_task(self):
        
        old_id = self.clicked_element
        old_name = old_id[old_id[:-1].rfind('/') + 1:-1]
        
        dialog = InputDialog('Task name',
                                 'Please input a Task name, preferably composed only of alphanumeric characters.',
                                 'Name',
                                 entry_length = 25,
                                 regex = FactPlace.REGEX,
                                 value = old_name)
        dialog.window.transient(self.root)
        self.root.wait_window(dialog.window)
        if not dialog.value_set:
            return
        
        name = dialog.input_var.get()
        
        #Need to set it for the create_task call
        self.clicked_element = self.project_tree.parent(self.clicked_element)
        is_primitive_task = 'primitive_task' in self.project_tree.item(self.clicked_element, 'tags')
        item_id = self.create_task(name, is_primitive_task = is_primitive_task)
        if not item_id:
            return
        
        self.project_tree.detach(old_id)
        
        for subfolder in self.project_tree.get_children(old_id):
            sub_id = subfolder[subfolder[:-1].rfind('/') + 1:]
            self.clicked_element = item_id + sub_id
            for pn_id in self.project_tree.get_children(old_id + sub_id):
                pne, tab_open = self.delete_petri_net(pn_id)
                pne.set_pn_task(name)
                self.create_petri_net(pne)
                if tab_open:
                    self.open_petri_net(pne)
        
        self.project_tree.delete(old_id)
    
    def open_callback(self, event):
        self.clicked_element = self.project_tree.identify('item', event.x, event.y)
        self.open_petri_net()
    
    def open_petri_net(self, pne = None):
        if pne is None:
            pne = self.petri_nets[self.clicked_element]
        try:
            self.tab_manager.add(pne, text = pne.name)
        except:
            pass
        
        self.tab_manager.select(pne)
    
    def import_non_primitive_task(self):
        zip_filename = tkFileDialog.askopenfilename(
                                              defaultextension = '.npt.tsk',
                                              filetypes=[('Non Primitive Task file', '*.npt.tsk')],
                                              title = 'Open Non Primitive Task file...',
                                              initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
                                          )
        if not zip_filename:
            return
        
        self._import_task(zip_filename, is_primitive_task = False)
    
    def import_primitive_task(self):
        zip_filename = tkFileDialog.askopenfilename(
                                              defaultextension = '.pt.tsk',
                                              filetypes=[('Primitive Task file', '*.pt.tsk')],
                                              title = 'Open Primitive Task file...',
                                              initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
                                          )
        if not zip_filename:
            return
        
        self._import_task(zip_filename, is_primitive_task = True)
    
    def _import_task(self, zip_filename, is_primitive_task):
        
        zip_file = zipfile.ZipFile(zip_filename, 'r')
        
        tmp_dir = tempfile.mkdtemp()
        
        task_name = zip_file.read('task_name.txt')
        self.create_task(task_name, is_primitive_task, open = False)
        task_id = self.clicked_element + task_name + '/'
        
        # Create content from files in each folder
        for x in zip_file.infolist():
            
            file_name = x.filename
            PNEditorClass = None
            
            if file_name[:18] == 'Decomposing_Rules/':
                file_name = file_name[18:file_name.find('.')]
                PNEditorClass = NonPrimitiveTaskPNEditor
                self.clicked_element = task_id + 'Decomposing_Rules/'
            elif file_name[:16] == 'Executing_Rules/':
                file_name = file_name[18:file_name.find('.')]
                PNEditorClass = NonPrimitiveTaskPNEditor
                self.clicked_element = task_id + 'Executing_Rules/'
            elif file_name[:17] == 'Finalizing_Rules/':
                file_name = file_name[17:file_name.find('.')]
                PNEditorClass = FinalizingPNEditor
                self.clicked_element = task_id + 'Finalizing_Rules/'
            elif file_name[:16] == 'Canceling_Rules/':
                file_name = file_name[16:file_name.find('.')]
                PNEditorClass = RulePNEditor
                self.clicked_element = task_id + 'Canceling_Rules/'
            
            if PNEditorClass is None or not file_name:
                continue
            
            file_path = os.path.join(tmp_dir, file_name)
            f = open(file_path, 'w')
            f.write(zip_file.read(x))
            f.close()
            
            pn = PNEditorClass.PetriNetClass.from_pnml_file(file_path, task_name)[0]
            pne = PNEditorClass(self.tab_manager, PetriNet = pn)
            self.create_petri_net(pne_object = pne)
            
            os.remove(file_path) 
            
        os.rmdir(tmp_dir)
        zip_file.close()
        
        self.status_var.set('Imported task: ' + task_name)
    
    def import_from_PNML(self):
        
        item_tags = self.project_tree.item(self.clicked_element, 'tags')
        
        task = ''
        for t in item_tags:
            if t[:5] == 'task_':
                task = t[5:]
                break
        
        extension = ''
        filetype = ''
        
        if 'executing' in item_tags:
            extension = '.pt'
            filetype = 'Primitive Task '
            pneditor = PrimitiveTaskPNEditor
        elif 'decomposing' in item_tags:
            extension = '.npt'
            filetype = 'Non-Primitive Task '
            pneditor = NonPrimitiveTaskPNEditor
        elif 'finalizing' in item_tags:
            pneditor = FinalizingPNEditor
            if 'primitive_task' in item_tags:
                extension = '.pt.f'
                filetype = 'Finalizing Primitive Task '
            elif 'non_primitive_task' in item_tags:
                extension = '.npt.f'
                filetype = 'Finalizing Non-Primitive Task '
        elif 'canceling' in item_tags:
            pneditor = RulePNEditor
            if 'primitive_task' in item_tags:
                extension = '.pt.c'
                filetype = 'Canceling Primitive Task '
            elif 'non_primitive_task' in item_tags:
                extension = '.npt.f'
                filetype = 'Canceling Non-Primitive Task '
        
        filename = tkFileDialog.askopenfilename(
                                              defaultextension = extension + '.pnml',
                                              filetypes=[(filetype + 'PNML file', '*' + extension + '.pnml')],
                                              title = 'Open ' + filetype + 'PNML file...',
                                              initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
                                              )
        if not filename:
            return
        
        self._import_from_pnml(filename, pneditor, task)
        
    def _import_from_pnml(self, filename, PNEditorClass, task):
        
        try:
            petri_nets = PNEditorClass.PetriNetClass.from_pnml_file(filename, task)
        except Exception as e:
            tkMessageBox.showerror('Error reading PNML file.', 'An error occurred while reading the PNML file.\n\n' + str(e))
            return
        
        if len(petri_nets) > 1:
            print 'warning: More than 1 petri net read, only 1 loaded.'
        
        try:
            pn = petri_nets[0]
        except Exception as e:
            tkMessageBox.showerror('Error loading PetriNet.', 'An error occurred while loading the PetriNet object.\n\n' + str(e))
        
        pne = PNEditorClass(self.tab_manager, PetriNet = pn)
        self.create_petri_net(pne)
        pne.edited = False
        self.tab_manager.add(pne, text = pne.name)
        self.tab_manager.select(pne)
    
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
        tab_open = True
        try:
            self.tab_manager.forget(pne)
        except:
            tab_open = False
        self.project_tree.delete(item)
        return pne, tab_open
    
    def export_task(self):
        
        item_tags = self.project_tree.item(self.clicked_element, 'tags')
        
        extension = ''
        filetype = ''
        
        if 'primitive_task' in item_tags:
            extension = '.pt'
            filetype = 'Primitive '
        else:
            extension = '.npt'
            filetype = 'Non-Primitive '
        
        file_name = os.path.basename(self.clicked_element[:-1])
        pos = file_name.find('(')
        if pos > -1:
            file_name = file_name[:pos]
        
        zip_filename = tkFileDialog.asksaveasfilename(
                                                  defaultextension = extension + '.tsk',
                                                  filetypes=[(filetype + 'Task file', '*' + extension + '.tsk')],
                                                  title = 'Save as ' + filetype + 'Task file...',
                                                  initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
                                                  initialfile = file_name
                                              )
        if not zip_filename:
            return
        
        try:
            zip_file = zipfile.ZipFile(zip_filename, "w")
        except:
            tkMessageBox.showerror('Error opening file.', 'A problem occurred while opening a file for writing, make sure the file is not open by other program before saving.')
            return
        tmp_dir = tempfile.mkdtemp()
        
        file_name = os.path.join(tmp_dir, 'task_name.txt')
        name_file = open(file_name, 'w')
        name_file.write(os.path.basename(self.clicked_element[:-1]))
        name_file.close()
        
        zip_file.write(file_name, 'task_name.txt')
        os.remove(file_name)
        
        folders = self.project_tree.get_children(self.clicked_element)
        
        for f in folders:
            children = self.project_tree.get_children(f)
            folder_name = os.path.basename(f[:-1])
            if not children:
                file_path = os.path.join(tmp_dir, folder_name)
                os.mkdir(file_path)
                zip_file.write(file_path, folder_name)
                os.rmdir(file_path)
                continue
            for current in children:
                
                file_name = os.path.basename(current)
                
                ext, _ = self._get_ext_and_filetype(current)
                file_name = file_name + ext + '.pnml'
                path_name = os.path.join(folder_name, file_name)
                file_path = os.path.join(tmp_dir, file_name)
                
                pne = self.petri_nets[current]
                pne._petri_net.to_pnml_file(file_path)
                
                zip_file.write(file_path, path_name)
                os.remove(file_path)
        
        os.rmdir(tmp_dir)
        zip_file.close()
        
        try:
            tab_id = self.tab_manager.select()
            if not tab_id:
                raise Exception()
        except:
            self.status_label.configure(textvariable = self.status_var)
            self.status_var.set('Exported Task: ' + zip_filename)
            return
        
        pne = self.tab_manager.widget_dict[tab_id]
        pne.status_var.set('Exported Task: ' + zip_filename)
    
    def export_to_PNML(self):
        
        extension, filetype = self._get_ext_and_filetype(self.clicked_element)
        
        filename = tkFileDialog.asksaveasfilename(
                                                  defaultextension = extension + '.pnml',
                                                  filetypes=[(filetype + 'PNML file', '*' + extension + '.pnml')],
                                                  title = 'Save as ' + filetype + 'PNML file...',
                                                  initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
                                                  initialfile = os.path.basename(self.clicked_element) + extension + '.pnml'
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
                                                  initialdir = os.path.dirname(self.file_path) if self.file_path is not None else os.path.expanduser('~/Desktop'),
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
