"""
Handles all existing GUI of Garibaldi
"""
import multiprocessing.queues
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.helpers.utility import *
from src.helpers.save_watch import *
from src.helpers.extraction import *
from src.checkers.manager import perform_checking
import sys, json, os, glob, multiprocessing, queue

class Garibaldi_gui:
    """
    Defines functions commonly used by all gui windows
    """
    def __init__(self):
        super().__init__()
        self.variables = jopen("./src/variables.json")
        try:
            self.user_variables = jopen("./user_variables.json")
        except:
            self.user_variables = self.variables["default_directories"].copy()
            self.save_settings()
        self.tinkerable = None
        self.disabled_tinkerable = False
        self.is_browsing = False
    
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
        if self.is_browsing:
            return
        else:
            self.is_browsing = True
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
        self.is_browsing = False
    
    def browse_file(self, entry_widget, settings_key, initialdir=None):
        """Browses a file location then set the value in the provided entry_widget and settings key of the user variables.
        Intialdir may be provided to set the initial directory of the browser."""
        if self.is_browsing:
            return
        else:
            self.is_browsing = True
        if initialdir is None:
            initialdir = "/".join(self.get_var(settings_key).split("/")[:-1])
        file_path = filedialog.askopenfilename(initialdir=initialdir)
        if file_path:
            entry_widget.config(state='normal')  # Enable the entry to modify it
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file_path)
            entry_widget.config(state='readonly')  # Set the entry back to read-only
            self.set_var(settings_key, file_path)
        self.is_browsing = False


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
    
    def create_new_folder(self, campaign_folder, widget, window):
        try:
            os.mkdir(f"./saves/{campaign_folder}")
        except FileExistsError:
            messagebox.showerror("Error", "Folder already exists!")
            return
        window.destroy()
        widget.config(state="normal")
        widget.delete(0, tk.END)
        widget.insert(0, campaign_folder)
        widget.config(state="readonly")
        self.set_var("Campaign Folder", campaign_folder)

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
        "Disable/restore elements state"
        if not self.disabled_tinkerable:
            tinkerable_state = [(element, str(element.cget('state'))) for element in self.tinkerable]
            for element in self.tinkerable:
                element.config(state=tk.DISABLED)
            self.tinkerable = tinkerable_state
        else:
            for element, state in self.tinkerable:
                element.config(state=state)
            self.tinkerable = [element for element, state in self.tinkerable]
        self.disabled_tinkerable = not self.disabled_tinkerable
                


class Main_Menu(tk.Tk, Garibaldi_gui):
    """
    Main menu for Garibaldi
    """
    def __init__(self):
        super().__init__()
        Garibaldi_gui.__init__(self)
        self.title("Garibaldi")
        self.stop_event = multiprocessing.Event()
        self.stop_event.clear()
        self.main_menu_gui()
        self.mainloop()
        self.stop_event.set() # Clear all existing threads when closing the program
    
    def main_menu_gui(self):
        """Generates the Main Menu"""
        frame1, extract_button = self.custom_size_button(self, text="Extract saves", command= lambda:self.on_click(SaveExtractor), width=200, height=120)
        frame2, analyze_button = self.custom_size_button(self, text="Analyze saves", command= lambda:self.on_click(SaveAnalyzer), width=200, height=120)
        frame3, watch_button = self.custom_size_button(self, text="Watch Saves", command= lambda:self.on_click(SaveWatcher), width=200, height=120)
        frame4, tree_button = self.custom_size_button(self, text="View Savefile", command= lambda:self.on_click(DictViewer), width=200, height=120)
        frame5, config_button = self.custom_size_button(self, text="Configure", command= lambda:self.on_click(Configure_windows), width=200, height=120)
        self.tinkerable = [extract_button, analyze_button, watch_button, tree_button, config_button]
        self.make_grid([[frame1], [frame2], [frame3], [frame4], [frame5]], 50, 10)
    
    def on_click(self, function):
        """Opens a new window and disables all main menu buttons"""
        self.toggle_tinkerable()
        new_window = function(self)
        self.after(500, self.check_no_child, new_window)

    def check_no_child(self, new_window):
        if new_window.winfo_exists():
            self.after(500, self.check_no_child, new_window)
            return
        self.stop_event.clear()
        self.toggle_tinkerable()
    


class SaveExtractor(tk.Toplevel, Garibaldi_gui):
    """
    Handles Save extractor menu
    TODO Make a failure popup box
    """
    def __init__(self, master):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Save Extractor")
        self.extractor_config()
        self.watch_thread = None
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.stop_event = master.stop_event
        self.finish_events = None
    
    def extractor_config(self):
        """Generates the SaveExtractor menu"""
        label_desc = ttk.Label(self, text="Extract saves in a campaign folder into Python dictionaries")
        
        self.del_var = tk.BooleanVar(self, value=False)
        label_del = ttk.Label(self, text="Delete the save file after extraction?")
        yes_radio = ttk.Radiobutton(self, text="Yes", variable=self.del_var, value=True)
        no_radio = ttk.Radiobutton(self, text="No", variable=self.del_var, value=False)

        label_folder = ttk.Label(self, text="Campaign Folder")
        entry_folder = ttk.Entry(self, width=50)
        entry_folder.insert(0, self.get_var("Campaign Folder"))
        entry_folder.config(state="readonly")

        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(entry_folder, "Campaign Folder", only_folder_name=True, initialdir="./saves"))

        self.var_thread = tk.IntVar(self, value=1)
        label_thread = ttk.Label(self, text="How many threads to perform extraction at once?")
        radio_1thread = ttk.Radiobutton(self, text="1", variable=self.var_thread, value=1)
        radio_2thread = ttk.Radiobutton(self, text="2", variable=self.var_thread, value=2)
        radio_3thread = ttk.Radiobutton(self, text="3", variable=self.var_thread, value=3)
        radio_4thread = ttk.Radiobutton(self, text="4", variable=self.var_thread, value=4)
        label_risk = ttk.Label(self, text="(AT YOUR OWN RISK)")

        self.ok_button = ttk.Button(self, text="Start", command=lambda: self.on_start())
        self.stop_button = ttk.Button(self, text="Stop", command=lambda: self.on_stop())
        self.stop_button.config(state=tk.DISABLED)

        self.tinkerable = [yes_radio, no_radio, browse_button, self.ok_button]
        self.make_grid([
            [label_desc],
            [label_del, yes_radio, no_radio],
            [label_folder, (entry_folder, 3, 'w'), (browse_button, 1, 'w')],
            [label_thread, radio_1thread, radio_2thread, radio_3thread, radio_4thread, label_risk],
            [self.ok_button, (None, 1), self.stop_button]
        ], 5, 10)
        self.after(100, self.end_task)
    
    def on_start(self):
        """Starts extraction and toggles all buttons in the SaveExtractor menu"""
        self.toggle_tinkerable()
        self.stop_event.clear()
        if self.del_var.get():
            proceed = messagebox.askyesno("Wait a sec", "Save files will be deleted after successfully extracted, would you like to proceed?")
            if not proceed:
                self.toggle_tinkerable()
                return
        self.stop_button.config(state=tk.NORMAL)
        
        campaign_folder = self.get_var("Campaign Folder")
        folders = glob.glob(f"./saves/{campaign_folder}/*.v3") + glob.glob(f"./saves/{campaign_folder}/*/")
        self.num_targets = len([f for f in folders if not is_reserved_folder(f)])
        self.completed = 0
        folders = [[folder for j, folder in enumerate(folders) if j % self.var_thread.get() == i] for i in range(self.var_thread.get())]
        print(folders)
        self.watch_thread = []
        self.finish_events = [multiprocessing.Event() for _ in range(len(folders))]
        self.queue = multiprocessing.Queue(self.var_thread.get())
        for finish_event, folder_set in zip(self.finish_events, folders):
            thread = multiprocessing.Process(target=extract_files, args=(campaign_folder, folder_set, self.stop_event, finish_event, self.queue, self.del_var.get()))
            self.watch_thread.append(thread)
            thread.start()
        self.after(1000, self.check_progress)
    
    def check_progress(self):
        try:
            value = self.queue.get(block=False)
            self.completed += value
            print(f"Progress: {self.completed}/{self.num_targets}")
        except queue.Empty:
            pass
        self.after(1000, self.check_progress)

    def on_stop(self):
        """Starts extraction and toggles all buttons in the SaveExtractor menu"""
        self.stop_event.set()

    
    def on_closing(self):
        """Handles closing the SaveExtractor menu"""
        self.on_stop()
        self.end_task()
        self.destroy()
    
    def end_task(self):
        if self.stop_event.is_set() or (self.finish_events is not None and all([event.is_set() for event in self.finish_events])):
            if self.watch_thread is not None:
                for thread in self.watch_thread:
                    thread.join()
            self.watch_thread = None
            self.finish_events = None
            self.toggle_tinkerable()
            self.stop_event.clear()
            self.stop_button.config(state=tk.DISABLED)
        self.after(500, self.end_task)


"""
TODO Put the interactive plots as an integrated element on GUI
"""

class SaveAnalyzer(tk.Toplevel, Garibaldi_gui):
    """
    Handles analysis and plotting
    """
    def __init__(self, master):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Save Analyzer")
        self.save_analyze_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.stop_event = master.stop_event
        self.finish_event = multiprocessing.Event()
        self.finish_event.clear()
    
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
        Start year _____  End year _____
                     | Start |                 | Stop |
        """
        grid = []

        def add_checker(text, showable=True):
            label = ttk.Label(self, text=text)
            check_var = tk.BooleanVar(self, value=True)
            show_var = tk.BooleanVar(self, value=False)
            show_button = ttk.Checkbutton(self, text="Show plot", variable=show_var, onvalue=True, offvalue=False)
            yes_button = ttk.Radiobutton(self, text="Yes", variable=check_var, value=True, command=lambda: show_button.config(state=tk.NORMAL))
            no_button = ttk.Radiobutton(self, text="No", variable=check_var, value=False, command=lambda: show_button.config(state=tk.DISABLED))
            if showable:
                grid.append([label, yes_button, no_button, show_button])
            else:
                grid.append([label, yes_button, no_button])
            return check_var, show_var
        
        header = ttk.Label(self, text="Plot the statistics of some variables and optionally show it on an interactive screen")
        
        label_campaign_folder = ttk.Label(self, text="Campaign Folder")
        self.folder_entry = ttk.Entry(self, width=50)
        self.folder_entry.insert(0, self.user_variables["Campaign Folder"])
        self.folder_entry.config(state="readonly")
        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(self.folder_entry, "Campaign Folder", "./saves", only_folder_name=True))
        make_folder_button = ttk.Button(self, text="New Folder", command=lambda: self.new_window_entry(self, self.create_new_folder, self.folder_entry, "Create new campaign folder"))
        
        label_check = ttk.Label(self, text="Select which stats do you want to extract from the saves and plot?")
        self.check_list = dict()
        self.check_list["construction"] = add_checker("Construction")
        self.check_list["avg_cost"] = add_checker("Average Construction Cost")
        self.check_list["GDP"] = add_checker("Finance")
        self.check_list["innovation"] = add_checker("Innovation")
        self.check_list["capped_innovation"] = add_checker("Capped Innovation")
        self.check_list["infamy"] = add_checker("Infamy")
        self.check_list["literacy"] = add_checker("Demographics")
        self.check_list["total_prestige"] = add_checker("Prestige")
        self.check_list["production_techs"] = add_checker("Production Techs")
        self.check_list["military_techs"] = add_checker("Military Techs")
        self.check_list["society_techs"] = add_checker("Society Techs")
        self.check_list["total_techs"] = add_checker("Total Techs")
        self.check_list["goods_produced"] = add_checker("Goods Produced")

        warning_goods = ttk.Label(self, text="Note: We can only either not show or show ALL types of goods produced on interactive windows.")

        self.start_date_label = ttk.Label(self, text="Start year")
        self.start_date_entry = ttk.Entry(self, width=30)
        self.start_date_entry.insert(0, "1836")
        self.end_date_label = ttk.Label(self, text="End year")
        self.end_date_entry = ttk.Entry(self, width=30)
        self.end_date_entry.insert(0, "1984")

        self.ok_button = ttk.Button(self, text="Run", command=lambda: self.on_ok())
        self.stop_button = ttk.Button(self, text="Stop", command=lambda: self.on_stop())
        self.stop_button.config(state=tk.DISABLED)

        self.tinkerable = [browse_button, make_folder_button] + [a for b in grid for a in b] + [self.ok_button] # Checker buttons
        self.make_grid([
             [(header, 5, 'w')],
             [label_campaign_folder, self.folder_entry, browse_button, make_folder_button],
             [(label_check, 3, 'w')]] 
          + grid
          + [[(warning_goods, 7, 'w')], 
             [self.start_date_label, self.start_date_entry, self.end_date_label, self.end_date_entry],
             [self.ok_button, (None, 1), self.stop_button]], 10, 10) # Checker buttons
        self.after(500, self.end_task)

    def on_ok(self):
        self.toggle_tinkerable()
        checkers = []
        showers = []
        for checker, checkbox in self.check_list.items():
            check_var, show_var = [c.get() for c in checkbox]
            if check_var:
                checkers.append(checker)
            if show_var:
                showers.append(checker)
        self.after(100, perform_checking, checkers, showers, self.folder_entry.get(), self.stop_event, self.finish_event)
        self.stop_button.config(state=tk.NORMAL)
        # self.watch_thread = threading.Thread(target=perform_checking, args=(checkers, showers, self.folder_entry.get(), self.stop_event))
        # self.watch_thread.start()

    
    def on_closing(self):
        """Handles closing the SaveAnalyzer menu"""
        self.on_stop()
        self.end_task()
        self.destroy()
    
    def on_stop(self):
        self.stop_event.set()
    
    def end_task(self):
        """Checks if checking is done/terminated and restore the menu state"""
        """If finish event is raised but not stop_event, we proceed to draw plotting"""
        if self.stop_event.is_set() and self.finish_event.is_set():
            self.finish_event.clear()
            self.toggle_tinkerable()
            self.stop_event.clear()
            self.stop_button.config(state=tk.DISABLED)
        self.after(500, self.end_task)


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
        self.watch_thread = None
    
    def save_watch_settings(self):
        """Generates the SaveWatcher menu"""
        
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

        label5 = ttk.Label(self, text="Campaign Folder")
        self.folder_entry = ttk.Entry(self, width=50)
        self.folder_entry.insert(0, self.get_var("Campaign Folder"))
        self.folder_entry.config(state="readonly")
        browse_button_2 = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(self.folder_entry, "Campaign Folder", "./saves", only_folder_name=True))
        make_folder_button = ttk.Button(self, text="New Folder", command=lambda: self.new_window_entry(self, self.create_new_folder, self.folder_entry, "Create new campaign folder"))

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
        self.stop_button.config(state=tk.NORMAL)
        self.toggle_tinkerable()
        self.watch_thread = multiprocessing.Process(target=watch_save, args=(self.get_var("Autosave Location"), self.folder_entry.get(), self.stop_event, n_saves))
        self.watch_thread.start()
    
    def on_stop(self):
        """Stops watching and toggles all buttons in the SaveWatcher menu"""
        self.stop_event.set()
        if self.watch_thread is not None:
            self.watch_thread.join()
        self.watch_thread = None
        self.stop_button.config(state=tk.DISABLED)
        self.toggle_tinkerable()
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
        """Return the size of an object and all others objects constituting its tree
        TODO More efficient handling by get_size lower level branches and store values for get_size of higher level branches"""
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
        for key in ["Common Directory", "Events Directory", "Localization Directory", "Mod Directory"]:
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
    - May not be necessary now
"""