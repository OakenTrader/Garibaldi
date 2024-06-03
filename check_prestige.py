#%%
import pandas as pd
import numpy as np
import os
from utility import jopen

"""
There are several sources of prestige, some fixed to a certain amount, some scaling by another metric.
"""

defines = jopen("./common_json/defines/00_defines.json")
unit_types = jopen("./common_json/combat_unit_types/00_combat_unit_types.json")
military_keywords = ["unit_offense_mult", "unit_defense_mult", "unit_offense_add", "unit_defense_add"]

countries_def = dict()
for address in os.listdir("./common_json/country_definitions"):
    countries_def.update(jopen(f"./common_json/country_definitions/{address}"))

tier_def = {"hegemony": 50, "empire":25, "kingdom":15, "grand_principality":10, "principality":5, "city_state":0}

gdp_divisor = defines["NDiplomacy"]["PRESTIGE_FROM_COUNTRY_GDP_DIVISOR"]
pp_divisor = defines["NMilitary"]["POWER_PROJECTION_DIVISOR"]

import_save = ["country_manager", "new_combat_unit_manager", "interest_groups", "military_formation_manager"]
save_data = dict()
for i in import_save:
    save_data[i] = jopen(f"./save files/save_output_{i}.json")

countries = save_data["country_manager"]["database"]
combat_units = save_data["new_combat_unit_manager"]["database"]
formations = save_data["formation_manager"]["database"]

for key, combat_unit in combat_units.items():
    country = combat_unit["country"]
    formation = combat_unit["formation"]
    if "mil_formations" not in countries[country]:
        countries[country]["mil_formations"] = dict()
    if formation not in countries[country]["mil_formations"]:
        countries[country]["mil_formations"][formation] = dict()
    countries[country]["mil_formations"][formation][key] = combat_unit

# Get relevant mobilizations
mobilizations = jopen("./common_json/mobilization_options/00_mobilization_option.json")
dict_mobilizations = dict()
for key, mobilization in mobilizations.items():
    if "unit_modifier" in mobilization:
        if any([x in mobilization["unit_modifier"] for x in military_keywords]):
            dict_mobilizations[key] = mobilization

ig_data = save_data["interest_groups"]
for key, ig_armed in ig_data.items():
    country = ig_armed["country"]
    countries[country]["ig_armed_forces"] = ig_armed

columns = ["tier prestige", "army projection", "navy projection", "GDP prestige",
            "subject prestige", "production prestige", "monuments prestige", "events prestige", "tech prestige", "modifiers"]
df_prestige = pd.DataFrame(columns=columns)
for key, country in countries.items():
    prestige = []
    modifiers = []
    if type(country) != dict:
        continue

    """
    A country's tier provides a small amount of prestige. This is inherent to a specific nation and can only be increased by forming a new, higher tier nation.
    """
    tier_prestige = tier_def[countries_def[country["definition"]]["tier"]]

    """
    Military power, both army and navy, increases prestige. The larger and more advanced a military, the more prestige is gained.
    # Average of Offense and Defense is multiplied by manpower and divided by this to determine a unit's power projection
    """

    # Patriotic Fervor
    ig_armed = country["ig_armed_forces"]
    fervor = 0
    if "ig_trait_patriotic_fervor" in ig_armed["enabled_traits"] and ig_armed.get("influence_type") == "influential":
        fervor = 0.2
    elif "ig_trait_patriotic_fervor" in ig_armed["enabled_traits"] and ig_armed.get("influence_type") == "neutral":
        fervor = 0.1
    
    for key1, formation in countries["mil_formations"].items():
        for key2, unit in formation.items():
    # Calculate Offense/Defennse
            offense = dict()
            defense = dict()
            offense_modifiers = {"patriotic fervor": fervor}
            defense_modifiers = {"patriotic fervor": fervor}
    # Base
            soldier_type = unit["type"]
            offense["base"] = unit_types[soldier_type]["battle_modifier"]["unit_offense_add"]
            defense["base"] = unit_types[soldier_type]["battle_modifier"]["unit_defense_add"]
            
    # Mobilization
            unit_mobilizations = list(set(dict_mobilizations) & set(formation["active_mobilization_options"]["value"]))
            for mobilization in unit_mobilizations:
                mob_modifiers = dict_mobilizations[mobilization]["unit_modifier"]
                if "unit_offense_add" in mob_modifiers:
                    offense[mobilization] = mob_modifiers["unit_offense_add"]
                if "unit_defense_add" in mob_modifiers:
                    defense[mobilization] = mob_modifiers["unit_defense_add"]
                if "unit_offense_mult" in mob_modifiers:
                    offense_modifiers[mobilization] = mob_modifiers["unit_offense_mult"]
                if "unit_defense_mult" in mob_modifiers:
                    defense_modifiers[mobilization] = mob_modifiers["unit_defense_mult"]
    # Veterancy

    # Companies
    # Technology



    """
    The total GDP (and thus indirectly level of industrialization) of a country gives it prestige.
    """


    """
    Subjects contribute prestige to their overlord based on their own military and economic might. These contributions are reduced compared to the amount generated for the country itself.
    """

    """
    Being a global leader (first, second, or third) in the production of goods gives a country prestige, with some goods being more prestigious than others.
    """

    """
    The major canals and most other monuments grant prestige.
    """

    """
    Certain events, such as expeditions to discover the South Pole or the source of Nile
    """

    """
    A number of society technologies provide a multiplier to prestige
    """
# %%
