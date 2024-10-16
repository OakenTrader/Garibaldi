import pandas as pd
import numpy as np
from scripts.checkers.check_base import Checker
from scripts.checkers.checkers_functions import *
from scripts.helpers.utility import *

class CheckInnovation(Checker):
    """
    Retrieve Innovation and its cap of player nations and nations with > base innovation
    """
    requirements = ["building_manager", "country_manager", "pops", "player_manager", "companies", "power_bloc_manager", "pacts", "institutions"]
    output = {"innovation.csv":["innovation", "capped_innovation"]}
    
    def __init__(self):
        super().__init__()

    def execute_check(self, cache):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = cache["metadata"]["players"]
        address = cache["address"]

        buildings = save_data["building_manager"]["database"]
        countries = save_data["country_manager"]["database"]
        pops = save_data["pops"]["database"]

        universities = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_university"}
        for pop_id, pop in pops.items():
            if "workplace" not in pop or pop["workplace"] not in universities:
                continue
            building = universities[pop["workplace"]]
            if "pops_employed" not in building:
                building["pops_employed"] = dict()
            building["pops_employed"][pop_id] = pop
        players = [v[1] for v in players]

        relevant_modifiers = ["country_weekly_innovation_add", "country_weekly_innovation_mult", "country_weekly_innovation_max_add"]
        def_production_methods = load_def_multiple("production_methods", "Common Directory")
        def_static_modifiers = load_def_multiple("static_modifiers", "Common Directory")
        base_innovation = float(retrieve_from_tree(def_static_modifiers, ["base_values", "country_weekly_innovation_add"], null=0))
        literacy_innovation = float(retrieve_from_tree(def_static_modifiers, ["country_literacy_rate", "country_weekly_innovation_add"], null=0))
        literacy_max_inno = float(retrieve_from_tree(def_static_modifiers, ["country_literacy_rate", "country_weekly_innovation_max_add"], null=0))
        companies_manager(save_data, countries, relevant_modifiers)
        subject_manager(save_data, countries)
        institution_manager(save_data, countries, ["institution_schools"])
        principles, blocs = bloc_manager(save_data, relevant_modifiers)

        columns = ["id", "tag", "country", "innovation", "cap"]
        df_innov = []
        for kc, country in countries.items():
            if any([country == "none", "states" not in country]):
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

            inno_cap = base_innovation + literacy_max_inno * float(literacy)

            states = country["states"]["value"]
            innov = base_innovation + literacy_innovation * float(literacy)
            innov_mult = 1
            innov_list = []
            universities_country = {i: universities[i] for i in universities if universities[i]["state"] in states}
            for u_key, university_c in universities_country.items():
                innov_out = get_building_output(university_c, "country_weekly_innovation_add", def_production_methods)
                innov_list.append(innov_out)
                innov += innov_out

            # Companies
            if (companies := retrieve_from_tree(country, "companies")) is not None:
                for company_name, company in companies.items():
                    inno_cap += float(retrieve_from_tree(company, ["prosperity_modifier", "country_weekly_innovation_max_add"], 0))
                    innov += float(retrieve_from_tree(company, ["prosperity_modifier", "country_weekly_innovation_add"], 0))
                    innov_mult += float(retrieve_from_tree(company, ["prosperity_modifier", "country_weekly_innovation_mult"], 0))

            # Power blocs education principles
            if "power_bloc_as_core" in country:
                if (bloc := retrieve_from_tree(blocs, country["power_bloc_as_core"])) is not None:
                    for principle in bloc["principles"]["value"]:
                        bloc_cap = float(retrieve_from_tree(principles, [principle, "institution_modifier", "country_weekly_innovation_max_add"], 0)) * float(retrieve_from_tree(country, ["institutions", "institution_schools"], 0))
                        inno_cap += bloc_cap

            national_modifiers = national_modifiers_manager(country, save_date, def_static_modifiers, relevant_modifiers)
            innov += sum([float(v) for v in national_modifiers["country_weekly_innovation_add"]])
            inno_cap += sum([float(v) for v in national_modifiers["country_weekly_innovation_max_add"]])

            innov = innov * innov_mult
            country_name = get_country_name(country, localization)

            new_data = pd.DataFrame([[kc, country["definition"], country_name, innov, inno_cap]], columns=columns)
            df_innov.append(new_data)
            # print(kc, country["definition"], innov)

        df_innov = pd.concat(df_innov, ignore_index=True)
        players_innov = df_innov[df_innov["tag"].isin(players)]
        non_players_innov = df_innov[~df_innov["tag"].isin(players)]
        min_players_innov = players_innov["innovation"].min() + 0.0001 # Prevent showing everyone if a player has 50 innovation
        df_innov = pd.concat([players_innov, non_players_innov[non_players_innov["innovation"] >= min_players_innov]])
        df_innov["capped_innovation"] = np.minimum(df_innov["innovation"], df_innov["cap"])
        df_innov = df_innov.sort_values(by='capped_innovation', ascending=False)

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_innov.to_csv(f"{address}/innovation.csv", sep=",", index=False)
            with open(f"{address}/innovation.txt", "w", encoding="utf-8") as file:
                file.write(f"{day}/{month}/{year}\n")
                file.write(df_innov.to_string())
        print(f"Finished checking innovation on {day}/{month}/{year}")
        return df_innov