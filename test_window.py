import tkinter as tk
from tkinter import ttk
import json

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
            if isinstance(value, dict):
                # Insert the parent node collapsed
                node = self.tree.insert(parent, 'end', text=key, open=False)
                # Recursively populate the tree with the nested dictionary
                self.populate_tree(node, value)
            elif isinstance(value, list):
                # Insert the parent node collapsed
                node = self.tree.insert(parent, 'end', text=key, open=False)
                for item in value:
                    self.tree.insert(node, 'end', text=str(item))
            else:
                # Insert a leaf node
                self.tree.insert(parent, 'end', text=f"{key}: {value}")

# Sample dictionary to visualize
with open("./save files/save_output_interest_groups.json") as file:
    data = json.load(file)
with open("./common_json/mobilization_options/00_mobilization_option.json") as file:
    data = json.load(file)

# Run the application
if __name__ == "__main__":
    app = DictViewer(data)
    app.mainloop()
