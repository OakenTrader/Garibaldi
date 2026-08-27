from src.checkers.aggregates import Agg, F, present, run_aggregates
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import get_country_name, get_building_output, institution_manager, safe_ratio, MISSING
from src.helpers.utility import retrieve_from_tree
import pandas as pd

demographics_columns = ["literacy", "standard of living", "population", "incorporated population", "total peasants", "total unemployed", "peasants percentage", "unemployed percentage", "radicals", "loyalists", "radicals percentage", "loyalists percentage"]

# `loyalists_and_radicals` is a pop's NET count of politically aligned individuals:
# positive => loyalists, negative => radicals. Fixed-point, shown by the melter as
# raw / 100000, so multiply back to recover the count. Not a per-capita rate.
LOYALTY_SCALE = 100000

_TOTAL_KEYS = ("population", "workforce", "literates", "peasants", "unemployed",
               "loyalists", "radicals")

# What demographics needs out of the pop table.
LOYALTY = F("loyalists_and_radicals", scaled=True)

POP_AGGREGATES = [
    Agg("pop", by="location", name="population",
        value=F("workforce") + F("dependents")),
    Agg("pop", by="location", name="workforce", value=F("workforce")),
    Agg("pop", by="location", name="literates", value=F("num_literate")),
    Agg("pop", by="location", name="peasants", value=F("workforce"),
        where=F("type") == "peasants"),
    Agg("pop", by="location", name="unemployed", value=F("workforce"),
        where=~present("workplace")),
    Agg("pop", by="location", name="loyalists", value=LOYALTY, where=LOYALTY > 0),
    # Summed as raw negatives, then negated once per group.
    Agg("pop", by="location", name="radicals", value=LOYALTY, where=LOYALTY < 0,
        negate=True),
]


def _state_totals(state):
    """The per-state accumulator, created on first use."""
    totals = state.get("demographics")
    if totals is None:
        totals = state["demographics"] = dict.fromkeys(_TOTAL_KEYS, 0)
    return totals


def apply_state_demographics(states, totals):
    """Attach the engine's per-state sums to the states that hold pops.

    Only populated states get an entry, which is what the country rollup keys off.
    """
    for name in _TOTAL_KEYS:
        for location, value in totals.get(name, {}).items():
            state = states.get(location)
            if isinstance(state, dict):
                _state_totals(state)[name] += value


class CheckDemographics(Checker):
    
    name = "CheckDemographics"
    display_name = "Demographics"
    sort_order = 20
    requirements = ["pops", "states", "country_manager", "building_manager"]
    column_backed = {"pops": "pop"}  # reached only through the declared aggregates
    aggregates = POP_AGGREGATES
    output = {"demographics.csv":demographics_columns}

    def __init__(self):
        super().__init__()
    
    def before_countries(self, cache: dict):
        save_data = cache["save_data"]
        states = save_data["states"]["database"]
        countries = save_data["country_manager"]["database"]
        # buildings = save_data["building_manager"]["database"]
        # def_production_methods = load_def_multiple("production_methods", "Common Directory")
        # institution_manager(save_data, countries, "")

        # for building_key, building in buildings.items():
        #     """Get pollution"""
        #     pollution = get_building_output(building, "state_pollution_generation_add", def_production_methods, modifier_type="state_modifiers")
        #     state = building["state"]
        #     if "GBD_pollution" not in state:
        #         state["GB_pollution"] = 0
        #     state["GBD_pollution"] += float(pollution)

        # # Process pollution data
        # for key, state in states.items():
        #     if retrieve_from_tree(state, ["GBD_pollution"]) is None:
        #         continue
        #     if "country" not in state:
        #         continue # dead state
        #     arable_land = retrieve_from_tree(state, ["arable_land"], null=0) # Assume it's never zero
        #     pollution = retrieve_from_tree(state, ["GBD_pollution"], null=0)
        #     if pollution > 0:
        #         pollution_effect = (pollution / (50 + 1.5 * arable_land**0.5)) / 255
        #         state["GBD_pollution_effect"] = pollution_effect


        # Per-state totals from the shared pop pass, attached to the states.
        apply_state_demographics(states, cache["aggregates"])

        for key, state in states.items():
            if retrieve_from_tree(state, ["demographics"]) is None:
                continue
            if "country" not in state:
                continue # dead state
            country = countries[state["country"]]
            if "demographics" not in country:
                country["demographics"] = []
            incorporation = float(retrieve_from_tree(state, ["incorporation"], null=0))
            country["demographics"].append([incorporation, state["demographics"]])

    def on_country(self, country_id, country, cache):
        if "demographics" not in country:
            return None
        total_population, total_workers, total_literates, total_unemployed, total_peasants, total_radicals, total_loyalists = 0, 0, 0, 0, 0, 0, 0
        incorporated_population, incorporated_workers, incorporated_literates, incorporated_unemployed, incorporated_peasants = 0, 0, 0, 0, 0
        for state in country["demographics"]:
            incorporation, totals = state
            total_population += totals["population"]
            total_workers += totals["workforce"]
            total_literates += totals["literates"]
            total_unemployed += totals["unemployed"]
            total_peasants += totals["peasants"]
            total_loyalists += totals["loyalists"]
            total_radicals += totals["radicals"]
            if incorporation >= 1:
                incorporated_population += totals["population"]
                incorporated_workers += totals["workforce"]
                incorporated_literates += totals["literates"]
                incorporated_peasants += totals["peasants"]
                incorporated_unemployed += totals["unemployed"]
        literacy = safe_ratio(incorporated_literates, incorporated_workers)
        peasants_percentage = safe_ratio(total_peasants, total_workers)
        unemployed_percentage = safe_ratio(total_unemployed, total_workers)
        radicals_percentage = safe_ratio(total_radicals, total_population)
        loyalists_percentage = safe_ratio(total_loyalists, total_population)
        standard_of_living = retrieve_from_tree(country, ["avgsoltrend", "channels", "0", "values", "value"], null=[MISSING])[-1]
        return {
                "id": country_id,
                "tag": country["definition"],
                "country": get_country_name(country, cache["localization"]),
                "population": total_population,
                "literacy": literacy,
                "standard of living": standard_of_living,
                "incorporated population": incorporated_population,
                "incorporated workforce": incorporated_workers,
                "incorporated literates": incorporated_literates,
                "incorporated peasants": incorporated_peasants,
                "incorporated unemployed": incorporated_unemployed,
                "total workforce": total_workers,
                "total literates": total_literates,
                "total peasants": total_peasants,
                "total unemployed": total_unemployed,
                "peasants percentage": peasants_percentage,
                "unemployed percentage": unemployed_percentage,
                "radicals": total_radicals,
                "loyalists": total_loyalists,
                "radicals percentage": radicals_percentage,
                "loyalists percentage": loyalists_percentage,
            }

    def execute_check(self, cache: dict):
        save_date = cache["metadata"]["save_date"]
        players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        df_demographics = cache["country_rows"][self.name]
        df_demographics = pd.DataFrame(df_demographics, columns=df_demographics[0].keys())
        df_demographics = df_demographics.sort_values(by='population', ascending=False)

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_demographics.to_csv(f"{address}/data/demographics.csv", sep=",", index=False)
            df_demographics_players = df_demographics[df_demographics["id"].isin(players)]
            df_demographics_players.to_csv(f"{address}/demographics.csv", sep=",", index=False)
            with open(f"{address}/demographics.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                df_demographics_players.to_string(buf=f"{address}/demographics.txt", encoding="utf-8")
        
        print(f"Finished checking demographics on {day}/{month}/{year}")

        return df_demographics