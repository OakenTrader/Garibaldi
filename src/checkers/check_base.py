import os
import pandas as pd

class Checker:
    """
    Base Checker class with defined common attributes and methods.

    Checker objects are viewed as independent from specific save file.

    Attributes:
        - requirements (list): List of sub-trees in save_data needed in a checker
        - definitions (tuple): Game/mod definition folders the checker parses
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

    # Agg declarations. SaveManager unions them across the selected checkers, runs
    # them once per save, and delivers results as cache["aggregates"][name].
    aggregates = []

    # topic -> column entity, for topics reachable through the columns instead.
    # Such a topic is skipped at load time only when the columns exist AND every
    # checker requiring it declares it here; otherwise it is loaded as a tree.
    column_backed = dict()

    # Game/mod definition folders this checker reads. load_definitions parses the
    # union across the selected checkers once and passes it as cache["definitions"].
    # An entry is a folder ("production_methods"), a single file
    # ("defines/00_defines.txt"), or a (folder, depth_add) pair for a folder merged
    # section-wise rather than file-wise. Include folders read on this checker's
    # behalf by helpers in checkers_functions; an undeclared one is a KeyError.
    definitions = ()

    display_name = None
    column_labels = dict()
    sort_order = 100

    # Output files this checker is the canonical producer of. Only needed when two
    # checkers declare the same file, to make the column -> checker map deterministic.
    owns_output = ()

    # file -> (category label, sort order), for outputs listed under a tree category
    # of their own rather than this checker's.
    file_categories = dict()

    # Output files whose plottable columns vary per campaign (a mod's goods, a
    # version's budget slots) and are read from the CSV header instead of ``output``.
    header_columns = ()

    # file -> what one of its rows is ("company"). Undeclared files are per country.
    # The plotting layer picks its plotter from this.
    row_grain = dict()

    # key -> file, for keys naming a whole output rather than one column. Plotting
    # renders one figure per column of that file; the tree shows a single entry.
    file_keys = dict()

    # key -> the CSV column carrying it, where the two names differ.
    csv_columns = dict()

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

    def before_countries(self, cache: dict):
        """Prepare whatever ``on_country`` needs, once per save.

        Runs immediately before the walk, and only for checkers about to run. State
        put on ``self`` here is valid only for that walk: instances outlive a save.
        """

    def on_country(self, country_id: str, country: dict, cache: dict):
        """This checker's row for one country, or None to leave the country out.

        Called by SaveManager.country_pass for each country in turn. Non-dict
        entries never reach here.
        """
        return None

    @classmethod
    def walks_countries(cls):
        return cls.on_country is not Checker.on_country

    def check_needs(self, address: str, reset: bool):
        if reset:
            return True
        else:
            for output in self.output:
                if not (output in os.listdir(address) and output in os.listdir(f"{address}/data")):
                    return True
        return False

    def dependencies_met(self, cache: dict):
        return all(dependency in os.listdir(f"{cache['address']}/data")
                   for dependency in self.dependencies)

    def will_run(self, cache: dict):
        """Whether ``check`` would do work now: dependencies met and output missing."""
        return (self.dependencies_met(cache)
                and self.check_needs(cache["address"], cache.get("reset", False)))

    def check(self, cache: dict):
        """
        Check if the output is already present. If it is, and is not told explicitly to check anyway, no check will be performed.
        Cache (dict): Contains all data necessary
        """
        if "reset" not in cache: # TODO Remove this later when reset is properly wired
            cache["reset"] = False
        if not self.dependencies_met(cache):
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
    