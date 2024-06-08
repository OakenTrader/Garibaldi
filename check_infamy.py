from utility import load
import pandas as pd

def check_infamy(address=None):
    """
    Retrieve infamy of player countries and countries with non-zero infamy
    """
    topics = ["player_manager", "country_manager"]
    data = load(topics, address)
    players, countries = [data[topic]["database"] for topic in topics]
    players = [v["country"] for k, v in players.items()]
    infamies = dict()
    for k, v in countries.items():
        if "definition" not in v:
            continue
        if "infamy" in v:
            infamies[k] = (v["definition"], v["infamy"])
        else:
            infamies[k] = (v["definition"], 0)

    vlist = []
    for k, v in infamies.items():
        if k in players or float(v[1]) > 0:
            vlist.append([v[0] ,float(v[1])])
    
    df = pd.DataFrame(vlist, columns=["country", "infamy"])
    df = df.sort_values(by='infamy', ascending=False)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df)
        """
        [ ] Print to a file 
        """