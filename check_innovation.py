import json
import pandas as pd
import numpy as np
import os

def check_innovation():
    def load():
        if "save_output_country_manager.json" in os.listdir("./save files"):
            with open("./save files/save_output_building_manager.json", "r") as file:
                buildings = json.load(file)["database"]
                universities = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_university"}
            with open("./save files/save_output_country_manager.json", "r") as file:
                countries = json.load(file)["database"]
            with open("./save files/save_output_pops.json", "r") as file:
                pops = {k: v for k, v in json.load(file)["database"].items() if "workplace" in v and v["workplace"] in universities}
        elif "save_output_all.json" in os.listdir("./save files"):
            with open("./save files/save_output_all.json", "r") as file:
                data = json.load(file)
                buildings = data["building_manager"]["database"]
                countries = data["country_manager"]["database"]
                universities = {i: buildings[i] for i in buildings if type(buildings[i]) == dict and buildings[i]["building"] == "building_university"}
                pops = {k: v for k, v in data["pops"]["database"].items() if "workplace" in v and v["workplace"] in universities}
        return universities, countries, pops

    universities, countries, pops = load()

    with open("./common_json/production_methods/07_government.json", "r") as file:
        pms = json.load(file)
    base = 50
    df_inno = pd.DataFrame(columns=["country", "innovation", "cap"])
    for kc in countries:
        country = countries[kc]
        if country == "none":
            continue
        literacy = country["literacy"]["channels"]["0"]["values"]["value"][-1]
        inno_cap = base + 150 * float(literacy)
        states = country["states"]["value"]
        innov = base
        innov_list = []
        universities_country = {i: universities[i] for i in universities if universities[i]["state"] in states}
        for i in universities_country:
            university_c = universities_country[i]
            output = 0
            employees = 0
            employees_pl = dict()
            for kpm, pm in pms.items():
                if kpm in university_c["production_methods"]["value"]:
                    if "country_modifiers" in pm and "workforce_scaled" in pm["country_modifiers"] and "country_weekly_innovation_add" in pm["country_modifiers"]["workforce_scaled"]:
                        output += float(pm["country_modifiers"]["workforce_scaled"]["country_weekly_innovation_add"])
                    if "building_modifiers" in pm and "level_scaled" in pm["building_modifiers"]:
                        for key, addition in pm["building_modifiers"]["level_scaled"].items():
                            if key not in employees_pl:
                                employees_pl[key] = int(addition)
                            else:
                                employees_pl[key] += int(addition)
            
            for pop in pops.copy():
                if pops[pop]["workplace"] == i:
                    pp = pops.pop(pop)
                    employees += int(pp["workforce"] )

            employees /= sum([employees_pl[e] for e in employees_pl])
            if "throughput" not in university_c:
                university_c["throughput"] = 1.0
            innov_out =  output * float(university_c["throughput"]) * employees
            innov_list.append(innov_out)
            innov += innov_out
            universities.pop(i)
        print(country["definition"], innov)
        new_data = pd.DataFrame([[country["definition"], innov, inno_cap]], columns=["country", "innovation", "cap"])
        df_inno = pd.concat([df_inno, new_data], ignore_index=True)
    df_inno["capped_innovation"] = np.minimum(df_inno["innovation"], df_inno["cap"])
    df_inno = df_inno.sort_values(by='capped_innovation', ascending=False)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df_inno)
        
check_innovation()