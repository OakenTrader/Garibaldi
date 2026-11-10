from src.checkers.aggregates import Agg, F, present, run_aggregates
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import get_country_name, get_building_output, institution_manager, safe_ratio, MISSING
from src.checkers.pop_growth import (GROWTH_DEFINITIONS, CONTEXT_TOPICS, LOYALTY_SCALE, POP_FIELDS, context_of,
                                     state_growth)
from src.helpers.columnar import build_columns, load_columns
from src.helpers.utility import retrieve_from_tree
import pandas as pd

demographics_columns = ["literacy", "standard of living", "population", "incorporated population", "total peasants", "total unemployed", "peasants percentage", "unemployed percentage", "radicals", "loyalists", "radicals percentage", "loyalists percentage",
                       "birth rate", "mortality rate", "natural growth"]

# The engine grows a pop once a month and shows its rates per year. The births and
# deaths ``state_growth`` returns are for one month.
MONTHS_PER_YEAR = 12

_TOTAL_KEYS = ("population", "workforce", "literates", "peasants", "unemployed",
               "loyalists", "radicals", "births", "deaths")

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
    """
    Population, literacy, standard of living, political leaning and growth, per country.

    birth rate, mortality rate, natural growth: per year, as a fraction of the population.
    The save stores none of them. The engine computes them for every pop from its SoL and a
    set of modifiers, and pop_growth.py rebuilds that: the base rates exactly, the modifiers
    from laws, technologies, timed modifiers, devastation, pollution, turmoil, interest group
    traits, institutions, state traits (malaria, for pops away from their homeland), harvest
    conditions (earthquakes), power bloc principles and identities, unemployment, settlement
    density, literacy, building hazards and starvation. It does not rebuild modifiers from
    character traits or companies, so a country that has one is off. The bloc and harvest terms
    are checked against the game only in structure and, for the earthquake, in one window.

    Checked against the engine's own per-pop results for a 1836 world, on the pops it grew in
    the month before the February autosaves of 1836, 1840, 1845 and 1850, natural growth for
    the world as a whole is within 0.007 percentage points a year (under 1% of the growth),
    births within 0.15% and deaths within 0.1% of the engine's. Of the large countries the
    worst, China in 1840, is 0.014 off. Small, fast-growing colonies can be off by more (a few
    hundredths) for reasons not yet found. Natural growth is not realised growth, since
    migration and annexation move population too.
    """

    name = "CheckDemographics"
    display_name = "Demographics"
    sort_order = 20
    requirements = ["pops", "states", "country_manager", "building_manager", "laws", *CONTEXT_TOPICS]
    column_backed = {"pops": "pop"}  # reached only through the declared aggregates
    aggregates = POP_AGGREGATES
    definitions = GROWTH_DEFINITIONS
    output = {"demographics.csv":demographics_columns}
    column_labels = {"birth rate": "Birth rate (estimate, per year)",
                     "mortality rate": "Mortality rate (estimate, per year)",
                     "natural growth": "Natural growth (estimate, per year)"}

    def __init__(self):
        super().__init__()
    
    def before_countries(self, cache: dict):
        save_data = cache["save_data"]
        states = save_data["states"]["database"]
        countries = save_data["country_manager"]["database"]
        # Births and deaths from the pop table, with the modifiers the save lets us rebuild.
        pops = load_columns(cache["address"], "pop")
        if pops is None:   # a save with no column cache: the pop tree was loaded instead
            pops = build_columns(save_data["pops"]["database"], "pop", only=POP_FIELDS)
        columns, vocabs, _ = pops
        growth = state_growth(columns, vocabs, states, countries, save_data["laws"]["database"],
                              save_data["building_manager"]["database"], cache["definitions"], context_of(save_data),
                              cache["metadata"]["save_date"])

        # Per-state totals from the shared pop pass, attached to the states.
        apply_state_demographics(states, {**cache["aggregates"], **growth})

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
        total_births, total_deaths = 0, 0
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
            total_births += totals["births"]
            total_deaths += totals["deaths"]
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
        birth_rate = safe_ratio(total_births * MONTHS_PER_YEAR, total_population)
        mortality_rate = safe_ratio(total_deaths * MONTHS_PER_YEAR, total_population)
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
                "birth rate": birth_rate,
                "mortality rate": mortality_rate,
                "natural growth": birth_rate - mortality_rate,   # NaN when either is
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