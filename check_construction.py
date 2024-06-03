#%%
import json
import pandas as pd
import numpy as np
import os

def check_construction():
    def load():
        if "save_output_country_manager.json" in os.listdir("./save files"):
            with open("./save files/save_output_building_manager.json", "r") as file:
                buildings = json.load(file)["database"]
            with open("./save files/save_output_country_manager.json", "r") as file:
                countries = json.load(file)["database"]
                csectors = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_construction_sector"}
            with open("./save files/save_output_pops.json", "r") as file:
                pops = {k: v for k, v in json.load(file)["database"].items() if "workplace" in v and v["workplace"] in csectors}
        elif "save_output_all.json" in os.listdir("./save files"):
            with open("./save files/save_output_all.json", "r") as file:
                data = json.load(file)
                buildings = data["building_manager"]["database"]
                countries = data["country_manager"]["database"]
                csectors = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_construction_sector"}
                pops = {k: v for k, v in data["pops"]["database"].items() if "workplace" in v and v["workplace"] in csectors}
        return csectors, countries, pops

    csectors, countries, pops = load()
    # print(pops)

    with open("./common_json/production_methods/13_construction.json", "r") as file:
        pms = json.load(file)
        # print(pms)
    base = 10
    columns = ["country", "construction", "used_cons", "avg_cost", "total_cost"]
    df_construction = pd.DataFrame(columns=columns)
    for kc in countries:
        country = countries[kc]
        if country == "none":
            continue
        states = country["states"]["value"]
        construction = base
        construction_list = []
        csectors_country = {i: csectors[i] for i in csectors if csectors[i]["state"] in states}
        for i in csectors_country:
            csector_c = csectors_country[i]
            if csector_c["level"] == "0":
                continue
            # print(university_c)
            output = 0
            employees = 0
            employees_pl = dict()
            for kpm, pm in pms.items():
                # print(pm)
                # print(university_c["production_methods"]["value"])
                if kpm in csector_c["production_methods"]["value"]:
                    if "country_modifiers" in pm and "workforce_scaled" in pm["country_modifiers"] and "country_construction_add" in pm["country_modifiers"]["workforce_scaled"]:
                        output += float(pm["country_modifiers"]["workforce_scaled"]["country_construction_add"])
                    if "building_modifiers" in pm and "level_scaled" in pm["building_modifiers"]:
                        for key, addition in pm["building_modifiers"]["level_scaled"].items():
                            # print(key, addition)
                            if key not in employees_pl:
                                employees_pl[key] = int(addition)
                            else:
                                employees_pl[key] += int(addition)
            
            for pop in pops.copy():
                # print(f"pop: {pop['workplace']}")
                if pops[pop]["workplace"] == i:
                    pp = pops.pop(pop)
                    employees += int(pp["workforce"] )

            # print(employees_pl)
            # print(f"Total Employees at level {int(csector_c['level'])}: {employees}")
            employees /= sum([employees_pl[e] for e in employees_pl])
            # print(f"Employees ratio: {employees}")
            # print([employees_pl[e] for e in employees_pl])
            if "throughput" not in csector_c:
                csector_c["throughput"] = 1.0
            # print(output)

            construction_out =  output * float(csector_c["throughput"]) * employees
            try:
                construction_cost = float(csector_c["goods_cost"]) + float(csector_c["salaries"])
            except:
                print(csector_c)
                construction_cost = -float(csector_c["dividends"])
            construction_list.append([construction_out, construction_cost])
            construction += construction_out
            csectors.pop(i)
            # print(construction_out)
        
        """
        Check current used construction
        """
        used_cons = 0
        if "government_queue" in country:
            gov_queue = country["government_queue"]["construction_elements"]
            gov_cons = [float(v["base_construction_speed"]) for k, v in gov_queue.items() if "base_construction_speed" in v]
            used_cons += sum(gov_cons)
        if "private_queue" in country:
            priv_queue = country["private_queue"]["construction_elements"]
            priv_cons = [float(v["base_construction_speed"]) for k, v in priv_queue.items() if "base_construction_speed" in v]
            used_cons += sum(priv_cons)

        if len(construction_list) > 0:
            construction_list = np.stack(construction_list)
            out_list, cost_list = construction_list[:, 0], construction_list[:, 1]
            total_cost = np.sum(cost_list)
            average_cost = total_cost / used_cons
            # print(country["definition"], construction)
            # print(construction_list)
        else:
            total_cost = 0
            average_cost = 0

        new_data = pd.DataFrame([[country["definition"], construction, used_cons, average_cost, total_cost]], columns=columns)
        df_construction = pd.concat([df_construction, new_data], ignore_index=True)
    df_construction = df_construction.sort_values(by='construction', ascending=False)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df_construction)

check_construction()

# %%
