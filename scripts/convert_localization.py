import re
from pathlib import Path

def get_localization(address):
    """
    Obtains the localization text from the files.
    
    Returns a Python Dictionary
    """
    data = dict()
    with open(address, "r", encoding="utf8") as file:
        for line in file:
            line = line.split('#')[0].strip()
            if not line:
                continue
            # print(line)
            key, value = line.split(":", 1)
            match = re.search(r"\"(.*?)\"", value)
            if match:
                result = match.group(1)
                data[key] = result
    return data

def get_all_localization():
    lcl_files = list(Path("./localization").rglob("*.yml"))
    dicts = []
    for f in lcl_files:
        names = get_localization(f)
        dicts.append(names)
    localization = dict()
    for d in dicts:
        localization.update(d)
    return localization