"""
Whatever functions written to help the program.
"""
import sys, os, shutil, fnmatch, pickle, gzip, glob, json, re
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
    """
    Opens a gzip file.
    """
    with gzip.open(address, 'rb') as f:
        return pickle.load(f)

def jopen(address:str):
    """
    Opens a json file.
    """
    with open(address, "r") as file:
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

def retrieve_from_tree(tree:dict, directory:list, null=None):
    """
    Retrieve a value from a nested dictionary (tree) using a list of keys (directory).

    Returns:
        The value found at the specified directory path, or value specified in 'null' (default None) if any key in the path does not exist in the tree.

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
            return null
        current = current[subdir]
    return current

def load_def(address, mode="Common Directory"):
    """
    Load a define (content) script
    """
    user_variables = jopen("./user_variables.json")
    address = user_variables[mode] + "/" + address
    data = Extractor(address)
    data.unquote()
    data = data.data
    return data

def load_def_multiple(folder, mode="Common Directory", depth_add=0):
    """
    Load a define (content) script from the vanilla folder, and then its mod counterpart if exists.
    depth_add (int): The maximum depth the content dict to have the subsequent files' dict's content
    added inside instead of completely clearing the existing content
    """
    user_variables = jopen("./user_variables.json")
    def_folder = user_variables[mode] + "/" + folder
    defs = dict()
    for address in glob.glob(f"{def_folder}/*.txt"):
        data = Extractor(address)
        data.unquote()
        data = data.data
        if depth_add == 0:
            defs.update(data)
        else:
            for key, value in data.items():
                if isinstance(value, dict) and key in defs:
                    defs[key].update(value)
                else:
                    defs[key] = value

    if user_variables["Mod Directory"] and os.path.isdir(user_variables["Mod Directory"] + "//common//" + folder):
        """
        FIXME Replace //common// with mode and properly implement depth_add
        """
        for address in glob.glob(user_variables["Mod Directory"] + "//common//" + folder + "//*.txt"):
            data = Extractor(address)
            data.unquote()
            data = data.data
            if depth_add == 0:
                defs.update(data)
            else:
                for key, value in data.items():
                    if isinstance(value, dict) and key in defs:
                        defs[key].update(value)
                    else:
                        defs[key] = value

    return defs


def load_save(topics:list, address:str):
    """
    Load a subset of information from a save file or pre-extracted data files

    Returns a dictionary of data according to the specified topic
    Elements of topics that aren't strings are ignored.
    """
    if len(topics) == 0: #
        return dict()
    topics_original = topics.copy()
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
        elif not isinstance(topic, str): # results of resolve compatibility of unimplemented variables
            topics.pop(topics.index(topic))
    if len(topics) > 0:
        raise FileNotFoundError(f"Failed to load {topics} from {address}.")
    print(f"Finished loading {topics_original} from {address} in {time.time() - t0} seconds")
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
            dest = f"./saves/{campaign_folder}/{save.replace('.txt', '')}/save.txt"
            try:
                os.mkdir(f"./saves/{campaign_folder}/{save.replace('.txt', '')}")
            except FileExistsError:
                pass
            shutil.move(source, dest)

def date_to_day(date:str):
    """
    Get the number of days passed since the start of the year to the current date
    """
    year, month, day = date.split(".")[:3]
    year, month, day = int(year), int(month), int(day)
    def_month = {1:0, 2:31, 3:59, 4:90, 5:120, 6:151, 7:181, 8:212, 9:243, 10:273, 11:304, 12:334}
    if year % 4 == 0 and not year % 100 == 0:
        for i in range(3, 13):
            def_month[i] += 1
    return def_month[month] + day

def get_duration(this_date, start_date, end_date=None):
    """
    Get duration since start date (if end_date isn't provided) and the total duration and the fraction of time since start_date
    Doesn't exactly follow the calendar format so subject to ~1% inaccuracy
    This function operates date in list format [year, month, day], but can and will convert str date to that format.
    """
    if isinstance(this_date, str):
        this_date = [int(i) for i in this_date.split(".")][:3]
    if isinstance(start_date, str):
        start_date = [int(i) for i in start_date.split(".")][:3]
    duration_from_start = (this_date[0] - start_date[0]) + (date_to_day(this_date) - date_to_day(start_date)) / 365.2422
    if end_date is not None:
        if isinstance(end_date, str):
            end_date = [int(i) for i in end_date.split(".")][:3]
        total_duration = (end_date[0] - start_date[0]) + (date_to_day(end_date) - date_to_day(start_date)) / 365.2422
        return duration_from_start, total_duration, duration_from_start / total_duration
    else:
        return duration_from_start

def walk_tree(tree:dict, target, path:list=[]):
    """
    Check if there is a key existing in any end part of the tree
    Return a list of keys relative to the root dictionary
    """
    root = path.copy()
    leaves = []
    for key, value in tree.items():
        if key == target:
            leaves.append(root + [target]) 
        if isinstance(value, dict):
            leaves += walk_tree(value, target, root + [key])
    return leaves

def is_reserved_folder(folder):
    return re.split(r"[\\/]", folder.strip("\\/"))[-1] in ["campaign_data", "archive"]