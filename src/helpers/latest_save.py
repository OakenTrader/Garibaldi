"""
Campaign-level exports taken from the latest save: its player CSVs, and a leaderboard.

Both land in ``saves/<campaign>/campaign_data/``, next to the plots, so the end state
of a campaign can be read without opening any save folder.
"""

import glob
import os
import shutil

import pandas as pd

from src.helpers.utility import iter_save_folders

# (player CSV in the save folder, its columns), in the order the leaderboard shows them.
LEADERBOARD_SOURCES = (
    ("tech_tree.csv", ("production_techs", "military_techs", "society_techs",
                       "total_techs", "researching")),
    ("finance.csv", ("GDP",)),
    ("demographics.csv", ("literacy", "standard of living")),
    ("construction.csv", ("construction",)),
    ("innovation.csv", ("innovation", "innovation cap")),
    ("prestige.csv", ("total",)),
)
# Source column -> leaderboard column, where the source name says too little on its own.
LEADERBOARD_RENAMES = {"construction": "construction points", "total": "prestige"}
LEADERBOARD_SORT = ["total_techs", "GDP"]  # GDP only breaks ties between equal tech counts


def latest_save_folder(campaign_folder, start_date=0, end_date=2024):
    """The save folder with the latest date in range. Raises ValueError when there is none."""
    saves = list(iter_save_folders(campaign_folder, start_date, end_date, need_metadata=False))
    if not saves:
        raise ValueError(f"No saves of {campaign_folder} in {start_date}-{end_date}")
    return max(saves, key=lambda save: save[1])[0]


def copy_player_stats(save_folder, destination):
    """Copy the player CSVs of one save (the ``*.csv`` directly in it) into ``destination``.

    The ``data/`` subfolder holds the same files for every country; those stay behind.
    Returns the copied file names.
    """
    os.makedirs(destination, exist_ok=True)
    names = []
    for path in sorted(glob.glob(f"{save_folder}/*.csv")):
        shutil.copy(path, destination)
        names.append(os.path.basename(path))
    return names


def build_leaderboard(save_folder):
    """One row per player country of the save, most technologies first.

    Raises ValueError when a source CSV is missing or lacks a column, e.g. a save checked
    before that column existed.
    """
    leaderboard = None
    for file, columns in LEADERBOARD_SOURCES:
        path = f"{save_folder}/{file}"
        if not os.path.isfile(path):
            raise ValueError(f"No {file} at {save_folder}")
        # "None" is the text of an empty research slot, not a missing value.
        frame = pd.read_csv(path, keep_default_na=False, na_values=[""],
                            usecols=["id", *(["tag", "country"] if leaderboard is None else []), *columns])
        leaderboard = frame if leaderboard is None else leaderboard.merge(frame, on="id", how="left")
    leaderboard = leaderboard.sort_values(LEADERBOARD_SORT, ascending=False, kind="stable")
    columns = [column for _, columns in LEADERBOARD_SOURCES for column in columns]
    return leaderboard[["tag", "country", *columns]].rename(columns=LEADERBOARD_RENAMES)


def export_latest_save(campaign_folder, start_date=0, end_date=2024):
    """Copy the latest save's player CSVs to campaign_data/ and write leaderboard.csv there.

    The copy goes first, so a save missing one leaderboard source still delivers its files.
    """
    save_folder = latest_save_folder(campaign_folder, start_date, end_date)
    destination = f"saves/{campaign_folder}/campaign_data"
    names = copy_player_stats(save_folder, destination)
    print(f"Copied {len(names)} player CSVs from {save_folder} to {destination}")
    build_leaderboard(save_folder).to_csv(f"{destination}/leaderboard.csv", index=False)
    print(f"Wrote {destination}/leaderboard.csv from {save_folder}")
