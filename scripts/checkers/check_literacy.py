from scripts.checkers.check_base import Checker
from scripts.checkers.checkers_functions import get_country_name
from scripts.helpers.utility import retrieve_from_tree
import pandas as pd

class CheckLiteracy(Checker):
    
    requirements = ["pops", "states", "country_manager"]
    output = {"literacy.csv":["literacy", "population", "incorporated population"]}

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
        for pop_key, pop in pops.items():
            if not isinstance(pop, dict):
                continue
            workers, dependents, literates, literacy = 0, 0, 0, 0
            if "workforce" in pop:
                workers = int(pop["workforce"])
            if "dependents" in pop:
                dependents = int(pop["dependents"])
            if "num_literate" in pop:
                literates = int(pop["num_literate"])
            total = workers + dependents
            literacy = literates / max(workers, 0.0000001) # TODO Might use this to visualize distribution of literacy
            state = states[pop["location"]]
            if "demographics" not in state:
                state["demographics"] = []
            demographics = {"population":total, "workforce":workers, "dependents":dependents, "literates":literates, "literacy":literacy}
            state["demographics"].append(demographics) # Total pop, literacy rate
        
        for key, state in states.items():
            if retrieve_from_tree(state, ["demographics"]) is None:
                continue
            if "country" not in state:
                state["country"] = state["zero_token_259"] # FIXME Rectify this after updating melter
            country = countries[state["country"]]
            if "demographics" not in country:
                country["demographics"] = []
            incorporation = float(retrieve_from_tree(state, ["incorporation"], null=0))
            country["demographics"].append([incorporation, state["demographics"]])

        df_literacy = []
        for country_id, country in countries.items():
            if not isinstance(country, dict) or "demographics" not in country:
                continue
            total_population, total_workers, total_literates = 0, 0, 0
            incorporated_population, incorporated_workers, incorporated_literates = 0, 0, 0
            for state in country["demographics"]:
                incorporation, pops = state
                total_population += sum([pop["population"] for pop in pops])
                total_workers += sum([pop["workforce"] for pop in pops])
                total_literates += sum([pop["literates"] for pop in pops])
                if incorporation >= 1:
                    incorporated_population += sum([pop["population"] for pop in pops])
                    incorporated_workers += sum([pop["workforce"] for pop in pops])
                    incorporated_literates += sum([pop["literates"] for pop in pops])
            literacy = incorporated_literates / max(incorporated_workers, 0.0000001)
            country_tag = country["definition"]
            country_name = get_country_name(country, localization)
            df_country = {"id":country_id, "tag":country_tag, "country":country_name, "population":total_population, "literacy":literacy, "incorporated population":incorporated_population}
            df_literacy.append(df_country)
        
        df_literacy = pd.DataFrame(df_literacy, columns=["id", "tag", "country", "population", "literacy"])
        df_literacy.sort_values(by='literacy', ascending=False)
        df_literacy = df_literacy[df_literacy["id"].isin(players)]

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_literacy.to_csv(f"{address}/literacy.csv", sep=",", index=False)
            with open(f"{address}/literacy.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                df_literacy.to_string(buf=f"{address}/literacy.txt", encoding="utf-8")
        
        print(f"Finished checking literacy on {day}/{month}/{year}")

        return df_literacy