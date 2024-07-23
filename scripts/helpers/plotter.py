"""
Functions that manage data plotting.
"""

import os, warnings
from scripts.helpers.utility import *
import matplotlib.pyplot as plt
from matplotlib import colors as mpl_colors
import numpy as np
import pandas as pd

# plt.rcParams.update({
#     'axes.facecolor': [0.1, 0.1, .1, 1],
#     'axes.edgecolor': 'white',
#     'axes.labelcolor': 'white',
#     'figure.facecolor': 'black',
#     'grid.color': 'gray',
#     'text.color': 'white',
#     'xtick.color': 'white',
#     'ytick.color': 'white',
#     'legend.facecolor': 'black',
#     'legend.edgecolor': 'white',
#     'lines.color': 'white',
#     'patch.edgecolor': 'white',
#     'savefig.facecolor': 'black',
#     'savefig.edgecolor': 'black'
# })

def get_color(tag):
    """
    Get a color of a tag (three letters defining a country) and its format
    """
    def_countries = load_def_multiple("country_definitions", "Common Directory")
    try:
        color = def_countries[tag]["color"]
    except KeyError:
        color = {"field_type":"hsv360", "value":[np.random.randint(360), 100, 50]}
        warnings.warn(f"No color provided for {tag}, used hsv360 {color['value']}")
        # raise KeyError(f"No color provided for {tag}")

    color_type = color["field_type"]
    if color_type == "list":
        color_type = "rgb"
        if any([float(v) > 0 for v in color["value"]]):
            colors = [float(v) / 255 for v in color["value"]]
        else:
            colors = [float(v) for v in color["value"]]
    elif color_type == "hsv":
        colors = mpl_colors.hsv_to_rgb([float(v) for v in color["value"]])
    elif color_type == "hsv360":
        colors = [float(v) for v in color["value"]]
        colors = mpl_colors.hsv_to_rgb([colors[0]/360, colors[1]/100, colors[2]/100])
        # print(f"hsv360 {color} -> {colors}")
    else:
        raise NotImplementedError(f"Currently supported only rgb and hsv360 values. Received {color_type} from {tag}")
    if any([v > 1 for v in colors]):
        raise ValueError(f"Value Error, got {color} from {tag} resulting in {colors}")
    colors = np.concatenate([colors, [1]])
    return np.array(colors)

def plot_stat(campaign_folder, mode, checker=None, input_file=None, reset=False, limit=10, players=True, title=None, show=False, save_name=None, start_date=0):
    """
    Plot a variable over the campaign
    
    campaign_folder: The address of the folder containing the campaign's saves
    mode: The variable you want to plot
    checker: The checker function which to retrieve said variable if there is no existing output
    reset: Whether or not to run the checker regardless of the output's existence, overwriting it
    title: Title of the plot
    limit: Int (Limit to first N places in the last save)
    players: Whether to include all players in the plot
    save_name = the file name of the plot image
    start_date = The starting year in which save files are included in the plot
    """
    if title is None:
        title = mode
    if save_name is None:
        save_name = title
    dfs = dict()
    if input_file is None:
        input_file = f"{mode}.csv"
    last_save = None
    for folder in os.listdir(f"saves/{campaign_folder}"):
        save_folder = f"saves/{campaign_folder}/{folder}"
        if os.path.isdir(save_folder) and "campaign_data" not in folder:
            try:
                year, month, day = folder.split("_")[-3:]
            except ValueError:
                metadata = load_save(["meta_data"], save_folder, True)
                year, month, day = metadata["meta_data"]["game_date"].split(".")[:3]
            year_number = int(year) + (int(month) - 1) / 12 + int(day) / 30 # Simplified formula
            if year_number < start_date:
                continue
            if input_file not in os.listdir(save_folder) or reset:
                if checker is None:
                    raise ValueError("No checker provided.")
                df_stat = t_execute(checker)(save_folder)
                df_stat["id"] = df_stat["id"].astype(int)
            else:
                df_stat = pd.read_csv(f"{save_folder}/{input_file}")
            if limit and limit == "players":
                data = load_save(["player_manager"], save_folder)
                players = data["player_manager"]["database"]
                players = [int(v["country"]) for v in players.values()]
                df_stat = df_stat[df_stat["id"].isin(players)]
            elif limit and isinstance(limit, int):
                df_stat = df_stat.sort_values(by=mode, ascending=False)
                df_stat = df_stat.iloc[:limit]
            elif limit:
                raise KeyError(f"Expected limit argument in integers, received {limit}")
            dfs[year_number] = df_stat
    # Plotting
    fig, ax = plt.subplots(figsize=(20,10))
    countries = dict()
    for year in sorted(dfs.keys()):
        df = dfs[year]
        for row in range(len(df)):
            country = (df.iloc[row]["tag"], df.iloc[row]["country"])
            if country not in countries:
                countries[country] = []
            countries[country].append([year, df.iloc[row][mode]])

    last_save = dfs[sorted(dfs.keys(), reverse=True)[0]]
    last_save = last_save.sort_values(by=mode, ascending=False)
    for c in range(len(last_save)):
        row_c = last_save.iloc[c]
        name = (row_c["tag"], row_c["country"])
        country = countries[name]
        country_color = get_color(name[0])
        if "Revolutionary" in name[1]:
            country_color[-1] *= 0.7
        df = np.stack(country)
        ax.plot(df[:, 0], df[:, 1], label=name[1], color=country_color, linewidth=3.5)
        ax.plot(df[:, 0], df[:, 1], linestyle="--", color="black", linewidth=1)
    ax.legend(loc='upper left', bbox_to_anchor=(1.05, 1))
    ax.set_title(f"{title} graph over the years")
    ax.grid(True)
    # plt.tight_layout()
    plt.subplots_adjust(right=0.75)
    plt.savefig(f"saves/{campaign_folder}/campaign_data/{save_name}.png")
    if show:
        plt.show()
    return fig

def plot_goods_produced(campaign_folder, limit=10):
    """
    Plot all goods produced in a campaign
    """
    goods = load_def_multiple("goods", "Common Directory")
    for i, good in enumerate(goods.keys()):
        plot_stat(campaign_folder, good, checker=None, input_file="goods_produced.csv", reset=False, limit=limit, title=good, save_name=f"goods_produced_{i + 1}_{good}")