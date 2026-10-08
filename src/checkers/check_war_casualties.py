import pandas as pd

from src.checkers.check_base import Checker
from src.checkers.checkers_functions import get_country_name
from src.helpers.utility import retrieve_from_tree

# ---------------------------------------------------------------------------
# War casualties
# ---------------------------------------------------------------------------
# The save keeps casualties per diplomatic play and participating country:
# ``diplomatic_plays.database.<id>.casualties.indexN`` carries, for one country, the
# maps ``{casualties,wounded}_from_{battles,attrition}_by_{culture,front}``.
#
# Two things the save does not say, both read off the game binary
# (CDiplomaticPlay::AddCasualties / GetTotalDead):
#   - "casualties" is the TOTAL taken: wounded are a subset of it, so
#     dead = casualties - wounded (GetTotalDead sums the casualty maps and subtracts
#     the wounded maps).
#   - the stored counts are whole individuals (``long long``) that the melter prints
#     divided by 100000. The same pattern as ``loyalists_and_radicals`` in pops; the
#     magnitude confirms it (Mexico, 1894: 1.07033 battle casualties is 107,033 men
#     against an army of ~105,000, where 1,070 would be fewer than one battle costs).
#
# The record lives only as long as the play. An ended war leaves nothing in the save,
# so one save shows the casualties of the wars still running. Totals over a campaign
# are built across saves by ``plot_cumulative_stat``, which is why this file keeps one
# row per (war, country) instead of one per country.
CASUALTY_SCALE = 100000

war_casualty_columns = ["war_casualties", "war_dead"]

# Kept in the CSV, not plotted on their own.
_war_extra_columns = ["war_wounded", "war_battle_casualties", "war_attrition_casualties"]


def _count(record, key):
    """Individuals in one ``{culture or front id: fixed-point count}`` map."""
    values = record.get(key)
    if not isinstance(values, dict):
        return 0
    return sum(round(float(v) * CASUALTY_SCALE) for v in values.values())


class CheckWarCasualties(Checker):
    """
    Casualties each country has taken in the wars still running at the save date,
    one row per (war, country).
    """

    name = "CheckWarCasualties"
    display_name = "War casualties"
    sort_order = 45
    requirements = ["diplomatic_plays", "country_manager"]
    output = {"war_casualties.csv": war_casualty_columns}
    # A row of war_casualties.csv is a (war, country) pair. The plotter sums the rows
    # of a country across saves, so it must not be handed one row per country.
    row_grain = {"war_casualties.csv": "war"}
    column_labels = {"war_casualties": "Casualties (dead and wounded)",
                     "war_dead": "Dead"}

    def __init__(self):
        super().__init__()

    def execute_check(self, cache: dict):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        countries = save_data["country_manager"]["database"]
        plays = retrieve_from_tree(save_data, ["diplomatic_plays", "database"], null={})

        rows = []
        for play_id, play in plays.items():
            if not isinstance(play, dict):
                continue
            for record in retrieve_from_tree(play, ["casualties"], null={}).values():
                country_id = record.get("country")
                country = retrieve_from_tree(countries, [country_id], null=None)
                if not isinstance(country, dict):
                    continue
                battles = _count(record, "casualties_from_battles_by_culture")
                attrition = _count(record, "casualties_from_attrition_by_culture")
                wounded = (_count(record, "wounded_from_battles_by_culture")
                           + _count(record, "wounded_from_attrition_by_culture"))
                rows.append({
                    "id": country_id,
                    "tag": country["definition"],
                    "country": get_country_name(country, localization),
                    "play_id": play_id,
                    "war_type": play.get("type", ""),
                    "start_date": play.get("start_date", ""),
                    "war_casualties": battles + attrition,
                    "war_dead": battles + attrition - wounded,
                    "war_wounded": wounded,
                    "war_battle_casualties": battles,
                    "war_attrition_casualties": attrition,
                })

        columns = ["id", "tag", "country", "play_id", "war_type", "start_date"] + \
                  war_casualty_columns + _war_extra_columns
        df = pd.DataFrame(rows).reindex(columns=columns)
        if not df.empty:
            df = df.sort_values(by="war_casualties", ascending=False)

        year, month, day = save_date
        df.to_csv(f"{address}/data/war_casualties.csv", sep=",", index=False)
        df_players = df[df["id"].astype(str).isin(players)]
        df_players.to_csv(f"{address}/war_casualties.csv", sep=",", index=False)
        with open(f"{address}/war_casualties.txt", "w", encoding="utf-8") as file:
            file.write(f"{day}/{month}/{year}\n")
            file.write(df_players.to_string())
        print(f"Finished checking war casualties on {day}/{month}/{year}")
        return df
