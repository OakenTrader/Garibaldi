from scripts.checkers.check_base import Checker
from scripts.checkers.checkers_functions import get_country_name
from scripts.helpers.utility import *
import pandas as pd

class CheckTech(Checker):
    """
    Retrieve some information about each nation's technology. i.e. number of researched techs and missing techs which are researched elsewhere
    """

    requirements = ["country_manager", "technology"]
    output = {"tech_tree.txt": ["tech_tree"]}

    def __init__(self):
        super().__init__()
    
    def execute_check(self, cache):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = cache["metadata"]["players"]
        address = cache["address"]

        countries = save_data["country_manager"]["database"]
        technologies = save_data["technology"]["database"]
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
        
        def_techs = load_def_multiple("technology/technologies", "Common Directory")
        def_prod_tech = {key:value for key, value in def_techs.items() if retrieve_from_tree(value, ["category"]) == "production"}
        def_mil_tech = {key:value for key, value in def_techs.items() if retrieve_from_tree(value, ["category"]) == "military"}
        def_soc_tech = {key:value for key, value in def_techs.items() if retrieve_from_tree(value, ["category"]) == "society"}

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
        notable_countries = [p[0] for p in players] # get country_id
        df_tech = []
        for tech_id, tech_entry in technologies.items():
            if not isinstance(tech_entry, dict):
                continue
            country_id = tech_entry["country"]
            if not isinstance(retrieve_from_tree(countries, [country_id]), dict):
                continue
            researching_tech = retrieve_from_tree(tech_entry, ["research_technology"], null="None")
            country_tag = countries[country_id]["definition"]
            country_name = get_country_name(countries[country_id], localization)

            if researching_tech in frontier or int(country_id) in notable_countries:
                output += f"{tech_id} {country_tag} {country_name} : {researching_tech}\n"
                his_tech = technologies[tech_id]["acquired_technologies"]["value"]
                his_prod_tech = [tech for tech in his_tech if tech in def_prod_tech]
                his_mil_tech = [tech for tech in his_tech if tech in def_mil_tech]
                his_soc_tech = [tech for tech in his_tech if tech in def_soc_tech]
                output += f"Number of tech: {len(his_tech)}, {[len(his_prod_tech), len(his_mil_tech), len(his_soc_tech)]}\n"
                his_missing_tech = [tech for tech in techs if tech not in his_tech]
                output += "Missing tech\n"
                output += f"{len(his_missing_tech)}, {his_missing_tech}\n\n"
                df_tech.append({"id": country_id, "tag": country_tag, "country": country_name, "production techs":len(his_prod_tech), "military techs":len(his_mil_tech), "society techs":len(his_soc_tech), "total techs":len(his_tech)})

        df_tech = pd.DataFrame(df_tech, columns=["id", "tag", "country", "production techs", "military techs", "society techs", "total techs"])
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            df_tech.to_csv(f"{address}/tech_tree.csv", sep=",", index=False)
            with open(f"{address}/tech_tree.txt", "w") as file:
                year, month, day = save_date
                file.write(f"{day}/{month}/{year}\n")
                file.write(output)
                print(f"Finished checking technology on {day}/{month}/{year}")