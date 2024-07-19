import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from scripts.helpers.utility import *
from scripts.helpers.save_watch import *
import sys, json, os, threading

class Garibaldi_gui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.user_variables = jopen("./user_variables.json")
        self.variables = jopen("./scripts/variables.json")
    
    def browse_folder(self, entry_widget, settings_key, initialdir=None, save_settings=True):
        if initialdir is None:
            initialdir = "/".join(self.user_variables[settings_key].split("/")[:-1])
        folder_path = filedialog.askdirectory(initialdir=initialdir)
        if folder_path:
            entry_widget.config(state='normal')  # Enable the entry to modify it
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder_path)
            entry_widget.config(state='readonly')  # Set the entry back to read-only
            self.user_variables[settings_key] = folder_path
            if save_settings:
                self.save_settings()
    
    def browse_file(self, entry_widget, settings_key, initialdir=None, save_settings=True):
        if initialdir is None:
            initialdir = "/".join(self.user_variables[settings_key].split("/")[:-1])
        file_path = filedialog.askopenfilename(initialdir=initialdir)
        if file_path:
            entry_widget.config(state='normal')  # Enable the entry to modify it
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file_path)
            entry_widget.config(state='readonly')  # Set the entry back to read-only
            self.user_variables[settings_key] = file_path
            if save_settings:
                self.save_settings()

    def restore_defaults(self, entry_widget, settings_key):
        entry_widget.config(state='normal')  # Enable the entry to modify it
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, self.variables["default_directories"][settings_key])
        entry_widget.config(state='readonly')  # Set the entry back to read-only
        self.user_variables[settings_key] = self.variables["default_directories"][settings_key]
        self.save_settings()

    def save_settings(self):
        with open("./user_variables.json", 'w') as file:
            json.dump(self.user_variables, file, indent=4)


class DictViewer(Garibaldi_gui):
    def __init__(self, preprocessor=None):
        super().__init__()
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
        settings_entry.insert(0, self.user_variables["Tree File Location"])
        settings_entry.config(state="readonly")
        settings_entry.grid(row=3, column=1, columnspan=10, padx=0, pady=10, sticky='w')
        settings_entry.insert(0, "your file location")
        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_file(settings_entry, "Tree File Location"))
        browse_button.grid(row=3, column=11, padx=0, pady=10, sticky='w')

        ok_button = ttk.Button(self, text="OK", command=self.on_ok)
        ok_button.grid(row=4, column=0, padx=10, pady=10)

    def on_ok(self):
        if not os.path.isfile(self.user_variables["Tree File Location"]):
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
        data = zopen(self.user_variables["Tree File Location"])
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
            
class Configure_windows(Garibaldi_gui):
    def __init__(self) -> None:
        super().__init__()
        self.title("Configure settings")
        self.n_entries = 0
        for key in ["Common Directory", "Events Directory", "Localization Directory"]:
            self.add_directory_settings(key)
    
    def add_directory_settings(self, target):
        ttk.Label(self, text=target).grid(row=self.n_entries, column=0, padx=10, pady=10, sticky='e')
        settings_entry = ttk.Entry(self, width=50)
        settings_entry.grid(row=self.n_entries, column=1, padx=10, pady=10)
        settings_entry.insert(0, self.user_variables[target])
        settings_entry.config(state="readonly")
        browse_button = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(settings_entry, target))
        browse_button.grid(row=self.n_entries, column=2, padx=2, pady=10)
        reset_button = ttk.Button(self, text="Restore Defaults", command=lambda: self.restore_defaults(settings_entry, target))
        reset_button.grid(row=self.n_entries, column=3, padx=2, pady=10)
        self.n_entries += 1

class SaveWatcher(Garibaldi_gui):
    def __init__(self):
        super().__init__()
        self.title("Save Watcher")
        self.save_watch_settings()
    
    def save_watch_settings(self):
        ttk.Label(self, text="Copy every").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        self.freq_settings = ttk.Entry(self, width=50)
        self.freq_settings.grid(row=0, column=1, padx=10, pady=10, columnspan=2)
        self.freq_settings.insert(0, "1")
        ttk.Label(self, text="autosave(s)").grid(row=0, column=3, padx=10, pady=10, sticky='w')
        
        ttk.Label(self, text="Autosave Location").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        autosave_entry = ttk.Entry(self, width=50)
        autosave_entry.grid(row=1, column=1, padx=10, pady=10, columnspan=2)
        autosave_entry.insert(0, self.user_variables["Autosave Location"])
        autosave_entry.config(state="readonly")
        browse_button_1 = ttk.Button(self, text="Browse", command=lambda: self.browse_file(autosave_entry, "Autosave Location"))
        browse_button_1.grid(row=1, column=3, padx=2, pady=10)

        ttk.Label(self, text="Campaign Folder").grid(row=2, column=0, padx=10, pady=10, sticky='w')
        folder_entry = ttk.Entry(self, width=50)
        folder_entry.grid(row=2, column=1, padx=10, pady=10, columnspan=2)
        folder_entry.insert(0, "")
        folder_entry.config(state="readonly")
        browse_button_2 = ttk.Button(self, text="Browse", command=lambda: self.browse_folder(folder_entry, "Campaign Folder", "./saves"))
        browse_button_2.grid(row=2, column=3, padx=2, pady=10)

        self.ok_button = ttk.Button(self, text="Run", command=lambda: self.on_ok())
        self.ok_button.grid(row=3, column=1, padx=2, pady=10)

        self.cancel_button = ttk.Button(self, text="Stop", command=lambda: self.on_stop())
        self.cancel_button.grid(row=3, column=2, padx=2, pady=10)
        self.cancel_button.config(state=tk.DISABLED)

        self.tinkerable = [self.ok_button, self.freq_settings, browse_button_1, browse_button_2]

    def on_ok(self):
        try:
            n_saves = int(self.freq_settings.get())
        except:
            messagebox.showerror("Error", "Invalid input!")
            return
        self.ok_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        for element in self.tinkerable:
            element.config(state=tk.DISABLED)
        self.stop_event = threading.Event()
        self.stop_event.clear()
        self.watch_thread = threading.Thread(target=watch_save, args=(self.user_variables["Autosave Location"], self.user_variables["Campaign Folder"], self.stop_event, n_saves))
        self.watch_thread.start()
    
    def on_stop(self):
        self.stop_event.set()
        self.watch_thread.join()
        self.ok_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        for element in self.tinkerable:
            element.config(state=tk.NORMAL)