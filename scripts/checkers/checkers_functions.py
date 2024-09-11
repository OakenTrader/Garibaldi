"""
Functions related to game variables that are used commonly by the checker functions.
"""
import os
import re
from scripts.helpers.utility import *

def companies_manager(save_data, countries, relevant_modifiers):
    """
    Provides checkers with information of companies with relevant traits
    """
    def_companies = dict()
    companies = load_def_multiple("company_types", "Common Directory")
    for name, company_name in companies.items():
        if any([x in relevant_modifiers for x in company_name["prosperity_modifier"]]):
            def_companies.update({name:company_name["prosperity_modifier"]})

    companies = save_data["companies"]["database"]
    for name, company_name in companies.items():
        if "prosperity" not in company_name or not float(company_name["prosperity"]) >= 100:
            continue
        country = company_name["country"]
        if retrieve_from_tree(countries, [country, "definition"]) is None:
            continue
        if (company := retrieve_from_tree(def_companies, [company_name["company_type"]])) is None:
            continue
        if "companies" not in countries[country]:
            countries[country]["companies"] = dict()
        countries[country]["companies"][company_name["company_type"]] = company

def subject_manager(save_data, countries):
    """
    Get all subjects of each country and the country it is subject to
    """
    def_subjects = [v["diplomatic_action"] for v in load_def_multiple("subject_types", "Common Directory").values()]
    for _, pact in save_data["pacts"]["database"].items():
        if not isinstance(pact, dict):
            continue
        if pact["action"] not in def_subjects:
            continue
        targets = (pact["targets"]["first"], pact["targets"]["second"])
        country1 = countries[targets[0]]
        country2 = countries[targets[1]]
        if "subjects" not in country1:
            country1["subjects"] = []
        country1["subjects"].append(targets[1])
        if "subject_to" not in country2:
            country2["subject_to"] = []
        country2["subject_to"].append(targets[0])
        if "power_bloc_as_core" in country1:
            country2["power_bloc_as_core"] = country1["power_bloc_as_core"]
            for subject in retrieve_from_tree(country2, "subjects", []):
                countries[subject]["power_bloc_as_core"] = country1["power_bloc_as_core"]
                """
                FIXME Not sure if we can get all countries in their power blocs, i.e in some deep subject networks (subject of subject of subject)
                """

def bloc_manager(save_data, relevant_modifiers):
    """
    Retrieve power blocs and/with relevant principles
    """
    def_principles = load_def("power_bloc_principles/00_power_bloc_principles.txt")
    principles = dict()
    for principle_key, principle in def_principles.items():
        for relevant_modifier in relevant_modifiers:
            if relevant_modifier in retrieve_from_tree(principle, "institution_modifier", []):
                pass
            elif relevant_modifier in retrieve_from_tree(principle, "member_modifier", []):
                pass
            elif relevant_modifier in retrieve_from_tree(principle, "participant_modifier", []):
                pass
            elif relevant_modifier in retrieve_from_tree(principle, "leader_modifier", []):
                pass
            else:
                continue
            principles[principle_key] = principle
            break
    power_blocs = save_data["power_bloc_manager"]["database"]
    blocs = dict()
    for bloc_number, power_bloc in power_blocs.items():
        if not isinstance(power_bloc, dict):
            continue
        for principle in power_bloc["principles"]["value"]:
            if principle in principles:
                blocs[bloc_number] = power_bloc
    return principles, blocs

def institution_manager(save_data, countries, relevant_institutions):
    all_institutions = save_data["institutions"]["database"]
    for _, institution in all_institutions.items():
        if not isinstance(institution, dict):
            continue
        if institution["institution"] in relevant_institutions:
            if "institutions" not in (country := countries[institution["country"]]):
                country["institutions"] = dict()
            country["institutions"][institution["institution"]] = institution["investment"]


def get_country_name(country:dict, localization:dict):
    country_tag = country["definition"]
    if country_tag in localization:
        country_name = localization[country_tag]
    else:
        country_name = country_tag
    if retrieve_from_tree(country, "civil_war") is not None:
        country_name = "Revolutionary " + country_name
    return country_name


def get_version(address):
    meta_data = load_save(["meta_data"], address)["meta_data"]
    version = meta_data["version"]
    return version


def get_save_date(address, split=True):
    """
    Get the date of a save file in a string format (i.e. 1836.1.1.18) if split=False or list of strings (i.e. [1836, 1, 1]) if split=True
    """
    metadata = load_save(["meta_data"], address)
    save_date = metadata["meta_data"]["game_date"]
    if split:
        year, month, day = save_date.split(".")[:3]
        return year, month, day
    return save_date

def get_building_output(building, target, def_production_methods):
    """
    Calculate a building's output of a variable with respected to production methods, employees and throughput
    Employees must be added into a building from the outside in building["pops_employed"]
    """
    output = 0
    employees = 0
    employees_pl = dict()
    for pm_name in building["production_methods"]["value"]:
        pm = def_production_methods[pm_name]
        if (output_workforce := retrieve_from_tree(pm, ["country_modifiers", "workforce_scaled", target])) is not None:
            output += float(output_workforce)
        if (employees_dict := retrieve_from_tree(pm, ["building_modifiers", "level_scaled"])) is not None:
            for key, addition in employees_dict.items():
                if key not in employees_pl:
                    employees_pl[key] = int(addition)
                else:
                    employees_pl[key] += int(addition)

    if "pops_employed" in building:
        for key, pop in building["pops_employed"].items():
            employees += int(pop["workforce"] )

    # print(employees_pl)
    # print(f"Total Employees at level {int(building['level'])}: {employees}")
    employees /= sum([employees_pl[e] for e in employees_pl])
    # print(f"Employees ratio: {employees}")
    # print([employees_pl[e] for e in employees_pl])
    if "throughput" not in building:
        building["throughput"] = 1.0
    # print(output)
    output =  output * float(building["throughput"]) * employees
    return output


def rename_folder_to_date(folder):
    """
    Rename a save folder in a campaign folder into format campaign_folder_year_month_day 
    """
    campaign_folder = re.split(r"[\\/]", folder.strip("/\\"))[-2]
    year, month, day = get_save_date(folder)
    new_name = f"{campaign_folder}_{year}_{month}_{day}"
    try:
        os.rename(folder, f"./saves/{campaign_folder}/{new_name}")
    except PermissionError as e:
        raise PermissionError("Error when renaming folder:", e)