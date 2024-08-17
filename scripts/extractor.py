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

    Parameters:
    address (str): The file path of the text file to be parsed.
    focus (str, optional): A specific section of the file to focus on, if any. If specified, parsing will 
                           only occur within the scope where this substring is found at the root level. Default is None.
    pline (bool, optional): If True, print each line of the file as it's processed. This is useful for debugging. 
                            Default is False.

    Attributes:
    data (dict): The structured data extracted from the file, organized as a nested dictionary.
    
    Methods:
    write(output, sections=None, separate=False): Write the data tree into a zipped pickle.

    Examples:
    extractor = Extractor("path/to/victoria3_data.txt", focus="population", pline=True)
    extractor.write("saves/campaign/save", ["population"])
    """
    def __init__(self, address, is_save=False, focuses=None, pline=False, stop_event=None, version="1.7") -> None:
        self.data = dict()
        self.check_stop = (lambda : None) if stop_event is None else stop_event.is_set
        bracket_counter = 0
        scope = [self.data]
        current_key = None
        scope_boolean = False
        in_focus = False
        spacing_ex = re.compile(r"(#+.*\n|\s+)")
        split_ex = re.compile(r'(?<!<|>|=)\s(?!<|>|=|\?)')
        if is_save:
            split_ex = re.compile(r'(?<!=)\s(?!=)')
            catch_ex = re.compile(r"^\s?([^=]*)\s?(=)?\s?(rgb|hsv360|hsv)?\s?(\S+)?") # Include less conditions for potentially faster computation
        else:
            split_ex = re.compile(r'(?<!<|>|=)\s(?!<|>|=|\?)')
            catch_ex = re.compile(r"^([^=><\?\s]*)\s?([><\?])?(=)?\s?(rgb|hsv360|hsv)?\s?(\S+)?$")
        
        match_count = [0,0,0,0,0,0,0,0]

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
            else:
                text = file.read()
            text = spacing_ex.sub(" ", text)
        if self.check_stop():
            raise InterruptedError("Stop event set")
        

        for sstr in re.split(r"\s?([{}])\s?", text):
            if self.check_stop():
                raise InterruptedError("Stop event set")
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
            if not sstr:
                continue
            if pline:
                print(repr(sstr))
            last_scope = scope[-1]
            if "{" in sstr:
                bracket_counter += 1
                if current_key is None: # Double opening brackets
                    current_key = f"index{len(last_scope)}"
                    last_scope[current_key] = dict()
                scope.append(last_scope[current_key])
                current_key = None
                match_count[0] += 1
            elif '}' in sstr:
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
                if "field_type" not in last_scope:
                    last_scope.update({"field_type":"list"})
                last_scope.update({"value":[field for field in split_ex.split(sstr) if len(field) > 0]})
                match_count[1] += 1
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
                                match_count[2] += 1
                            else: # boolean logic match
                                if equality is not None: # >= <= ?=
                                    last_scope[key] = {"sign": boolean + equality, "value":value}
                                else: # > <
                                    last_scope[key] = {"sign": boolean, "value":value}
                                match_count[3] += 1
                        else:
                            if color is None:
                                if boolean is None:
                                    if equality is None: # Lone entries without key is assigned a default key
                                        last_scope[f"index{len(last_scope)}"] = field
                                        match_count[4] += 1
                                    else: # Incomplete equality match
                                        last_scope[key] = {}
                                        current_key = key
                                        match_count[5] += 1
                                else: # Incomplete boolean match
                                    scope_boolean = bracket_counter
                                    if equality is not None:
                                        last_scope[key] = {"sign":boolean + equality}
                                    else:
                                        last_scope[key] = {"sign":boolean}
                                    current_key = key
                                    match_count[6] += 1
                            else: # Colorcode match
                                last_scope[key] = {"field_type": color}
                                current_key = key
                                match_count[7] += 1
                    else:
                        raise NotImplementedError(f"Exceptional field: {field}")
        if is_save:
            print(f"Bracket pairs: {match_count[0]}")
            print(f"lists count: {match_count[1]}")
            print(f"Equality matches: {match_count[2]}")
            print(f"Boolean matches: {match_count[3]}")
            print(f"Lone entry matches: {match_count[4]}")
            print(f"Incomplete equality matches: {match_count[5]}")
            print(f"Incomplete boolean matches: {match_count[6]}")
            print(f"Color matches: {match_count[7]}")

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
            if self.check_stop():
                raise InterruptedError("Stop event set")
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
        if self.check_stop():
            raise InterruptedError("Stop event set")
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

