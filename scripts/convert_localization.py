"""
Handles obtaining localization of the game's variables
"""
import re
from pathlib import Path
from scripts.helpers.utility import *

user_variables = jopen("./user_variables.json")

def get_localization(address):
    """
    Obtains the localization text from the files.
    
    Returns a Python Dictionary mapping a variable name to its localization
    """
    data = dict()
    with open(address, "r", encoding="utf8") as file:
        for i, line in enumerate(file):
            line = line.split('#')[0].strip()
            if not line or ":" not in line:
                continue
            try:
                key, value = line.split(":", 1)
            except ValueError:
                raise ValueError(f"Attempt to split {line} of length {len(line)} at line {i} of file {address} into two failed")
            match = re.search(r"\"(.*?)\"", value)
            if match:
                result = match.group(1)
                data[key] = result
    return data

def get_all_localization():
    """
    Returns every single localization definition in the game for a language.
    """
    lcl_files = list(Path(user_variables["Localization Directory"]).rglob("*.yml"))
    dicts = []
    for f in lcl_files:
        names = get_localization(f)
        dicts.append(names)
    localization = dict()
    for d in dicts:
        localization.update(d)
    return localization