import pandas as pd
import numpy as np
import warnings
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import *
from src.helpers.utility import *

RELEVANT_MODIFIERS = ["country_weekly_innovation_add", "country_weekly_innovation_mult",
                      "country_weekly_innovation_max_add"]

UNIVERSITY_INNOVATION = Agg(
    "building", by=BUILD_GROUP, name="university_innovation",
    value=building_output_of("country_weekly_innovation_add"),
    where=building_of_type("building_university"))


class CheckInnovation(Checker):
    """
    Retrieve Innovation and its cap of player nations and nations with > base innovation
    """
    name = "CheckInnovation"
    display_name = "Innovation"
    sort_order = 70
    requirements = ["building_manager", "country_manager", "pops", "player_manager", "companies", "power_bloc_manager", "pacts", "institutions"]
    column_backed = {"pops": "pop"}  # reached only through the declared aggregates
    aggregates = [EMPLOYED_WORKFORCE, UNIVERSITY_INNOVATION]
    # company_types, subject_types and power_bloc_principles are loaded on this
    # checker's behalf by companies_manager, subject_manager and bloc_manager.
    definitions = ("production_methods", "static_modifiers", "company_types",
                   "subject_types", "power_bloc_principles")
    output = {"innovation.csv":["innovation", "capped innovation", "innovation ratio"]}
    dependencies = ["demographics.csv"]
    
    def __init__(self):
        super().__init__()

    def before_countries(self, cache):
        save_data = cache["save_data"]
        countries = save_data["country_manager"]["database"]
        definitions = cache["definitions"]
        self.save_date = cache["metadata"]["save_date"]
        self.university_innovation = cache["aggregates"].get("university_innovation", {})

        # Literacy per country id, read back from demographics.csv.
        df_demographics = pd.read_csv(f"{cache['address']}/data/demographics.csv", sep=",")[["id", "literacy"]]
        self.literacy = {}
        for country_id, literacy in zip(df_demographics["id"], df_demographics["literacy"]):
            self.literacy.setdefault(str(country_id), literacy)

        self.static_modifiers = definitions["static_modifiers"]
        self.base_innovation = float(retrieve_from_tree(self.static_modifiers, ["base_values", "country_weekly_innovation_add"], null=0))
        self.literacy_innovation = float(retrieve_from_tree(self.static_modifiers, ["country_literacy_rate", "country_weekly_innovation_add"], null=0))
        self.literacy_max_inno = float(retrieve_from_tree(self.static_modifiers, ["country_literacy_rate", "country_weekly_innovation_max_add"], null=0))
        companies_manager(save_data, definitions, countries, RELEVANT_MODIFIERS)
        subject_manager(save_data, definitions, countries)
        institution_manager(save_data, countries, ["institution_schools"])
        self.principles, self.blocs = bloc_manager(save_data, definitions, RELEVANT_MODIFIERS)

    def on_country(self, country_id, country, cache):
        if "states" not in country:
            return None
        literacy = self.literacy.get(str(country_id))
        if literacy is None:
            literacy = MISSING
            warnings.warn(f"No literacy record for {country_id}:{country['definition']}")

        inno_cap = self.base_innovation + self.literacy_max_inno * float(literacy)

        innov = self.base_innovation + self.literacy_innovation * float(literacy)
        innov_mult = 1
        # University output, from the shared building pass.
        innov += self.university_innovation.get(country_id, 0)

        # Companies
        if (companies := retrieve_from_tree(country, "companies")) is not None:
            for company_name, company in companies.items():
                inno_cap += float(retrieve_from_tree(company, ["prosperity_modifier", "country_weekly_innovation_max_add"], 0))
                innov += float(retrieve_from_tree(company, ["prosperity_modifier", "country_weekly_innovation_add"], 0))
                innov_mult += float(retrieve_from_tree(company, ["prosperity_modifier", "country_weekly_innovation_mult"], 0))

        # Power blocs education principles
        if "power_bloc_as_core" in country:
            if (bloc := retrieve_from_tree(self.blocs, country["power_bloc_as_core"])) is not None:
                for principle in bloc["principles"]["value"]:
                    bloc_cap = float(retrieve_from_tree(self.principles, [principle, "institution_modifier", "country_weekly_innovation_max_add"], 0)) * float(retrieve_from_tree(country, ["institutions", "institution_schools"], 0))
                    inno_cap += bloc_cap

        national_modifiers = national_modifiers_manager(country, self.save_date, self.static_modifiers, RELEVANT_MODIFIERS)
        innov += sum([float(v) for v in national_modifiers["country_weekly_innovation_add"].values()])
        inno_cap += sum([float(v) for v in national_modifiers["country_weekly_innovation_max_add"].values()])

        innov = innov * innov_mult
        return [country_id, country["definition"], get_country_name(country, cache["localization"]),
                innov, inno_cap, safe_ratio(innov, inno_cap)]

    def execute_check(self, cache):
        save_date = cache["metadata"]["save_date"]
        players = players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        columns = ["id", "tag", "country", "innovation", "innovation cap", "innovation ratio"]
        df_innov = pd.DataFrame(cache["country_rows"][self.name], columns=columns)
        df_innov["capped innovation"] = np.minimum(df_innov["innovation"], df_innov["innovation cap"])
        df_innov = df_innov.sort_values(by='capped innovation', ascending=False)

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_innov.to_csv(f"{address}/data/innovation.csv", sep=",", index=False)
            df_innov_players = df_innov[df_innov["id"].isin(players)]
            df_innov_players.to_csv(f"{address}/innovation.csv", sep=",", index=False)
            with open(f"{address}/innovation.txt", "w", encoding="utf-8") as file:
                file.write(f"{day}/{month}/{year}\n")
                file.write(df_innov_players.to_string())
        print(f"Finished checking innovation on {day}/{month}/{year}")
        return df_innov