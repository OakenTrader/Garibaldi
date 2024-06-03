import json

def jopen(address):
    with open(address) as file:
        return json.load(file)

def get_all_possible_keys(data):
    unique_keys = set()
    for k, v in data.items():
        if isinstance(v, dict):
            for kv, vv in v.items():
                unique_keys.add(kv)
    return unique_keys