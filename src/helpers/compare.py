"""
Statistics that only exist across saves.

A checker describes one save. A growth rate compares a save with the one a year
before it, so no single save can produce it: it is derived from the CSVs the
checkers already wrote, one save after another. This module is that layer. It reads
a column over a campaign (``collect_series``), turns the series into something else
(``annual_growth``) and describes what a checker offers that way (``Growth``).
It holds no plotting code, so the arithmetic can be tested without a figure.

A checker offers a derived statistic by listing it in its ``comparisons``; the
statistics tree, the batch pass and the interactive plot all read that list.
"""

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.helpers.utility import campaign_tag_filters, iter_save_folders

# ``save_year_number`` builds each date as a float from year, month and day, so two
# dates exactly a year apart can differ in the last bits. This is the width inside
# which two dates are the same date.
DATE_TOLERANCE = 1e-6


def annual_growth(points, max_gap=1.0):
    """
    Year-over-year growth of one ``[[year, value], ...]`` series, in percent.

    Every point is compared with the value one year before it. Saves are not evenly
    spaced — monthly for a while, quarterly later, sometimes nothing for decades —
    so the earlier value is read off the saves around that date: taken as is when a
    save sits on it, interpolated linearly when the two saves around it are at most
    ``max_gap`` years apart, and missing otherwise. A point with no earlier value
    gets no growth and is left out; nothing is stretched across a stretch with no
    saves.

    NaN and non-positive values are dropped before anything else. A ratio with them
    means nothing, and when one falls on a reference date its neighbours stand in
    for it.

    Returns ``[[year, percent], ...]`` for the points that have a growth, oldest first.
    """
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    points = points[np.isfinite(points[:, 1]) & (points[:, 1] > 0)]
    points = points[np.argsort(points[:, 0], kind="stable")]
    years, values = points[:, 0], points[:, 1]

    growth = []
    for year, value in zip(years, values):
        target = year - 1.0
        # First save on or after the reference date.
        after = int(np.searchsorted(years, target - DATE_TOLERANCE))
        if abs(years[after] - target) <= DATE_TOLERANCE:
            earlier = values[after]
        else:
            before = after - 1
            if before < 0 or years[after] - years[before] > max_gap + DATE_TOLERANCE:
                continue
            share = (target - years[before]) / (years[after] - years[before])
            earlier = values[before] + share * (values[after] - values[before])
        growth.append([year, (value / earlier - 1.0) * 100.0])
    return growth


def break_at_gaps(points, max_gap=1.0):
    """
    ``points`` with a NaN point put between neighbours more than ``max_gap`` apart.

    A line drawn through consecutive points would cross a stretch with no saves as
    if it had been measured; the NaN makes it stop there and start again.
    """
    out = []
    for point in points:
        if out and point[0] - out[-1][0] > max_gap + DATE_TOLERANCE:
            out.append([(out[-1][0] + point[0]) / 2, float("nan")])
        out.append(point)
    return out


@dataclass(frozen=True)
class Growth:
    """
    A checker column shown as its year-over-year growth.

    key:        the name the statistic is selected, plotted and saved under
    input_file: the per-save CSV the level is read from
    column:     the level's column in that file
    label:      what the tree and the plot call it
    """
    key: str
    input_file: str
    column: str
    label: str
    unit = "%"

    def transform(self, points):
        return annual_growth(points)


def collect_series(campaign_folder, input_file, column, players=True, limit=10,
                   start_date=0, end_date=2024):
    """
    One column of one output file, followed across the saves of a campaign.

    Reads each save's ``data/{input_file}``, which holds every country, so a country
    has its whole history even in the saves where it was not a player. Countries are
    identified as ``plot_stat`` does, by ``(tag, country)``.

    players: True keeps every country that was a player in any save in range, plus the
        campaign's extra AI tags (or only the tags the campaign config names). False
        keeps the ``limit`` countries with the highest value in the latest save.

    Returns ``{(tag, country): [[year, value], ...]}``, oldest first. A country shows
    up only in the saves that list it. Raises ValueError when no save has the file.
    """
    set_player_list, set_ai_list = campaign_tag_filters(campaign_folder)

    frames = dict()
    player_tags = set()
    for save_folder, year_number, metadata in iter_save_folders(campaign_folder, start_date, end_date):
        path = f"{save_folder}/data/{input_file}"
        if not os.path.isfile(path):
            print(f"No {input_file} at {save_folder}")
            continue
        # A tag and name shared by two ids in one save would put two points on one
        # date. The files are sorted largest first, so the first is the one that counts.
        frames[year_number] = pd.read_csv(path, usecols=["tag", "country", column]) \
            .drop_duplicates(["tag", "country"])
        player_tags.update(player[1] for player in metadata["players"])
    if not frames:
        raise ValueError(f"No {input_file} data to compare for {campaign_folder} in {start_date}-{end_date}")

    series = dict()
    for year in sorted(frames):
        for tag, country, value in frames[year].itertuples(index=False):
            series.setdefault((tag, country), []).append([year, value])

    if set_player_list:
        chosen = [name for name in series if name[0] in set_player_list + set_ai_list]
    elif players:
        chosen = [name for name in series if name[0] in player_tags or name[0] in set_ai_list]
    else:
        latest = max(frames)
        ranked = frames[latest].sort_values(by=column, ascending=False)
        chosen = [(tag, country) for tag, country in zip(ranked["tag"], ranked["country"])][:limit]
    return {name: series[name] for name in chosen}
