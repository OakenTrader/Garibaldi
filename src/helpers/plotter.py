"""
Functions that manage data plotting.
"""

import os, warnings, time
from src.helpers.utility import *
from matplotlib.figure import Figure
from random import randint
from matplotlib import colors as mpl_colors
import numpy as np
import pandas as pd

"""
Figures are built with the object-oriented ``Figure`` API rather than pyplot.
pyplot keeps every figure alive in a global registry and binds a GUI backend at
import time; embedding those in a Qt canvas leaks figures and fights the backend.
A bare ``Figure`` can be handed straight to ``FigureCanvasQTAgg``, saved
headlessly, or thrown away — which is what lets one plotting function serve batch
rendering, interactive display and save-as alike.
"""

DEFAULT_FIGSIZE = (20, 10)


def label_figure(figure, name, suffix=None):
    """Tag a figure with what it depicts and the filename stem it is saved under.

    ``plot_company_stat`` emits a variable number of figures — bands with no
    companies are skipped — so position in the returned list identifies nothing.
    Callers that present or save a figure read these instead of counting.
    """
    figure.garibaldi_name = name
    figure.garibaldi_suffix = suffix
    return figure

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

def interpolate_missing(series):
    """
    Repair MISSING (NaN) values in one country's ``[[year, value], ...]`` time
    series, using neighboring saves. This is the "manager outside the checking
    logic" of proposal 02: checkers emit NaN for a statistic that is absent or
    undefined for a given save, and this fills those in across the campaign.

    - Interior gaps (a NaN bracketed by known saves) are linearly interpolated
      weighted by the actual save date (the year index).
    - Leading / trailing gaps (no known neighbor on one side) are hold-filled from
      the nearest known value so the line spans its full date range.
    - A series with no known value at all is returned unchanged (all-NaN -> the
      country simply won't plot; nothing is fabricated).
    """
    arr = np.asarray(series, dtype=float)
    if arr.size == 0:
        return series
    years, values = arr[:, 0], arr[:, 1]
    s = pd.Series(values, index=years).sort_index()
    if s.notna().any():
        # interpolate(method="index") fills interior NaNs by date; ffill/bfill then
        # hold-fills the ends that interpolation cannot reach.
        s = s.interpolate(method="index").ffill().bfill()
    return [[year, value] for year, value in zip(s.index, s.values)]


def plot_stat(campaign_folder, mode, input_file=None, limit=10, players=True, title=None, save=True, save_name=None, start_date=0, end_date=2024, figsize=DEFAULT_FIGSIZE):
    """
    Plot a variable over the campaign

    campaign_folder: The address of the folder containing the campaign's saves
    mode: The variable you want to plot
    input_file: The address of the file you draw the data from (mode.csv by default)
    title: Title of the plot
    limit: Int (Limit to first N places in the last save)
    players: Whether to include all players in the plot
    save: Whether to write the figure to campaign_data/ (off for interactive use)
    save_name: the file name of the plot image
    start_date: The starting year in which save files are included in the plot
    end_date: The ending year in which save files are included in the plot
    figsize: Figure size in inches; the GUI passes a canvas-sized value

    Returns the Figure. Nothing is displayed — the caller decides whether to embed
    it, save it, or discard it.
    """
    if title is None:
        title = mode
    if save_name is None:
        save_name = title
    if input_file is None:
        input_file = f"{mode}.csv"
    img_folder = input_file.replace(".csv", "")
    if save:
        os.makedirs(f"saves/{campaign_folder}/campaign_data/{img_folder}", exist_ok=True)

    set_player_list, set_ai_list = campaign_tag_filters(campaign_folder)

    t0 = time.time()
    last_save = None
    dfs = dict()
    was_player = set()
    current_year = 0
    for save_folder, year_number, metadata in iter_save_folders(campaign_folder, start_date, end_date):
        if input_file not in os.listdir(save_folder):
            print(f"No {input_file} at {save_folder}")
            continue
        df_stat = pd.read_csv(f"{save_folder}/{input_file}")
        if set_player_list:
            player_list = set_player_list + set_ai_list
            df_players = df_stat[df_stat["tag"].isin(player_list)]
            was_player.update([(player["tag"], player["country"]) for _, player in df_players.reset_index().iterrows()])
            df_stat = df_stat[df_stat["tag"].isin(player_list)]
        elif players:
            player_list = [v[1] for v in metadata["players"]] + set_ai_list
            df_players = df_stat[df_stat["tag"].isin(player_list)]
            was_player.update([(player["tag"], player["country"]) for _, player in df_players.reset_index().iterrows()])
            df_stat = df_stat[df_stat["tag"].isin(player_list)]
        elif limit and isinstance(limit, int):
            df_stat = df_stat.sort_values(by=mode, ascending=False)
            df_stat = df_stat.iloc[:limit]
        elif limit:
            raise KeyError(f"Expected limit argument in integers, received {limit}")
        dfs[year_number] = df_stat
    if not dfs:
        raise ValueError(f"No {input_file} data to plot for {campaign_folder} in {start_date}-{end_date}")
    current_year = max(dfs.keys())
    # Plotting
    fig = Figure(figsize=figsize)
    ax = fig.add_subplot(111)
    countries = dict()
    for year in sorted(dfs.keys()): # Get ascending order date
        df = dfs[year]
        for row in range(len(df)):
            country = (df.iloc[row]["tag"], df.iloc[row]["country"])
            if country not in countries:
                countries[country] = []
            countries[country].append([year, df.iloc[row][mode]])

    # Repair statistics the checkers marked MISSING (NaN) for individual saves by
    # interpolating each country's series across neighboring saves before plotting.
    for name in countries:
        countries[name] = interpolate_missing(countries[name])

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
    fig.subplots_adjust(right=0.75)
    label_figure(fig, title, save_name)
    if save:
        fig.savefig(f"saves/{campaign_folder}/campaign_data/{img_folder}/{save_name}.png")
    print(f"Finished plotting {mode} in {time.time() - t0} seconds")
    return fig

# Level bands the company plots are split into, so a few giant companies don't flatten
# the rest. Each company is classified by its levels in its latest save; the plot for a
# band draws that band's companies in full, and (on the two lower bands) the larger
# companies faded and behind for context. Each tuple:
#   (filename suffix, title fragment, in_band(levels), in_background(levels) | None,
#    upper level threshold | None)
# The upper threshold caps the y-axis on the ``levels`` plots (whose y is levels), so a
# band fills exactly up to its boundary; it is dimensionless for the other metrics and
# ignored there.
COMPANY_LEVEL_BANDS = [
    ("above_1000", "above 1000 levels", lambda L: L > 1000, None, None),
    ("100_1000", "100-1000 levels", lambda L: 100 <= L <= 1000, lambda L: L > 1000, 1000),
    ("below_100", "below 100 levels", lambda L: L < 100, lambda L: L >= 100, 100),
]


def plot_company_stat(campaign_folder, mode, input_file="companies.csv", limit=10, players=True, title=None, save=True, save_name=None, start_date=0, end_date=2024, top_n=30, figsize=DEFAULT_FIGSIZE):
    """
    Plot a per-company variable (levels / productivity / profit) over the campaign,
    split into three plots by company size so that a handful of giant companies don't
    flatten everyone else: **above 1000 levels**, **100-1000 levels**, and **below 100
    levels**. A company is placed by its levels in its latest save (the ``levels``
    column, regardless of which ``mode`` is plotted).

    Also emits a ``_top{top_n}`` leaderboard plot of the ``top_n`` companies with the
    highest latest ``mode`` value. Ranking by the plotted metric means the levels /
    productivity / profit leaderboards list different companies — the biggest companies
    are not necessarily the most productive or profitable.

    On the two lower plots the larger companies are still drawn for context — faded,
    behind the band's own lines, and left off the legend. Each plot's y-axis is scaled
    to its own band's companies, so those faded context lines simply run off the top as
    they outgrow the band (rather than squashing the band's lines flat).

    A sibling of ``plot_stat``. Where ``plot_stat`` identifies each line by a country
    (tag, country name), a company cannot be identified that way: a country owns
    several companies and a company_type recurs across countries. Each line here is a
    single company, identified by ``(tag, company_type)`` — unique per save since the
    game allows only one instance of each company_type per country.

    Lines are coloured by the owning country (``get_color(tag)``); when one country
    owns several companies their lines share a colour and are separated by line style.
    Legend labels read ``"<name> (<country>)"`` where ``<name>`` is the company's
    custom in-game name when set, else the localised company_type name.

    ``limit`` caps how many foreground companies each band lists (top by the latest
    value of ``mode``) when not plotting a players-only view, keeping legends legible;
    the faded background lines are never capped. Other arguments mirror ``plot_stat``.
    """
    if title is None:
        title = mode
    if save_name is None:
        save_name = title
    img_folder = input_file.replace(".csv", "")
    if save:
        os.makedirs(f"saves/{campaign_folder}/campaign_data/{img_folder}", exist_ok=True)

    set_player_list, set_ai_list = campaign_tag_filters(campaign_folder)

    t0 = time.time()
    dfs = dict()
    for save_folder, year_number, metadata in iter_save_folders(campaign_folder, start_date, end_date):
        if input_file not in os.listdir(save_folder):
            print(f"No {input_file} at {save_folder}")
            continue
        df_stat = pd.read_csv(f"{save_folder}/{input_file}")
        # Player filtering keeps companies whose OWNING country tag is a player.
        # Without it, every company is kept — the level bands (not a top-N cut) are
        # what keep each plot legible.
        if set_player_list:
            df_stat = df_stat[df_stat["tag"].isin(set_player_list + set_ai_list)]
        elif players:
            df_stat = df_stat[df_stat["tag"].isin([v[1] for v in metadata["players"]] + set_ai_list)]
        dfs[year_number] = df_stat
    if not dfs:
        print(f"No {input_file} data to plot for {campaign_folder}")
        return []

    # Build each company's [[year, value], ...] series keyed by (tag, company_type),
    # tracking its latest display name/country (legend) and latest levels (band).
    series = dict()
    label_info = dict()
    latest_levels = dict()
    for year in sorted(dfs.keys()):
        df = dfs[year]
        for row in range(len(df)):
            r = df.iloc[row]
            identity = (r["tag"], r["company_type"])
            series.setdefault(identity, []).append([year, r[mode]])
            label_info[identity] = (r["company_name"], r["country"])
            try:
                latest_levels[identity] = float(r["levels"])
            except (TypeError, ValueError):
                latest_levels[identity] = 0.0

    for identity in series:
        series[identity] = interpolate_missing(series[identity])

    def latest_value(identity):
        v = series[identity][-1][1] if series[identity] else 0.0
        return v if v == v else float("-inf")  # push NaN to the bottom of the sort

    linestyles = ["-", "--", ":", "-."]

    def draw_companies(ax, identities):
        """Plot each company coloured by its owning country, distinguishing a country's
        several companies by line style and labelling each ``"<name> (<country>)"``.
        Returns every plotted (non-NaN) y-value, for axis scaling."""
        tag_seen = dict()
        values = []
        for identity in identities:
            tag = identity[0]
            idx = tag_seen.get(tag, 0)
            tag_seen[tag] = idx + 1
            style = linestyles[idx % len(linestyles)]
            name, country = label_info[identity]
            arr = np.stack(series[identity])
            values.extend(v for v in arr[:, 1] if v == v)
            ax.plot(arr[:, 0], arr[:, 1], label=f"{name} ({country})", color=get_color(tag), linewidth=3, linestyle=style, zorder=2)
        return values

    def finish(fig, ax, band_title, out_suffix):
        ax.legend(loc='upper left', bbox_to_anchor=(1.05, 1))
        ax.set_title(f"{title} graph over the years ({band_title})")
        ax.grid(True)
        fig.subplots_adjust(right=0.75)
        # Label the figure with the band it belongs to. Bands with no companies are
        # skipped, so a caller cannot infer which band a figure is from its position
        # in the returned list.
        label_figure(fig, band_title, out_suffix)
        if save:
            fig.savefig(f"saves/{campaign_folder}/campaign_data/{img_folder}/{save_name}_{out_suffix}.png")

    # Only cap foreground legends when showing the whole field (not a players view).
    cap = None if (set_player_list or players) else (limit if isinstance(limit, int) and limit else None)
    figs = []
    for suffix, band_title, in_band, in_background, upper_threshold in COMPANY_LEVEL_BANDS:
        foreground = sorted((i for i in series if in_band(latest_levels.get(i, 0.0))),
                            key=latest_value, reverse=True)
        if not foreground:
            continue
        if cap is not None:
            foreground = foreground[:cap]
        background = [i for i in series if in_background and in_background(latest_levels.get(i, 0.0))]

        fig = Figure(figsize=figsize)
        ax = fig.add_subplot(111)
        # Context first: larger companies faded and behind, no legend entry.
        for identity in background:
            arr = np.stack(series[identity])
            ax.plot(arr[:, 0], arr[:, 1], color=get_color(identity[0]), linewidth=1.5, alpha=0.15, zorder=1)
        # Band's own companies on top.
        fg_values = draw_companies(ax, foreground)

        # Scale the y-axis to the band's own companies so faded context lines that grow
        # past the band clip off the top instead of squashing everything flat. On the
        # levels plot the y-axis is the level count itself, so cap the top at the band's
        # level threshold (1000 / 100) for a clean band-height boundary.
        if fg_values:
            lo, hi = min(fg_values), max(fg_values)
            pad = (hi - lo) * 0.05 or abs(hi) * 0.05 or 1.0
            top = upper_threshold if (mode == "levels" and upper_threshold is not None) else hi + pad
            ax.set_ylim(lo - pad, top)

        finish(fig, ax, band_title, suffix)
        figs.append(fig)

    # Leaderboard: the top_n companies by their latest value of the plotted metric.
    # Ranking by mode means the levels / productivity / profit boards differ.
    if top_n:
        leaders = sorted(series, key=latest_value, reverse=True)[:top_n]
        if leaders:
            fig = Figure(figsize=figsize)
            ax = fig.add_subplot(111)
            draw_companies(ax, leaders)
            finish(fig, ax, f"top {len(leaders)}", f"top{top_n}")
            figs.append(fig)

    print(f"Finished plotting company {mode} in {time.time() - t0} seconds")
    return figs

# Columns that name a row rather than measure it, in any checker output.
IDENTITY_COLUMNS = ("", "id", "tag", "country", "company_name", "company_type")


def csv_value_columns(campaign_folder, filename):
    """The measurable columns a campaign's copy of ``filename`` actually has.

    For outputs whose columns cannot be declared up front — the goods a mod
    defines, the income and expense slots a game version uses — the campaign's own
    CSV header is the only honest source. Returns [] when no save has that file.
    """
    for save_folder, _, _ in iter_save_folders(campaign_folder, need_metadata=False):
        path = f"{save_folder}/{filename}"
        if os.path.isfile(path):
            columns = list(pd.read_csv(path, nrows=0).columns)
            # The saved index column comes back as "Unnamed: 0".
            return [c for c in columns
                    if c not in IDENTITY_COLUMNS and not c.startswith("Unnamed:")]
    return []


def goods_in_campaign(campaign_folder):
    """The goods this campaign recorded, falling back to the game defines."""
    return csv_value_columns(campaign_folder, "goods_produced.csv") or \
        list(load_def_multiple("goods", "Common Directory").keys())


def plot_file_columns(campaign_folder, key, input_file, limit=10, save=True,
                      start_date=0, end_date=2024, figsize=DEFAULT_FIGSIZE):
    """Plot every column of an output whose columns the campaign decides.

    For a declared key naming a file rather than one of its columns: ``goods_produced``
    renders one figure per good. Columns come from the campaign's CSV header, and the
    images are numbered in header order.
    """
    figs = []
    for i, column in enumerate(csv_value_columns(campaign_folder, input_file)):
        figs.append(plot_stat(campaign_folder, column, input_file=input_file, limit=limit,
                              players=True, title=column, save_name=f"{key}_{i + 1}_{column}",
                              save=save, start_date=start_date, end_date=end_date, figsize=figsize))
    return figs