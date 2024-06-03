#%%
import json, re
import convert_localization, extractor
from pathlib import Path

save_name = "./save files/1865.v3"

lcl_files = list(Path("./localization").rglob("*.yml"))
dicts = []
for f in lcl_files:
    print(f)
    names = convert_localization.get_localization(f)
    dicts.append(names)
localization = dict()
for d in dicts:
    localization.update(d)

#%%
countries_data = extractor.Extractor(save_name, "country_manager")
tech_data = extractor.Extractor(save_name,"technology")
countries_data.unquote()
tech_data.unquote()

#%%
countries_data = countries_data.data["country_manager"]["database"]
tech_data = tech_data.data["technology"]["database"]

#%%

techs = dict()
# print(tech_data["13"])
for key in tech_data:
    # print(key, tech_data[key])
    if tech_data[key] == "none":
        continue
    researched = tech_data[key]["acquired_technologies"]["value"]
    for t in researched:
        if t not in techs:
            techs[t] = 1
        else:
            techs[t] += 1

with open("./common_json/technology/technologies/10_production.json", "r") as file:
    prod_tech = [f'{tech}' for tech in json.load(file)]
with open("./common_json/technology/technologies/20_military.json", "r") as file:
    mil_tech = [f'{tech}' for tech in json.load(file)]
with open("./common_json/technology/technologies/30_society.json", "r") as file:
    soc_tech = [f'{tech}' for tech in json.load(file)]

#determine which new tech is being researched
print("Techs in research")
researching_techs = dict()
for key in tech_data:
    if "research_technology" in tech_data[key]:
        researching = tech_data[key]["research_technology"]
        if researching not in researching_techs:
            researching_techs[researching] = 1
        else:
            researching_techs[researching] += 1
print(researching_techs)
print("Research Frontier")
frontier = [tech for tech in researching_techs if tech not in techs]
print(frontier)

# Who is researching which
notable_countries = ["GBR", "RUS", "FRA", "SPA", "AUS", "TUR", "PRU", "SAR", "USA", "GER"]
for tech_id in tech_data:
    if "research_technology" not in tech_data[tech_id]:
        continue
    country_id = tech_data[tech_id]["country"]
    researching_tech = tech_data[tech_id]["research_technology"]
    country_tag = countries_data[country_id]["definition"]
    if country_tag not in localization:
        country_name = country_tag
    else:
        country_name = localization[country_tag]
    if researching_tech in frontier or country_tag in notable_countries:
        print(f"{tech_id} {country_tag} {country_name} : {researching_tech}")
        his_tech = tech_data[tech_id]["acquired_technologies"]["value"]
        his_prod_tech = [tech for tech in his_tech if tech in prod_tech]
        his_mil_tech = [tech for tech in his_tech if tech in mil_tech]
        his_soc_tech = [tech for tech in his_tech if tech in soc_tech]
        print(f"Number of tech: {len(his_tech)}, {[len(his_prod_tech), len(his_mil_tech), len(his_soc_tech)]}")
        his_missing_tech = [tech for tech in techs if tech not in his_tech]
        print("Missing tech")
        print(len(his_missing_tech), his_missing_tech)
        print("")


# %%
