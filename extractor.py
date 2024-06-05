import json
import re

class Extractor:
    """
    A class dedicated to parsing Victoria 3's common and save files from plain text to a JSON-parsable Python dictionary.

    Based on observed pattern, this class processes text data by removing comments, normalizing whitespace, and structuring data based on 
    nesting levels indicated by curly braces. It specifically handles conditions, logical checks, and assignments 
    within the game's data files, ensuring accurate representation in dictionary format which can be serialized into JSON.

    Issues: 
    - Strings with whitespaces will be separated into different entries, "United States of America" will
    not be kept in a single variable.
    - DNA variables in the savefile contain equal signs which the script struggles to keep together.
    This should not affect other parts of the result.

    Parameters:
    address (str): The file path of the text file to be parsed.
    focus (str, optional): A specific section of the file to focus on, if any. If specified, parsing will 
                           only occur within the scope where this substring is found at the root level. Default is None.
    pline (bool, optional): If True, print each line of the file as it's processed. This is useful for debugging. 
                            Default is False.

    Attributes:
    data (dict): The structured data extracted from the file, organized as a nested dictionary.
    
    Methods:
    dump_json(output): Serializes the parsed data into JSON format and writes it to a specified output file.

    Examples:
    extractor = Extractor("path/to/victoria3_data.txt", focus="population", pline=True)
    extractor.dump_json("output.json")
    """
    def __init__(self, address, focuses=None, pline=False) -> None:
        self.data = dict()
        bracket_counter = 0
        scope = [self.data]
        current_key = None
        scope_boolean = False
        in_focus = False
        with open(address, "r", encoding='utf-8-sig') as file:
            lines = []
            for line in list(file):
                line = line.split("#")[0].strip()
                if line:
                    lines.append(line)
        text = "\n".join(lines)
        del lines
        for sstr in re.split(r"([{}])", text):
            if focuses is not None:
                for focus in focuses:
                    if focus in sstr and bracket_counter == 0:
                        in_focus = True
                        focuses.pop(focuses.index(focus))
                        break
                if not in_focus:
                    if "{" in sstr:
                        bracket_counter += 1
                    elif "}" in sstr:
                        bracket_counter -= 1
                    continue
            sstr = sstr.strip("\n\t ")
            sstr = re.sub(r'#.*?\n', '\n', sstr) # Remove comments
            sstr = re.sub(r'[\t\n]+', ' ', sstr) # Remove tab and linebreak
            sstr = re.sub(r'\s+', ' ', sstr) # Normalize all whitespace into one length space
            if not sstr:
                continue
            if pline:
                print(repr(sstr))
            parts = re.split(r'(?<!<|>|=|\?)\s(?!<|>|=|\?)', sstr) # Split by whitespaces not adjacent to the (in)equality sign
            if "{" in parts:
                bracket_counter += 1
                if current_key is None: # Double opening brackets
                    current_key = f"index{len(scope[-1])}"
                    scope[-1][current_key] = dict()
                scope.append(scope[-1][current_key])
                current_key = None
            elif '}' in parts:
                bracket_counter -= 1
                scope = scope[:-1]
                if bracket_counter == scope_boolean: # End of a Boolean Check
                    scope_boolean = False
                if bracket_counter == 0 and focuses is not None and in_focus:
                    if focuses == []:
                        break
                    else:
                        in_focus = False
            elif all([i not in sstr for i in [">", "=", "<"]]): # Simple list of values
                values = parts
                if "field_type" not in scope[-1]:
                    scope[-1].update({"field_type":"list"})
                scope[-1].update({"value":values})
            else: # Dictionary type fields with equations
                for field in parts:
                    if incomplete_boolean_match := re.compile(r"^(.*)(<|>|>=|<=|\?=)\s*$").match(field): # [A = ]{ 
                        key, operator = incomplete_boolean_match.groups()
                        key = key.strip()
                        scope_boolean = bracket_counter
                        scope[-1][key] = {"sign":operator}
                        current_key = key
                    elif incomplete_equality_match := re.compile(r"^(.*)(=)\s*$").match(field): # [A = ]{ 
                        key, operator = incomplete_equality_match.groups()
                        key = key.strip()
                        scope[-1][key] = {}
                        current_key = key
                    elif boolean_logic_match := re.compile(r"^(.*)(<|>|>=|<=|\?=)(?!.*(?:hsv|rgb))(.*)$").match(field): # Boolean A > B
                        key, operator, value = boolean_logic_match.groups()
                        key = key.strip()
                        scope[-1][key] = {"sign": operator, "value":value}
                    elif equality_match := re.compile(r"^(.*)=(?!.*(?:hsv|rgb))(.*)$").match(field): # A = B
                        key, value = equality_match.groups()
                        key = key.strip()
                        if scope_boolean:
                            scope[-1][key] = {"sign": "=", "value":value}
                        else:
                            scope[-1][key] = value.strip()
                    elif color_entry_match := re.compile(r"^(.*?)=\s*(hsv|rgb|hsv360)\s*$").match(field): # color entries
                        key, value = color_entry_match.groups()
                        scope[-1][key.strip()] = {"field_type": value.strip()}
                        current_key = key.strip()
                    elif "=" not in field:  # Lone entries without key
                        scope[-1][f"index{len(scope[-1])}"] = field.strip()
                    elif ordinary_field_match := re.compile(r"^(.*?)=(.*)$").match(field): # A = B
                        key, value = ordinary_field_match.groups()
                        scope[-1][key.strip()] = value.strip()

    def dump_json(self, output, sections=None, separate=False):
        """
        Serialize the parsed data to JSON and write it to a specified output file.

        Parameters:
        output (str): The file path where the JSON data will be written.
        """ 
        if sections is not None:
            data_output = {k : v for k, v in self.data.items() if k in sections}
        else:
            data_output = self.data
        if not separate:
            data_output = {"full": data_output}
        for k, v in data_output.items():
            with open(f"{output}_{k}.json", "w") as f:
                f.write(json.dumps({k : v}, indent=4))



    
    def unquote(self, scope=None):
        """
        Recursively removes quotation marks from all string values within the provided scope of the data dictionary.

        This method navigates through the dictionary (or a sub-dictionary) to clean up string entries by removing any 
        embedded double quotes. It processes dictionaries, lists within dictionaries, and string values recursively. 
        If no scope is provided, it defaults to the entire data structure managed by the class.

        Parameters:
        scope (dict, optional): The dictionary or sub-dictionary to clean. Defaults to the entire data dictionary 
                                if None is provided.

        Effects:
        Modifies the dictionary 'scope' in-place, removing double quotes from all string values, including those 
        within nested dictionaries and lists.
        """
        if scope is None:
            scope = self.data
        for key in scope:
            if isinstance(scope[key], str):
                scope[key] = scope[key].replace("\"", "")
            if isinstance(scope[key], dict):
                self.unquote(scope[key])
            if isinstance(scope[key], list):
                for i, item in enumerate(scope[key]):
                    if isinstance(item, str):
                        scope[key][i] = item.replace("\"", "")

