import json
import pandas as pd

def check_infamy():
    with open("./save files/save_output_player_manager.json") as file:
        players = json.load(file)["database"]
        players = [v["country"] for k, v in players.items()]

    with open("./save files/save_output_country_manager.json") as file:
        countries = json.load(file)["database"]

    infamies = dict()
    for k, v in countries.items():
        if "definition" in v:
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

if __name__ == "__main__":
    check_infamy()