import pandas as pd
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import get_country_name
from src.helpers.utility import *

class CheckInfamy(Checker):
    """
    Retrieve infamy of player countries and countries with non-zero infamy
    """
    name = "CheckInfamy"
    display_name = "Infamy"
    sort_order = 90
    requirements = ["country_manager"]
    output = {"infamy.csv": ["infamy"]}
    
    def __init__(self):
        super().__init__()

    def on_country(self, country_id, country, cache):
        if "definition" not in country:
            return None
        return [country_id, country["definition"],
                get_country_name(country, cache["localization"]),
                float(country.get("infamy", 0))]

    def execute_check(self, cache):
        save_date = cache["metadata"]["save_date"]
        players = players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        df = pd.DataFrame(cache["country_rows"][self.name],
                          columns=["id", "tag", "country", "infamy"])
        df = df.sort_values(by='infamy', ascending=False)
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df.to_csv(f"{address}/data/infamy.csv", sep=",", index=False)
            df_players = df[df["id"].isin(players)]
            df_players.to_csv(f"{address}/infamy.csv", sep=",", index=False)
            with open(f"{address}/infamy.txt", "w", encoding="utf-8") as file:
                file.write(f"{day}/{month}/{year}\n")
                file.write(df_players.to_string())
        print(f"Finished checking infamy on {day}/{month}/{year}")
        return df