import pandas as pd
import os, warnings
from scripts.helpers.utility import *
from scripts.convert_localization import get_all_localization

"""
There are several sources of prestige, some fixed to a certain amount, some scaling by another metric. (Vickypedia)
"""
prestige_columns = ["tier prestige", "army projection", "navy projection", "GDP prestige",
            "subject gdp prestige", "subject army projection", "subject navy projection", "production leader prestige", "monuments prestige", "events prestige", "modifiers"]

def check_prestige(address, **kwargs):
    localization = get_all_localization()
    save_date = get_save_date(address, split=False)
    defines_file = load_def("./common/defines/00_defines.txt")
    defines = dict()
    for key, defs in defines_file.items():
        if not isinstance(defs, dict):
            defines[key] = defs
            continue
        if any([k in defines for k in defs]):
            raise KeyError(f"Duplicate defines definition")
        defines.update(defs)

    relevant_modifiers = ["country_prestige_add", "country_prestige_mult",
                           "country_prestige_from_army_power_projection_mult", "country_prestige_from_navy_power_projection_mult"]
    def_modifiers = {k:v for k, v in load_def_multiple("./common/modifiers").items() if any([vi in relevant_modifiers for vi in v.keys()])}

    import_save = ["country_manager", "new_combat_unit_manager", "states",
                    "interest_groups", "military_formation_manager", "building_manager",
                    "companies", "technology", "character_manager", "player_manager", "pacts", "pops"]
    save_data = load_save(import_save, address)

    """
    Countries
    """
    countries = save_data["country_manager"]["database"]
    dynamic_countries = retrieve_from_tree(save_data, ["country_manager", "dynamic_country_definition_data"], null=[])
    def_countries = dict()
    for countries_file in os.listdir("./common/country_definitions"):
        def_countries.update(load_def(f"./common/country_definitions/{countries_file}"))
    
    players = [countries[v["country"]]["definition"] for k, v in save_data["player_manager"]["database"].items() if retrieve_from_tree(countries[v["country"]], ["definition"]) is not None]

    """
    Tier
    """
    # Yet to see the way the game let modding country tiers so tiers are hardcoded here
    tiers = ["hegemony", "empire", "kingdom", "grand_principality", "principality", "city_state"]
    try:
        def_tier = {k:float(defines[f"COUNTRY_TIER_{k.upper()}_PRESTIGE"]) for k in tiers}
    except KeyError:
        raise KeyError("Unsupported country tier modding: vanilla tier not found")

    """
    GDP
    """
    gdp_divisor = float(defines["PRESTIGE_FROM_COUNTRY_GDP_DIVISOR"])
    prestige_per_gdp = float(defines["PRESTIGE_FROM_COUNTRY_GDP"])

    """
    Military
    """
    pp_divisor = float(defines["POWER_PROJECTION_DIVISOR"])
    def_unit_types = load_def("./common/combat_unit_types/00_combat_unit_types.txt")
    def_unit_type_groups = load_def("./common/combat_unit_groups/00_combat_unit_groups.txt")
    unit_types_specific_modifiers = [f"unit_{def_unit_type}_{modifier}" for def_unit_type in def_unit_types for modifier in ["offense_mult", "defense_mult", "offense_add", "defense_add"]]
    relevant_modifiers += unit_types_specific_modifiers

    # Grouping
    army_type_groups = {type_name:def_unit_type_groups[unit_type["group"]]["type"] for type_name, unit_type in def_unit_types.items()}

    combat_units = save_data["new_combat_unit_manager"]["database"]
    formations = save_data["military_formation_manager"]["database"]

    for key, combat_unit in combat_units.items():
        if not isinstance(combat_unit, dict):
            continue
        country = combat_unit["country"]
        formation = combat_unit["formation"]
        if "mil_formations" not in countries[country]:
            countries[country]["mil_formations"] = dict()
        if formation not in countries[country]["mil_formations"]:
            countries[country]["mil_formations"][formation] = formations[formation]
        if "units" not in countries[country]["mil_formations"][formation]:
            countries[country]["mil_formations"][formation]["units"] = dict()
        countries[country]["mil_formations"][formation]["units"][key] = combat_unit

    # Get relevant mobilizations
    mobilizations_def = load_def("./common/mobilization_options/00_mobilization_option.txt")
    def_mobilizations = dict()
    for key, mobilization in mobilizations_def.items():
        if "unit_modifier" in mobilization:
            if any([x in mobilization["unit_modifier"] for x in relevant_modifiers]):
                def_mobilizations[key] = mobilization

    veterancy_def = load_def("./common/combat_unit_experience_levels/00_combat_unit_experience_levels.txt")
    def_veterancy = dict()
    for key, veterancy in veterancy_def.items():
        def_veterancy[veterancy["level"]] = veterancy

    pp_prestige_divisor_land = float(defines["PRESTIGE_FROM_ARMY_POWER_PROJECTION"])
    pp_prestige_divisor_navy = float(defines["PRESTIGE_FROM_NAVY_POWER_PROJECTION"])

    """
    Companies
    """
    def_companies = dict()
    for company_file in os.listdir("./common/company_types"):
        companies = load_def(f"./common/company_types/{company_file}")
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
        countries[country]["companies"][company_name["company_type"]] = company_name

    """
    Politics
    """
    def_ig_traits_file = load_def_multiple("./common/interest_group_traits")
    def_ig_traits = dict()
    for ig_trait in def_ig_traits_file:
        if any([ig_mod in relevant_modifiers for ig_mod in def_ig_traits_file[ig_trait]["modifier"]]):
            def_ig_traits[ig_trait] = def_ig_traits_file[ig_trait]

    ig_data = save_data["interest_groups"]["database"]
    ig_influence_modifier = {"influential":2, "neutral":1}
    for key, ig in ig_data.items():
        if not isinstance(ig, dict):
            continue
        if not isinstance(country := countries[ig["country"]], dict):
            continue
        if (ig_traits := retrieve_from_tree(ig, ["enabled_traits", "value"])) is None:
            continue
        if influence := retrieve_from_tree(ig, "influence") is None:
            continue
        ig_traits = [[ig_trait, ig_influence_modifier[influence]] for ig_trait in ig_traits if any(mod in relevant_modifiers for mod in def_ig_traits[ig_trait]["modifier"])]
        if len(ig_traits.keys()) == 0:
            continue
        if "interest_groups_traits" not in country:
            country["interest_groups_traits"] = dict()
        country["interest_groups_traits"].update(ig_traits)


    def_character_traits = dict()
    characters = save_data["character_manager"]["database"]
    # Consider only ruler modifier
    for character_trait_name, character_trait in load_def_multiple("./common/character_traits").items():
        if (ruler_modifiers := retrieve_from_tree(character_trait, "country_modifier")) is None:
            continue
        if any([modifier in relevant_modifiers for modifier in ruler_modifiers]):
            def_character_traits[character_trait_name] = character_trait

    """
    Technology
    """
    def_techs = dict()
    file_techs = load_def_multiple("./common/technology/technologies")
    for name, tech in file_techs.items():
        if (tech_mod := retrieve_from_tree(tech, ["modifier"])) is None:
            continue
        if any(x in relevant_modifiers for x in tech_mod):
            def_techs[name] = tech

    save_techs = save_data["technology"]["database"]
    for tech_id, save_tech in save_techs.items():
        if (country := retrieve_from_tree(save_tech, "country")) is None:
            continue
        if not isinstance(country := retrieve_from_tree(countries, [country]), dict):
            continue
        if (country_techs := retrieve_from_tree(save_tech, ["acquired_technologies", "value"])) is None:
            continue
        country["acquired_technologies"] = {tech:def_techs[tech] for tech in country_techs if tech in def_techs}


    """
    Defining Monuments
    """

    def_monument_methods = dict()
    for pm_name, production_method in load_def_multiple("./common/production_methods").items():
        for relevant_modifier in relevant_modifiers:
            if len(walk_tree(production_method, relevant_modifier)) > 0:
                def_monument_methods[pm_name] = production_method
                break
    
    def_monument_method_groups = dict()
    for pmg_name, production_method_group in load_def_multiple("./common/production_method_groups").items():
        if any([pm in def_monument_methods for pm in retrieve_from_tree(production_method_group, ["production_methods"], null=[])]):
            def_monument_method_groups[pmg_name] = production_method_group

    def_monuments = dict()
    for building_name, building in load_def_multiple("./common/buildings").items():
        for def_pmg in def_monument_methods:
            if def_pmg in building["production_method_groups"]:
                def_monuments[building_name] = building
                break

    """
    Buildings Goods output
    Assume that the formula is prestige_factor * (2)^(MIN_SPOT_PRESTIGE_AWARD - #ranking)
    """
    

    if (min_spot_prestige_award := int(defines["MIN_SPOT_PRESTIGE_AWARD"])) != 3:
        warnings.warn("This mod modifies the MIN_SPOT_PRESTIGE_AWARD and may make the producing leader prestige calculation inaccurate", UserWarning)
    states = save_data["states"]["database"]
    num_to_goods = dict()
    def_goods = load_def_multiple("./common/goods")
    for i, good in enumerate(def_goods.keys()):
        num_to_goods[i] = good
    
    goods_leaderboard = {f'{v}':{} for v in range(len(num_to_goods))}
    buildings = save_data["building_manager"]["database"]
    df_countries_goods = dict()
    """
    Loop buildings for goods and monuments
    """
    # Loop through population to get monument employees
    pops = save_data["pops"]["database"]
    for pop_id, pop in pops.items():
        if not isinstance(pop, dict):
            continue
        if "workplace" not in pop:
            continue
        building = buildings[pop["workplace"]]
        if "pops_employed" not in building:
            building["pops_employed"] = dict()
        building["pops_employed"][pop_id] = pop
        
    for building_id, building in buildings.items():
        if not isinstance(building, dict):
            continue
        if retrieve_from_tree(building, "dead") == "yes":
            continue
        country = states[building["state"]]["country"]
        country_tag = countries[country]["definition"]
        if any([pm in def_monument_methods for pm in retrieve_from_tree(building, ["production_methods", "value"], null=[])]):
            if "monuments" not in countries[country]:
                countries[country]["monuments"] = dict()
            countries[country]["monuments"][building_id] = building
        if (output_goods := retrieve_from_tree(building, ["output_goods", "goods"])) is None:
            continue
        for k, v in output_goods.items():
            if country not in goods_leaderboard[k]:
                goods_leaderboard[k][country] = float(v)
            else:
                goods_leaderboard[k][country] += float(v)
            if country_tag not in df_countries_goods:
                df_countries_goods[country_tag] = {"id":country, "country":get_country_name(countries[country], localization)} | {num_to_goods[j]:0 for j in range(len(num_to_goods))}
            df_countries_goods[country_tag][num_to_goods[int(k)]] += float(v)
            


    df_countries_goods = [{"tag": k} | v for k, v in df_countries_goods.items()]
    df_goods_leaderboard = pd.DataFrame(df_countries_goods, columns=["id", "tag", "country"] + [num_to_goods[int(i)] for i in range(len(num_to_goods))])
    df_goods_leaderboard.to_csv(f"{address}/goods_produced.csv", sep=",")
    # print(goods_leaderboard)
    goods_leaderboard = {k:sorted(dictionary.items(), key=lambda item: item[1], reverse=True)[:10] for k, dictionary in goods_leaderboard.items()}
    # for k, v in goods_leaderboard.items():
    #     print(k)
    #     print(v)

    """
    Government wages affecting prestige and power projection
    """
    
    static_modifiers = dict()
    for mod_name, static_modifier in load_def_multiple("./common/modifiers").items():
        for relevant_modifier in relevant_modifiers:
            if relevant_modifier in static_modifier:
                static_modifiers[mod_name] = static_modifier
                break

    """
    Main Countries Loop
    """

    df_prestige = []
    # focus = "RUS"
    for country_key, country in countries.items():
        if not isinstance(country, dict):
            continue
        # if country["definition"] not in players:
        #     continue
        country_tag = country["definition"]
        national_prestige = {key:0 for key in prestige_columns}
        national_modifiers = dict()
        for relevant_modifier in relevant_modifiers:
            national_modifiers[relevant_modifier] = dict()
        
        """
        Government and Military Wages
        """

        gov_salaries = retrieve_from_tree(country, "salaries", null="medium")
        mil_salaries = retrieve_from_tree(country, "mil_salaries", null="medium")
        if f"government_wages_{gov_salaries}" in static_modifiers:
            for modifier, value in static_modifiers[f"government_wages_{gov_salaries}"].items():
                if modifier in relevant_modifiers:
                    national_modifiers[modifier][f"government_wages_{gov_salaries}"] = float(value)
        if f"military_wages_{mil_salaries}" in static_modifiers:
            for modifier, value in static_modifiers[f"military_wages_{mil_salaries}"].items():
                if modifier in relevant_modifiers:
                    national_modifiers[modifier][f"military_wages_{mil_salaries}"] = float(value)

        """
        Timed and untimed modifiers registered on national level
        Certain events, such as expeditions to discover the South Pole or the source of Nile (Vickypedia)
        """
        if "timed_modifiers" in country:
            timed_modifiers = country["timed_modifiers"]
            for _, modifier in timed_modifiers["modifiers"].items():
                modifier_name = modifier["modifier"]
                if modifier_name not in def_modifiers:
                    continue
                decay = retrieve_from_tree(modifier, "decay", null=1)
                start_date = retrieve_from_tree(modifier, "start_date")
                end_date = retrieve_from_tree(modifier, "end_date")
                multiplier = retrieve_from_tree(modifier, "multiplier", null=1)
                modifier = def_modifiers[modifier_name]
                if decay == "yes":
                    # print(modifier_name)
                    decay = (1 - get_duration(save_date, start_date, end_date)[-1])
                for mod, value in modifier.items():
                    if mod in relevant_modifiers:
                        national_modifiers[mod][modifier_name] = float(value) * float(multiplier) * decay
                        if mod == "country_prestige_add":
                            national_prestige["events prestige"] += float(value) * float(multiplier) * decay

        """
        Ruler traits
        """

        ruler_traits = retrieve_from_tree(characters, [country["ruler"], "traits", "value"], null=[])
        for ruler_trait in ruler_traits:
            if ruler_trait not in def_character_traits:
                continue
            for country_modifier, value in def_character_traits[ruler_trait]["country_modifier"].items():
                if country_modifier in relevant_modifiers:
                    national_modifiers[country_modifier][ruler_trait] = float(value)
        
        """
        A country's tier provides a small amount of prestige. This is inherent to a specific nation and can only be increased by forming a new, higher tier nation. (Vickypedia)
        """
        try:
            if country_tag in dynamic_countries:
                dynamic_country_data = dynamic_countries[country_tag]
                tier = dynamic_country_data["tier"]
            else:
                tier = def_countries[country_tag]["tier"]
            if tier not in tiers:
                raise NotImplementedError(f"Unsupported tier modding: {tier}")
        except KeyError:
            # Assume principality (tier prestige isn't that important anyway)
            tier = "principality"
            # raise KeyError(f"Tier undefined for {country_key}:{country["definition"]} in {save_date}")
        national_modifiers["country_prestige_add"]["Nation Tier"] = def_tier[tier]
        national_prestige["tier prestige"] = national_modifiers["country_prestige_add"]["Nation Tier"]

        """
        Companies
        """
        if "companies" in country:
            for company_name, company in country["companies"].items():
                for modifier, value in company.items():
                    if modifier in relevant_modifiers:
                        national_modifiers[modifier][company_name] = float(value)
                        if modifier == "country_prestige_add":
                            raise ValueError(f"Unexpected company prestige add from {company_name} of {country_tag}")


        """
        Interest Group traits
        """
        if "interest_groups_traits" in country:
             for ig_trait, influence in country["interest_groups_traits"].items():
                 for modifier in [m for m in ig_trait["modifier"] if m in relevant_modifiers]:
                    national_modifiers[modifier][ig_trait] = float(def_ig_traits[ig_trait]["modifier"][modifier]) * influence
                    if modifier == "country_prestige_add":
                        raise ValueError(f"Unexpected interest group prestige add from {ig_trait} of {country_tag}")
                    # pass
       
        """
        Technologies that affect prestige and military stats
        """
        if "acquired_technologies" in country:
            for tech_name, tech in country["acquired_technologies"].items():
                if (tech_modifiers := retrieve_from_tree(tech, "modifier")) is None:
                    continue
                for tech_modifier, value in tech_modifiers.items():
                    if tech_modifier not in relevant_modifiers:
                        continue
                    national_modifiers[tech_modifier][tech_name] = float(value)
                    if tech_modifier == "country_prestige_add":
                        raise ValueError(f"Unexpected technology prestige add from {tech_name} of {country_tag}")
                    

        """
        Military power, both army and navy, increases prestige. The larger and more advanced a military, the more prestige is gained.
        # Average of Offense and Defense is multiplied by manpower and divided by this to determine a unit's power projection (Vickypedia)
        Apparently the only factor affecting power projections are base offense/defense and veterancy (also character traits that directly boost pp)
        """
        army_power_projection = {"army":0, "navy":0}

        if "mil_formations" in country:
            for key1, formation in country["mil_formations"].items():
                if "units" not in formation:
                    continue
                for key2, unit in formation["units"].items():
                    # Calculate Offense/Defennse
                    unit_modifiers = {"unit_offense_add":{}, "unit_defense_add":{}, "unit_offense_mult":{}, "unit_defense_mult":{}}
                    # Base
                    unit_type = unit["type"]
                    unit_type_group = army_type_groups[unit_type]
                    for battle_modifier in def_unit_types[unit_type]["battle_modifier"]:
                        if battle_modifier not in unit_modifiers:
                            continue
                        unit_modifiers[battle_modifier]["base"] = float(def_unit_types[unit_type]["battle_modifier"][battle_modifier])

                    # Veterancy
                    veterancy = def_veterancy[unit["current_veterancy_level"]]
                    if "unit_modifier" in veterancy:
                        for vet_modifier, value in veterancy["unit_modifier"].items():
                            if vet_modifier not in unit_modifiers:
                                continue
                            unit_modifiers[vet_modifier][f"Veterancy level {unit["current_veterancy_level"]}"] = float(value)

                    # print(unit_modifiers)
                    unit_offense = sum(unit_modifiers["unit_offense_add"].values())
                    unit_offense_mult = sum(unit_modifiers["unit_offense_mult"].values())
                    unit_defense = sum(unit_modifiers["unit_defense_add"].values())
                    unit_defense_mult = sum(unit_modifiers["unit_defense_mult"].values())
                    # unit_offense_mult, unit_defense_mult = 0, 0
                    unit_pp = float(unit["current_manpower"]) * (unit_offense * (1 + unit_offense_mult) + unit_defense * (1 + unit_defense_mult)) / 2 / pp_divisor
                    army_power_projection[unit_type_group] += unit_pp

                    # if country_tag == focus:
                    #     print(f"Unit {key2} Type {unit_type}")
                    #     print(unit_offense)
                    #     print(unit_offense_mult)
                    #     print(unit_defense)
                    #     print(unit_defense_mult)
                    #     print({key:value for key,value in unit_modifiers.items() if len(value) > 0})

        # if sum(army_power_projection.values()) > 2000:
        country["power_projection"] = army_power_projection
        national_prestige["army projection"] = army_power_projection["army"] * pp_prestige_divisor_land * (1 + sum(retrieve_from_tree(national_modifiers, ["country_prestige_from_army_power_projection_mult"], null={}).values()))
        national_prestige["navy projection"] = army_power_projection["navy"] * pp_prestige_divisor_navy * (1 + sum(retrieve_from_tree(national_modifiers, ["country_prestige_from_navy_power_projection_mult"], null={}).values()))
        # if country_tag in players:
        #     print(country_tag)
        #     # print(f"Army Projection: {army_power_projection["army"]}")
        #     # print(f"Naval Projection: {army_power_projection["navy"]}")
        #     print(f"Army Projection Prestige: {national_prestige["army projection"]}")
        #     print(f"Naval Projection Prestige: {national_prestige["navy projection"]}")


        """
        The total GDP (and thus indirectly level of industrialization) of a country gives it prestige. (Vickypedia)
        FIXME This is actually gdp of the last record (week/month idk), actually gdp at game time will have to be recalculated (daunting task)
        """
        if (country_gdp := retrieve_from_tree(country, ["gdp", "channels", "0", "values", "value"])) is None:
            warnings.warn(f"No GDP record for {country_key}:{country_tag}")
            country_gdp = [0]
        # print(f"{country_key} {country_tag}: {country_gdp[-1]}")
        national_prestige["GDP prestige"] = float(country_gdp[-1]) / gdp_divisor * prestige_per_gdp
        # print(country_tag, country_gdp)

        """
        Being a global leader (first, second, or third) in the production of goods gives a country prestige, with some goods being more prestigious than others. (Vickypedia)
        
        Goods are index (perhaps) by the order in the definition file. Hopefully this stays constant in all saves.
        """

        for goods_type, leaderboard in goods_leaderboard.items():
            for rank, stat in enumerate(leaderboard[:min_spot_prestige_award]):
                if country_key == stat[0]:
                    national_prestige["production leader prestige"] += float(def_goods[num_to_goods[int(goods_type)]]["prestige_factor"]) * 2 ** (min_spot_prestige_award - rank - 1)
                    break

        """
        The major canals and most other monuments grant prestige. (Vickypedia)
        """
        for monument_id, monument in retrieve_from_tree(country, "monuments", null=dict()).items():
            for relevant_modifier in relevant_modifiers:
                output = get_building_output(monument, relevant_modifier, def_monument_methods)
                if output == 0:
                    continue
                national_modifiers[relevant_modifier][buildings[monument_id]["building"]] = output
                if relevant_modifier == "country_prestige_add":
                    national_prestige["monuments prestige"] += output
        
        country["national_prestige"] = national_prestige
        country["national_modifiers"] = national_modifiers
        

    """
    Subjects contribute prestige to their overlord based on their own military and economic might. These contributions are reduced compared to the amount generated for the country itself. (Vickypedia)
    """
    prestige_per_subject_gdp = float(defines["PRESTIGE_FROM_SUBJECT_GDP"])
    prestige_per_subject_army_pp = float(defines["PRESTIGE_FROM_SUBJECT_ARMY_POWER_PROJECTION"])
    prestige_per_subject_navy_pp = float(defines["PRESTIGE_FROM_SUBJECT_NAVY_POWER_PROJECTION"])

    def_subjects = [v["diplomatic_action"] for v in load_def_multiple("./common/subject_types").values()]
    for _, pact in save_data["pacts"]["database"].items():
        if not isinstance(pact, dict):
            continue
        if pact["action"] not in def_subjects:
            continue
        targets = (pact["targets"]["first"], pact["targets"]["second"])
        country1 = countries[targets[0]]
        country2 = targets[1]
        if "subjects" not in country1:
            country1["subjects"] = []
        country1["subjects"].append(country2)
    
    for country_id, country in countries.items():
        if not isinstance(country, dict):
            continue
        if "national_prestige" not in country:
            continue
        if "subjects" in country:
            for subject in country["subjects"]:
                country["national_prestige"]["subject army projection"] += countries[subject]["power_projection"]["army"] * prestige_per_subject_army_pp
                country["national_prestige"]["subject navy projection"] += countries[subject]["power_projection"]["navy"] * prestige_per_subject_navy_pp
                country["national_prestige"]["subject gdp prestige"] += countries[subject]["national_prestige"]["GDP prestige"] * prestige_per_subject_gdp / prestige_per_gdp
        
        total_prestige = sum([v for v in country["national_prestige"].values()])
        total_modifiers = sum([v for v in country["national_modifiers"]["country_prestige_mult"].values()])
        country["national_prestige"]["modifiers"] = total_modifiers
        # if country["definition"] not in players:
        #     continue
        # for modifier, value in country["national_modifiers"].items():
        #     if len(value) < 1:
        #         continue
        #     print(modifier)
        #     print(value)
        # print(f"{country["definition"]}'s prestige: {total_prestige}")
        # print(f"Modifier: {total_modifiers}")
        # print(f"Total: {total_prestige * (1 + total_modifiers)}")
        # for prestige, value in country["national_prestige"].items():
        #     print(prestige, value)
        # print("---------------------------------")
        country_tag = country["definition"]
        country_name = get_country_name(country, localization)
        df_country = {"id":country_id, "tag":country_tag, "country":country_name, "total":total_prestige * (1 + total_modifiers)}
        df_country.update(country["national_prestige"])
        df_prestige.append(df_country)

    df_prestige = pd.DataFrame(df_prestige, columns=["id", "tag", "country", "total"] + prestige_columns)
    df_prestige = df_prestige.sort_values(by='total', ascending=False)

    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        year, month, day = save_date.split(".")
        print(f"{day}/{month}/{year}")
        # print(df_prestige)
        df_prestige.to_csv(f"{address}/prestige.csv", sep=",", index=False)
        with open(f"{address}/prestige.txt", "w") as file:
            file.write(f"{day}/{month}/{year}\n")
            df_prestige.to_string(buf=f"{address}/prestige.txt", encoding="utf-8")
    
    return df_prestige

# %%
