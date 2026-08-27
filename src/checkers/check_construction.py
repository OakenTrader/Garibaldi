import pandas as pd
import numpy as np
import warnings
from src.checkers.aggregates import Agg, Call
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import BUILD_GROUP, EMPLOYED_WORKFORCE, building_output_of, get_building_output, get_country_name, national_modifiers_manager, safe_ratio, MISSING
from src.helpers.utility import *

def _is_active_csector(building, ctx):
    return (building.get("building") == "building_construction_sector"
            and building.get("levels") != "0")


def _construction_cost(building, ctx):
    if "government_dividends" in building:
        return -float(building["government_dividends"])
    warnings.warn(f"No construction cost for building {building.get('_id', '?')}, "
                  "assumed zero cost instead")
    return 0.0


# FIXME New base construction now scales with GDP, which is so little it is ignored;
# the define is def_static_modifiers["base_values"]["country_construction_add"].
BASE_CONSTRUCTION = 10

RELEVANT_MODIFIERS = ["country_construction_add"]

_ACTIVE_CSECTOR = Call(_is_active_csector, name="active_csector")

CONSTRUCTION_CAPACITY = Agg(
    "building", by=BUILD_GROUP, name="construction_capacity",
    value=building_output_of("country_construction_add"), where=_ACTIVE_CSECTOR)
CONSTRUCTION_COST = Agg(
    "building", by=BUILD_GROUP, name="construction_total_cost",
    value=Call(_construction_cost, name="construction_cost"), where=_ACTIVE_CSECTOR)


class CheckConstruction(Checker):
    """
    Retrieve the construction, construction in use, construction cost and its average per construction point
    of player nations and nations with more construction than a minimum player's construction
    """
    name = "CheckConstruction"
    display_name = "Construction"
    sort_order = 10
    requirements = ["building_manager", "country_manager", "pops"]
    column_backed = {"pops": "pop"}  # reached only through the declared aggregates
    aggregates = [EMPLOYED_WORKFORCE, CONSTRUCTION_CAPACITY, CONSTRUCTION_COST]
    definitions = ("production_methods", "static_modifiers")
    output = {"construction.csv": ["construction", "avg_cost"]}

    def __init__(self):
        super().__init__()

    def before_countries(self, cache):
        self.capacity = cache["aggregates"].get("construction_capacity", {})
        self.costs = cache["aggregates"].get("construction_total_cost", {})
        self.save_date = cache["metadata"]["save_date"]
        self.static_modifiers = {
            name: modifier for name, modifier in cache["definitions"]["static_modifiers"].items()
            if any(entry in RELEVANT_MODIFIERS for entry in modifier)}

    def on_country(self, country_id, country, cache):
        if "states" not in country:
            return None
        # Absent from the aggregate means no construction sectors; base stands.
        construction = BASE_CONSTRUCTION + self.capacity.get(country_id, 0)

        """
        Check current used construction
        """
        used_cons = 0
        if (gov_queue := retrieve_from_tree(country, ["government_queue", "construction_elements"])) is not None:
            gov_cons = [float(v["base_construction_speed"]) for k, v in gov_queue.items() if "base_construction_speed" in v]
            used_cons += sum(gov_cons)
        if (priv_queue := retrieve_from_tree(country, ["private_queue", "construction_elements"])) is not None:
            priv_cons = [float(v["base_construction_speed"]) for k, v in priv_queue.items() if "base_construction_speed" in v]
            used_cons += sum(priv_cons)

        if country_id in self.costs:
            total_cost = self.costs[country_id]
            # avg cost per construction point is undefined when nothing is being
            # built (used_cons == 0) -> MISSING, not a fabricated 0.
            average_cost = safe_ratio(total_cost, used_cons)
            if average_cost > 10000:  # NaN compares False, so a MISSING stays MISSING
                average_cost = MISSING  # implausibly large -> spurious
        else:
            total_cost = 0
            average_cost = MISSING

        national_modifiers = national_modifiers_manager(country, self.save_date, self.static_modifiers, RELEVANT_MODIFIERS)
        construction += sum([float(v) for v in national_modifiers["country_construction_add"].values()])

        country_name = get_country_name(country, cache["localization"])
        return [country_id, country["definition"], country_name, construction,
                used_cons, average_cost, total_cost]

    def execute_check(self, cache):
        save_date = cache["metadata"]["save_date"]
        players = players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        columns = ["id", "tag", "country", "construction", "used_cons", "avg_cost", "total_cost"]
        df_construction = pd.DataFrame(cache["country_rows"][self.name], columns=columns)
        df_construction = df_construction.sort_values(by='construction', ascending=False)

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_construction.to_csv(f"{address}/data/construction.csv", sep=",", index=False)
            df_construction_players = df_construction[df_construction["id"].isin(players)]
            df_construction_players.to_csv(f"{address}/construction.csv", sep=",", index=False)
            with open(f"{address}/construction.txt", "w", encoding="utf-8") as file:
                file.write(f"{day}/{month}/{year}\n")
                file.write(df_construction_players.to_string())
        print(f"Finished checking construction on {day}/{month}/{year}")

        return df_construction