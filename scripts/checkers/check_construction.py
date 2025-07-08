import pandas as pd
import numpy as np
import warnings
from scripts.checkers.check_base import Checker
from scripts.checkers.checkers_functions import get_building_output, get_country_name, national_modifiers_manager
from scripts.helpers.utility import *

class CheckConstruction(Checker):
    """
    Retrieve the construction, construction in use, construction cost and its average per construction point
    of player nations and nations with more construction than a minimum player's construction
    """
    requirements = ["building_manager", "country_manager", "pops"]
    output = {"construction.csv": ["construction", "avg_cost"]}

    def __init__(self):
        super().__init__()

    def execute_check(self, cache):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = cache["metadata"]["players"]
        address = cache["address"]

        relevant_modifiers = ["country_construction_add"]
        buildings = save_data["building_manager"]["database"]
        countries = save_data["country_manager"]["database"]
        pops = save_data["pops"]["database"]
        players = [v[1] for v in players]

        csectors = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_construction_sector"}
        for pop_id, pop in pops.items():
            if "workplace" not in pop or pop["workplace"] not in csectors:
                continue
            building = csectors[pop["workplace"]]
            if "pops_employed" not in building:
                building["pops_employed"] = dict()
            building["pops_employed"][pop_id] = pop
        
        def_production_methods = load_def_multiple("production_methods", "Common Directory")
        def_static_modifiers = {k:v for k,v in load_def_multiple("static_modifiers", "Common Directory").items() if any([vi in relevant_modifiers for vi in v.keys()])}
        base_construction = float(def_static_modifiers["base_values"]["country_construction_add"])

        columns = ["id", "tag", "country", "construction", "used_cons", "avg_cost", "total_cost"]
        df_construction = []
        for country_id, country in countries.items():
            if country == "none" or "states" not in country:
                continue
            states = country["states"]["value"]
            construction = base_construction
            construction_list = []
            csectors_country = {i: csectors[i] for i in csectors if csectors[i]["state"] in states}
            for csector_id, csector_c in csectors_country.items():
                if csector_c["levels"] == "0":
                    continue
                construction_out = get_building_output(csector_c, "country_construction_add", def_production_methods)
                if (construction_cost_term := "government_dividends") in csector_c:
                    construction_cost = -float(csector_c[construction_cost_term])
                else:
                    warnings.warn(f"No construction cost for building {csector_id}, assumed zero cost instead")
                    # raise ValueError("construction cost not available")
                    construction_cost = 0
                construction_list.append([construction_out, construction_cost])
                construction += construction_out
                csectors.pop(csector_id)
                # print(construction_out)
            
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

            if len(construction_list) > 0:
                construction_list = np.stack(construction_list)
                out_list, cost_list = construction_list[:, 0], construction_list[:, 1]
                total_cost = np.sum(cost_list)
                average_cost = total_cost / (used_cons + 0.000001)
            else:
                total_cost = 0
                average_cost = 0
            
            national_modifiers = national_modifiers_manager(country, save_date, def_static_modifiers, relevant_modifiers)
            construction += sum([float(v) for v in national_modifiers["country_construction_add"].values()])

            country_name = get_country_name(country, localization)
            new_data = pd.DataFrame([[country_id, country["definition"], country_name, construction, used_cons, average_cost, total_cost]], columns=columns)
            df_construction.append(new_data)

        df_construction = pd.concat(df_construction, ignore_index=True)
        df_construction = df_construction.sort_values(by='construction', ascending=False)
        # Output countries that are players or have more construction than the players' least
        players_cons = df_construction[df_construction["tag"].isin(players)]
        non_players_cons = df_construction[~df_construction["tag"].isin(players)]
        min_players_cons = players_cons["construction"].min() + 0.0001 # Prevent showing everyone if a player has 10 construction
        df_construction = pd.concat([players_cons, non_players_cons[non_players_cons["construction"] >= min_players_cons]])
        df_construction = df_construction.sort_values(by='construction', ascending=False)
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_construction.to_csv(f"{address}/construction.csv", sep=",", index=False)
            with open(f"{address}/construction.txt", "w", encoding="utf-8") as file:
                file.write(f"{day}/{month}/{year}\n")
                file.write(df_construction.to_string())
        print(f"Finished checking construction on {day}/{month}/{year}")

        return df_construction