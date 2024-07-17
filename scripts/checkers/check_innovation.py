import pandas as pd
import numpy as np
from scripts.convert_localization import get_all_localization
from scripts.helpers.utility import *

def check_innovation(address=None, **kwargs):
    """
    Retrieve Innovation and its cap of player nations and nations with > base innovation
    """
    localization = get_all_localization()
    topics = ["building_manager", "country_manager", "pops", "player_manager"]
    year, month, day = get_save_date(address)
    version = get_version(address)
    data = load_save(topics, address)
    buildings, countries, pops, players = [data[topic]["database"] for topic in topics]
    universities = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_university"}
    for pop_id, pop in pops.items():
        if "workplace" not in pop or pop["workplace"] not in universities:
            continue
        building = universities[pop["workplace"]]
        if "pops_employed" not in building:
            building["pops_employed"] = dict()
        building["pops_employed"][pop_id] = pop
    players = [countries[v["country"]]["definition"] for k, v in players.items() if countries[v["country"]] != "none"]

    variables = resolve_compatibility_multiple(["dir_static_modifiers"], version)
    def_production_methods = load_def_multiple("production_methods", "Common Directory")
    def_static_modifiers = load_def(variables["dir_static_modifiers"], "Common Directory")
    base_innovation = float(def_static_modifiers["base_values"]["country_weekly_innovation_add"])

    columns = ["id", "tag", "country", "innovation", "cap"]
    df_innov = pd.DataFrame(columns=columns)
    for kc, country in countries.items():
        if any([country == "none", "states" not in country]):
            continue
        if "player_only" in kwargs and kwargs["player_only"] and country["definition"] not in players:
            continue
        try:
            literacy = country["literacy"]["channels"]["0"]["values"]["value"][-1]
        except KeyError:
            literacy = 0
            """
            FIXME Some countries don't provide literacy graph and we need to extract it somehow else
            Either interpolate it from nearby saves or calculate directly from pops info
            """
            # raise KeyError(country["literacy"])
        inno_cap = base_innovation + 150 * float(literacy)
        states = country["states"]["value"]
        innov = base_innovation
        innov_list = []
        universities_country = {i: universities[i] for i in universities if universities[i]["state"] in states}
        for u_key, university_c in universities_country.items():
            innov_out = get_building_output(university_c, "country_weekly_innovation_add", def_production_methods)
            innov_list.append(innov_out)
            innov += innov_out

        country_name = get_country_name(country, localization)

        new_data = pd.DataFrame([[kc, country["definition"], country_name, innov, inno_cap]], columns=columns)
        df_innov = pd.concat([df_innov, new_data], ignore_index=True)
        # print(kc, country["definition"], innov)

    players_innov = df_innov[df_innov["tag"].isin(players)]
    non_players_innov = df_innov[~df_innov["tag"].isin(players)]
    min_players_innov = players_innov["innovation"].min() + 0.0001 # Prevent showing everyone if a player has 50 innovation
    df_innov = pd.concat([players_innov, non_players_innov[non_players_innov["innovation"] >= min_players_innov]])
    df_innov["capped_innovation"] = np.minimum(df_innov["innovation"], df_innov["cap"])
    df_innov = df_innov.sort_values(by='capped_innovation', ascending=False)

    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(f"{day}/{month}/{year}")
        print(df_innov)
        df_innov.to_csv(f"{address}/innovation.csv", sep=",", index=False)
        with open(f"{address}/innovation.txt", "w") as file:
            file.write(f"{day}/{month}/{year}\n")
            file.write(df_innov.to_string())
    return df_innov