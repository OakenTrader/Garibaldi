import os
from scripts.helpers.utility import load_save
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def plot_stat(campaign_folder, mode, checker=None, input_file=None, reset=False, player_only=False):
    """
    Plot a variable over the campaign
    
    campaign_folder: The address of the folder containing the campaign's saves
    mode: The variable you want to plot
    checker: The checker function which to retrieve said variable if there is no existing output
    reset: Whether or not to run the checker regardless of the output's existence, overwriting it
    player_only: Whether or not to only include players in the plot 
    """
    dfs = dict()
    if input_file is None:
        input_file = f"{mode}.csv"
    for folder in os.listdir(f"saves/{campaign_folder}"):
        save_folder = f"saves/{campaign_folder}/{folder}"
        if os.path.isdir(save_folder) and "campaign_data" not in folder:
            metadata = load_save(["meta_data"], save_folder, True)
            year, month, day = metadata["meta_data"]["game_date"].split(".")
            year_number = int(year) + (int(month) - 1) / 12 + int(day) / 30 # Simplified formula
            if input_file not in os.listdir(save_folder) or reset:
                if checker is None:
                    raise ValueError("No checker provided.")
                df_stat = checker(save_folder, player_only=player_only)
            else:
                df_stat = pd.read_csv(f"{save_folder}/{input_file}")
            dfs[year_number] = df_stat
    fig, ax = plt.subplots()
    countries = dict()
    for year, df in dfs.items():
        for row in range(len(df)):
            country = df.iloc[row]["country"]
            if country not in countries:
                countries[country] = []
            countries[country].append([year, df.iloc[row][mode]])
    for name, country in countries.items():
        df = np.stack(country)
        ax.plot(df[:, 0], df[:, 1], label=name)
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
    ax.set_title(f"{mode} graph over the years")
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(f"saves/{campaign_folder}/campaign_data/{mode}.png")
    plt.show()