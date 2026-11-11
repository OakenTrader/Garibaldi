import pandas as pd
import os, warnings
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import *
from src.helpers.utility import *

"""
There are several sources of prestige, some fixed to a certain amount, some scaling by another metric. (Vickypedia)
"""
prestige_columns = ["tier prestige", "army projection", "navy projection", "GDP prestige",
            "subject gdp prestige", "subject army projection", "subject navy projection", "production leader prestige", "prestige goods prestige", "monuments prestige", "events prestige",
            "ruler prestige", "disband penalty", "modifiers"]

PRESTIGE_MODIFIERS = ["country_prestige_add", "country_prestige_mult",
                      "country_prestige_from_army_power_projection_mult",
                      "country_prestige_from_navy_power_projection_mult"]
# Since 1.15 a ship's power projection is its own stat: the type's and modifications'
# ``ship_power_projection_add``, scaled by the country's laws and the ship's veterancy.
SHIP_STATS = ("ship_power_projection_add", "ship_hit_points_max_add", "ship_crew_max_add")
SHIP_PROJECTION_MULT = "ship_power_projection_mult"
# A unit's power projection uses its offense and defense with every country-wide bonus
# applied (technologies, laws, timed modifiers, ...), not just the unit type and veterancy.
# Terrain and battle conditions are left out: they only exist in a battle.
UNIT_STAT_NAMES = ("offense_add", "defense_add", "offense_mult", "defense_mult")
UNIT_GENERIC_MODIFIERS = [f"unit_{prefix}{stat}" for prefix in ("", "army_") for stat in UNIT_STAT_NAMES]


def prestige_modifiers(definitions):
    """Every modifier this checker reads, prestige's own plus the combat stats.

    Also selects the production methods in ``_prestige_production_methods``.
    """
    unit_stats = [f"unit_{unit_type}_{stat}"
                  for unit_type in definitions["combat_unit_types"]
                  for stat in ("offense_mult", "defense_mult", "offense_add", "defense_add")]
    return PRESTIGE_MODIFIERS + unit_stats


_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def calendar_day(date):
    """Day number on the game's 365-day calendar (no leap years), from ``y.m.d[.h]`` or ``[y, m, d]``.

    The hour is dropped: the engine's disband penalty works in whole days.
    """
    year, month, day = (int(part) for part in (date.split(".") if isinstance(date, str) else date)[:3])
    return year * 365 + sum(_MONTH_DAYS[:month - 1]) + day - 1


def _prestige_production_methods(ctx):
    """The production methods carrying any modifier this checker reads.

    Part of the result, not a shortcut: ``get_building_output`` divides by the
    employment the given methods declare. Built once per save, kept on the payload.
    """
    methods = ctx.payload.get("_prestige_pms")
    if methods is None:
        definitions = ctx.payload["definitions"]
        modifiers = prestige_modifiers(definitions)
        methods = {name: pm for name, pm in definitions["production_methods"].items()
                   if any(walk_tree(pm, modifier) for modifier in modifiers)}
        ctx.payload["_prestige_pms"] = methods
    return methods


def _is_alive(building, ctx):
    return retrieve_from_tree(building, "dead") != "yes"


def _is_monument(building, ctx):
    """A building running a production method that carries a prestige modifier."""
    methods = _prestige_production_methods(ctx)
    return any(pm in methods
               for pm in retrieve_from_tree(building, ["production_methods", "value"], null=[]))


def _output_goods(building, ctx):
    """What this building produces, as ``{good index: amount}``."""
    goods = retrieve_from_tree(building, ["output_goods", "goods"])
    if goods is None:
        return {}
    return {index: float(entry["value"]) for index, entry in goods.items()}


# What prestige needs from the building tree: goods produced per country per good,
# and the two monument modifiers.
_MONUMENT = Call(_is_alive, name="building_alive") & Call(_is_monument, name="building_is_monument")

GOODS_PRODUCED = Agg(
    "building", by=STATE_COUNTRY, name="goods_produced",
    value=Emit(_output_goods, name="output_goods"),
    where=Call(_is_alive, name="building_alive"))
MONUMENT_PRESTIGE = Agg(
    "building", by=STATE_COUNTRY, name="monument_prestige",
    value=building_output_of("country_prestige_add", _prestige_production_methods, "prestige"),
    where=_MONUMENT)
MONUMENT_PRESTIGE_MULT = Agg(
    "building", by=STATE_COUNTRY, name="monument_prestige_mult",
    value=building_output_of("country_prestige_mult", _prestige_production_methods, "prestige"),
    where=_MONUMENT)

class CheckPrestige(Checker):
    """
    Retrieve prestige and its modifiers for each country in each category.
    """
    name = "CheckPrestige"
    display_name = "Prestige"
    sort_order = 50
    requirements = ["country_manager", "new_combat_unit_manager", "states",
                    "interest_groups", "military_formation_manager", "building_manager",
                    "companies", "technology", "character_manager", "player_manager", "pacts", "pops",
                    "ship_manager", "ship_templates_manager", "laws"]
    column_backed = {"pops": "pop"}  # reached only through the declared aggregates
    aggregates = [EMPLOYED_WORKFORCE, GOODS_PRODUCED, MONUMENT_PRESTIGE,
                  MONUMENT_PRESTIGE_MULT]
    # ``defines`` is declared with depth_add=1: the prestige defines are spread
    # across sections (NEconomy, NMilitary, NCountry, ...) that must merge across
    # files rather than the last file replacing them wholesale. No other checker
    # reads the defines folder, so there is no conflicting depth_add.
    # company_types and subject_types are used by companies_manager and
    # subject_manager, which now take the definitions dict as an argument.
    definitions = (
        ("defines", 1), "static_modifiers", "country_definitions",
        "goods", "prestige_goods", "production_methods",
        "company_types", "subject_types", "interest_group_traits", "character_traits",
        "technology/technologies", "combat_unit_types", "combat_unit_groups",
        "combat_unit_experience_levels", "mobilization_options", "ship_types",
        "ship_modifications", "ship_veterancy_levels", "laws",
        # Prestige per point of power projection moved from defines to script values in 1.15.
        "script_values",
        # Some country types (decentralized) have no prestige at all.
        "country_types",
    )
    output = {"prestige.csv": ["total_prestige"] + prestige_columns, "goods_produced.csv": ["goods_produced"]}
    # Goods production is written here (production leaders need it) but belongs in
    # its own tree category rather than nested under Prestige. Which goods exist
    # depends on the mod, so the columns come from the CSV header.
    file_categories = {"goods_produced.csv": ("Goods", 60)}
    header_columns = ("goods_produced.csv",)
    # goods_produced names the file, not a column: one figure per good.
    file_keys = {"goods_produced": "goods_produced.csv"}
    # prestige.csv calls the campaign-wide total "total".
    csv_columns = {"total_prestige": "total"}
    dependencies = ["finance.csv"]

    def __init__(self):
        super().__init__()

    def execute_check(self, cache):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]
        definitions = cache["definitions"]
        df_finance = pd.read_csv(f"{address}/data/finance.csv", sep=",")[["id", "GDP"]]

        tiers = ["hegemony", "empire", "kingdom", "grand_principality", "principality", "city_state"]
        needed_defines = {
            "MIN_SPOT_PRESTIGE_AWARD", "PRESTIGE_FROM_COUNTRY_GDP_DIVISOR",
            "PRESTIGE_FROM_COUNTRY_GDP", "POWER_PROJECTION_DIVISOR",
            "PRESTIGE_FROM_SUBJECT_GDP",
            # Goods-leaderboard prestige is scaled by global GDP since 1.12.
            "GOODS_LEADERBOARD_GLOBAL_GDP_SCALING", "GOODS_LEADERBOARD_PRESTIGE_BASE",
            "GOODS_LEADERBOARD_PRESTIGE_SCALED", "PRESTIGE_FROM_PRESTIGE_GOODS_PRODUCTION",
            # Navy power projection (1.15): a ship counts while its crew is above the active
            # share, and its projection is scaled by hit points over this reference.
            "PRESTIGE_FROM_NAVY_POWER_PROJECTION_HIT_POINTS_REFERENCE",
            "ACTIVE_SHIP_LIVING_CREW_PERCENTAGE",
            # Disbanding a unit costs prestige that fades linearly over this many years.
            "DISBAND_PRESTIGE_PENALTY_YEARS",
            # Conscripts (units of this building) do not count towards army prestige.
            "CONSCRIPTION_CENTER_BUILDING",
        } | {f"COUNTRY_TIER_{t.upper()}_PRESTIGE" for t in tiers}

        defines_file = definitions["defines"]
        defines = dict()
        for key, defs in defines_file.items():
            if not isinstance(defs, dict):
                defines[key] = defs
                continue
            if not any(k in needed_defines for k in defs):
                continue
            if any(k in defines for k in defs):
                raise KeyError(f"Duplicate defines definition in section '{key}'")
            defines.update(defs)

        # key_veterancy = resolve_compatibility("veterancy", version)
        key_veterancy = "current_veterancy_level"

        """
        Countries
        """
        countries = save_data["country_manager"]["database"]
        dynamic_countries = retrieve_from_tree(save_data, ["country_manager", "dynamic_country_definition_data"], null=[])
        def_countries = definitions["country_definitions"]
        
        """
        Tier
        """
        # Yet to see the way the game let modding country tiers so tiers are hardcoded here
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
        def_unit_types = definitions["combat_unit_types"]
        def_unit_type_groups = definitions["combat_unit_groups"]
        # Grouping
        army_type_groups = {type_name: def_unit_type_groups[unit_type["group"]].get("type", "army") for type_name, unit_type in def_unit_types.items() if "group" in unit_type}

        # Prestige's own modifiers plus the combat stats, for the tech and trait loops.
        relevant_modifiers = prestige_modifiers(definitions) + UNIT_GENERIC_MODIFIERS
        # Static modifiers that the saved timed modifiers can refer to.
        def_modifiers = {k: v for k, v in definitions["static_modifiers"].items()
                         if any(vi in relevant_modifiers for vi in v.keys())}
        def ship_stats_of(definition):
            mod = retrieve_from_tree(definition, "modifier", {})
            return {stat: float(mod.get(stat, 0)) for stat in SHIP_STATS}

        def_ship_types = {name: ship_stats_of(ship_type)
                          for name, ship_type in definitions["ship_types"].items()}
        # Gun/armor/etc. modifications add flat stats on top of the base ship type.
        def_ship_modifications = {name: ship_stats_of(ship_mod)
                                  for name, ship_mod in definitions["ship_modifications"].items()}
        # Each ship references a design version -> ship type + chosen modifications. Precompute
        # the (base type + modifications) stats per version id.
        ship_version_stats = dict()
        for version_id, version in retrieve_from_tree(save_data, ["ship_templates_manager", "versions", "database"], null={}).items():
            info = retrieve_from_tree(version, "info")
            if not isinstance(info, dict):
                continue
            stats = dict(def_ship_types.get(info.get("type"), dict.fromkeys(SHIP_STATS, 0.0)))
            for mod_name in retrieve_from_tree(info, ["modifications", "value"], null=[]):
                for stat, value in def_ship_modifications.get(mod_name, {}).items():
                    stats[stat] += value
            ship_version_stats[version_id] = stats

        # Ship veterancy: a ship's experience puts it at the highest level whose threshold it has
        # reached, and that level adds to its power projection.
        veterancy_steps = sorted(
            (float(level.get("experience_threshold", 0)),
             float(retrieve_from_tree(level, ["modifier", SHIP_PROJECTION_MULT], null=0)))
            for level in definitions["ship_veterancy_levels"].values()
            if isinstance(level, dict) and "experience_threshold" in level)

        def ship_veterancy_mult(experience):
            bonus = 0.0
            for threshold, mult in veterancy_steps:
                if experience >= threshold:
                    bonus = mult
            return bonus

        # The laws that scale every ship's power projection (the navy model).
        law_ship_projection = {
            name: float(retrieve_from_tree(law, ["modifier", SHIP_PROJECTION_MULT], null=0))
            for name, law in definitions["laws"].items()
            if isinstance(law, dict) and retrieve_from_tree(law, ["modifier", SHIP_PROJECTION_MULT]) is not None}
        # Laws also carry prestige modifiers of their own (the professional navy law raises
        # the prestige earned from navy power projection).
        law_prestige_modifiers = {
            name: {modifier: float(value) for modifier, value in law["modifier"].items()
                   if modifier in PRESTIGE_MODIFIERS}
            for name, law in definitions["laws"].items()
            if isinstance(law, dict) and isinstance(law.get("modifier"), dict)}
        country_ship_projection_mult = dict()
        country_law_prestige = dict()
        for law in save_data["laws"]["database"].values():
            if not isinstance(law, dict) or law.get("active") != "yes":
                continue
            if law.get("law") in law_ship_projection:
                country_ship_projection_mult[law.get("country")] = (
                    country_ship_projection_mult.get(law.get("country"), 0.0) + law_ship_projection[law["law"]])
            if law_prestige_modifiers.get(law.get("law")):
                country_law_prestige.setdefault(law.get("country"), {})[law["law"]] = law_prestige_modifiers[law["law"]]

        combat_units = save_data["new_combat_unit_manager"]["database"]
        formations = save_data["military_formation_manager"]["database"]

        for key, combat_unit in combat_units.items():
            if not isinstance(combat_unit, dict):
                continue
            country = retrieve_from_tree(combat_unit, ["country"])
            if (country is None) or (country not in countries) or (isinstance(countries[country], str)):
                # print(f"Combat unit belonging to ghost country: {country}")
                # print(combat_unit)
                continue
            formation = combat_unit["formation"]
            if "mil_formations" not in countries[country]:
                countries[country]["mil_formations"] = dict()
            if formation not in countries[country]["mil_formations"]:
                if formation not in formations:
                    print(f"Formation {formation} doesn't exist!")
                    print(combat_unit)
                    continue
                if formations[formation] == "none":
                    countries[country]["mil_formations"][formation] = dict()
                else:
                    countries[country]["mil_formations"][formation] = formations[formation]
            if "units" not in countries[country]["mil_formations"][formation]:
                countries[country]["mil_formations"][formation]["units"] = dict()
            countries[country]["mil_formations"][formation]["units"][key] = combat_unit

        # Attach ships to their country via fleet -> formation -> country. Ships live in
        # a separate manager and carry no explicit type, so the type is inferred later
        # from crew size / hit points.
        ships = save_data["ship_manager"]["database"]
        for ship_key, ship in ships.items():
            if not isinstance(ship, dict):
                continue
            fleet = ship.get("fleet")
            formation = formations.get(fleet)
            if not isinstance(formation, dict):
                continue
            country = formation.get("country")
            if (country not in countries) or (not isinstance(countries[country], dict)):
                continue
            countries[country].setdefault("ships", dict())[ship_key] = ship

        # Get relevant mobilizations
        mobilizations_def = definitions["mobilization_options"]
        def_mobilizations = dict()
        for key, mobilization in mobilizations_def.items():
            if "unit_modifier" in mobilization:
                if any([x in mobilization["unit_modifier"] for x in relevant_modifiers]):
                    def_mobilizations[key] = mobilization

        veterancy_def = definitions["combat_unit_experience_levels"]
        def_veterancy = dict()
        for key, veterancy in veterancy_def.items():
            def_veterancy[veterancy["level"]] = veterancy

        # Prestige per point of power projection (script values since 1.15, defines before).
        script_values = definitions["script_values"]
        pp_prestige_divisor_land = float(script_values["prestige_from_army_power_projection"])
        pp_prestige_divisor_navy = float(script_values["prestige_from_navy_power_projection"])
        ship_hit_points_reference = float(defines["PRESTIGE_FROM_NAVY_POWER_PROJECTION_HIT_POINTS_REFERENCE"])
        ship_active_crew_share = float(defines["ACTIVE_SHIP_LIVING_CREW_PERCENTAGE"])
        conscription_building = str(defines["CONSCRIPTION_CENTER_BUILDING"]).strip('"')
        buildings = save_data["building_manager"]["database"]
        disband_penalty_days = float(defines["DISBAND_PRESTIGE_PENALTY_YEARS"]) * 365
        today = calendar_day(save_date)

        """
        Companies
        """
        companies_manager(save_data, definitions, countries, relevant_modifiers)

        """
        Politics
        """
        def_ig_traits_file = definitions["interest_group_traits"]
        def_ig_traits = dict()
        for ig_trait in def_ig_traits_file:
            if any([ig_mod in relevant_modifiers for ig_mod in def_ig_traits_file[ig_trait]["modifier"]]):
                def_ig_traits[ig_trait] = def_ig_traits_file[ig_trait]

        ig_data = save_data["interest_groups"]["database"]
        for key, ig in ig_data.items():
            if not isinstance(ig, dict):
                continue
            if not isinstance(country := countries.get(ig.get("country")), dict):
                continue
            # The IG's currently-enabled traits carry their country modifiers at full value.
            active = [t for t in retrieve_from_tree(ig, ["enabled_traits", "value"], null=[]) if t in def_ig_traits]
            if not active:
                continue
            ig_traits = country.setdefault("interest_groups_traits", dict())
            for trait in active:
                ig_traits[trait] = 1.0


        def_character_traits = dict()
        characters = save_data["character_manager"]["database"]
        company_database = save_data["companies"]["database"]
        # Consider only ruler modifier
        for character_trait_name, character_trait in definitions["character_traits"].items():
            if (ruler_modifiers := retrieve_from_tree(character_trait, "country_modifier")) is None:
                continue
            if any([modifier in relevant_modifiers for modifier in ruler_modifiers]):
                def_character_traits[character_trait_name] = character_trait

        """
        Technology
        """
        def_techs = dict()
        file_techs = definitions["technology/technologies"]
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
        Buildings Goods output
        Per-spot award = prestige_factor * 2^(MIN_SPOT_PRESTIGE_AWARD - rank - 1),
        scaled (since 1.12) by the global-GDP factor below.
        """
        # Since 1.12 the goods-leader award is scaled against global yearly GDP:
        #   k = BASE + SCALED * min(1, global_yearly_GDP / GLOBAL_GDP_SCALING)
        # Early game (small global GDP) k is small; it rises toward BASE+SCALED (=3) late game.
        global_yearly_gdp = float(df_finance["GDP"].sum())
        goods_leaderboard_scale = (
            float(defines["GOODS_LEADERBOARD_PRESTIGE_BASE"])
            + float(defines["GOODS_LEADERBOARD_PRESTIGE_SCALED"])
            * min(1.0, global_yearly_gdp / float(defines["GOODS_LEADERBOARD_GLOBAL_GDP_SCALING"]))
        )

        if (min_spot_prestige_award := int(defines["MIN_SPOT_PRESTIGE_AWARD"])) != 3:
            warnings.warn("This mod modifies the MIN_SPOT_PRESTIGE_AWARD and may make the producing leader prestige calculation inaccurate", UserWarning)
        num_to_goods = dict()
        def_goods = definitions["goods"]
        for i, good in enumerate(def_goods.keys()):
            num_to_goods[i] = good

        """
        Goods and monuments, from the shared building pass
        """
        # From the shared building pass. goods_leaderboard is the same table
        # transposed, per good rather than per country.
        goods_produced = cache["aggregates"].get("goods_produced", {})
        monument_prestige = cache["aggregates"].get("monument_prestige", {})
        monument_prestige_mult = cache["aggregates"].get("monument_prestige_mult", {})

        goods_leaderboard = {f'{v}':{} for v in range(len(num_to_goods))}
        df_countries_goods = []
        for country_key, per_good in goods_produced.items():
            country = countries[country_key]
            row = {"tag": country["definition"], "id": country_key,
                   "country": get_country_name(country, localization)}
            row |= {num_to_goods[j]: 0 for j in range(len(num_to_goods))}
            for goods_num, produced in per_good.items():
                goods_leaderboard[goods_num][country_key] = produced
                row[num_to_goods[int(goods_num)]] = produced
            df_countries_goods.append(row)
        df_goods_leaderboard = pd.DataFrame(df_countries_goods, columns=["id", "tag", "country"] + [num_to_goods[int(i)] for i in range(len(num_to_goods))])
        df_goods_leaderboard.to_csv(f"{address}/data/goods_produced.csv", sep=",")
        df_goods_leaderboard = df_goods_leaderboard[df_goods_leaderboard["id"].isin(players)]
        df_goods_leaderboard.to_csv(f"{address}/goods_produced.csv", sep=",")
        goods_leaderboard = {k:sorted(dictionary.items(), key=lambda item: item[1], reverse=True)[:10] for k, dictionary in goods_leaderboard.items()}

        """
        Prestige goods: a company that can produce a prestige good grants its country the
        base good's leaderboard prestige (rank-0 spot) multiplied by
        PRESTIGE_FROM_PRESTIGE_GOODS_PRODUCTION. Each prestige-good variant is unique to its
        producer, so the top-spot weight (2^(MIN_SPOT-1)) applies.
        """
        # A base good whose prestige variant has been unlocked anywhere in the world moves off
        # the ordinary goods leaderboard onto the prestige-goods leaderboard, where the top
        # producers earn PRESTIGE_FROM_PRESTIGE_GOODS_PRODUCTION times the usual award. This is
        # a GLOBAL property of the good (not tied to the earner owning the company).
        prestige_goods_mult = float(defines["PRESTIGE_FROM_PRESTIGE_GOODS_PRODUCTION"])
        def_prestige_goods = definitions["prestige_goods"]
        goods_name_to_num = {good: str(i) for i, good in num_to_goods.items()}
        company_type_base_good = dict()
        for company_type_name, company_type in definitions["company_types"].items():
            possible = retrieve_from_tree(company_type, ["possible_prestige_goods", "value"], null=[])
            for prestige_good in possible:
                base_good = retrieve_from_tree(def_prestige_goods, [prestige_good, "base_good"])
                if base_good in goods_name_to_num:
                    company_type_base_good[company_type_name] = goods_name_to_num[base_good]
                    break
        prestige_base_good_nums = set()
        for company in save_data["companies"]["database"].values():
            if not isinstance(company, dict) or company.get("can_produce_prestige_goods") != "yes":
                continue
            base_num = company_type_base_good.get(company.get("company_type"))
            if base_num is not None:
                prestige_base_good_nums.add(base_num)

        """
        Government wages affecting prestige and power projection
        """
        
        # government_wages_* / military_wages_* (which carry country_prestige_mult) live in
        # the static_modifiers folder, not modifiers/.
        static_modifiers = dict()
        for mod_name, static_modifier in definitions["static_modifiers"].items():
            for relevant_modifier in relevant_modifiers:
                if relevant_modifier in static_modifier:
                    static_modifiers[mod_name] = static_modifier
                    break

        """
        Main Countries Loop
        """

        df_prestige = []
        for country_key, country in countries.items():
            if not isinstance(country, dict):
                continue
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

            for law_name, law_modifiers in country_law_prestige.get(country_key, {}).items():
                for modifier, value in law_modifiers.items():
                    national_modifiers[modifier][law_name] = value

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
                    if decay in ["yes", "linear"]:
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

            # A chartered company country has no ruler of its own: its founding company's CEO
            # holds the ruler role, so that character's traits apply.
            ruler = country["ruler"]
            if ruler not in characters:
                ruler = retrieve_from_tree(company_database, [country.get("founding_company"), "ceo"])
            ruler_traits = retrieve_from_tree(characters, [ruler, "traits", "value"], null=[])
            for ruler_trait in ruler_traits:
                if ruler_trait not in def_character_traits:
                    continue
                for country_modifier, value in def_character_traits[ruler_trait]["country_modifier"].items():
                    if country_modifier in relevant_modifiers:
                        national_modifiers[country_modifier][ruler_trait] = float(value)
                        if country_modifier == "country_prestige_add":
                            # The explorer trait: flat prestige for as long as it is the ruler's.
                            national_prestige["ruler prestige"] += float(value)
            
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
                for ig_trait, mult in country["interest_groups_traits"].items():
                    for modifier, value in def_ig_traits[ig_trait]["modifier"].items():
                        if modifier in relevant_modifiers:
                            national_modifiers[modifier][ig_trait] = float(value) * mult
        
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
                        # Army prestige counts regular units only; those raised in the
                        # conscription center are conscripts (CCountry::CalcTotalPowerProjectionImpl
                        # called with the regular service type).
                        if retrieve_from_tree(buildings, [unit.get("building"), "building"]) == conscription_building:
                            continue
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
                        try:
                            veterancy = def_veterancy[unit[key_veterancy]]
                        except KeyError:
                            key_veterancy = "upgrades"
                            veterancy = def_veterancy[unit[key_veterancy]]
                        if "unit_modifier" in veterancy:
                            for vet_modifier, value in veterancy["unit_modifier"].items():
                                if vet_modifier not in unit_modifiers:
                                    continue
                                unit_modifiers[vet_modifier][f"Veterancy level {unit[key_veterancy]}"] = float(value)

                        # Country-wide bonuses, for all units, for army units, and for this unit type.
                        for stat in UNIT_STAT_NAMES:
                            for key in (f"unit_{stat}", f"unit_army_{stat}", f"unit_{unit_type}_{stat}"):
                                for source, value in national_modifiers.get(key, {}).items():
                                    unit_modifiers[f"unit_{stat}"][f"{key} {source}"] = value
                        unit_offense = sum(unit_modifiers["unit_offense_add"].values())
                        unit_offense_mult = sum(unit_modifiers["unit_offense_mult"].values())
                        unit_defense = sum(unit_modifiers["unit_defense_add"].values())
                        unit_defense_mult = sum(unit_modifiers["unit_defense_mult"].values())
                        # unit_offense_mult, unit_defense_mult = 0, 0
                        unit_pp = float(unit["current_manpower"]) * (unit_offense * (1 + unit_offense_mult) + unit_defense * (1 + unit_defense_mult)) / 2 / pp_divisor
                        army_power_projection[unit_type_group] += unit_pp

            # Navy power projection: ships sit outside mil_formations. Since 1.15 a ship's
            # projection is its ``ship_power_projection_add`` (design type + modifications),
            # scaled by (1 + navy-model law + veterancy), times max hit points over a
            # reference (NShips::CalcHullWeightedPowerProjection). A ship whose living crew
            # is at or below the active share of its maximum crew counts for nothing.
            law_mult = country_ship_projection_mult.get(country_key, 0.0)
            navy_pp = 0.0
            for ship in retrieve_from_tree(country, "ships", null={}).values():
                stats = ship_version_stats.get(ship.get("version"))
                if stats is None or stats["ship_crew_max_add"] <= 0:
                    continue
                crew = sum(float(slot.get("crew", 0)) for slot in retrieve_from_tree(ship, "crew", null={}).values()
                           if isinstance(slot, dict))
                if crew / stats["ship_crew_max_add"] <= ship_active_crew_share:
                    continue
                experience = float(ship.get("veterancy_experience", 0))
                mult = 1 + law_mult + ship_veterancy_mult(experience)
                navy_pp += (stats["ship_power_projection_add"] * mult
                            * stats["ship_hit_points_max_add"] / ship_hit_points_reference)
            army_power_projection["navy"] = navy_pp

            # if sum(army_power_projection.values()) > 2000:
            country["power_projection"] = army_power_projection
            national_prestige["army projection"] = army_power_projection["army"] * pp_prestige_divisor_land * (1 + sum(retrieve_from_tree(national_modifiers, ["country_prestige_from_army_power_projection_mult"], null={}).values()))
            national_prestige["navy projection"] = army_power_projection["navy"] * pp_prestige_divisor_navy * (1 + sum(retrieve_from_tree(national_modifiers, ["country_prestige_from_navy_power_projection_mult"], null={}).values()))


            # df_finance["id"] is int64 while country_key is a string dict key,
            # so compare on the integer id (a raw == would never match -> GDP 0).
            country_gdp_row = df_finance[df_finance["id"] == int(country_key)]
            if not country_gdp_row.empty:
                country_gdp = country_gdp_row.iloc[0]["GDP"]
            else:
                country_gdp = 0
            # print(f"{country_key} {country_tag}: {country_gdp[-1]}")
            national_prestige["GDP prestige"] = float(country_gdp) / gdp_divisor * prestige_per_gdp
            # print(country_tag, country_gdp)

            """
            Being a global leader (first, second, or third) in the production of goods gives a country prestige, with some goods being more prestigious than others. (Vickypedia)
            
            Goods are index (perhaps) by the order in the definition file. Hopefully this stays constant in all saves.
            """

            for goods_type, leaderboard in goods_leaderboard.items():
                for rank, stat in enumerate(leaderboard[:min_spot_prestige_award]):
                    if country_key == stat[0]:
                        # Rank 0 (top) gets 2^(MIN_SPOT-1) of the base, halving each rank down,
                        # scaled by the global-GDP factor. Goods with an unlocked prestige
                        # variant go to the prestige-goods line at PRESTIGE_FROM_PRESTIGE_GOODS
                        # times the award; the rest to the ordinary leading-goods line.
                        award = float(retrieve_from_tree(def_goods, [num_to_goods[int(goods_type)], "prestige_factor"], 0)) * 2 ** (min_spot_prestige_award - rank - 1) * goods_leaderboard_scale
                        if goods_type in prestige_base_good_nums:
                            national_prestige["prestige goods prestige"] += award * prestige_goods_mult
                        else:
                            national_prestige["production leader prestige"] += award
                        break

            """
            The major canals and most other monuments grant prestige. (Vickypedia)
            """
            # Flat prestige and a prestige multiplier, each summed over the
            # country's monuments and scaled by their employed workforce.
            national_prestige["monuments prestige"] = monument_prestige.get(country_key, 0)
            national_modifiers["country_prestige_mult"]["monuments"] = monument_prestige_mult.get(country_key, 0)

            """
            Disbanding battalions and ships costs prestige (new in 1.15). Each disbanding is
            logged with the prestige it cost, which then fades linearly to zero over
            DISBAND_PRESTIGE_PENALTY_YEARS. The engine counts whole days of the 365-day calendar.
            """
            for penalty in retrieve_from_tree(country, "disband_prestige_penalties", null={}).values():
                if not isinstance(penalty, dict):
                    continue
                start = calendar_day(penalty["date"])
                end = start + disband_penalty_days
                remaining = max(0, end - today)
                national_prestige["disband penalty"] -= float(penalty["prestige"]) * remaining / disband_penalty_days


            country["national_prestige"] = national_prestige
            country["national_modifiers"] = national_modifiers
            

        """
        Subjects contribute prestige to their overlord based on their own military and economic might. These contributions are reduced compared to the amount generated for the country itself. (Vickypedia)
        """
        prestige_per_subject_gdp = float(defines["PRESTIGE_FROM_SUBJECT_GDP"])
        prestige_per_subject_army_pp = float(script_values["prestige_from_subject_army_power_projection"])
        prestige_per_subject_navy_pp = float(script_values["prestige_from_subject_navy_power_projection"])

        subject_manager(save_data, definitions, countries)
        def_country_types = definitions["country_types"]

        for country_id, country in countries.items():
            if not isinstance(country, dict):
                continue
            if "national_prestige" not in country:
                continue
            # The overlord earns prestige from its whole subject tree, not just direct subjects.
            for subject in collect_subject_tree(countries, country_id):
                subj = countries[subject]
                country["national_prestige"]["subject army projection"] += retrieve_from_tree(subj, ["power_projection", "army"], null=0) * prestige_per_subject_army_pp
                country["national_prestige"]["subject navy projection"] += retrieve_from_tree(subj, ["power_projection", "navy"], null=0) * prestige_per_subject_navy_pp
                country["national_prestige"]["subject gdp prestige"] += retrieve_from_tree(subj, ["national_prestige", "GDP prestige"], null=0) * prestige_per_subject_gdp / prestige_per_gdp
            
            total_prestige = sum([v for v in country["national_prestige"].values()])
            total_modifiers = sum([v for v in country["national_modifiers"]["country_prestige_mult"].values()])
            country["national_prestige"]["modifiers"] = total_modifiers
            country_tag = country["definition"]
            country_name = get_country_name(country, localization)
            df_country = {"id":country_id, "tag":country_tag, "country":country_name, "total":total_prestige * (1 + total_modifiers)}
            df_country.update(country["national_prestige"])
            if retrieve_from_tree(def_country_types, [country.get("country_type"), "uses_prestige"], null="yes") == "no":
                # Decentralized countries always have a prestige of 0.
                df_country.update({key: 0 for key in df_country if key in prestige_columns or key == "total"})
            df_prestige.append(df_country)

        df_prestige = pd.DataFrame(df_prestige, columns=["id", "tag", "country", "total"] + prestige_columns)
        df_prestige = df_prestige.sort_values(by='total', ascending=False)

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_prestige.to_csv(f"{address}/data/prestige.csv", sep=",", index=False)
            df_prestige_players = df_prestige[df_prestige["id"].isin(players)]
            df_prestige_players.to_csv(f"{address}/prestige.csv", sep=",", index=False)
            with open(f"{address}/prestige.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                df_prestige_players.to_string(buf=f"{address}/prestige.txt", encoding="utf-8")
        
        print(f"Finished checking prestige on {day}/{month}/{year}")

        return df_prestige

    # %%
