import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from convert_localization import get_all_localization
from utility import jopen, retrieve_from_tree, load

def check_construction(address=None):
    """
    Retrieve the construction, construction in use, construction cost and its average per construction point
    of player nations and nations with more construction than a minimum player's construction
    """
    localization = get_all_localization()
    topics = ["building_manager", "country_manager", "pops", "player_manager"]
    data = load(topics, address)
    buildings, countries, pops, players = [data[topic]["database"] for topic in topics]
    csectors = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_construction_sector"}
    for pop_id, pop in pops.items():
        if "workplace" not in pop or pop["workplace"] not in csectors:
            continue
        building = csectors[pop["workplace"]]
        if "pops_employed" not in building:
            building["pops_employed"] = dict()
        building["pops_employed"][pop_id] = pop
    players = [v["country"] for k, v in players.items()]

    def_production_methods = jopen("./common_json/production_methods/13_construction.json")
    def_static_modifiers = jopen("./common_json/modifiers/00_static_modifiers.json")
    base_construction = float(def_static_modifiers["base_values"]["country_construction_add"])

    columns = ["id", "country", "construction", "used_cons", "avg_cost", "total_cost"]
    df_construction = pd.DataFrame(columns=columns)
    for country_id, country in countries.items():
        if country == "none" or "states" not in country:
            continue
        states = country["states"]["value"]
        construction = base_construction
        construction_list = []
        csectors_country = {i: csectors[i] for i in csectors if csectors[i]["state"] in states}
        for csector_id, csector_c in csectors_country.items():
            if csector_c["level"] == "0":
                continue
            output = 0
            employees = 0
            employees_pl = dict()

            for pm_name in csector_c["production_methods"]["value"]:
                pm = def_production_methods[pm_name]
                if (innov_uni := retrieve_from_tree(pm, ["country_modifiers", "workforce_scaled", "country_construction_add"])) is not None:
                    output += float(innov_uni)
                if (employees_dict := retrieve_from_tree(pm, ["building_modifiers", "level_scaled"])) is not None:
                    for key, addition in employees_dict.items():
                        if key not in employees_pl:
                            employees_pl[key] = int(addition)
                        else:
                            employees_pl[key] += int(addition)
            
            for key, pop in csector_c["pops_employed"].items():
                employees += int(pop["workforce"] )

            # print(employees_pl)
            # print(f"Total Employees at level {int(csector_c['level'])}: {employees}")
            employees /= sum([employees_pl[e] for e in employees_pl])
            # print(f"Employees ratio: {employees}")
            # print([employees_pl[e] for e in employees_pl])
            if "throughput" not in csector_c:
                csector_c["throughput"] = 1.0

            construction_out =  output * float(csector_c["throughput"]) * employees
            try:
                construction_cost = float(csector_c["goods_cost"]) + float(csector_c["salaries"])
            except:
                # print(csector_c)
                construction_cost = -float(csector_c["dividends"])
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

        if country["definition"] not in localization:
            country_name = country["definition"]
        else:
            country_name = localization[country["definition"]]
        new_data = pd.DataFrame([[country_id, country_name, construction, used_cons, average_cost, total_cost]], columns=columns)
        df_construction = pd.concat([df_construction, new_data], ignore_index=True)

    df_construction = df_construction.sort_values(by='construction', ascending=False)
    # Output countries that are players or have more construction than the players' least
    players_cons = df_construction[df_construction["id"].isin(players)]
    min_players_cons = players_cons["construction"].min()
    df_construction = df_construction[df_construction["construction"] >= min_players_cons]
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df_construction)
        """
        [ ] Print to a file 
        """

    return df_construction

def plot_construction(dfs):
    fig, ax = plt.subplots()
    countries = dict()
    for year, df in dfs.items():
        df = df.to_numpy()
        for row in df:
            country = row[1]
            if country not in countries:
                countries[country] = []
            countries[country].append([year, row[2]])
    for name, country in countries.items():
        df = np.stack(country)
        ax.plot(df[:, 0], df[:, 1], label=name)
    ax.legend()
    ax.set_title("Construction graph over the years")
    ax.grid(True)
    plt.show()