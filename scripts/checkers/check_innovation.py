import pandas as pd
import numpy as np
from scripts.convert_localization import get_all_localization
from scripts.helpers.utility import load_def, load_save, retrieve_from_tree, get_save_date

def check_innovation(address=None, **kwargs):
    """
    Retrieve Innovation and its cap of player nations and nations with > base innovation
    """
    localization = get_all_localization()
    topics = ["building_manager", "country_manager", "pops", "player_manager"]
    year, month, day = get_save_date(address)
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

    def_production_methods = load_def("./common/production_methods/07_government.txt")
    def_static_modifiers = load_def("./common/modifiers/00_static_modifiers.txt")
    base_innovation = float(def_static_modifiers["base_values"]["country_weekly_innovation_add"])

    columns = ["tag", "country", "innovation", "cap"]
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
            output = 0
            employees = 0
            employees_pl = dict()
            for pm_name in university_c["production_methods"]["value"]:
                pm = def_production_methods[pm_name]
                if (innov_uni := retrieve_from_tree(pm, ["country_modifiers", "workforce_scaled", "country_weekly_innovation_add"])) is not None:
                    output += float(innov_uni)
                if (employees_dict := retrieve_from_tree(pm, ["building_modifiers", "level_scaled"])) is not None:
                    for key, addition in employees_dict.items():
                        if key not in employees_pl:
                            employees_pl[key] = int(addition)
                        else:
                            employees_pl[key] += int(addition)
            
            if "pops_employed" in university_c:
                for key, pop in university_c["pops_employed"].items():
                    employees += int(pop["workforce"] )

            # print(employees_pl)
            # print(f"Total Employees at level {int(university_c['level'])}: {employees}")
            employees /= sum([employees_pl[e] for e in employees_pl])
            # print(f"Employees ratio: {employees}")
            # print([employees_pl[e] for e in employees_pl])
            if "throughput" not in university_c:
                university_c["throughput"] = 1.0
            # print(output)
            innov_out =  output * float(university_c["throughput"]) * employees
            innov_list.append(innov_out)
            innov += innov_out

        if not (kc in players or innov > base_innovation):
            continue
        if country["definition"] in localization:
            country_name = localization[country["definition"]]
        else:
            country_name = country["definition"]
        if retrieve_from_tree(country, "civil_war") is not None:
            country_name = "Revolutionary " + country_name 

        new_data = pd.DataFrame([[country["definition"], country_name, innov, inno_cap]], columns=columns)
        df_innov = pd.concat([df_innov, new_data], ignore_index=True)
        # print(kc, country["definition"], innov)

    players_innov = df_innov[df_innov["tag"].isin(players)]
    min_players_innov = players_innov["innovation"].min()
    df_innov = df_innov[df_innov["innovation"] >= min_players_innov]
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