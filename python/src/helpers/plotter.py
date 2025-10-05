"""
Functions that manage data plotting.
"""

import os, warnings, time
from src.helpers.utility import *
import matplotlib.pyplot as plt
from random import randint
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
    named_colors = load_def_multiple("named_colors", depth_add=1)["colors"]
    try:
        color = def_countries[tag]["color"]
        if isinstance(color, str) and color in named_colors:
            color = named_colors[color]
    except KeyError:
        color = {"field_type":"hsv360", "value":[randint(0, 359), 100, 50]}
        warnings.warn(f"No color provided for {tag}, used hsv360 {color['value']}")
        # raise KeyError(f"No color provided for {tag}")

    color_type = color["field_type"]
    if color_type == "list" or color_type == "rgb":
        color_type = "rgb"
        if any([float(v) > 0 for v in color["value"]]):
            colors = [float(v) / 255 for v in color["value"]]
        else:
            colors = [float(v) for v in color["value"]]
    elif color_type == "hsv":
        color_ = [float(v) for v in color["value"]]
        colors = mpl_colors.hsv_to_rgb([color_[0]/360, color_[1]/100, color_[2]/100])
        # colors = mpl_colors.hsv_to_rgb([float(v) for v in color["value"]])
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

def plot_stat(campaign_folder, mode, input_file=None, limit=10, players=True, title=None, show=False, save_name=None, start_date=0, end_date=2024):
    """
    Plot a variable over the campaign
    
    campaign_folder: The address of the folder containing the campaign's saves
    mode: The variable you want to plot
    input_file: The address of the file you draw the data from (mode.csv by default)
    title: Title of the plot
    limit: Int (Limit to first N places in the last save)
    players: Whether to include all players in the plot
    save_name: the file name of the plot image
    start_date: The starting year in which save files are included in the plot
    end_date: The ending year in which save files are included in the plot
    """
    if title is None:
        title = mode
    if save_name is None:
        save_name = title
    if input_file is None:
        input_file = f"{mode}.csv"
    if "campaign_data" not in os.listdir(f"saves/{campaign_folder}"):
        os.mkdir(f"saves/{campaign_folder}/campaign_data")
    img_folder = input_file.replace(".csv", "")
    if img_folder not in os.listdir(f"saves/{campaign_folder}/campaign_data"):
        os.mkdir(f"saves/{campaign_folder}/campaign_data/{img_folder}")

    t0 = time.time()
    last_save = None
    dfs = dict()
    was_player = set()
    current_year = 0
    for folder in os.listdir(f"saves/{campaign_folder}"):
        save_folder = f"saves/{campaign_folder}/{folder}"
        if os.path.isdir(save_folder) and not is_reserved_folder(folder):
            try:
                metadata = jopen(f"{save_folder}/metadata.json")
            except FileNotFoundError:
                metadata = None
            try:
                year, month, day = metadata["save_date"]
            except KeyError:
                metadata = load_save(["meta_data"], save_folder, True)
                year, month, day = metadata["meta_data"]["game_date"].split(".")[:3]
            year_number = int(year) + (int(month) - 1) / 12 + int(day) / (365) # Simplified formula
            if year_number < start_date or year_number > end_date + 1:
                continue
            if input_file not in os.listdir(save_folder):
                print(f"No file provided at {year}, {month}, {day}")
                continue
            else:
                df_stat = pd.read_csv(f"{save_folder}/{input_file}")
            if players:
                players = [v[0] for v in metadata["players"]]
                df_players = df_stat[df_stat["id"].isin(players)]
                was_player.update([(player["tag"], player["country"]) for _, player in df_players.reset_index().iterrows()])
                df_stat = df_stat[df_stat["id"].isin(players)]
            elif limit and isinstance(limit, int):
                df_stat = df_stat.sort_values(by=mode, ascending=False)
                df_stat = df_stat.iloc[:limit]
            elif limit:
                raise KeyError(f"Expected limit argument in integers, received {limit}")
            dfs[year_number] = df_stat
            current_year = year_number
    # Plotting
    fig, ax = plt.subplots(figsize=(20,10))
    countries = dict()
    for year in sorted(dfs.keys()): # Get ascending order date
        df = dfs[year]
        for row in range(len(df)):
            country = (df.iloc[row]["tag"], df.iloc[row]["country"])
            if country not in countries:
                countries[country] = []
            countries[country].append([year, df.iloc[row][mode]])

    last_save = dfs[current_year]
    last_save = last_save.sort_values(by=mode, ascending=False)
    plot_countries = dict()
    for c in range(len(last_save)):
        row_c = last_save.iloc[c]
        name = (row_c["tag"], row_c["country"])
        plot_countries[name] = countries[name]
        was_player.discard(name)
    for name in was_player:
        if name in countries:
            plot_countries[name] = countries[name]
    for name, country in plot_countries.items():
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
    plt.savefig(f"saves/{campaign_folder}/campaign_data/{img_folder}/{save_name}.png")
    print(f"Finished plotting {mode} in {time.time() - t0} seconds")
    if show:
        plt.show()
    plt.close()
    return fig

def plot_goods_produced(campaign_folder, limit=10, show=False):
    """
    Plot all goods produced in a campaign
    """
    goods = load_def_multiple("goods", "Common Directory")
    for i, good in enumerate(goods.keys()):
        plot_stat(campaign_folder, good, input_file="goods_produced.csv", limit=limit, players=True, title=good, save_name=f"goods_produced_{i + 1}_{good}", show=show)