import tkinter as tk
from tkinter import ttk
from scripts.helpers.utility import zopen
import sys

    
def get_size(obj, seen=None):
    """Recursively finds the size of objects."""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    if isinstance(obj, dict):
        size += sum([get_size(v, seen) for v in obj.values()])
        size += sum([get_size(k, seen) for k in obj.keys()])
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum([get_size(i, seen) for i in obj])
    return size

class DictViewer(tk.Tk):
    def __init__(self, dictionary):
        super().__init__()
        self.title("Dictionary Viewer")
        self.geometry("600x400")

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

        # Populate the treeview with the dictionary content
        self.populate_tree("", dictionary)


    def populate_tree(self, parent, dictionary):
        for key, value in dictionary.items():
            size = get_size(value)
            if isinstance(value, dict):
                # Insert the parent node collapsed
                node = self.tree.insert(parent, 'end', text=f"{key} ({size} bytes)", open=False)
                # Recursively populate the tree with the nested dictionary
                self.populate_tree(node, value)
            elif isinstance(value, list):
                # Insert the parent node collapsed
                node = self.tree.insert(parent, 'end', text=f"{key} ({size} bytes)", open=False)
                for item in value:
                    item_size = get_size(item)
                    self.tree.insert(node, 'end', text=f"{str(item)} ({item_size} bytes)")
            else:
                # Insert a leaf node
                self.tree.insert(parent, 'end', text=f"{key}: {value} ({size} bytes)")
                
# Sample dictionary to visualize
data = zopen("your/extracted/save/file.gz")

# Run the application
if __name__ == "__main__":
    app = DictViewer(data)
    app.mainloop()
