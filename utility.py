import json, sys, os, shutil, fnmatch
from extractor import Extractor
import time, functools

def t_execute(func):
    @functools.wraps(func)
    def return_func(*args, **kwargs):
        start = time.time()
        out = func(*args, **kwargs)
        length = time.time() - start
        print(f"Length of time used by {func.__name__}: {length} seconds")
        return out

    return return_func

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
        current = current[subdir]
    return current

def load_def(address):
    """
    Load a define (content) script
    """
    data = Extractor(address)
    data.unquote()
    data = data.data
    return data

def load_save(topics:list, address:str, save=False):
    """
    Load a subset of information from a save file or pre-extracted json files

    Returns a dictionary of data according to the specified topic

    May optionally save a loaded result from the Extractor into a json
    """
    topics = topics.copy()
    t0 = time.time()
    data_output = dict()
    for i, topic in enumerate(topics):
        if f"save_output_{topic}.json" in os.listdir(address):
            data_output[topic] = jopen(f"{address}/save_output_{topic}.json")[topic]
            topics.pop(i)
    if len(topics) > 0:
        if "save_output_all.json" in os.listdir(address):
            data = jopen("./saves/save_output_all.json")
        else:
            data = Extractor(f"{address}/save.txt", topics.copy())
            data.unquote()
            if save:
                data.dump_json(f"{address}/save_output", separate=True)
            data = data.data
        for topic in topics:
            data_output[topic] = data[topic]
    print(f"Finished loading in {time.time() - t0} seconds")
    return data_output

def make_save_dirs(campaign_folder):
    "Make a folder for each individual save in a campaign folder"
    saves = os.listdir(f"./saves/{campaign_folder}")
    try:
        os.mkdir(f"./saves/{campaign_folder}/campaign_data")
    except FileExistsError:
        pass
    for save in saves:
        if fnmatch.fnmatch(save, "*.txt"):
            source = f"./saves/{campaign_folder}/{save}"
            dest = f"./saves/{campaign_folder}/{save.replace(".txt", "")}/save.txt"
            os.mkdir(f"./saves/{campaign_folder}/{save.replace(".txt", "")}")
            shutil.move(source, dest)