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
    Define functions commonly used by all gui windows
    """
    def __init__(self):
        super().__init__()
        self.user_variables = jopen("./user_variables.json")
        self.variables = jopen("./scripts/variables.json")
    
    def get_var(self, key):
        if key not in self.user_variables:
            self.set_var(key, self.variables["default_directories"][key])
        return self.user_variables[key]
    
    def set_var(self, key, value):
        self.user_variables[key] = value
        self.save_settings()

    def browse_folder(self, entry_widget, settings_key, initialdir=None, only_folder_name=False):
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
        entry_widget.config(state='normal')  # Enable the entry to modify it
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, self.variables["default_directories"][settings_key])
        entry_widget.config(state='readonly')  # Set the entry back to read-only
        self.set_var(settings_key, self.variables["default_directories"][settings_key])

    def save_settings(self):
        with open("./user_variables.json", 'w') as file:
            json.dump(self.user_variables, file, indent=4)
    
    def custom_size_button(self, root, text, command, width, height):
        frame = tk.Frame(root, width=width, height=height)
        frame.pack_propagate(False)  # Prevent frame from resizing to fit its contents
        button = ttk.Button(frame, text=text, command=command)
        button.pack(expand=True, fill=tk.BOTH)
        return frame, button
    
    def new_window_entry(self, root, on_click, target, title):
        window = tk.Toplevel(root)
        window.title(title)
        entry = tk.Entry(window, width=50)
        entry.grid(row=0, column=0, padx=50, pady=10)
        button = tk.Button(window, text="Ok", command=lambda: on_click(entry.get(), target, window))
        button.grid(row=1, column=0, padx=50, pady=10)


class Main_Menu(tk.Tk, Garibaldi_gui):
    """
    Main menu for Garibaldi
    """
    def __init__(self):
        super().__init__()
        Garibaldi_gui.__init__(self)
        self.title("Garibaldi")
        self.main_menu_gui()
        self.mainloop()
    
    def main_menu_gui(self):
        frame, extract_button = self.custom_size_button(self, text="Extract saves", command= lambda:self.on_click(SaveExtractor), width=200, height=120)
        frame.grid(row=0, column=0, padx=50, pady=10)
        frame, watch_button = self.custom_size_button(self, text="Watch Saves", command= lambda:self.on_click(SaveWatcher), width=200, height=120)
        frame.grid(row=1, column=0, padx=50, pady=10)
        frame, tree_button = self.custom_size_button(self, text="View Savefile", command= lambda:self.on_click(DictViewer), width=200, height=120)
        frame.grid(row=2, column=0, padx=50, pady=10)
        frame, config_button = self.custom_size_button(self, text="Configure", command= lambda:self.on_click(Configure_windows), width=200, height=120)
        frame.grid(row=3, column=0, padx=50, pady=10)
        self.tinkerable = [extract_button, watch_button, tree_button, config_button]
    
    def on_click(self, function):
        for button in self.tinkerable:
            button.config(state=tk.DISABLED)
        new_window = function(self)
        self.wait_window(new_window)
        for button in self.tinkerable:
            button.config(state=tk.NORMAL)

class SaveExtractor(tk.Toplevel, Garibaldi_gui):
    """
    Handles Save extractor menu
    """
    def __init__(self, master):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Save Extractor")
        self.extractor_config()
    
    def extractor_config(self):
        ttk.Label(self, text="Extract saves in a campaign folder").grid(row=0, column=0, padx=10, pady=10)
        
        self.del_var = tk.IntVar(self, value=0)
        ttk.Label(self, text="Delete the save file after extraction?").grid(row=0, column=0, padx=10, pady=10)
        yes_radio = ttk.Radiobutton(self, text="Yes", variable=self.del_var, value=1)
        yes_radio.grid(row=0, column=1, padx=0, pady=5, sticky='w')
        no_radio = ttk.Radiobutton(self, text="No", variable=self.del_var, value=0)
        no_radio.grid(row=0, column=2, padx=0, pady=5, sticky='w')

        ttk.Label(self, text="Campaign Folder").grid(row=1, column=0, padx=10, pady=10)
        settings_entry = ttk.Entry(self, width=50)
        settings_entry.insert(0, self.get_var("Campaign Folder"))
        settings_entry.config(state="readonly")
        settings_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=10, sticky='w')
        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(settings_entry, "Campaign Folder", only_folder_name=True))
        browse_button.grid(row=1, column=4, padx=5, pady=10, sticky='w')

        self.ok_button = ttk.Button(self, text="Start", command=lambda: self.start_extraction())
        self.ok_button.grid(row=2, column=1, padx=5, pady=10)
        self.stop_button = ttk.Button(self, text="Stop", command=lambda: self.start_extraction())
        self.stop_button.grid(row=2, column=3, padx=5, pady=10)
        self.stop_button.config(state=tk.DISABLED)

        self.tinkerable = [yes_radio, no_radio, browse_button, self.ok_button]
    
    def start_extraction(self):
        if self.del_var == 1:
            proceed = messagebox.askyesno("Save files will be deleted after successfully extracted, would you like to procees?")
            if not proceed:
                return
        del_var = bool(self.del_var)
        self.stop_button.config(state=tk.NORMAL)
        for element in self.tinkerable:
            element.config(state=tk.DISABLED)
        self.stop_event = threading.Event()
        self.stop_event.clear()
        self.watch_thread = threading.Thread(target=extract_all_files, args=(self.get_var("Campaign Folder"), self.stop_event, del_var))
        self.watch_thread.start()
    
    def stop_extraction(self):
        self.stop_event.set()
        self.watch_thread.join()
        self.stop_button.config(state=tk.DISABLED)
        for element in self.tinkerable:
            element.config(state=tk.NORMAL)


class SaveWatcher(tk.Toplevel, Garibaldi_gui):
    """
    Handles Save watcher menu
    """
    def __init__(self, master):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Save Watcher")
        self.save_watch_settings()
    
    def save_watch_settings(self):
        def create_new_folder(campaign_folder, widget, window):
            try:
                os.mkdir(f"./saves/{campaign_folder}")
            except FileExistsError:
                pass
            window.destroy()
            widget.config(state="normal")
            widget.delete(0, tk.END)
            widget.insert(0, f"./saves/{campaign_folder}")
            widget.config(state="readonly")
            self.set_var("Campaign Folder", f"./saves/{campaign_folder}")
        
        ttk.Label(self, text="Watch the autosave file and copy it to the target campaign folder when modified").grid(row=0, column=0, padx=10, pady=20, sticky='w', columnspan=3)
        ttk.Label(self, text="Copy every").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        self.freq_settings = ttk.Entry(self, width=65)
        self.freq_settings.grid(row=1, column=1, padx=10, pady=10, columnspan=2)
        self.freq_settings.insert(0, "1")
        ttk.Label(self, text="autosave(s)").grid(row=1, column=3, padx=10, pady=10, sticky='w')
        
        ttk.Label(self, text="Autosave Location").grid(row=2, column=0, padx=10, pady=10, sticky='w')
        autosave_entry = ttk.Entry(self, width=65)
        autosave_entry.grid(row=2, column=1, padx=10, pady=10, columnspan=2)
        autosave_entry.insert(0, self.get_var("Autosave Location"))
        autosave_entry.config(state="readonly")
        browse_button_1 = ttk.Button(self, text="Browse", command=lambda: self.browse_file(autosave_entry, "Autosave Location"))
        browse_button_1.grid(row=2, column=3, padx=2, pady=10)

        ttk.Label(self, text="Campaign Folder").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        self.folder_entry = ttk.Entry(self, width=50)
        self.folder_entry.grid(row=3, column=1, padx=10, pady=10, columnspan=1)
        self.folder_entry.insert(0, "./saves/autosaves")
        self.folder_entry.config(state="readonly")
        browse_button_2 = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(self.folder_entry, "Campaign Folder", "./saves"))
        browse_button_2.grid(row=3, column=2, padx=2, pady=10)
        make_folder_button = ttk.Button(self, text="New Folder", command=lambda: self.new_window_entry(self, create_new_folder, self.folder_entry, "Create new campaign folder"))
        make_folder_button.grid(row=3, column=3, padx=2, pady=10)

        self.ok_button = ttk.Button(self, text="Run", command=lambda: self.on_ok())
        self.ok_button.grid(row=4, column=1, padx=2, pady=10)

        self.stop_button = ttk.Button(self, text="Stop", command=lambda: self.on_stop())
        self.stop_button.grid(row=4, column=2, padx=2, pady=10)
        self.stop_button.config(state=tk.DISABLED)

        self.tinkerable = [self.ok_button, self.freq_settings, browse_button_1, browse_button_2, make_folder_button]

    def on_ok(self):
        try:
            n_saves = int(self.freq_settings.get())
        except:
            messagebox.showerror("Error", "Invalid input!")
            return
        self.ok_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        for element in self.tinkerable:
            element.config(state=tk.DISABLED)
        self.stop_event = threading.Event()
        self.stop_event.clear()
        self.watch_thread = threading.Thread(target=watch_save, args=(self.get_var("Autosave Location"), self.folder_entry.get(), self.stop_event, n_saves))
        self.watch_thread.start()
    
    def on_stop(self):
        self.stop_event.set()
        self.watch_thread.join()
        self.ok_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        for element in self.tinkerable:
            element.config(state=tk.NORMAL)


class DictViewer(tk.Toplevel, Garibaldi_gui):
    """
    Handles Save Viewer menu and tree view
    """
    def __init__(self, master, preprocessor=None):
        super().__init__(master)
        Garibaldi_gui.__init__(self)
        self.title("Settings Viewer App")
        self.geometry("600x400")
        self.preprocessor = preprocessor
        self.create_settings_window()

    def get_size(self, obj):
        if isinstance(obj, dict):
            return sum(self.get_size(v) for v in obj.values())
        elif isinstance(obj, list):
            return sum(self.get_size(v) for v in obj)
        else:
            return sys.getsizeof(obj)

    def create_settings_window(self):
        self.size_var = tk.IntVar(value=0)
        
        ttk.Label(self, text="Get the object size?").grid(row=0, column=0, padx=10, pady=10)
        yes_radio = ttk.Radiobutton(self, text="Yes", variable=self.size_var, value=1)
        yes_radio.grid(row=0, column=1, padx=0, pady=5, sticky='w')
        no_radio = ttk.Radiobutton(self, text="No", variable=self.size_var, value=0)
        no_radio.grid(row=0, column=2, padx=0, pady=5, sticky='w')

        ttk.Label(self, text="File location").grid(row=3, column=0, padx=10, pady=10, sticky='w')
        settings_entry = ttk.Entry(self, width=50)
        settings_entry.insert(0, self.get_var("Tree File Location"))
        settings_entry.config(state="readonly")
        settings_entry.grid(row=3, column=1, columnspan=10, padx=0, pady=10, sticky='w')
        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_file(settings_entry, "Tree File Location"))
        browse_button.grid(row=3, column=11, padx=0, pady=10, sticky='w')

        ok_button = ttk.Button(self, text="OK", command=self.on_ok)
        ok_button.grid(row=4, column=0, padx=10, pady=10)

    def on_ok(self):
        if not os.path.isfile(self.get_var("Tree File Location")):
            messagebox.showerror("Invalid Directory", "The selected directory is not valid. Please choose a valid directory.")
        else:
            self.show_size = self.size_var.get() == 1
            self.create_tree_viewer()

    def create_tree_viewer(self):
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