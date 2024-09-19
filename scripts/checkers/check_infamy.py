import pandas as pd
from scripts.checkers.check_base import Checker
from scripts.checkers.checkers_functions import get_country_name
from scripts.helpers.utility import *

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
        players = cache["metadata"]["players"]
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

        vlist = []
        for k, v in infamies.items():
            if k in players or float(v[2]) > 0:
                vlist.append([k, v[0] , v[1], float(v[2])])
        
        df = pd.DataFrame(vlist, columns=["id", "tag", "country", "infamy"])
        df = df.sort_values(by='infamy', ascending=False)
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df.to_csv(f"{address}/infamy.csv", sep=",", index=False)
            with open(f"{address}/infamy.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                file.write(df.to_string())
        print(f"Finished checking infamy on {day}/{month}/{year}")
        return df