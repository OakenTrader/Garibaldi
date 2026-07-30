import os
import pandas as pd

class Checker:
    """
    Base Checker class with defined common attributes and methods.

    Checker objects are viewed as independent from specific save file.

    Attributes:
        - requirements (list): List of sub-trees in save_data needed in a checker
        - dependencies (list): List of Checkers that need to be executed before this one
        - output (dict): Dictionary mapping files produced by the checker mapping to lists of plottable variables.
        Used to check if checking is necessary (whether or not these files exist) and to assign file for plotter to read

    Display attributes, read by the GUI's statistics tree. That tree is built from
    the registered checkers at runtime and is never hardcoded, so a new checker
    shows up in the UI with no GUI edit — these three control how it looks:
        - display_name (str): category label; defaults to ``name`` minus "Check"
        - column_labels (dict): per-column overrides, where prettifying reads badly
        - sort_order (int): tree position, ties broken alphabetically. Without it
          the tree would reshuffle whenever import order changed.
    """
    requirements = []
    dependencies = []
    output = dict()

    display_name = None
    column_labels = dict()
    sort_order = 100

    # Output files this checker is the canonical producer of. Only needed when two
    # checkers declare the same file, so that the column -> checker map does not
    # depend on iteration order.
    owns_output = ()

    # Output files that belong under their own tree category rather than this
    # checker's. Maps file -> (category label, sort order). CheckPrestige writes
    # goods_produced.csv as a by-product of its production-leader maths, but goods
    # should not appear nested under "Prestige".
    file_categories = dict()

    # Output files whose plottable columns cannot be written down here because they
    # depend on the campaign: the goods a mod defines, or the income and expense
    # slots a game version happens to use. Their columns are read from the CSV
    # header instead. Everything else must be declared in ``output``, which is the
    # only thing the statistics tree reads.
    header_columns = ()

    def __init__(self):
        pass

    @classmethod
    def category_name(cls):
        """Label for this checker's category in the statistics tree."""
        if cls.display_name:
            return cls.display_name
        name = getattr(cls, "name", cls.__name__)
        return name[len("Check"):] if name.startswith("Check") else name

    @classmethod
    def owns(cls, output_file):
        return output_file in cls.owns_output

    @classmethod
    def label_for(cls, column):
        """Human-readable label for one of this checker's output columns."""
        if column in cls.column_labels:
            return cls.column_labels[column]
        return column.replace("_", " ").capitalize()

    def check_needs(self, address: str, reset: bool):
        if reset:
            return True
        else:
            for output in self.output:
                if not (output in os.listdir(address) and output in os.listdir(f"{address}/data")):
                    return True
        return False            

    def check(self, cache: dict):
        """
        Check if the output is already present. If it is, and is not told explicitly to check anyway, no check will be performed.
        Cache (dict): Contains all data necessary
        """
        if "reset" not in cache: # TODO Remove this later when reset is properly wired
            cache["reset"] = False
        for dependency in self.dependencies:
            if dependency not in os.listdir(f"{cache["address"]}/data"):
                return False
        if self.check_needs(cache["address"], cache["reset"]):
            check_output = self.execute_check(cache)
        else:
            check_output = []
            for file, variables in self.output.items():
                if variables:
                    check_output.append(pd.read_csv(f"{cache['address']}/data/{file}", sep=","))
            if len(check_output) == 1:
                check_output = check_output[0]
        return check_output

    def execute_check(self, cache:dict):
        """
        Template for execute_check methods
        """
        pass
    