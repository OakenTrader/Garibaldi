from scripts.checkers.checkers_functions import get_country_name, get_save_date
import scripts.convert_localization as convert_localization
from scripts.helpers.utility import *

def check_tech_tree(address):
    """
    Retrieve some information about each nation's technology. i.e. number of researched techs and missing techs which are researched elsewhere
    """
    localization = convert_localization.get_all_localization()
    topics = ["country_manager", "technology", "player_manager"]
    year, month, day = get_save_date(address)
    data = load_save(topics, address)
    countries, technologies, players = [data[topic]["database"] for topic in topics]
    players = [v["country"] for k, v in players.items()]
    output = ""

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
    
    def_prod_tech = load_def("technology/technologies/10_production.txt", "Common Directory")
    def_mil_tech = load_def("technology/technologies/20_military.txt", "Common Directory")
    def_soc_tech = load_def("technology/technologies/30_society.txt", "Common Directory")

    """Determine which new tech is being researched"""
    output += "Techs in research\n"
    researching_techs = dict()
    for key in technologies:
        if "research_technology" in technologies[key]:
            researching = technologies[key]["research_technology"]
            if researching not in researching_techs:
                researching_techs[researching] = 1
            else:
                researching_techs[researching] += 1
    output += f"{researching_techs}\n"
    output += f"Research Frontier (World's new technologies being researched)\n"
    frontier = [tech for tech in researching_techs if tech not in techs]
    output += f"{frontier}\n"

    """Who is researching which"""
    notable_countries = players
    for tech_id in technologies:
        if "research_technology" not in technologies[tech_id]:
            continue
        country_id = technologies[tech_id]["country"]
        if not isinstance(countries[country_id],dict):
            continue
        researching_tech = technologies[tech_id]["research_technology"]
        country_tag = countries[country_id]["definition"]
        country_name = get_country_name(countries[country_id], localization)

        if researching_tech in frontier or country_id in notable_countries:
            output += f"{tech_id} {country_tag} {country_name} : {researching_tech}\n"
            his_tech = technologies[tech_id]["acquired_technologies"]["value"]
            his_prod_tech = [tech for tech in his_tech if tech in def_prod_tech]
            his_mil_tech = [tech for tech in his_tech if tech in def_mil_tech]
            his_soc_tech = [tech for tech in his_tech if tech in def_soc_tech]
            output += f"Number of tech: {len(his_tech)}, {[len(his_prod_tech), len(his_mil_tech), len(his_soc_tech)]}\n"
            his_missing_tech = [tech for tech in techs if tech not in his_tech]
            output += "Missing tech\n"
            output += f"{len(his_missing_tech)}, {his_missing_tech}\n\n"

    with open(f"{address}/tech_tree.txt", "w") as file:
        print(f"{day}/{month}/{year}")
        print(output)
        file.write(f"{day}/{month}/{year}\n")
        file.write(output)