import json, sys, os
from extractor import Extractor

def jopen(address:str):
    with open(address) as file:
        return json.load(file)

def get_all_possible_keys(data:dict):
    """
    Retrieve a list of all unique keys of member dictionaries in a dictionary.
    """
    unique_keys = set()
    for k, v in data.items():
        if isinstance(v, dict):
            for kv, vv in v.items():
                unique_keys.add(kv)
    return unique_keys

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

def retrieve_from_tree(tree:dict, directory:list):
    """
    Retrieve a value from a nested dictionary (tree) using a list of keys (directory).

    Returns:
        The value found at the specified directory path, or None if any key in the path does not exist in the tree.

    Example:
        tree = {'a': {'b': {'c': 'value'}}}
        directory = ['a', 'b', 'c']
        result = retrieve_from_tree(tree, directory)  # result will be 'value'
    """
    current = tree
    for subdir in directory:
        if subdir not in current:
            return None
        current = tree[subdir]
    return current

def load(topics:list, address:str=None):
    """
    Load a subset of information from a save file or pre-extracted json files
    """
    if address is not None:
        data = Extractor(address, topics)
        data.unquote()
        data = data.data
    elif "save_output_all.json" in os.listdir("./save files"):
        data = jopen("./save files/save_output_all.json")
    else:
        data = dict()
        for topic in topics:
            data.update(jopen(f"./save files/save_output_{topic}.json"))
    return (topic for k, topic in data.items())