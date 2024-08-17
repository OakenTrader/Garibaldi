"""
Handles all existing GUI of Garibaldi
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from scripts.helpers.utility import *
from scripts.helpers.save_watch import *
from scripts.helpers.extraction import *
import sys, json, os, threading

class Garibaldi_gui:
    """
    Defines functions commonly used by all gui windows
    """
    def __init__(self):
        super().__init__()
        self.variables = jopen("./scripts/variables.json")
        try:
            self.user_variables = jopen("./user_variables.json")
        except:
            self.user_variables = self.variables["default_directories"].copy()
            self.save_settings()
        self.tinkerable = None
    
    def get_var(self, key):
        """Gets a user variable. If unavailable, gets the default variable from variables.json"""
        if key not in self.user_variables:
            self.set_var(key, self.variables["default_directories"][key])
        return self.user_variables[key]
    
    def set_var(self, key, value):
        """Sets a user variable and save the user variables into user_variables.json"""
        self.user_variables[key] = value
        self.save_settings()

    def browse_folder(self, entry_widget, settings_key, initialdir=None, only_folder_name=False):
        """Browses a folder location then set the value in the provided entry_widget and settings key of the user variables.
        Intialdir may be provided to set the initial directory of the browser."""
        if initialdir is None:
            initialdir = "/".join(self.get_var(settings_key).split("/")[:-1])
        folder_path = filedialog.askdirectory(initialdir=initialdir)
        if folder_path:
            if only_folder_name:
                folder_path = folder_path.split("/")[-1]
            entry_widget.config(state='normal')  # Enable the entry to modify it
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder_path)
            entry_widget.config(state='readonly')  # Set the entry back to read-only
            self.set_var(settings_key,folder_path)
    
    def browse_file(self, entry_widget, settings_key, initialdir=None):
        """Browses a file location then set the value in the provided entry_widget and settings key of the user variables.
        Intialdir may be provided to set the initial directory of the browser."""
        if initialdir is None:
            initialdir = "/".join(self.get_var(settings_key).split("/")[:-1])
        file_path = filedialog.askopenfilename(initialdir=initialdir)
        if file_path:
            entry_widget.config(state='normal')  # Enable the entry to modify it
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file_path)
            entry_widget.config(state='readonly')  # Set the entry back to read-only
            self.set_var(settings_key, file_path)


    def restore_defaults(self, entry_widget, settings_key):
        """Return a user variable back to a default value defined in variables.json"""
        entry_widget.config(state='normal')  # Enable the entry to modify it
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, self.variables["default_directories"][settings_key])
        entry_widget.config(state='readonly')  # Set the entry back to read-only
        self.set_var(settings_key, self.variables["default_directories"][settings_key])

    def save_settings(self):
        """Write the current user variables into user_variables.json"""
        with open("./user_variables.json", 'w') as file:
            json.dump(self.user_variables, file, indent=4)
    
    def custom_size_button(self, root, text, command, width, height):
        """Generates a button with a custom size"""
        frame = tk.Frame(root, width=width, height=height)
        frame.pack_propagate(False)  # Prevent frame from resizing to fit its contents
        button = ttk.Button(frame, text=text, command=command)
        button.pack(expand=True, fill=tk.BOTH)
        return frame, button
    
    def new_window_entry(self, root, on_click, target, title):
        """Creates a window that takes in a string before executing an on_click function on a target"""
        window = tk.Toplevel(root)
        window.title(title)
        entry = tk.Entry(window, width=50)
        entry.grid(row=0, column=0, padx=50, pady=10)
        button = tk.Button(window, text="Ok", command=lambda: on_click(entry.get(), target, window))
        button.grid(row=1, column=0, padx=50, pady=10)
    
    def make_grid(self, objects:list, pad_x, pad_y):
        """Formats objects in a window"""
        extra_row = 0
        for i, row in enumerate(objects):
            max_rowspan = 0
            if not isinstance(row, list):
                row = [row]
            extra_column = 0
            for j, o in enumerate(row):
                if not isinstance(o, tuple):
                    """ Object / columnspan / sticky """
                    o = (o, 1, None)
                if o[0] is not None: # Could be none to indicate empty columnspan
                    o[0].grid(row=i, column=j + extra_column, padx=pad_x, pady=pad_y, columnspan=o[1], sticky=o[2])
                extra_column += o[1] - 1
                # max_rowspan = 
    
    def toggle_tinkerable(self):
        """Toggle on/off the buttons"""
        for element in self.tinkerable:
            state = str(element.cget('state'))
            if state == 'disabled':
                element.config(state=tk.NORMAL)
            elif state == 'normal':
                element.config(state=tk.DISABLED)
            


class Main_Menu(tk.Tk, Garibaldi_gui):
    """
    Main menu for Garibaldi
    """
    def __init__(self):
        super().__init__()
        Garibaldi_gui.__init__(self)
        self.title("Garibaldi")
        self.stop_event = threading.Event()
        self.stop_event.clear()
        self.main_menu_gui()
        self.mainloop()
        self.stop_event.set()
    
    def main_menu_gui(self):
        """Generates the Main Menu"""
        frame1, extract_button = self.custom_size_button(self, text="Extract saves", command= lambda:self.on_click(SaveExtractor), width=200, height=120)
        frame2, watch_button = self.custom_size_button(self, text="Watch Saves", command= lambda:self.on_click(SaveWatcher), width=200, height=120)
        frame3, tree_button = self.custom_size_button(self, text="View Savefile", command= lambda:self.on_click(DictViewer), width=200, height=120)
        frame4, config_button = self.custom_size_button(self, text="Configure", command= lambda:self.on_click(Configure_windows), width=200, height=120)
        self.tinkerable = [extract_button, watch_button, tree_button, config_button]
        self.make_grid([[frame1], [frame2], [frame3], [frame4]], 50, 10)
    
    def on_click(self, function):
        """Opens a new window and disables all main menu buttons"""
        self.toggle_tinkerable()
        new_window = function(self)
        self.wait_window(new_window)
        self.toggle_tinkerable()
    


class SaveExtractor(tk.Toplevel, Garibaldi_gui):
    """
    Handles Save extractor menu
    TODO Make an option to have multiple threads extracting at the same time
    """
    def __init__(self, master):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Save Extractor")
        self.extractor_config()
        self.watch_thread = None
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.stop_event = master.stop_event
    
    def extractor_config(self):
        """Generates the SaveExtractor menu"""
        label1 = ttk.Label(self, text="Extract saves in a campaign folder into Python dictionaries")
        
        self.del_var = tk.BooleanVar(self, value=False)
        label2 = ttk.Label(self, text="Delete the save file after extraction?")
        yes_radio = ttk.Radiobutton(self, text="Yes", variable=self.del_var, value=True)
        no_radio = ttk.Radiobutton(self, text="No", variable=self.del_var, value=False)

        self.anal_var = tk.BooleanVar(self, value=False)
        label3 = ttk.Label(self, text="Analyze the files right after extraction?")
        yes_radio_anal = ttk.Radiobutton(self, text="Yes", variable=self.anal_var, value=True)
        no_radio_anal = ttk.Radiobutton(self, text="No", variable=self.anal_var, value=False)

        label4 = ttk.Label(self, text="Campaign Folder")
        settings_entry = ttk.Entry(self, width=50)
        settings_entry.insert(0, self.get_var("Campaign Folder"))
        settings_entry.config(state="readonly")

        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(settings_entry, "Campaign Folder", only_folder_name=True, initialdir="./saves"))

        self.ok_button = ttk.Button(self, text="Start", command=lambda: self.on_start())
        self.stop_button = ttk.Button(self, text="Stop", command=lambda: self.on_stop())
        self.stop_button.config(state=tk.DISABLED)

        self.tinkerable = [yes_radio, no_radio, yes_radio_anal, no_radio_anal, browse_button, self.ok_button, self.stop_button]
        self.make_grid([
            [label1],
            [label2, yes_radio, no_radio],
            [label3, yes_radio_anal, no_radio_anal],
            [label4, (settings_entry, 3, 'w'), (browse_button, 1, 'w')],
            [self.ok_button, (None, 1), self.stop_button]
        ], 5, 10)
        self.after(100, self.end_task)
    
    def on_start(self):
        """Starts extraction and toggles all buttons in the SaveExtractor menu"""
        for element in self.tinkerable:
            element.config(state=tk.DISABLED)
        self.stop_event.clear()
        if self.del_var.get():
            proceed = messagebox.askyesno("Wait a sec", "Save files will be deleted after successfully extracted, would you like to proceed?")
            if not proceed:
                self.on_stop()
                return
        self.stop_button.config(state=tk.NORMAL)
        self.watch_thread = threading.Thread(target=extract_all_files, args=(self.get_var("Campaign Folder"), self.stop_event, self.del_var.get(), self.anal_var.get()))
        self.watch_thread.start()
    
    def on_stop(self):
        """Starts extraction and toggles all buttons in the SaveExtractor menu"""
        self.stop_event.set()

    
    def on_closing(self):
        """Handles closing the SaveExtractor menu"""
        self.on_stop()
        self.end_task()
        self.destroy()
    
    def end_task(self):
        if self.stop_event.is_set():
            if self.watch_thread is not None:
                self.watch_thread.join()
            self.toggle_tinkerable()
            self.stop_event.clear()
        self.after(500, self.end_task)


"""
TODO Make analyzing and plotting a separate task from extracting so that we use plots on the main thread
"""

class SaveAnalyzer(tk.Toplevel, Garibaldi_gui):
    """
    Handles analysis and plotting
    """
    def __init__(self, master):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Save Watcher")
        self.save_watch_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.stop_event = master.stop_event
    
    def save_analyze_settings(self):
        """
        Plot the statistics of some variables and/or show it on an interactive screen
        Campaign Folder    _autosaves_________________________  |Browse| |New Folder|
        Select which stats do you want to extract from the saves and plot?
        Construction  o yes  o no  [] show plot
        Average Construction cost  o yes  o no  [] show plot
        Innovation  o yes  o no  [] show plot
        Capped Innovation  o yes  o no  [] show plot
        Prestige  o yes  o no  [] show plot
        Infamy  o yes  o no  [] show plot
        Goods produced  o yes  o no  [] show plot
                     | Start |                 | Stop |
        """
        pass


class SaveWatcher(tk.Toplevel, Garibaldi_gui):
    """
    Handles Save watcher menu
    """
    def __init__(self, master):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Save Watcher")
        self.save_watch_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.stop_event = master.stop_event
    
    def save_watch_settings(self):
        """Generates the SaveWatcher menu"""
        def create_new_folder(campaign_folder, widget, window):
            try:
                os.mkdir(f"./saves/{campaign_folder}")
            except FileExistsError:
                messagebox.showerror("Error", "Folder already exists!")
                return
            window.destroy()
            widget.config(state="normal")
            widget.delete(0, tk.END)
            widget.insert(0, f"./saves/{campaign_folder}")
            widget.config(state="readonly")
            self.set_var("Campaign Folder", f"./saves/{campaign_folder}")
        
        label1 = ttk.Label(self, text="Watch the autosave file and copy it to the target campaign folder when modified")

        label2 = ttk.Label(self, text="Copy every")
        self.freq_settings = ttk.Entry(self, width=65)
        self.freq_settings.insert(0, "1")
        label3 = ttk.Label(self, text="autosave(s)")
        
        label4 = ttk.Label(self, text="Autosave Location")
        autosave_entry = ttk.Entry(self, width=65)
        autosave_entry.insert(0, self.get_var("Autosave Location"))
        autosave_entry.config(state="readonly")
        browse_button_1 = ttk.Button(self, text="Browse", command=lambda: self.browse_file(autosave_entry, "Autosave Location"))

        label5 = ttk.Label(self, text="Campaign Folder").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        self.folder_entry = ttk.Entry(self, width=50)
        self.folder_entry.insert(0, "./saves/autosaves")
        self.folder_entry.config(state="readonly")
        browse_button_2 = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(self.folder_entry, "Campaign Folder", "./saves"))
        make_folder_button = ttk.Button(self, text="New Folder", command=lambda: self.new_window_entry(self, create_new_folder, self.folder_entry, "Create new campaign folder"))

        self.ok_button = ttk.Button(self, text="Run", command=lambda: self.on_ok())

        self.stop_button = ttk.Button(self, text="Stop", command=lambda: self.on_stop())
        self.stop_button.config(state=tk.DISABLED)

        self.tinkerable = [self.ok_button, self.freq_settings, browse_button_1, browse_button_2, make_folder_button]
        self.make_grid(
            [[(label1, 3, 'w')], 
             [(label2, 1, 'w'), (self.freq_settings, 2, 'w'), label3],
             [(label4, 1, 'w'), (autosave_entry, 2, 'w'), browse_button_1],
             [(label5, 1, 'w'), self.folder_entry, browse_button_2, make_folder_button],
             [None, self.ok_button, self.stop_button]
            ], 10, 20
        )

    def on_ok(self):
        """Starts watching and toggles all buttons in the SaveWatcher menu"""
        try:
            n_saves = int(self.freq_settings.get())
        except:
            messagebox.showerror("Error", "Invalid input!")
            return
        self.ok_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        for element in self.tinkerable:
            element.config(state=tk.DISABLED)
        self.watch_thread = threading.Thread(target=watch_save, args=(self.get_var("Autosave Location"), self.folder_entry.get(), self.stop_event, n_saves))
        self.watch_thread.start()
    
    def on_stop(self):
        """Stops watching and toggles all buttons in the SaveWatcher menu"""
        self.stop_event.set()
        self.watch_thread.join()
        self.ok_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        for element in self.tinkerable:
            element.config(state=tk.NORMAL)
        self.stop_event.clear()

    def on_closing(self):
        """Handles closing the SaveWatcher window"""
        self.on_stop()
        self.destroy()

class DictViewer(tk.Toplevel, Garibaldi_gui):
    """
    Handles Save Viewer menu and tree view
    """
    def __init__(self, master, preprocessor=None):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Settings Viewer App")
        self.preprocessor = preprocessor
        self.create_settings_window()

    def get_size(self, obj):
        """Return the size of an object and all others objects constituting its tree"""
        #TODO 
        """More efficient handling by get_size lower level branches and store values for get_size of higher level branches"""
        if isinstance(obj, dict):
            return sum(self.get_size(v) for v in obj.values())
        elif isinstance(obj, list):
            return sum(self.get_size(v) for v in obj)
        else:
            return sys.getsizeof(obj)

    def create_settings_window(self):
        """Generates the DictViewer menu"""
        self.size_var = tk.BooleanVar(value=False)
        
        label1 = ttk.Label(self, text="Get the object size?")
        yes_radio = ttk.Radiobutton(self, text="Yes", variable=self.size_var, value=True)
        no_radio = ttk.Radiobutton(self, text="No", variable=self.size_var, value=False)

        label2 = ttk.Label(self, text="File location")
        settings_entry = ttk.Entry(self, width=50)
        settings_entry.insert(0, self.get_var("Tree File Location"))
        settings_entry.config(state="readonly")
        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_file(settings_entry, "Tree File Location"))

        ok_button = ttk.Button(self, text="OK", command=self.on_ok)

        self.make_grid(
            [[(label1, 1, 'w'), yes_radio, no_radio],
             [(label2, 1, 'w'), (settings_entry, 10, 'w'), (browse_button, 1, 'w')],
             [(None, 4), ok_button]
            ], 10, 10
        )

    def on_ok(self):
        """Handles the tree viewer generation"""
        if not os.path.isfile(self.get_var("Tree File Location")):
            messagebox.showerror("Invalid Directory", "The selected directory is not valid. Please choose a valid directory.")
        else:
            self.show_size = self.size_var.get()
            self.create_tree_viewer()
            self.geometry("600x400")

    def create_tree_viewer(self):
        """Generates the Tree (Dict) Viewer window"""
        for widget in self.winfo_children():
            widget.destroy()
        
        self.title("Dictionary Viewer")

        # Create a frame for the Treeview and Scrollbars
        frame = ttk.Frame(self)
        frame.pack(expand=True, fill=tk.BOTH)

        # Create the Treeview
        self.tree = ttk.Treeview(frame)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Vertical Scrollbar
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)

        # Horizontal Scrollbar
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.configure(xscrollcommand=hsb.set)

        # Load the data and populate the treeview
        data = zopen(self.get_var("Tree File Location"))
        if self.preprocessor is not None:
            data = self.preprocessor(data)
        self.populate_tree("", data)

    def populate_tree(self, parent, dictionary):
        """Algorithm that constructs the tree from the dictionary"""
        for key, value in dictionary.items():
            if isinstance(value, dict):
                size = f" ({self.get_size(value)} bytes)" if self.show_size else ""
                node = self.tree.insert(parent, 'end', text=f"{key}{size}", open=False)
                self.populate_tree(node, value)
            elif isinstance(value, list):
                size = f" ({self.get_size(value)} bytes)" if self.show_size else ""
                node = self.tree.insert(parent, 'end', text=f"{key}{size}", open=False)
                for item in value:
                    self.tree.insert(node, 'end', text=str(item))
            else:
                self.tree.insert(parent, 'end', text=f"{key}: {value}")
            

class Configure_windows(tk.Toplevel, Garibaldi_gui):
    """
    Handles configuration menu
    """
    def __init__(self, master) -> None:
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Configure settings")
        self.n_entries = 0
        for key in ["Common Directory", "Events Directory", "Localization Directory"]:
            self.add_directory_settings(key)
    
    def add_directory_settings(self, target):
        """Generates Label/entry/button for each specified user variable"""
        ttk.Label(self, text=target).grid(row=self.n_entries, column=0, padx=10, pady=10, sticky='e')
        settings_entry = ttk.Entry(self, width=50)
        settings_entry.grid(row=self.n_entries, column=1, padx=10, pady=10)
        settings_entry.insert(0, self.get_var(target))
        settings_entry.config(state="readonly")
        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(settings_entry, target))
        browse_button.grid(row=self.n_entries, column=2, padx=2, pady=10)
        reset_button = ttk.Button(self, text="Restore Defaults", command=lambda: self.restore_defaults(settings_entry, target))
        reset_button.grid(row=self.n_entries, column=3, padx=2, pady=10)
        self.n_entries += 1

"""
TODO Implement cleaning process to clean up things if some processes unexpectedly failed e.g. leftover save.txt
"""