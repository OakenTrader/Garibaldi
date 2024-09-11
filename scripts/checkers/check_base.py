import os

class Checker:
    """
    Base Checker class with defined common attributes and methods.

    Checker objects are viewed as independent from specific save file.

    Attributes:
        - variables (list): List of labels for variables with different names on each version to be resolved
        - requirements (list): List of sub-trees in save_data needed in a checker
        - dependencies (list): List of Checkers that need to be executed before this one
        - output (dict): Dictionary mapping files produced by the checker mapping to lists of plottable variables. 
        Used to check if checking is necessary (whether or not these files exist) and to assign file for plotter to read
    """
    variables = []
    requirements = []
    dependencies = []
    output = dict()

    def __init__(self):
        pass

    def check_needs(self, address: str, reset: bool):
        if reset:
            return True
        else:
            for output in self.output:
                if output not in os.listdir(address):
                    return True
        return False            

    def check(self, cache: dict):
        """
        Check if the output is already present. If it is, and is not told explicitly to check anyway, no check will be performed.
        Cache (dict): Contains all data necessary
        """
        if "reset" not in cache: # TODO Remove this later when reset is properly wired
            cache["reset"] = False
        if self.check_needs(cache["address"], cache["reset"]):
            self.execute_check(cache)

    def execute_check(self, cache:dict):
        """
        Template for execute_check methods
        """
        pass
    