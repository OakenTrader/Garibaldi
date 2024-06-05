import convert_localization, extractor
from utility import load, jopen
from pathlib import Path
import time

def get_tech_tree(address):
    localization = convert_localization.get_all_localization()

    t0 = time.time()
    countries, technologies, players = load(["country_manager", "technology", "player_manager"], address)
    countries, technologies, players = countries["database"], technologies["database"], players["database"]
    print(f"Loaded data in {time.time() - t0} seconds")
    players = [v["country"] for k, v in players.items()]

    techs = dict()
    for key in technologies:
        if technologies[key] == "none":
            continue
        researched = technologies[key]["acquired_technologies"]["value"]
        for t in researched:
            if t not in techs:
                techs[t] = 1
            else:
                techs[t] += 1
    
    def_prod_tech = jopen("./common_json/technology/technologies/10_production.json")
    def_mil_tech = jopen("./common_json/technology/technologies/20_military.json")
    def_soc_tech = jopen("./common_json/technology/technologies/30_society.json")

    # Determine which new tech is being researched
    print("Techs in research")
    researching_techs = dict()
    for key in technologies:
        if "research_technology" in technologies[key]:
            researching = technologies[key]["research_technology"]
            if researching not in researching_techs:
                researching_techs[researching] = 1
            else:
                researching_techs[researching] += 1
    print(researching_techs)
    print("Research Frontier")
    frontier = [tech for tech in researching_techs if tech not in techs]
    print(frontier)

    # Who is researching which
    notable_countries = players
    for tech_id in technologies:
        if "research_technology" not in technologies[tech_id]:
            continue
        country_id = technologies[tech_id]["country"]
        researching_tech = technologies[tech_id]["research_technology"]
        country_tag = countries[country_id]["definition"]
        if country_tag not in localization:
            country_name = country_tag
        else:
            country_name = localization[country_tag]
        if researching_tech in frontier or country_id in notable_countries:
            print(f"{tech_id} {country_tag} {country_name} : {researching_tech}")
            his_tech = technologies[tech_id]["acquired_technologies"]["value"]
            his_prod_tech = [tech for tech in his_tech if tech in def_prod_tech]
            his_mil_tech = [tech for tech in his_tech if tech in def_mil_tech]
            his_soc_tech = [tech for tech in his_tech if tech in def_soc_tech]
            print(f"Number of tech: {len(his_tech)}, {[len(his_prod_tech), len(his_mil_tech), len(his_soc_tech)]}")
            his_missing_tech = [tech for tech in techs if tech not in his_tech]
            print("Missing tech")
            print(len(his_missing_tech), his_missing_tech)
            print("")