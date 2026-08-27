import re
import pandas as pd

from src.checkers.check_base import Checker
from src.checkers.checkers_functions import get_country_name, safe_ratio, MISSING
from src.helpers.utility import retrieve_from_tree

# ---------------------------------------------------------------------------
# Company statistics
# ---------------------------------------------------------------------------
# Companies live in the save's ``companies.database`` map. Each entry carries an
# owning ``country`` id, a ``company_type`` (e.g. ``company_john_cockerill``) and a
# set of trend time-series. The three player-facing figures are the latest sample of
# a trend each:
#   levels       -> size_trend        (equal to the company HQ building's ``levels``)
#   productivity -> productivity_trend
#   profit       -> profit_trend
# Individual companies are named by the player's custom in-game name when one exists,
# otherwise by the localization of the company_type (see ``resolve_company_name``).
#
# ``company_columns`` are the per-company metrics plotted individually (via
# ``plot_company_stat``); ``company_country_columns`` are the per-country rollups
# plotted with the ordinary ``plot_stat``. Both lists are imported by manager.py.
company_columns = ["levels", "productivity", "profit"]
company_country_columns = ["company_levels", "company_productivity", "company_profit", "company_count"]

# Extra per-company columns kept in the CSV but not plotted on their own.
_company_extra_columns = ["prosperity"]

_INDEX_KEY = re.compile(r"index\d+$")


def resolve_company_name(company, localization):
    """
    Return a company's display name.

    A player-given ``custom_name`` takes precedence. The save extractor splits a
    quoted multi-word custom name on whitespace: the first token stays in
    ``custom_name`` and the remaining tokens become contiguous ``indexN`` string keys
    immediately following it in the entry (e.g. ``custom_name='The'`` +
    ``index5='Dutch'`` + ``index6='Hate'`` + ``index7='Club'`` -> "The Dutch Hate
    Club"). We stitch the name back together by joining ``custom_name`` with that run
    of ``indexN`` keys.

    With no custom name, fall back to the localization of the ``company_type``
    (e.g. ``company_john_cockerill`` -> "Société anonyme John Cockerill"), and finally
    to the raw ``company_type`` string if it is unlocalized.
    """
    keys = list(company.keys())
    if "custom_name" in company and isinstance(company["custom_name"], str):
        i = keys.index("custom_name")
        parts = [company["custom_name"]]
        j = i + 1
        while j < len(keys) and _INDEX_KEY.match(keys[j]) and isinstance(company[keys[j]], str):
            parts.append(company[keys[j]])
            j += 1
        name = " ".join(p for p in parts if p)
        if name:
            return name
    company_type = company.get("company_type", "")
    return localization.get(company_type, company_type)


def trend_last(company, trend_key):
    """
    Latest sample of one of a company's trend series (0.0 if unavailable), read from
    ``[trend_key, "channels", "0", "values", "value"]`` — the same time-series shape
    the finance checker's ``_current_prestige`` reads.
    """
    series = retrieve_from_tree(company, [trend_key, "channels", "0", "values", "value"], null=None)
    if isinstance(series, list) and series:
        try:
            return float(series[-1])
        except (TypeError, ValueError):
            return 0.0
    return 0.0


class CheckCompanies(Checker):
    """
    Per-company economic figures (levels, productivity, profit) and their per-country
    rollups (total levels, level-weighted average productivity, total profits, count).
    """

    name = "CheckCompanies"
    display_name = "Companies"
    sort_order = 40
    requirements = ["companies", "country_manager"]
    output = {"companies.csv": company_columns,
              "company_countries.csv": company_country_columns}
    # A row of companies.csv is a company; company_countries.csv is per country.
    row_grain = {"companies.csv": "company"}
    dependencies = []

    def __init__(self):
        super().__init__()

    def execute_check(self, cache: dict):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        countries = save_data["country_manager"]["database"]
        companies = retrieve_from_tree(save_data, ["companies", "database"], null={})

        company_rows = []
        rollups = {}  # country_id -> accumulators

        for company in companies.values():
            if not isinstance(company, dict):
                continue
            country_id = company.get("country")
            country = retrieve_from_tree(countries, [country_id], null=None)
            if not isinstance(country, dict):
                continue

            tag = country["definition"]
            country_name = get_country_name(country, localization)
            company_type = company.get("company_type", "")
            company_name = resolve_company_name(company, localization)

            levels = trend_last(company, "size_trend")
            productivity = trend_last(company, "productivity_trend")
            profit = trend_last(company, "profit_trend")
            prosperity = float(company["prosperity"]) if "prosperity" in company else MISSING

            company_rows.append({
                "id": country_id,
                "tag": tag,
                "country": country_name,
                "company_type": company_type,
                "company_name": company_name,
                "levels": levels,
                "productivity": productivity,
                "profit": profit,
                "prosperity": prosperity,
            })

            acc = rollups.setdefault(country_id, {
                "id": country_id, "tag": tag, "country": country_name,
                "company_levels": 0.0, "_prod_weighted": 0.0,
                "company_profit": 0.0, "company_count": 0,
            })
            acc["company_levels"] += levels
            acc["_prod_weighted"] += productivity * levels
            acc["company_profit"] += profit
            acc["company_count"] += 1

        country_rows = []
        for acc in rollups.values():
            country_rows.append({
                "id": acc["id"],
                "tag": acc["tag"],
                "country": acc["country"],
                "company_levels": acc["company_levels"],
                # Average productivity weighted by each company's levels.
                "company_productivity": safe_ratio(acc["_prod_weighted"], acc["company_levels"]),
                "company_profit": acc["company_profit"],
                "company_count": acc["company_count"],
            })

        company_cols = ["id", "tag", "country", "company_type", "company_name"] + \
                       company_columns + _company_extra_columns
        country_cols = ["id", "tag", "country"] + company_country_columns

        df_companies = pd.DataFrame(company_rows).reindex(columns=company_cols)
        df_countries = pd.DataFrame(country_rows).reindex(columns=country_cols)
        if not df_companies.empty:
            df_companies = df_companies.sort_values(by="levels", ascending=False)
        if not df_countries.empty:
            df_countries = df_countries.sort_values(by="company_levels", ascending=False)

        year, month, day = save_date
        for fname, df in (("companies", df_companies), ("company_countries", df_countries)):
            df.to_csv(f"{address}/data/{fname}.csv", sep=",", index=False)
            df_players = df[df["id"].astype(str).isin(players)]
            df_players.to_csv(f"{address}/{fname}.csv", sep=",", index=False)
            with open(f"{address}/{fname}.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                df_players.to_string(buf=f"{address}/{fname}.txt", encoding="utf-8")

        print(f"Finished checking companies on {day}/{month}/{year}")

        return df_companies
