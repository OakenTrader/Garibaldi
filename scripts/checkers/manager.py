from scripts.checkers.checkers_functions import *
from scripts.checkers.check_construction import CheckConstruction
from scripts.checkers.check_innovation import CheckInnovation
from scripts.checkers.check_infamy import CheckInfamy
from scripts.checkers.check_prestige import CheckPrestige, prestige_columns
from scripts.checkers.check_tech import CheckTech

from scripts.helpers.plotter import plot_stat, plot_goods_produced
from scripts.convert_localization import get_all_localization
import os, glob

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
        for check in self.checks:
            check.check(self.cache)

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
            for _, player in players.items():
                player_id = player["country"]
                player_tag = countries[player_id]["definition"]
                player_country = get_country_name(countries[player_id], self.localization)
                player_data.append([int(player_id), player_tag, player_country])
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

def perform_checking(checks, shows, campaign_folder, stop_event, finish_event):
    """
    Interface between GUI and the checkers / plotters
    """
    check_map = dict()
    all_checkers = [CheckConstruction, CheckInnovation, CheckInfamy, CheckPrestige, CheckTech]
    for checker_class in all_checkers:
        for output, outvars in checker_class.output.items():
            for outvar in outvars:
                check_map[outvar] = (checker_class, output)
    try:
        checkers = [c() for c in list(set([check_map[check][0] for check in checks]))] # Instantiate a single object from each class
        for folder in glob.glob(f".\\saves\\{campaign_folder}\\*\\"):
            if stop_event.is_set():
                raise InterruptedError("Stop event set")
            if is_reserved_folder(folder):
                continue
            save = SaveManager(folder, checkers)
            save.start_checking()
        """
        Make exceptional cases for prestige (many subcategories), tech (no plot yet) and goods_produced (many goods)
        """
        for check in checks:
            show = check in shows
            if check == "total_prestige":
                for prestige in prestige_columns:
                    plot_stat(campaign_folder, prestige, input_file="prestige.csv", players=True, show=show)
                plot_stat(campaign_folder, "total", input_file="prestige.csv", players=True, save_name="total_prestige.csv", show=show)
            elif check == "tech_tree":
                continue
            elif check == "goods_produced":
                plot_goods_produced(campaign_folder, 10, show=show)
            else:
                check_class, outfile = check_map[check]
                plot_stat(campaign_folder, check, input_file=outfile, show=show, players=True)

    except InterruptedError as e:
        raise InterruptedError("Checking stopped:", e)
    finally:
        stop_event.set()
        finish_event.set()

