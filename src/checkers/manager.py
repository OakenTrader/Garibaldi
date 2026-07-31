from src.checkers.checkers_functions import *
from src.checkers.check_construction import CheckConstruction
from src.checkers.check_innovation import CheckInnovation
from src.checkers.check_infamy import CheckInfamy
from src.checkers.check_prestige import CheckPrestige
from src.checkers.check_tech import CheckTech
from src.checkers.check_demographics import CheckDemographics
from src.checkers.check_finance import CheckFinance
# company_columns still decides which plotter a check needs; the other per-checker
# column lists became import-only once plot_results stopped expanding groups, since
# every column is now declared in its checker's `output`.
from src.checkers.check_companies import CheckCompanies, company_columns

from src.helpers.plotter import plot_stat, plot_goods_produced, plot_company_stat, csv_value_columns
from src.helpers.convert_localization import get_all_localization
from src.helpers.utility import load_def, load_def_multiple
import os, glob, multiprocessing

ALL_CHECKERS = [
    CheckConstruction, CheckInnovation, CheckInfamy, CheckPrestige, CheckTech,
    CheckDemographics, CheckFinance, CheckCompanies,
]


def registered_checkers():
    """Checker classes in stable display order (sort_order, then name)."""
    return sorted(ALL_CHECKERS, key=lambda c: (c.sort_order, c.category_name()))


def load_definitions(checkers):
    """
    Parse the union of the given checkers' declared ``definitions``, once.

    Definitions are identical for every save, so they are read here — before the
    first save is opened — and handed down as ``cache["definitions"]``, keyed by
    the declared path. Previously each checker loaded its own folders inside every
    save: 36 load_def* calls expanding to ~690 files per save, because
    static_modifiers, production_methods, company_types and
    technology/technologies are each wanted by three or four checkers.

    A ``.txt`` entry is one file (``load_def``); anything else is a folder
    (``load_def_multiple``). ``depth_add`` comes from the declaration because the
    same folder read with a different value yields a different tree, so two
    checkers disagreeing about it is an error rather than a silent coin-flip.
    """
    depths = dict()
    for checker in checkers:
        for spec in checker.definitions:
            path, depth_add = spec if isinstance(spec, tuple) else (spec, 0)
            if depths.setdefault(path, depth_add) != depth_add:
                raise ValueError(
                    f"Checkers disagree on depth_add for definition '{path}': "
                    f"{depths[path]} and {depth_add}. The two settings produce "
                    f"different trees, so they cannot share one cache entry.")

    definitions = dict()
    for path, depth_add in sorted(depths.items()):
        if path.endswith(".txt"):
            definitions[path] = load_def(path, "Common Directory")
        else:
            definitions[path] = load_def_multiple(path, "Common Directory", depth_add)
    return definitions

class SaveManager:
    """
    Class to manage a single save file's resource

    Each checker function takes in cache data of date, version, variables with compatibilty and save data as needed.
    Checkers will no longer load data on their own.
    """

    def __init__(self, address, checks=None, definitions=None, localization=None):
        """
        definitions / localization: game data that is the same for every save.
        ``check_save_folders`` reads them once and passes them in; they are built
        here only when a caller (a script, a test) drives a single save directly.
        This used to call get_all_localization twice per save, 0.30 s and ~20 MiB
        each time, on top of every checker re-reading its own definition folders.
        """
        self.localization = get_all_localization() if localization is None else localization
        self.definitions = load_definitions(checks) if definitions is None else definitions
        self.cache = {"address": address, "localization": self.localization,
                      "definitions": self.definitions}
        self.checks = checks
        os.makedirs(f"{address}/data", exist_ok=True)  # Create a data folder for outputs
        requirements = self.check_metadata(False) # mandatory to obtain metadata
        for check in checks: # Combine all needed requirements
            if not check.check_needs(address, False): # TODO deal with resetting later
                continue
            requirements.update(check.requirements)
        self.save_data = load_save(list(requirements), address)
        self.metadata = self.get_metadata(address)
        self.cache = {"save_data":self.save_data, "metadata":self.metadata, "localization":self.localization,
                      "definitions":self.definitions, "address":address}

        """TODO Check sequence matters because some data from the first checkers can be reused later"""

    def start_checking(self):
        outputs = dict()
        while self.checks:
            remaining_checks = []
            for check in self.checks:
                output = check.check(self.cache)
                if output is False: # Due to dependencies
                    remaining_checks.append(check)
                else:
                    outputs[check.name] = output
            self.checks = remaining_checks

    def check_metadata(self, reset=False):
        """Check if loading metadata from the save file is necessary. Returns the requirement set"""
        requirements = set(["meta_data", "player_manager", "country_manager"])
        if "metadata.json" not in os.listdir(self.cache["address"]) or reset:
            return requirements
        return set([])


    def get_metadata(self, address):
        """Obtains data of players, date and version from metadata.json (creates one if not existing)
        address: directory of campaign folder"""

        metadata = dict()
        if "metadata.json" not in os.listdir(address):
            data = self.save_data
            metadata["version"] = data["meta_data"]["version"]
            metadata["save_date"] = data["meta_data"]["game_date"].split(".")[:3]
            players = data["player_manager"]["database"]
            countries = data["country_manager"]["database"]
            player_data = []
            countries_id = []
            for _, player in players.items():
                player_id = player["country"]
                if not isinstance(retrieve_from_tree(countries, player_id), dict):
                    continue
                if player_id in countries_id:
                    continue
                player_tag = countries[player_id]["definition"]
                player_country = get_country_name(countries[player_id], self.localization)
                player_data.append([int(player_id), player_tag, player_country])
                countries_id.append(player_id)
            metadata["players"] = player_data
            with open(f"{address}/metadata.json", "w") as file:
                json.dump(metadata, file, indent=4)
        else:
            metadata = jopen(f"{address}/metadata.json")
        return metadata
    
    """
    TODO Methods that manage common computationally intensive aspects such as looping through every single pops or building
    so that we get all needed information for every checker by looping a single time
    """

def build_check_map():
    """Maps each selectable output key to its (checker_class, output_file).

    Two checkers can declare the same column — CheckPrestige writes
    goods_produced.csv as a by-product of its production-leader maths, and a
    dedicated goods checker would own it. Iterating in a stable order and letting
    the declared owner (``owns_output``) win keeps this deterministic; the previous
    version iterated a ``set()``, so the winner varied between runs.
    """
    check_map = dict()
    for checker_class in registered_checkers():
        for output, outvars in checker_class.output.items():
            for outvar in outvars:
                if outvar in check_map and not checker_class.owns(output):
                    continue
                check_map[outvar] = (checker_class, output)
    return check_map


def all_check_keys():
    """Every selectable stat key — what a parse runs, now that checking is not selective."""
    return list(build_check_map())


def check_save_folders(checks, campaign_folder, folders, stop_event, finish_event, queue):
    """
    Run the selected checkers over a subset of save folders. This is the parallelisable
    phase of analysis: each save folder writes into its own ``{folder}/data`` directory,
    so disjoint folder sets can be processed concurrently by several processes.

    The signature mirrors ``extract_files`` so the GUI can drive both the same way:
        - checks (list[str]) : selected output keys
        - campaign_folder (str) : name of the target folder in ./saves (unused here, kept
          for symmetry / logging; folders are passed explicitly)
        - folders (list[str]) : subset of save folders this worker handles
        - stop_event (multiprocessing.Event) : to communicate termination with the GUI
        - finish_event (multiprocessing.Event) : set once the subset is done (or aborted)
        - queue (multiprocessing.Queue) : per-folder progress reporting
    """
    check_map = build_check_map()
    try:
        # Sorted by the registered display order rather than iterated out of a set:
        # a set's order varies between runs, and checkers with a CSV dependency
        # (Prestige needs finance.csv, Innovation and Finance need demographics.csv)
        # would then be deferred and retried a varying number of times.
        selected = {check_map[check][0] for check in checks}
        checkers = [c() for c in registered_checkers() if c in selected] # Instantiate a single object from each class
        # Game data is the same for every folder below, so it is read once here
        # rather than inside each save.
        definitions = load_definitions(checkers)
        localization = get_all_localization()
        for folder in folders:
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            if is_reserved_folder(folder):
                continue
            save = SaveManager(folder, checkers, definitions, localization)
            save.start_checking()
            queue.put(1)
    except Exception as e:
        stop_event.set()
        raise e
    finally:
        finish_event.set()


def plot_results(checks, campaign_folder, start_date=0, end_date=2024):
    """
    Reduction phase of analysis: aggregate the per-folder CSVs produced by
    ``check_save_folders`` and write the plots to campaign_data/. Must run exactly once,
    after every folder has been checked, since ``plot_stat`` reads across all folders.

    Nothing is displayed — figures are written and dropped. The GUI renders its own
    figures on demand via ``figures_for``; this is purely the batch pass, so the PNG
    set on disk stays complete for use outside the app.

    Make exceptional cases for prestige (many subcategories) and goods_produced (many goods).

    A stat that cannot be plotted is skipped rather than aborting the batch. One
    pass renders ~90 figures and any single CSV may be stale: ValueError covers
    "no saves with this data in range", KeyError covers a CSV written before a
    column existed (prestige.csv gains columns as the checker grows). Letting
    either escape would cost every plot queued behind it.
    """
    check_map = build_check_map()
    dates = {"start_date": start_date, "end_date": end_date}

    def render(check, plot):
        try:
            plot()
        except (ValueError, KeyError) as e:
            print(f"Skipped plotting {check}: {type(e).__name__}: {e}")

    # One plot per declared column. There used to be group branches here — "GDP"
    # rendered every finance column, "literacy" every demographic one — left over
    # from the old Analyze window's one-checkbox-per-group. Every column is now a
    # key in its own right, so those branches would render each figure twice.
    for check in checks:
        if check == "total_prestige":
            # The campaign-wide total lives in prestige.csv under the column "total".
            render(check, lambda: plot_stat(
                campaign_folder, "total", input_file="prestige.csv", players=True,
                save_name="total_prestige.csv", **dates))
        elif check == "goods_produced":
            # Not a column: expands to one plot per good.
            render(check, lambda: plot_goods_produced(campaign_folder, 10, **dates))
        elif check in company_columns:
            # A line here is a company, not a country, so it needs the company
            # plotter; the per-country rollups in company_countries.csv go through
            # plot_stat like anything else.
            render(check, lambda c=check: plot_company_stat(
                campaign_folder, c, input_file="companies.csv", players=True, **dates))
        else:
            outfile = check_map[check][1]
            render(check, lambda c=check, f=outfile: plot_stat(
                campaign_folder, c, input_file=f, players=True, **dates))

    # Columns that only the campaign's own CSV header knows about (income and
    # expense slots, goods). They are not in ``checks`` because they cannot be
    # declared, but the batch pass still owns rendering them.
    for checker in registered_checkers():
        for input_file in checker.header_columns:
            if input_file == "goods_produced.csv":
                continue  # already covered by plot_goods_produced above
            for column in csv_value_columns(campaign_folder, input_file):
                render(column, lambda c=column, f=input_file: plot_stat(
                    campaign_folder, c, input_file=f, players=True, **dates))


def figures_for(campaign_folder, column, input_file, players=True, start_date=0,
                end_date=2024, figsize=None):
    """Render one stat interactively: return its Figures without saving anything.

    The interactive counterpart to ``plot_results``. Which plotter applies is
    decided by the source file, not the column: a line in companies.csv is a
    company, everywhere else it is a country.
    """
    kwargs = {"players": players, "save": False, "start_date": start_date, "end_date": end_date}
    if figsize is not None:
        kwargs["figsize"] = figsize
    if input_file == "companies.csv":
        return plot_company_stat(campaign_folder, column, input_file=input_file, **kwargs)
    if column == "total_prestige":
        # The campaign-wide total lives in prestige.csv under the column "total".
        return [plot_stat(campaign_folder, "total", input_file=input_file, **kwargs)]
    return [plot_stat(campaign_folder, column, input_file=input_file, **kwargs)]


def plot_results_job(checks, campaign_folder, start_date, end_date, stop_event, finish_event, queue):
    """``plot_results`` wrapped in the (stop_event, finish_event, queue) protocol.

    Module-level so it survives pickling under a spawn start method, and shaped like
    ``extract_files`` / ``check_save_folders`` so the GUI's job runner can drive all
    three phases identically.
    """
    try:
        plot_results(checks, campaign_folder, start_date=start_date, end_date=end_date)
        queue.put(1)
    except Exception as e:
        stop_event.set()
        raise e
    finally:
        finish_event.set()


def perform_checking(checks, campaign_folder, stop_event, finish_event, start_date=0, end_date=2024):
    """
    Single-process interface between GUI and the checkers / plotters. Retained for
    non-parallel callers (e.g. scripts); the GUI now drives ``check_save_folders`` across
    several processes and then calls ``plot_results`` directly.
    """
    try:
        folders = glob.glob(os.path.join("saves", campaign_folder, "*"))
        check_save_folders(checks, campaign_folder, folders, stop_event, finish_event, multiprocessing.Queue())
        if stop_event.is_set():
            raise InterruptedError("Stop event set")
        plot_results(checks, campaign_folder, start_date=start_date, end_date=end_date)
    except InterruptedError as e:
        raise InterruptedError("Checking stopped:", e)
    finally:
        stop_event.set()
        finish_event.set()

