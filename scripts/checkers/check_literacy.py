from scripts.checkers.check_base import Checker
from scripts.checkers.checkers_functions import get_country_name
from scripts.helpers.utility import retrieve_from_tree
import pandas as pd

class CheckLiteracy(Checker):
    
    requirements = ["pops", "states", "country_manager"]
    output = {"literacy.csv":["literacy", "population"]}

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
            if float(retrieve_from_tree(state := states[pop["location"]], ["incorporation"], null=0)) < 1:
                continue
            workers, dependents, literates, literacy = 0, 0, 0, 0
            if "workforce" in pop:
                workers = int(pop["workforce"])
            if "dependents" in pop:
                dependents = int(pop["dependents"])
            if "num_literate" in pop:
                literates = int(pop["num_literate"])
            total = workers + dependents
            literacy = literates / (workers + 0.0000001) # TODO Might use this to visualize distribution of literacy
            if "pop_literacy" not in state:
                state["pop_literacy"] = []
            state["pop_literacy"].append((total, workers, literates, literacy)) # Total pop, literacy rate
        
        for key, state in states.items():
            if retrieve_from_tree(state, ["pop_literacy"]) is None:
                continue
            if "country" not in state:
                state["country"] = state["zero_token_259"] # FIXME Rectify this after updating melter
            country = countries[state["country"]]
            if "pop_literacy" not in country:
                country["pop_literacy"] = []
            country["pop_literacy"] += state["pop_literacy"]

        df_literacy = []
        for country_id, country in countries.items():
            if not isinstance(country, dict) or "pop_literacy" not in country:
                continue
            total_population, total_workers, total_literates = 0, 0, 0
            for pl in country["pop_literacy"]:
                total_population += pl[0]
                total_workers += pl[1]
                total_literates += pl[2]
            literacy = total_literates / (total_workers + 0.0000001)
            country_tag = country["definition"]
            country_name = get_country_name(country, localization)
            df_country = {"id":country_id, "tag":country_tag, "country":country_name, "population":total_population, "literacy":literacy}
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