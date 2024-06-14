import sys, os, shutil, fnmatch, pickle, gzip, glob
from scripts.extractor import Extractor
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

def zopen(address:str):
    with gzip.open(address, 'rb') as f:
        return pickle.load(f)

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
    if isinstance(directory, str):
        directory = [directory]
    for subdir in directory:
        if not isinstance(current, dict) or subdir not in current:
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

def load_def_multiple(folder):
    """
    Load a define (content) script
    """
    defs = dict()
    for address in glob.glob(f"{folder}/*.txt"):
        data = Extractor(address)
        data.unquote()
        data = data.data
        defs.update(data)
    return defs


def load_save(topics:list, address:str, save=False):
    """
    Load a subset of information from a save file or pre-extracted data files

    Returns a dictionary of data according to the specified topic

    save: May optionally save a loaded result from the Extractor
    """
    topics = topics.copy()
    t0 = time.time()
    data_output = dict()
    if "extracted_save" not in os.listdir(address):
        os.mkdir(f"{address}/extracted_save")
    if "miscellaneous.gz" in os.listdir(f"{address}/extracted_save"):
        miscellaneous = zopen(f"{address}/extracted_save/miscellaneous.gz")
    else:
        miscellaneous = dict()
    for topic in topics.copy():
        if f"{topic}.gz" in os.listdir(f"{address}/extracted_save"):
            data_output[topic] = zopen(f"{address}/extracted_save/{topic}.gz")[topic]
            topics.pop(topics.index(topic))
        elif topic in miscellaneous:
            data_output[topic] = miscellaneous[topic]
            topics.pop(topics.index(topic))
    if len(topics) > 0:
        if "full.gz" in os.listdir(f"{address}/extracted_save"):
            data = zopen(f"{address}/extracted_save/full.gz")
        else:
            try:
                data = Extractor(f"{address}/save.txt", topics.copy())
            except FileNotFoundError:
                raise FileNotFoundError(f"Unable to locate {address}/save.txt while attempting to load {topics}")
            data.unquote()
            if save:
                data.write(address, separate=True)
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
            try:
                os.mkdir(f"./saves/{campaign_folder}/{save.replace(".txt", "")}")
            except FileExistsError:
                pass
            shutil.move(source, dest)

def rename_folder_to_date(campaign_folder):
    campaign_folder = f"saves/{campaign_folder}"
    for folder in os.listdir(campaign_folder):
        if "campaign_data" in folder:
            continue
        save_folder = f"{campaign_folder}/{folder}"
        metadata = load_save(["meta_data"], save_folder)
        year, month, day = metadata["meta_data"]["game_date"].split(".")
        new_name = f"{campaign_folder.split("/")[-1]}_{year}_{month}_{day}"
        os.rename(save_folder, f"{campaign_folder}/{new_name}")

def get_save_date(save_folder):
    metadata = load_save(["meta_data"], save_folder)
    year, month, day = metadata["meta_data"]["game_date"].split(".")
    return year, month, day