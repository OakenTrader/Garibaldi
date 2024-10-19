"""
Save files extraction logic.
"""
import re, gzip, pickle, os, json

with open("./scripts/variables.json", "r") as file:
    VARIABLES = json.load(file)

class Extractor:
    """
    A class dedicated to parsing Victoria 3's common and saves from plain text to a JSON-parsable Python dictionary.

    Based on observed pattern, this class processes text data by removing comments, normalizing whitespace, and structuring data based on 
    nesting levels indicated by curly braces. It specifically handles conditions, logical checks, and assignments 
    within the game's data files, ensuring accurate representation in dictionary format which can be serialized into JSON.
    Extracted data is saved by first pickling the object and then zip it.
    
    Issues: 
    - Strings with whitespaces will be separated into different entries, "United States of America" will
    not be kept in a single variable.
    - DNA variables in the savefile contain equal signs which the script struggles to keep together.
    This should not affect other parts of the result.
    - Boolean scopes which perform logical operations like "One/all of the following must be true" not properly captured yet. 
    Implicit Boolean scope indicators (like possible = { A > 1 B ?= 2} and OR = {}) are not yet implemented

    Parameters:
    address (str): The file path of the text file to be parsed.
    is_save (bool, optional): Specify whether this is a save file or not which may reduce time by omitting operations required
                            in extracting definition files (like removing comments)
    focuses (str, optional): A specific section of the file to focus on, if any. If specified, parsing will 
                           only occur within the scope where this substring is found at the root level. Default is None.
    pline (bool, optional): If True, print each line of the file as it's processed. This is useful for debugging. 
                            Default is False.
    stop_event (threading.Event, optional): threading Event used to interrupt the process from the outside. Default is None
    version (string, optional): Version of the game of this file.

    Attributes:
    data (dict): The structured data extracted from the file, organized as a nested dictionary.
    
    Methods:
    write(output, sections=None, separate=False): Write the data tree into a zipped pickle.

    Examples:
    extractor = Extractor("path/to/victoria3_data.txt", is_save=True, focus="population", pline=True)
    extractor.unquote()
    extractor.write("saves/campaign/save", ["population"])
    """
    def __init__(self, address, is_save=False, focuses=None, pline=False, version="1.7") -> None:
        self.data = dict()
        scope = [self.data]
        current_key = None
        scope_boolean = False
        in_focus = False
        spacing_ex = re.compile(r"(#+.*\n|\s+|#+.*$)")
        spacing_ex_save = re.compile(r"(\s+)")
        split_ex = re.compile(r'(?<!<|>|=)\s(?!<|>|=|\?)')
        if is_save:
            split_ex = re.compile(r'(?<!=)\s(?!=)')
            catch_ex = re.compile(r"^\s?([^=]*)\s?(=)?\s?(rgb|hsv360|hsv)?\s?(\S+)?") # Include less conditions for potentially faster computation
        else:
            split_ex = re.compile(r'(?<!<|>|=)\s(?!<|>|=|\?)')
            catch_ex = re.compile(r"^([^=><\?\s]*)\s?([><\?])?(=)?\s?(rgb|hsv360|hsv)?\s?(\S+)?$")

        with open(address, "r", encoding='utf-8-sig') as file:
            if not is_save:
                problematic_lines = None
                for f in VARIABLES["problematic_definition_files"][version]:
                    if f in address:
                        problematic_lines = VARIABLES["problematic_definition_files"][version][f]
                        break
                if problematic_lines is not None:
                    text = list(file)
                    for i in range(len(problematic_lines), 0, -1):
                        text.pop(problematic_lines[i - 1])
                    text = " ".join(text)
                else:
                    text = file.read()
                text = spacing_ex.sub(" ", text)
            else:
                text = file.read()
                text = spacing_ex_save.sub(" ", text)
        
        for sstr in re.split(r"\s?([{}])\s?", text):
            if not sstr.strip():
                continue
            if pline:
                print(repr(sstr))
            last_scope = scope[-1]
            if "{" in sstr:
                if current_key is None: # Double opening brackets
                    current_key = f"index{len(last_scope)}"
                    last_scope[current_key] = dict()
                scope.append(last_scope[current_key])
                current_key = None
            elif '}' in sstr:
                scope = scope[:-1]
                if len(scope) == scope_boolean: # End of a Boolean Check
                    scope_boolean = False
                if len(scope) == 0 and focuses is not None and in_focus:
                    if focuses == []:
                        break
                    else:
                        in_focus = False
            elif all([i not in sstr for i in [">", "=", "<"]]): # Simple list of values
                if "field_type" not in last_scope:
                    last_scope.update({"field_type":"list"})
                last_scope.update({"value":[field for field in split_ex.split(sstr) if len(field) > 0]})
            else: # Dictionary type fields with equations
                parts = split_ex.split(sstr) # Split by whitespaces not adjacent to the (in)equality sign
                for field in parts:
                    if len(field) == 0:
                        continue
                    if match := catch_ex.match(field):
                        if is_save:
                            key, equality, color, value = match.groups()
                            boolean = None
                        else:
                            key, boolean, equality, color, value = match.groups()
                        if value is not None: 
                            if boolean is None: # Simple Equality match
                                if scope_boolean:
                                    last_scope[key] = {"sign": "=", "value":value}
                                else:
                                    last_scope[key] = value
                            else: # boolean logic match
                                if equality is not None: # >= <= ?=
                                    last_scope[key] = {"sign": boolean + equality, "value":value}
                                else: # > <
                                    last_scope[key] = {"sign": boolean, "value":value}
                        else:
                            if color is None:
                                if boolean is None:
                                    if equality is None: # Lone entries without key is assigned a default key
                                        last_scope[f"index{len(last_scope)}"] = field
                                    else: # Incomplete equality match
                                        last_scope[key] = {}
                                        current_key = key
                                else: # Incomplete boolean match
                                    scope_boolean = len(scope)
                                    if equality is not None:
                                        last_scope[key] = {"sign":boolean + equality}
                                    else:
                                        last_scope[key] = {"sign":boolean}
                                    current_key = key
                            else: # Colorcode match
                                last_scope[key] = {"field_type": color}
                                current_key = key
                    else:
                        raise NotImplementedError(f"Exceptional field: {field}")

    def write(self, output, sections=None, separate=False):
        """
        Write the data tree into a zipped pickle.

        Arguments:
        output: Folder address
        sections: List of subtrees to be written. Default is None (Write all)
        separate: Whether or not the data should be written in one file. Default is False
        """ 
        if sections is not None:
            data_output = {k : v for k, v in self.data.items() if k in sections}
        else:
            data_output = self.data
        if not separate:
            data_output = {"full": data_output}
        try:
            os.mkdir(f"{output}/extracted_save")
        except FileExistsError:
            pass
        miscellaneous = dict()
        for k, v in data_output.items():
            if k not in VARIABLES["large_topics"]:
                miscellaneous[k] = v
                continue
            with gzip.open(f"{output}/extracted_save/{k}.gz", 'wb') as f:
                pickle.dump({k : v}, f, protocol=pickle.HIGHEST_PROTOCOL)
        with gzip.open(f"{output}/extracted_save/miscellaneous.gz", 'wb') as f:
            pickle.dump(miscellaneous, f, protocol=pickle.HIGHEST_PROTOCOL)


    
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

