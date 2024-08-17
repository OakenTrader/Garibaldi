import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
from scripts.checkers.checkers_functions import get_building_output, get_country_name, get_version, resolve_compatibility_multiple
from scripts.convert_localization import get_all_localization
from scripts.helpers.utility import *


def check_construction(address=None, **kwargs):
    """
    Retrieve the construction, construction in use, construction cost and its average per construction point
    of player nations and nations with more construction than a minimum player's construction
    """
    localization = get_all_localization()
    topics = ["building_manager", "country_manager", "pops", "player_manager"]
    year, month, day = get_save_date(address)
    version = get_version(address)
    data = load_save(topics, address)
    buildings, countries, pops, players = [data[topic]["database"] for topic in topics]
    csectors = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_construction_sector"}
    for pop_id, pop in pops.items():
        if "workplace" not in pop or pop["workplace"] not in csectors:
            continue
        building = csectors[pop["workplace"]]
        if "pops_employed" not in building:
            building["pops_employed"] = dict()
        building["pops_employed"][pop_id] = pop
    
    variables = resolve_compatibility_multiple(["dir_static_modifiers", "building_levels", "construction_cost"], version)
    players = [countries[v["country"]]["definition"] for k, v in players.items() if retrieve_from_tree(countries, [v["country"], "definition"]) is not None]
    def_production_methods = load_def("production_methods/13_construction.txt", "Common Directory")
    def_static_modifiers = load_def(variables["dir_static_modifiers"], "Common Directory")
    base_construction = float(def_static_modifiers["base_values"]["country_construction_add"])

    columns = ["id", "tag", "country", "construction", "used_cons", "avg_cost", "total_cost"]
    df_construction = pd.DataFrame(columns=columns)
    for country_id, country in countries.items():
        if country == "none" or "states" not in country:
            continue
        if "player_only" in kwargs and kwargs["player_only"] and country["definition"] not in players:
            continue
        states = country["states"]["value"]
        construction = base_construction
        construction_list = []
        csectors_country = {i: csectors[i] for i in csectors if csectors[i]["state"] in states}
        for csector_id, csector_c in csectors_country.items():
            if csector_c[variables["building_levels"]] == "0":
                continue
            construction_out = get_building_output(csector_c, "country_construction_add", def_production_methods)
            if (construction_cost_term := variables["construction_cost"]) in csector_c:
                construction_cost = -float(csector_c[construction_cost_term])
            else:
                warnings.warn(f"No construction cost for building {csector_c}, assumed zero cost instead")
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
            average_cost = total_cost / used_cons
        else:
            total_cost = 0
            average_cost = 0

        country_name = get_country_name(country, localization)
        new_data = pd.DataFrame([[country_id, country["definition"], country_name, construction, used_cons, average_cost, total_cost]], columns=columns)
        df_construction = pd.concat([df_construction, new_data], ignore_index=True)

    df_construction = df_construction.sort_values(by='construction', ascending=False)
    # Output countries that are players or have more construction than the players' least
    players_cons = df_construction[df_construction["tag"].isin(players)]
    non_players_cons = df_construction[~df_construction["tag"].isin(players)]
    min_players_cons = players_cons["construction"].min() + 0.0001 # Prevent showing everyone if a player has 10 construction
    df_construction = pd.concat([players_cons, non_players_cons[non_players_cons["construction"] >= min_players_cons]])
    df_construction = df_construction.sort_values(by='construction', ascending=False)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(f"{day}/{month}/{year}")
        print(df_construction)
        df_construction.to_csv(f"{address}/construction.csv", sep=",", index=False)
        with open(f"{address}/construction.txt", "w") as file:
            file.write(f"{day}/{month}/{year}\n")
            file.write(df_construction.to_string())

    return df_construction