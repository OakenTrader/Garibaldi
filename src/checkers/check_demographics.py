from src.checkers.check_base import Checker
from src.checkers.checkers_functions import get_country_name, get_building_output, institution_manager
from src.helpers.utility import retrieve_from_tree, load_def_multiple
import pandas as pd

demographics_columns = ["literacy", "population", "incorporated population", "total peasants", "total unemployed", "peasants percentage", "unemployed percentage", "radicals", "loyalists", "radicals percentage", "loyalists percentage"]

class CheckDemographics(Checker):
    
    requirements = ["pops", "states", "country_manager", "building_manager"]
    output = {"demographics.csv":demographics_columns}

    def __init__(self):
        super().__init__()
    
    def execute_check(self, cache: dict):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        pops = save_data["pops"]["database"]
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


        for pop_key, pop in pops.items():
            if not isinstance(pop, dict):
                continue
            workers, dependents, literates, literacy, peasants, unemployed, loyalists = 0, 0, 0, 0, 0, 0, 0
            try:
                if "workforce" in pop:
                    workers = int(pop["workforce"])
                if "dependents" in pop:
                    dependents = int(pop["dependents"])
                total = workers + dependents
                if "num_literate" in pop:
                    literates = int(pop["num_literate"])
                if pop["type"] == "peasants" and "workforce" in pop:
                    peasants = int(pop["workforce"])
                if "workplace" not in pop and "workforce" in pop:
                    unemployed = int(pop["workforce"])
                if "loyalists_and_radicals" in pop:
                    loyalists = float(pop["loyalists_and_radicals"]) * (total) / 100
                if "wealth" in pop:
                    """Standard of living (SOL) = wealth + modifiers + pollution_effect + ruler personality + power_bloc modifier + state modifiers
                    pollution_effect is workforce_scaled from all building production methods.
                    Pollution effect is reduced by institutions and technologies.
                    """
                    pass
            except KeyError:
                print(pop)
                raise KeyError("Missing key in pop")
            literacy = literates / max(workers, 0.0000001) # TODO Might use this to visualize distribution of literacy
            state = states[pop["location"]]
            if "demographics" not in state:
                state["demographics"] = []
            demographics = {"population":total, "workforce":workers, "dependents":dependents, "literates":literates, "literacy":literacy, "peasants":peasants, "unemployed":unemployed, "loyalists":loyalists}
            state["demographics"].append(demographics) # Total pop, literacy rate
        
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

        df_literacy = []
        for country_id, country in countries.items():
            if not isinstance(country, dict) or "demographics" not in country:
                continue
            total_population, total_workers, total_literates, total_unemployed, total_peasants, total_radicals, total_loyalists = 0, 0, 0, 0, 0, 0, 0
            incorporated_population, incorporated_workers, incorporated_literates, incorporated_unemployed, incorporated_peasants = 0, 0, 0, 0, 0
            for state in country["demographics"]:
                incorporation, pops = state
                total_population += sum([pop["population"] for pop in pops])
                total_workers += sum([pop["workforce"] for pop in pops])
                total_literates += sum([pop["literates"] for pop in pops])
                total_unemployed += sum([pop["unemployed"] for pop in pops])
                total_peasants += sum([pop["peasants"] for pop in pops])
                total_loyalists += sum([pop["loyalists"] for pop in pops if pop["loyalists"] > 0])
                total_radicals += -sum([pop["loyalists"] for pop in pops if pop["loyalists"] < 0])
                if incorporation >= 1:
                    incorporated_population += sum([pop["population"] for pop in pops])
                    incorporated_workers += sum([pop["workforce"] for pop in pops])
                    incorporated_literates += sum([pop["literates"] for pop in pops])
                    incorporated_peasants += sum([pop["peasants"] for pop in pops])
                    incorporated_unemployed += sum([pop["unemployed"] for pop in pops])
            literacy = incorporated_literates / max(incorporated_workers, 0.0000001)
            peasants_percentage = total_peasants / max(total_workers, 0.0000001)
            unemployed_percentage = total_unemployed / max(total_workers, 0.0000001)
            radicals_percentage = total_radicals / max(total_population, 0.0000001)
            loyalists_percentage = total_loyalists / max(total_population, 0.0000001)
            country_tag = country["definition"]
            country_name = get_country_name(country, localization)
            df_country = {
                "id": country_id,
                "tag": country_tag,
                "country": country_name,
                "population": total_population,
                "literacy": literacy,
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
            df_literacy.append(df_country)

        df_literacy = pd.DataFrame(df_literacy, columns=df_literacy[0].keys())
        df_literacy.sort_values(by='literacy', ascending=False)
        df_literacy = df_literacy[df_literacy["id"].isin(players)]

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_literacy.to_csv(f"{address}/demographics.csv", sep=",", index=False)
            with open(f"{address}/demographics.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                df_literacy.to_string(buf=f"{address}/demographics.txt", encoding="utf-8")
        
        print(f"Finished checking demographics on {day}/{month}/{year}")

        return df_literacy