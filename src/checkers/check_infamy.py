import pandas as pd
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import get_country_name
from src.helpers.utility import *

class CheckInfamy(Checker):
    """
    Retrieve infamy of player countries and countries with non-zero infamy
    """
    requirements = ["country_manager"]
    output = {"infamy.csv": ["infamy"]}
    
    def __init__(self):
        super().__init__()
    
    def execute_check(self, cache):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]
        
        countries = save_data["country_manager"]["database"]
        infamies = dict()
        for k, country in countries.items():
            if "definition" not in country:
                continue
            tag = country["definition"]
            country_name = get_country_name(country, localization)
            if "infamy" in country:
                infamies[k] = (tag, country_name, country["infamy"])
            else:
                infamies[k] = (tag, country_name, 0)

        vlist = [[k, v[0] , v[1], float(v[2])] for k, v in infamies.items()]
        
        df = pd.DataFrame(vlist, columns=["id", "tag", "country", "infamy"])
        df = df.sort_values(by='infamy', ascending=False)
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df.to_csv(f"{address}/data/infamy.csv", sep=",", index=False)
            df = df[df["id"].isin(players)]
            df.to_csv(f"{address}/infamy.csv", sep=",", index=False)
            with open(f"{address}/infamy.txt", "w", encoding="utf-8") as file:
                file.write(f"{day}/{month}/{year}\n")
                file.write(df.to_string())
        print(f"Finished checking infamy on {day}/{month}/{year}")
        return df