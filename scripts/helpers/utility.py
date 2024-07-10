import sys, os, shutil, fnmatch, pickle, gzip, glob, json
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

def jopen(address:str):
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
            return null
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
            dest = f"./saves/{campaign_folder}/{save.replace('.txt', '')}/save.txt"
            try:
                os.mkdir(f"./saves/{campaign_folder}/{save.replace('.txt', '')}")
            except FileExistsError:
                pass
            shutil.move(source, dest)

def rename_folder_to_date(campaign_folder):
    campaign_folder = f"saves/{campaign_folder}"
    for folder in os.listdir(campaign_folder):
        if "campaign_data" in folder or "." in folder:
            continue
        save_folder = f"{campaign_folder}/{folder}"
        year, month, day = get_save_date(save_folder)
        new_name = f"{campaign_folder.split('/')[-1]}_{year}_{month}_{day}"
        os.rename(save_folder, f"{campaign_folder}/{new_name}")

def get_save_date(save_folder, split=True):
    metadata = load_save(["meta_data"], save_folder)
    save_date = metadata["meta_data"]["game_date"]
    if split:
        year, month, day = save_date.split(".")
        return year, month, day
    return save_date

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
    """
    year1, month1, day1 = [int(i) for i in this_date.split(".")][:3]
    year2, month2, day2 = [int(i) for i in start_date.split(".")][:3]
    duration_from_start = (year1 - year2) + (date_to_day(this_date) - date_to_day(start_date)) / 365.2422
    if end_date is not None:
        year3, month3, day3 = [int(i) for i in end_date.split(".")][:3]
        total_duration = (year3 - year2) + (date_to_day(end_date) - date_to_day(start_date)) / 365.2422
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

def get_building_output(building, target, def_production_methods):
    """
    Calculate a building's output of a variable with respected to production methods, employees and throughput
    Employees must be added into a building from the outside in building["pops_employed"]
    """
    output = 0
    employees = 0
    employees_pl = dict()
    for pm_name in building["production_methods"]["value"]:
        pm = def_production_methods[pm_name]
        if (output_workforce := retrieve_from_tree(pm, ["country_modifiers", "workforce_scaled", target])) is not None:
            output += float(output_workforce)
        if (employees_dict := retrieve_from_tree(pm, ["building_modifiers", "level_scaled"])) is not None:
            for key, addition in employees_dict.items():
                if key not in employees_pl:
                    employees_pl[key] = int(addition)
                else:
                    employees_pl[key] += int(addition)
    
    if "pops_employed" in building:
        for key, pop in building["pops_employed"].items():
            employees += int(pop["workforce"] )

    # print(employees_pl)
    # print(f"Total Employees at level {int(building['level'])}: {employees}")
    employees /= sum([employees_pl[e] for e in employees_pl])
    # print(f"Employees ratio: {employees}")
    # print([employees_pl[e] for e in employees_pl])
    if "throughput" not in building:
        building["throughput"] = 1.0
    # print(output)
    output =  output * float(building["throughput"]) * employees
    return output

def get_country_name(country:dict, localization:dict):
    country_tag = country["definition"]
    if country_tag in localization:
        country_name = localization[country_tag]
    else:
        country_name = country_tag
    if retrieve_from_tree(country, "civil_war") is not None:
        country_name = "Revolutionary " + country_name 
    return country_name