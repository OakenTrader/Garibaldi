"""
Functions related to game variables that are used commonly by the checker functions.
"""
import os
import re
import numpy as np
from src.checkers.aggregates import Agg, Call, Emit, F, present, run_aggregates
from src.helpers.columnar import load_columns
from src.helpers.utility import *

# Sentinel for a statistic that could not be retrieved or is undefined for a save.
# Checkers must emit MISSING instead of a fabricated 0 so that a genuinely absent
# value is distinguishable from a legitimate 0. pandas writes it as an empty CSV
# cell and reads it back as NaN; the plotting layer interpolates it across
# neighboring saves (see plotter.interpolate_missing).
MISSING = np.nan


def safe_ratio(numer, denom, minimum=0):
    """
    Compute ``numer / denom`` guarding against a division by zero.

    Returns ``MISSING`` (NaN) when the denominator is at or below ``minimum``
    (default 0), i.e. when the ratio is undefined rather than legitimately zero.
    This supersedes the old ``numer / (denom + epsilon)`` / ``numer / max(denom,
    epsilon)`` fudges, which silently produced a spurious 0 or a huge number.
    """
    if denom is None or denom <= minimum:
        return MISSING
    return numer / denom

def companies_manager(save_data, definitions, countries, relevant_modifiers):
    """
    Provides checkers with information of companies with relevant traits

    definitions (dict): the manager's preloaded definitions; needs "company_types".
    Passed in rather than loaded here so that the folder is read once per session
    and stays visible in the calling checker's ``definitions`` declaration.
    """
    def_companies = dict()
    companies = definitions["company_types"]
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

def subject_manager(save_data, definitions, countries):
    """
    Get all subjects of each country and the country it is subject to

    definitions (dict): the manager's preloaded definitions; needs "subject_types".
    """
    def_subjects = [v["diplomatic_action"] for v in definitions["subject_types"].values()]
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

def collect_subject_tree(countries, root_id):
    """
    Return all descendants in a country's subject tree (subjects,
    subjects-of-subjects, ...) as a sorted list. Requires ``subject_manager`` to have
    populated the per-country ``subjects`` lists first. Cycle-guarded.

    Sorted rather than a bare set because the caller accumulates floats over the
    result (CheckPrestige's subject army/navy/GDP projection). Python randomises
    string hashing per process, so set order — and therefore summation order —
    varied between runs, leaving ~1 ULP of noise in prestige.csv that made
    output diffing unreliable.
    """
    seen = set()
    stack = list(retrieve_from_tree(countries[root_id], "subjects", null=[]))
    while stack:
        sid = stack.pop()
        if sid in seen or not isinstance(countries.get(sid), dict):
            continue
        seen.add(sid)
        stack.extend(retrieve_from_tree(countries[sid], "subjects", null=[]))
    return sorted(seen)

def bloc_manager(save_data, definitions, relevant_modifiers):
    """
    Retrieve power blocs and/with relevant principles

    definitions (dict): the manager's preloaded definitions; needs
    "power_bloc_principles".
    """
    def_principles = definitions["power_bloc_principles"]
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
    """Get data of institutions and their levels with relevant modifiers"""
    all_institutions = save_data["institutions"]["database"]
    for _, institution in all_institutions.items():
        if not isinstance(institution, dict):
            continue
        if institution["institution"] in relevant_institutions:
            if "institutions" not in (country := countries[institution["country"]]):
                country["institutions"] = dict()
            country["institutions"][institution["institution"]] = institution["investment"]

def national_modifiers_manager(country, save_date, def_modifiers, relevant_modifiers):
    """
    Timed and untimed modifiers registered on national level
    """
    out_modifiers = {key:dict() for key in relevant_modifiers}
    timed_modifiers = retrieve_from_tree(country, ["timed_modifiers"], null={"modifiers":dict()})
    for _, modifier in timed_modifiers["modifiers"].items():
        modifier_name = modifier["modifier"]
        if modifier_name not in def_modifiers:
            continue
        decay = retrieve_from_tree(modifier, "decay", null=1)
        start_date = retrieve_from_tree(modifier, "start_date")
        end_date = retrieve_from_tree(modifier, "end_date")
        multiplier = retrieve_from_tree(modifier, "multiplier", null=1)
        modifier = def_modifiers[modifier_name]
        if decay == "yes" or decay == "linear":
            decay = (1 - get_duration(save_date, start_date, end_date)[-1])
        for mod, value in modifier.items():
            if mod in relevant_modifiers:
                out_modifiers[mod][modifier_name] = float(value) * float(multiplier) * decay
    return out_modifiers

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

def state_owner(ctx):
    """state id -> the country listing it, built once per save.

    Countries are visited in database order and the first to claim a state keeps it.
    """
    owner = ctx.payload.get("_state_owner")
    if owner is None:
        owner = {}
        for country_id, country in ctx.payload["save_data"]["country_manager"]["database"].items():
            if not isinstance(country, dict) or "states" not in country:
                continue
            for state_id in country["states"]["value"]:
                owner.setdefault(state_id, country_id)
        ctx.payload["_state_owner"] = owner
    return owner


def building_country(building, ctx):
    """The country a building belongs to, via the state that holds it."""
    return state_owner(ctx).get(building.get("state"))


# Grouping keys available to building-stage aggregates.
BUILD_GROUP = Call(building_country, name="building_country")


def building_state_country(building, ctx):
    """The country the building's own state names as its owner.

    Differs from ``BUILD_GROUP`` for a handful of states per save; the two keys are
    not interchangeable.
    """
    state = ctx.payload["save_data"]["states"]["database"].get(building.get("state"))
    return state.get("country") if isinstance(state, dict) else None


STATE_COUNTRY = Call(building_state_country, name="building_state_country")


def building_output_of(target, methods=None, methods_name="all"):
    """A Call summing one modifier's building output, for a building-stage Agg.

    ``methods`` is a ``ctx -> {name: production_method}`` selection; it changes the
    result, since ``get_building_output`` divides by the employment those methods
    declare. ``methods_name`` distinguishes two selections in the dedup key.
    """
    def value(building, ctx):
        production_methods = (methods(ctx) if methods is not None
                              else ctx.payload["definitions"]["production_methods"])
        return get_building_output(building, target, production_methods)
    return Call(value, name=f"building_output:{target}@{methods_name}")


def building_of_type(building_type):
    """A Call selecting one kind of building."""
    def where(building, ctx):
        return building.get("building") == building_type
    return Call(where, name=f"building_is:{building_type}")


EMPLOYED_WORKFORCE = Agg(
    "pop", by="workplace", name="employed_workforce", value=F("workforce"),
    where=present("workplace") & present("workforce"),
    attach=("building_manager", "employed_workforce"),
)


def get_building_output(building, target, def_production_methods, modifier_type="country_modifiers"):
    """
    Calculate a building's output of a variable with respected to production methods, employees and throughput
    Employees come from the building's attached ``employed_workforce``.
    """
    output = 0
    employees = 0
    employees_pl = dict()
    for pm_name in building["production_methods"]["value"]:
        # Only the methods passed in count; a building's others carry no target.
        if pm_name not in def_production_methods:
            continue
        pm = def_production_methods[pm_name]
        if (output_workforce := retrieve_from_tree(pm, [modifier_type, "workforce_scaled", target])) is not None:
            output += float(output_workforce)
        if (employees_dict := retrieve_from_tree(pm, ["building_modifiers", "level_scaled"])) is not None:
            for key, addition in employees_dict.items():
                if key not in employees_pl:
                    employees_pl[key] = int(addition)
                else:
                    employees_pl[key] += int(addition)

    employees += building.get("employed_workforce", 0)

    # print(employees_pl)
    # print(f"Total Employees at level {int(building['level'])}: {employees}")
    employees_pl_total = sum([employees_pl[e] for e in employees_pl])
    if employees_pl_total <= 0:
        # Degenerate staffing (e.g. modded monuments with negative building_employment):
        # apply the workforce-scaled modifier in full rather than letting the ratio flip sign.
        employees = 1.0
    else:
        employees /= employees_pl_total
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
    return new_name