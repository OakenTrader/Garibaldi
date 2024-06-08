from utility import load
import pandas as pd
from convert_localization import get_all_localization

def check_infamy(address=None):
    """
    Retrieve infamy of player countries and countries with non-zero infamy
    """
    localization = get_all_localization()
    topics = ["player_manager", "country_manager"]
    data = load(topics, address)
    players, countries = [data[topic]["database"] for topic in topics]
    players = [v["country"] for k, v in players.items()]
    infamies = dict()
    for k, country in countries.items():
        if "definition" not in country:
            continue
        tag = country["definition"]
        if tag in localization:
            country_name = localization[tag]
        else:
            country_name = tag
        if "infamy" in country:
            infamies[k] = (tag, country_name, country["infamy"])
        else:
            infamies[k] = (tag, country_name, 0)

    vlist = []
    for k, v in infamies.items():
        if k in players or float(v[2]) > 0:
            vlist.append([v[0] , v[1], float(v[2])])
    
    df = pd.DataFrame(vlist, columns=["tag", "country", "infamy"])
    df = df.sort_values(by='infamy', ascending=False)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df)
        df.to_csv(f"{address}/infamy.csv", sep=",", index=False)
        with open(f"{address}/infamy.txt", "w") as file:
            file.write(df.to_string())
    return df