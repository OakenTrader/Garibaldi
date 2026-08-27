"""
Whatever functions written to help the program.
"""
import sys, os, shutil, fnmatch, pickle, gzip, glob, json, re
import zstandard as zstd
from src.extractor import ExtractorCommon
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
    Load a pickled, compressed data blob.

    Transparently handles both the current zstandard (.zst) format and the
    legacy gzip (.gz) format by sniffing the magic bytes, so previously
    extracted saves keep loading without re-extraction.
    """
    with open(address, 'rb') as f:
        blob = f.read()
    if blob[:2] == b'\x1f\x8b':  # legacy gzip
        return pickle.loads(gzip.decompress(blob))
    return pickle.loads(zstd.ZstdDecompressor().decompress(blob))  # zstd

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
    data = ExtractorCommon(address)
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
        data = ExtractorCommon(address)
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

    if user_variables["Selected Mod"] and os.path.isdir(user_variables["Selected Mod"] + "//common//" + folder):
        """
        FIXME Replace //common// with mode and properly implement depth_add
        """
        """
        FIXME Vibecoded this thing
        """
        for address in glob.glob(user_variables["Selected Mod"] + "//common//" + folder + "//*.txt"):
            data = ExtractorCommon(address)
            data.unquote()
            data = data.data
            if depth_add == 0:
                for key, value in data.items():
                    if ':' in key:
                        prefix, actual_key = key.split(':', 1)
                        prefix = prefix.upper()
                        if prefix == 'INJECT':
                            if actual_key not in defs:
                                raise ValueError(f"INJECT: {actual_key} does not exist")
                            if isinstance(value, dict) and isinstance(defs[actual_key], dict):
                                defs[actual_key].update(value)
                            else:
                                defs[actual_key] = value
                        elif prefix == 'REPLACE':
                            if actual_key not in defs:
                                raise ValueError(f"REPLACE: {actual_key} does not exist")
                            defs[actual_key] = value
                        elif prefix == 'TRY_INJECT':
                            if actual_key in defs:
                                if isinstance(value, dict) and isinstance(defs[actual_key], dict):
                                    defs[actual_key].update(value)
                                else:
                                    defs[actual_key] = value
                        elif prefix == 'TRY_REPLACE':
                            if actual_key in defs:
                                defs[actual_key] = value
                        elif prefix == 'REPLACE_OR_CREATE':
                            defs[actual_key] = value
                        elif prefix == 'INJECT_OR_CREATE':
                            if actual_key in defs:
                                if isinstance(value, dict) and isinstance(defs[actual_key], dict):
                                    defs[actual_key].update(value)
                                else:
                                    defs[actual_key] = value
                            else:
                                defs[actual_key] = value
                        else:
                            # Invalid prefix, treat as normal key
                            defs[key] = value
                    else:
                        defs[key] = value
            else:
                for key, value in data.items():
                    if isinstance(value, dict) and key in defs:
                        defs[key].update(value)
                    else:
                        defs[key] = value

    return defs

"""
Each mod entries now may or may not have prefixes:
INJECT:key - this mode tries to inject the script into an existing entry. Errors if the respective entry does not exist.

REPLACE:key - this mode replaces an existing entry with a new one. Errors if the respective entry does not exist.

TRY_INJECT:key same as INJECT: but does not error if the entry does not exist.

TRY_REPLACE:key same as REPLACE: but does not error if the entry does not exist.

REPLACE_OR_CREATE:key = { } # Same as REPLACE: but if the entry does not exist, it will create it

INJECT_OR_CREATE:key = { } # Same as INJECT: but if the entry does not exist, it will create it
"""

def _extracted_blob_path(folder:str, name:str):
    """
    Return the path to an extracted blob, preferring the current zstd (.zst)
    format over the legacy gzip (.gz) one. Returns None if neither exists.
    """
    for ext in (".zst", ".gz"):
        path = os.path.join(folder, name + ext)
        if os.path.exists(path):
            return path
    return None

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
    extracted_dir = f"{address}/extracted_save"
    if "extracted_save" not in os.listdir(address):
        os.mkdir(extracted_dir)
    misc_path = _extracted_blob_path(extracted_dir, "miscellaneous")
    if misc_path is not None:
        miscellaneous = zopen(misc_path)
    else:
        miscellaneous = dict()
    for topic in topics.copy():
        topic_path = _extracted_blob_path(extracted_dir, topic) if isinstance(topic, str) else None
        if topic_path is not None:
            data_output[topic] = zopen(topic_path)[topic]
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

def date_to_day(date:list):
    """
    Get the number of days passed since the start of the year to the current date
    """
    year, month, day = date[:3]
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
        this_date = [i for i in this_date.split(".")][:3]
    this_date = [int(i) for i in this_date]
    if isinstance(start_date, str):
        start_date = [i for i in start_date.split(".")][:3]
    start_date = [int(i) for i in start_date]
    duration_from_start = (this_date[0] - start_date[0]) + (date_to_day(this_date) - date_to_day(start_date)) / 365.2422
    if end_date is not None:
        if isinstance(end_date, str):
            end_date = [i for i in end_date.split(".")][:3]
        end_date = [int(i) for i in end_date]
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


def load_campaign_config(campaign_folder):
    """Read a campaign's ``campaign_config.json``, or an empty dict if it has none.

    Campaign-scoped settings, as opposed to the app-wide ones in
    ``user_variables.json``. Absent by default — every campaign works without one.
    """
    path = f"saves/{campaign_folder}/campaign_config.json"
    return jopen(path) if os.path.exists(path) else dict()


def campaign_tag_filters(campaign_folder):
    """Return ``(override_player_tags, show_ai_tags)`` for a campaign.

    ``override_player_tags`` replaces the player list derived from each save's
    ``player_manager``; ``show_ai_tags`` adds countries to plot alongside the
    players for comparison. Both plotters need exactly this pair, and both had
    their own copy of the read — which meant a new key had to be added twice.
    """
    config = load_campaign_config(campaign_folder)
    return config.get("override_player_tags", []), config.get("show_ai_tags", [])


def save_year_number(year, month, day):
    """Collapse a save date into a single fractional year, for plotting and sorting."""
    return int(year) + (int(month) - 1) / 12 + int(day) / 365


def date_from_folder_name(folder):
    """Recover (year, month, day) from a ``campaign_YYYY_M_D`` folder name.

    ``rename_folder_to_date`` gives every extracted save this shape, which lets a
    date range be applied without opening anything. Returns None when the name
    does not parse. Splitting from the right keeps campaign names with underscores
    working.
    """
    parts = folder.rsplit("_", 3)
    if len(parts) != 4:
        return None
    try:
        return tuple(int(part) for part in parts[1:])
    except ValueError:
        return None


def iter_save_folders(campaign_folder, start_date=0, end_date=2024, need_metadata=True):
    """Walk a campaign's save folders in a date range.

    Yields ``(save_folder, year_number, metadata)`` for every non-reserved save
    folder whose date falls within ``[start_date, end_date + 1]``. This is the one
    place that knows how to turn a save folder into a date, and it backs the two
    plotters, the Process window's year filter and the Statistics date slider.

    The date is taken from the folder name where possible so that folders outside
    the range cost nothing. Only folders that survive the filter are opened — and
    only when ``need_metadata`` is set, since callers that just want paths (the
    checking phase) would otherwise pay to load every freshly extracted save that
    has no ``metadata.json`` yet.

    Note the fallback for a save with no usable ``metadata.json`` calls
    ``load_save(["meta_data"], save_folder)``. The copies of this loop that used to
    live in plotter.py passed a third positional argument that ``load_save`` does
    not accept, so that branch raised TypeError instead of recovering.
    """
    root = f"saves/{campaign_folder}"
    for folder in sorted(os.listdir(root)):
        save_folder = f"{root}/{folder}"
        if not os.path.isdir(save_folder) or is_reserved_folder(folder):
            continue

        year_number = None
        from_name = date_from_folder_name(folder)
        if from_name is not None:
            year_number = save_year_number(*from_name)
            if year_number < start_date or year_number > end_date + 1:
                continue
            if not need_metadata:
                yield save_folder, year_number, None
                continue

        try:
            metadata = jopen(f"{save_folder}/metadata.json")
        except FileNotFoundError:
            metadata = None
        try:
            year, month, day = metadata["save_date"]
            year_number = save_year_number(year, month, day)
        except (KeyError, TypeError):
            if year_number is None or need_metadata:
                metadata = load_save(["meta_data"], save_folder)
                year, month, day = metadata["meta_data"]["game_date"].split(".")[:3]
                year_number = save_year_number(year, month, day)
        if year_number < start_date or year_number > end_date + 1:
            continue
        yield save_folder, year_number, metadata