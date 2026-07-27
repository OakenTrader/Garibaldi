from src.checkers.checkers_functions import *
from src.checkers.check_construction import CheckConstruction
from src.checkers.check_innovation import CheckInnovation
from src.checkers.check_infamy import CheckInfamy
from src.checkers.check_prestige import CheckPrestige, prestige_columns
from src.checkers.check_tech import CheckTech
from src.checkers.check_demographics import CheckDemographics, demographics_columns
from src.checkers.check_finance import CheckFinance, finance_columns
from src.checkers.check_companies import CheckCompanies, company_columns, company_country_columns

from src.helpers.plotter import plot_stat, plot_goods_produced, plot_company_stat
from src.helpers.convert_localization import get_all_localization
import os, glob, multiprocessing

class SaveManager:
    """
    Class to manage a single save file's resource

    Each checker function takes in cache data of date, version, variables with compatibilty and save data as needed.
    Checkers will no longer load data on their own.
    """

    def __init__(self, address, checks=None):
        self.cache = {"address": address, "localization":get_all_localization()}
        self.cache["address"] = address
        self.checks = checks
        self.localization = get_all_localization()
        os.makedirs(f"{address}/data", exist_ok=True)  # Create a data folder for outputs
        requirements = self.check_metadata(False) # mandatory to obtain metadata
        for check in checks: # Combine all needed requirements
            if not check.check_needs(address, False): # TODO deal with resetting later
                continue
            requirements.update(check.requirements)
        self.save_data = load_save(list(requirements), address)
        self.metadata = self.get_metadata(address)
        self.cache = {"save_data":self.save_data, "metadata":self.metadata, "localization":self.localization, "address":address}

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
    """Maps each selectable output key to its (checker_class, output_file)."""
    check_map = dict()
    all_checkers = [CheckConstruction, CheckInnovation, CheckInfamy, CheckPrestige, CheckTech, CheckDemographics, CheckFinance, CheckCompanies]
    for checker_class in all_checkers:
        for output, outvars in checker_class.output.items():
            for outvar in outvars:
                check_map[outvar] = (checker_class, output)
    return check_map


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
        checkers = [c() for c in list(set([check_map[check][0] for check in checks]))] # Instantiate a single object from each class
        for folder in folders:
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            if is_reserved_folder(folder):
                continue
            save = SaveManager(folder, checkers)
            save.start_checking()
            queue.put(1)
    except Exception as e:
        stop_event.set()
        raise e
    finally:
        finish_event.set()


def plot_results(checks, shows, campaign_folder):
    """
    Reduction phase of analysis: aggregate the per-folder CSVs produced by
    ``check_save_folders`` and render (optionally show) the plots. Must run exactly once,
    after every folder has been checked, since ``plot_stat`` reads across all folders.

    Make exceptional cases for prestige (many subcategories) and goods_produced (many goods).
    """
    check_map = build_check_map()
    for check in checks:
        show = check in shows
        if check == "total_prestige":
            for prestige in prestige_columns:
                plot_stat(campaign_folder, prestige, input_file="prestige.csv", players=True, show=show)
            plot_stat(campaign_folder, "total", input_file="prestige.csv", players=True, save_name="total_prestige.csv", show=show)
        elif check == "goods_produced":
            plot_goods_produced(campaign_folder, 10, show=show)
        elif check == "GDP":
            for finance in finance_columns:
                plot_stat(campaign_folder, finance, input_file="finance.csv", players=True, show=show)
        elif check == "literacy":
            for demographic in demographics_columns:
                plot_stat(campaign_folder, demographic, input_file="demographics.csv", players=True, show=show)
        elif check == "levels":
            # Companies checkbox (like "GDP" for finance): plot every company metric.
            # Per-company metrics need the company-aware plotter (a line is a company,
            # not a country); the per-country rollups use the ordinary plot_stat since
            # company_countries.csv carries tag/country columns.
            for metric in company_columns:
                plot_company_stat(campaign_folder, metric, input_file="companies.csv", players=True, show=show)
            for metric in company_country_columns:
                plot_stat(campaign_folder, metric, input_file="company_countries.csv", players=True, show=show)
        elif check in company_columns:
            plot_company_stat(campaign_folder, check, input_file="companies.csv", players=True, show=show)
        else:
            check_class, outfile = check_map[check]
            plot_stat(campaign_folder, check, input_file=outfile, show=show, players=True)


def perform_checking(checks, shows, campaign_folder, stop_event, finish_event):
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
        plot_results(checks, shows, campaign_folder)
    except InterruptedError as e:
        raise InterruptedError("Checking stopped:", e)
    finally:
        stop_event.set()
        finish_event.set()

