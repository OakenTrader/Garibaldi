from src.checkers.aggregates import Agg, Call
from src.checkers.check_base import Checker
from src.checkers.checkers_functions import STATE_COUNTRY, get_country_name, safe_ratio, MISSING
from src.helpers.utility import retrieve_from_tree
import pandas as pd
import numpy as np
import warnings

OWNERSHIP_BUILDINGS = ["building_financial_district", "building_manor_house", "building_company"]


def _has_cash_reserves(building, ctx):
    return "cash_reserves" in building


def _cash_reserves(building, ctx):
    return float(building["cash_reserves"])


def _is_ownership(building, ctx):
    # Containment, not equality, so modded variants of these buildings count too.
    return any(building["building"] in name for name in OWNERSHIP_BUILDINGS)


def _levels(building, ctx):
    return int(building["levels"])


# GDP is derived from a country's credit minus what its buildings hold.
_HAS_RESERVES = Call(_has_cash_reserves, name="has_cash_reserves")

BUILDING_RESERVES = Agg(
    "building", by=STATE_COUNTRY, name="building_cash_reserves",
    value=Call(_cash_reserves, name="cash_reserves"), where=_HAS_RESERVES)
OWNERSHIP_LEVELS = Agg(
    "building", by=STATE_COUNTRY, name="ownership_levels",
    value=Call(_levels, name="building_levels"),
    where=_HAS_RESERVES & Call(_is_ownership, name="is_ownership_building"))

# ---------------------------------------------------------------------------
# Weekly income / expense category maps
# ---------------------------------------------------------------------------
# ``country["budget"]["weekly_income"]`` / ``["weekly_expenses"]`` are flat lists
# serialised in a fixed internal enum order (the exact values shown by the
# in-game Budget panel for the save week). The labels below were calibrated on
# v1.13 saves by (a) matching the *named* per-building sub-totals in
# ``country_building_budget`` to array positions across all countries — these are
# self-verifying and re-checked at runtime (see ``_budget_selfcheck``) — and
# (b) matching the remaining "national" lines (tolls, minting, treaties, ...)
# against the Budget panel + structural signals (e.g. tolls only for strait
# controllers). A handful of naval expense slots could not be pinned to a panel
# line without a same-date screenshot; they are kept under ``expense_slot_N`` so
# their money is still counted in the totals but is never mislabelled.
#
# To recalibrate after a patch: open the Budget panel for a player nation, expand
# every line, and compare against that country's row in income.csv / expenses.csv.
INCOME_LABELS = {
    1: "income_taxes",           # building-derived (self-checked)
    2: "poll_taxes",             # building-derived (self-checked)
    3: "consumption_taxes",
    4: "dividends_taxes",        # building-derived (self-checked)
    5: "diplomatic_pacts",
    7: "investment_pool_transfer",
    8: "minting",
    9: "tariffs",                # building-derived (self-checked)
    10: "government_dividends",  # building-derived: government_share_dividends
    11: "war_reparations",       # small round transfers; panel folds into Treaties
    12: "treaties",              # panel "Treaties" income ~= [11] + [12]
    # tolls is stored GROSS here. For a major strait controller the Budget panel
    # shows a smaller NET tolls figure (gross received minus tolls the country
    # itself pays on its trade). v1.13.9 GBR: stored 1.49M vs panel 790K. So
    # total_income (and net_balance) run high by the netted amount for big toll
    # earners; it is exact for the many countries with negligible tolls.
    13: "tolls",
    15: "supply_network",
}
EXPENSE_LABELS = {
    0: "additional_expenses",
    1: "government_slaves",      # building-derived (self-checked)
    2: "government_goods",       # building-derived (self-checked)
    3: "government_wages",       # building-derived (self-checked)
    4: "military_slaves",        # building-derived (self-checked)
    5: "military_goods",         # building-derived (self-checked)
    6: "military_wages",         # building-derived (self-checked)
    7: "construction_goods",     # building-derived (self-checked)
    8: "subsidies",              # building-derived (self-checked)
    9: "subventions",            # building-derived (self-checked)
    10: "interest",
    11: "diplomatic_pacts",       # confirmed vs 1.13.9 BIC panel (116K); subjects pay their overlord here
    13: "welfare_payments",       # confirmed vs 1.13.9 GCO panel (13.7K)
    14: "government_share_losses",  # building-derived; matches panel "Losses from Nationally Owned Buildings"
    # The panel shows a single "Treaties" expense line = treaty_subsidies[15] +
    # treaties[16]. Confirmed on GCO where [15]=0 and [16]=823K == panel Treaties,
    # and BIC where both are 0 (its diplomacy expense is the pacts line [11]).
    # [15] is the subsidies-to-subjects/allies component (round amounts, only paid
    # by overlord powers: GBR 838K, SPA 341K, ...); GBR's panel Treaties 1.41M =
    # 838K [15] + 582K [16].
    15: "treaty_subsidies",
    16: "treaties",
    17: "supply_ship_construction",  # confirmed vs 1.13.9 GBR panel (206.6K)
    18: "ship_construction",         # temporary military-ship construction; confirmed vs GCO panel (14.2K)
    19: "supply_ships",              # supply-ship maintenance; confirmed (49.9K)
    20: "military_ships",            # military-ship maintenance; confirmed (GBR 205.3K, GCO 1.6K)
    21: "shipping_lanes",            # port-connection cost; confirmed (GBR 49.4K, GCO 295K)
    # Slot 12 is the only unlabelled position: it is zero for every country across
    # all 143 campaign saves and the 1.13.9 save, so no panel can name it. It stays
    # expense_slot_12 rather than risk a label it never carries data for.
}
# country_building_budget category name -> weekly array index, used by the
# runtime self-check to detect enum reordering in future game patches. Only
# categories whose array slot equals the building sub-total *exactly* are listed:
# a few labelled categories (government_wages, government_dividends, tariffs,
# subventions, government_share_losses) legitimately include non-building or
# reallocated components (e.g. construction-sector wages are billed under
# construction, not government_wages), so they are correctly labelled but must not
# be asserted for exact equality.
_INCOME_BUILDING_ANCHORS = {
    "income_taxes": 1, "poll_taxes": 2, "dividends_taxes": 4,
}
_EXPENSE_BUILDING_ANCHORS = {
    "government_slaves": 1, "government_goods": 2, "military_slaves": 4,
    "military_goods": 5, "military_wages": 6, "construction_goods": 7,
    "subsidies": 8,
}

# Interest is charged weekly; the game annualises the weekly payment over 52 weeks
# (verified against the Budget-panel tooltip: weekly_interest * 52 / principal
# reproduces the displayed yearly rate).
WEEKS_PER_YEAR = 52
# Society technologies that each add to country_loan_interest_rate_add (v1.13).
INTEREST_TECHS = {
    "banking", "central_banking", "mutual_funds",
    "international_exchange_standards", "modern_financial_instruments",
}


def _sum_building_category(cbb_side, category):
    """Sum the per-building values under one country_building_budget category."""
    body = (cbb_side or {}).get(category)
    if not isinstance(body, dict):
        return 0.0
    values = body.get("values")
    if not isinstance(values, dict):
        return 0.0
    return sum(float(v) for v in values.values())


def _budget_selfcheck(budget, warned):
    """
    Verify the array-index labels still line up with the named
    country_building_budget sub-totals; warn once per mislabelled category so a
    future enum reordering surfaces loudly instead of silently mislabelling money.
    """
    cbb = budget.get("country_building_budget")
    if not isinstance(cbb, dict):
        return
    checks = (
        (budget.get("weekly_income"), cbb.get("incomes"), _INCOME_BUILDING_ANCHORS, "income"),
        (budget.get("weekly_expenses"), cbb.get("expenses"), _EXPENSE_BUILDING_ANCHORS, "expense"),
    )
    for arr, side, anchors, side_name in checks:
        values = retrieve_from_tree(arr, "value", null=None)
        if not isinstance(values, list):
            continue
        for category, idx in anchors.items():
            total = _sum_building_category(side, category)
            if total <= 1.0 or idx >= len(values):
                continue
            if abs(float(values[idx]) - total) > max(1.0, total * 1e-4):
                key = (side_name, category)
                if key not in warned:
                    warned.add(key)
                    warnings.warn(
                        f"Budget {side_name} label mismatch: '{category}' expected at "
                        f"index {idx} but array value {float(values[idx]):.1f} != "
                        f"building sum {total:.1f}. The weekly_{side_name} enum order "
                        f"may have changed in this game version; recalibrate "
                        f"INCOME_LABELS/EXPENSE_LABELS.", UserWarning)


def _current_prestige(country):
    """Latest sample of a country's prestige time-series (0 if unavailable)."""
    series = retrieve_from_tree(country, ["prestige", "channels", "0", "values", "value"], null=None)
    if isinstance(series, list) and series:
        try:
            return float(series[-1])
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def load_interest_defs(definitions):
    """
    Gather everything needed to reconstruct the loan interest rate from game data
    (vanilla + selected mod). Returns a dict of:
      base_add        : always-on additive base (base_values, ~0.2)
      bankruptcy_mult : multiplicative penalty while bankrupt (~0.5)
      ranks           : ordered [(name, rank_value, avg_thr, rel_thr, valid_types, mult)]
      law_mults       : {law_name: multiplicative modifier}

    definitions (dict): the manager's preloaded definitions; needs
    "static_modifiers", "country_ranks" and "laws".
    """
    sm = definitions["static_modifiers"]
    base_add = float(retrieve_from_tree(sm, ["base_values", "country_loan_interest_rate_add"], null=0.0))
    bankruptcy_mult = float(retrieve_from_tree(sm, ["declared_bankruptcy", "country_loan_interest_rate_mult"], null=0.0))

    ranks = []
    for name, rd in definitions["country_ranks"].items():
        if not isinstance(rd, dict):
            continue
        mult = retrieve_from_tree(rd, ["modifier", "country_loan_interest_rate_mult"], null=0.0)
        valid = retrieve_from_tree(rd, ["valid_country_types", "value"], null=[])
        ranks.append((
            name,
            float(rd.get("rank_value", 0)),
            float(rd.get("prestige_average_threshold", 0)),
            float(rd.get("prestige_relative_threshold", 0)),
            set(valid),
            float(mult),
        ))
    ranks.sort(key=lambda r: r[1], reverse=True)  # highest rank_value first

    law_mults = {}
    for law_name, law in definitions["laws"].items():
        if not isinstance(law, dict):
            continue
        mult = retrieve_from_tree(law, ["modifier", "country_loan_interest_rate_mult"], null=None)
        if mult is not None:
            law_mults[law_name] = float(mult)
    return {"base_add": base_add, "bankruptcy_mult": bankruptcy_mult,
            "ranks": ranks, "law_mults": law_mults}


def compute_country_ranks(countries, ranks):
    """
    Assign each country its power rank (great_power, major_power, ...): a country
    takes the highest-rank_value tier whose country_type is valid and whose current
    prestige clears that rank's ``prestige_average_threshold`` multiple of the world
    average prestige. Prestige is read straight from the save (latest sample).

    The game additionally gates ranks with ``prestige_relative_threshold`` (0.75 of
    the single highest-prestige country) and applies day-count hysteresis; those are
    intentionally omitted here because the relative gate over-demotes clear great
    powers whenever one country runs far ahead on prestige (e.g. it would drop
    Great Britain to a major power merely because Germany leads it). The
    average-threshold rule reproduces the usual top-8 great powers. This makes the
    rank a close (not bit-exact) reconstruction; ``interest_rate_realized`` is the
    exact cross-check for indebted countries.
    """
    prestige = {cid: _current_prestige(c) for cid, c in countries.items() if isinstance(c, dict)}
    # World average over every real country (those carrying a definition), matching
    # the game's world-average base (decentralized/unrecognized pull it down).
    pool = [p for cid, p in prestige.items() if "definition" in countries[cid]]
    avg = sum(pool) / len(pool) if pool else 0.0

    out = {}
    for cid, c in countries.items():
        if not isinstance(c, dict):
            continue
        ctype = c.get("country_type")
        p = prestige.get(cid, 0.0)
        chosen = None
        for name, _rv, avg_thr, _rel_thr, valid_types, _mult in ranks:
            if valid_types and ctype not in valid_types:
                continue
            if p >= avg_thr * avg:
                chosen = name
                break
        out[cid] = chosen
    return out


def reconstruct_interest_rate(country, rank_name, defs, rank_mult_by_name):
    """
    Reconstruct a country's nominal yearly loan interest rate from its modifiers:
        rate = additive_bucket * (1 + multiplicative_bucket)
    (the standard Victoria 3 percentage-modifier stacking). Returns
    (rate, additive_sum, multiplicative_sum).

    Additive sources: base_values (+0.2) and society technologies (-0.02 each).
    Multiplicative sources: power rank, active economic law (laissez-faire),
    and the bankruptcy penalty. Country-specific event/power-bloc modifiers are
    not sourced here; interest_rate_realized is the exact validation column.

    Expects the country dict to carry ``interest_tech_add`` (summed tech add),
    ``active_laws`` (list) and ``is_bankrupt`` (bool), populated by the caller.
    """
    add = defs["base_add"] + float(retrieve_from_tree(country, "interest_tech_add", null=0.0))

    mult = 0.0
    if rank_name in rank_mult_by_name:
        mult += rank_mult_by_name[rank_name]
    for law in retrieve_from_tree(country, "active_laws", null=[]):
        if law in defs["law_mults"]:
            mult += defs["law_mults"][law]
    if retrieve_from_tree(country, "is_bankrupt", null=False):
        mult += defs["bankruptcy_mult"]

    rate = add * (1 + mult)
    return rate, add, mult


finance_columns = ["GDP", "GDP per capita", "money", "money_percentage", "credit", "debt_percentage", "cash_reserve_limit", "ownership_levels",
                   "total_income", "total_expense", "net_balance",
                   "income_pct_gdp", "income_per_capita", "expense_pct_gdp", "expense_per_capita",
                   "interest_payment", "interest_rate", "interest_rate_realized",
                   "interest_rate_add", "interest_rate_mult",
                   "interest_pct_gdp", "interest_per_capita", "interest_pct_income"]

class CheckFinance(Checker):
    """
    Financial data. 
    money: Just money if positive or principal if negative
    money_percentage: percentage of money/cash_reserves_limit or principal/credit
    Credit limit: credit

    Building cash reserves: Loop over all buildings and sum up the cash reserves
    GDP: 
    Cash reserves limit: 1/5 of GDP
    Interest: Calculated from the rate and prinncipal

    We are going to measure gdp indirectly by credit limit in the save file and the measurement of total
    cash reserve in a country.

    Each country has a gold reserve limit, which is a soft-cap equal to 20% of its annual 
    gross domestic product (GDP) (Vickypedia)

    A country's credit limit is the maximum amount of principal it can borrow before going into default. 
    This limit is based on its buildings' current cash reserves plus £100K plus 50% of its GDP. (Vickypedia)

    """
    
    name = "CheckFinance"
    display_name = "Finance"
    sort_order = 30
    requirements = ["country_manager", "building_manager", "states", "laws", "technology"]
    # defines/00_defines.txt is declared as a single file rather than the defines
    # folder, so a mod override of GOLD_RESERVE_LIMIT_FACTOR / COUNTRY_MIN_CREDIT_*
    # keeps being ignored exactly as it was before — folding it into the folder read
    # would change what the GDP formula sees, which is not a caching change.
    definitions = ("defines/00_defines.txt", "static_modifiers", "country_ranks",
                   "laws", "technology/technologies")
    # finance.csv carries every column in ``finance_columns``. This used to declare
    # a seven-item subset, which silently hid total income, total expense, net
    # balance and the whole interest group from the statistics tree even though the
    # checker wrote them and the batch pass plotted them.
    aggregates = [BUILDING_RESERVES, OWNERSHIP_LEVELS]
    output = {"finance.csv": finance_columns,
              "income.csv": [], "expenses.csv": []}
    # The per-slot income and expense breakdowns depend on game version and mod, so
    # their columns are read from the CSV header instead of being declared.
    header_columns = ("income.csv", "expenses.csv")
    file_categories = {"income.csv": ("Income", 31), "expenses.csv": ("Expenses", 32)}
    dependencies = ["demographics.csv"]

    def __init__(self):
        super().__init__()
    
    def before_countries(self, cache: dict):
        save_data = cache["save_data"]
        address = cache["address"]

        countries = save_data["country_manager"]["database"]
        # Population per country id, read back from demographics.csv.
        df_demographics = pd.read_csv(f"{address}/data/demographics.csv", sep=",")[["id", "population"]]
        self.population = {}
        for country_id, population in zip(df_demographics["id"], df_demographics["population"]):
            self.population.setdefault(str(country_id), population)

        self.selfcheck_warned = set()

        # --- Interest-rate reconstruction inputs (see reconstruct_interest_rate) ---
        definitions = cache["definitions"]
        idefs = self.idefs = load_interest_defs(definitions)
        self.rank_mult_by_name = {name: mult for name, _rv, _a, _r, _vt, mult in idefs["ranks"]}
        self.country_rank = compute_country_ranks(countries, idefs["ranks"])

        # Society technologies that shift country_loan_interest_rate_add. Values are
        # read from the tech defs (mod-robust) rather than hardcoded.
        tech_add_values = {}
        for tech_name, tech in definitions["technology/technologies"].items():
            add = retrieve_from_tree(tech, ["modifier", "country_loan_interest_rate_add"], null=None)
            if add is not None:
                tech_add_values[tech_name] = float(add)
        for save_tech in save_data["technology"]["database"].values():
            if not isinstance(save_tech, dict):
                continue
            country = retrieve_from_tree(countries, [retrieve_from_tree(save_tech, "country")], null=None)
            if not isinstance(country, dict):
                continue
            acquired = retrieve_from_tree(save_tech, ["acquired_technologies", "value"], null=[])
            country["interest_tech_add"] = sum(tech_add_values.get(t, 0.0) for t in acquired)

        # Active laws per country (for the laissez-faire interest multiplier, etc.).
        for law in save_data["laws"]["database"].values():
            if not isinstance(law, dict) or law.get("active") != "yes":
                continue
            country = retrieve_from_tree(countries, [law.get("country")], null=None)
            if isinstance(country, dict):
                country.setdefault("active_laws", []).append(law.get("law"))

        # Bankruptcy penalty applies while the declared_bankruptcy modifier is active.
        for country in countries.values():
            if not isinstance(country, dict):
                continue
            timed = retrieve_from_tree(country, ["timed_modifiers", "modifiers"], null={})
            country["is_bankrupt"] = any(
                isinstance(m, dict) and m.get("modifier") == "declared_bankruptcy"
                for m in (timed.values() if isinstance(timed, dict) else [])
            )

        """get definition from defines/00_defines.txt GOLD_RESERVE_LIMIT_FACTOR = 0.2"""
        defines = definitions["defines/00_defines.txt"]["NEconomy"]
        self.gold_reserve_limit_factor = float(defines["GOLD_RESERVE_LIMIT_FACTOR"])
        self.min_credit_base = float(defines["COUNTRY_MIN_CREDIT_BASE"])
        self.min_credit_scale = float(defines["COUNTRY_MIN_CREDIT_SCALED"])

        # From the shared building pass; a country absent from it has no
        # cash-reserve buildings and gets no finance row.
        self.building_reserves = cache["aggregates"].get("building_cash_reserves", {})
        self.ownership_levels = cache["aggregates"].get("ownership_levels", {})

    """Money and money_percentage, one country at a time"""
    def on_country(self, country_key, country, cache):
            if country_key not in self.building_reserves:
                return None
            if "money" not in country["budget"]:
                money = 0
            else:
                money = float(country["budget"]["money"])
            if "principal" not in country["budget"]:
                principal = 0
            else:
                principal = float(country["budget"]["principal"])
            if "credit" not in country["budget"]:
                credit = 0
            else:
                credit = float(country["budget"]["credit"])
            # print(country)
            localization = cache["localization"]
            building_cash_reserves = self.building_reserves[country_key]
            gdp = (credit - self.min_credit_base - building_cash_reserves) / self.min_credit_scale
            cash_reserve_limit = gdp * self.gold_reserve_limit_factor
            money_percentage = safe_ratio(money, gdp)
            debt_percentage = safe_ratio(principal, credit)
            if principal > 0:
                money = -principal
            population = self.population.get(str(country_key))
            if population is None:
                population = MISSING
                warnings.warn(f"No population record for {country_key}:{country['definition']}")
            gdp_per_capita = safe_ratio(gdp, population)  # MISSING when population is absent/zero

            # ---- Weekly income / expense breakdown (this save week) ----
            budget = country["budget"]
            _budget_selfcheck(budget, self.selfcheck_warned)
            weekly_income = [float(x) for x in retrieve_from_tree(budget, ["weekly_income", "value"], null=[])]
            weekly_expenses = [float(x) for x in retrieve_from_tree(budget, ["weekly_expenses", "value"], null=[])]
            total_income = sum(weekly_income)
            total_expense = sum(weekly_expenses)
            net_balance = total_income - total_expense

            base_row = {"id": country_key, "tag": country["definition"],
                        "country": get_country_name(country, localization)}
            income_row = dict(base_row)
            for i, v in enumerate(weekly_income):
                income_row[INCOME_LABELS.get(i, f"income_slot_{i}")] = v
            income_row["total_income"] = total_income
            income_row["income_pct_gdp"] = safe_ratio(total_income, gdp)
            income_row["income_per_capita"] = safe_ratio(total_income, population)

            expense_row = dict(base_row)
            for i, v in enumerate(weekly_expenses):
                expense_row[EXPENSE_LABELS.get(i, f"expense_slot_{i}")] = v
            expense_row["total_expense"] = total_expense
            expense_row["expense_pct_gdp"] = safe_ratio(total_expense, gdp)
            expense_row["expense_per_capita"] = safe_ratio(total_expense, population)

            # ---- Interest: payment (exact), realized rate (exact for debtors),
            #      reconstructed nominal rate from modifiers (approximate) ----
            interest_idx = next(i for i, n in EXPENSE_LABELS.items() if n == "interest")
            interest_payment = weekly_expenses[interest_idx] if interest_idx < len(weekly_expenses) else 0.0
            # principal>0 means the country is in debt; realized rate is undefined otherwise.
            interest_rate_realized = safe_ratio(interest_payment * WEEKS_PER_YEAR, principal)
            rank_name = self.country_rank.get(country_key)
            interest_rate, interest_add, interest_mult = reconstruct_interest_rate(
                country, rank_name, self.idefs, self.rank_mult_by_name)

            finance_row = {
                "id": country_key,
                "tag": country["definition"],
                "country": get_country_name(country, localization),
                "GDP": gdp,
                "GDP per capita": gdp_per_capita,
                "money": money,
                "money_percentage": money_percentage,
                "credit": credit,
                "debt_percentage": debt_percentage,
                "cash_reserve_limit": cash_reserve_limit,
                "ownership_levels": self.ownership_levels.get(country_key, 0),
                "total_income": total_income,
                "total_expense": total_expense,
                "net_balance": net_balance,
                "income_pct_gdp": safe_ratio(total_income, gdp),
                "income_per_capita": safe_ratio(total_income, population),
                "expense_pct_gdp": safe_ratio(total_expense, gdp),
                "expense_per_capita": safe_ratio(total_expense, population),
                "interest_payment": interest_payment,
                "interest_rate": interest_rate,
                "interest_rate_realized": interest_rate_realized,
                "interest_rate_add": interest_add,
                "interest_rate_mult": interest_mult,
                "interest_country_rank": rank_name,
                "interest_pct_gdp": safe_ratio(interest_payment, gdp),
                "interest_per_capita": safe_ratio(interest_payment, population),
                "interest_pct_income": safe_ratio(interest_payment, total_income),
            }
            # Three tables, one walk: the finance row and its income and expense
            # breakdowns all come from the same country's budget.
            return finance_row, income_row, expense_row

    def execute_check(self, cache: dict):
        save_date = cache["metadata"]["save_date"]
        players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        rows = cache["country_rows"][self.name]
        df_finance = [row[0] for row in rows]
        df_income = [row[1] for row in rows]
        df_expenses = [row[2] for row in rows]

        finance_cols = ["id", "tag", "country", "GDP", "GDP per capita", "money", "money_percentage",
                        "credit", "debt_percentage", "cash_reserve_limit", "ownership_levels"] + \
                       finance_columns[8:] + ["interest_country_rank"]
        # dedupe while preserving order (finance_columns[8:] repeats the summary block once)
        finance_cols = list(dict.fromkeys(finance_cols))
        df_finance = pd.DataFrame(df_finance, columns=finance_cols)
        df_finance = df_finance.sort_values(by='GDP', ascending=False)

        income_cols = ["id", "tag", "country"] + \
                      [INCOME_LABELS.get(i, f"income_slot_{i}") for i in range(16)] + \
                      ["total_income", "income_pct_gdp", "income_per_capita"]
        expense_cols = ["id", "tag", "country"] + \
                       [EXPENSE_LABELS.get(i, f"expense_slot_{i}") for i in range(22)] + \
                       ["total_expense", "expense_pct_gdp", "expense_per_capita"]
        df_income = pd.DataFrame(df_income).reindex(columns=income_cols).fillna(0)
        df_expenses = pd.DataFrame(df_expenses).reindex(columns=expense_cols).fillna(0)
        df_income = df_income.sort_values(by="total_income", ascending=False)
        df_expenses = df_expenses.sort_values(by="total_expense", ascending=False)

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_finance.to_csv(f"{address}/data/finance.csv", sep=",", index=False)
            df_finance_players = df_finance[df_finance["id"].isin(players)]
            df_finance_players.to_csv(f"{address}/finance.csv", sep=",", index=False)
            with open(f"{address}/finance.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                df_finance_players.to_string(buf=f"{address}/finance.txt", encoding="utf-8")

            for name, df in (("income", df_income), ("expenses", df_expenses)):
                df.to_csv(f"{address}/data/{name}.csv", sep=",", index=False)
                df_players = df[df["id"].isin(players)]
                df_players.to_csv(f"{address}/{name}.csv", sep=",", index=False)
                with open(f"{address}/{name}.txt", "w") as file:
                    file.write(f"{day}/{month}/{year}\n")
                    df_players.to_string(buf=f"{address}/{name}.txt", encoding="utf-8")

        print(f"Finished checking finance on {day}/{month}/{year}")

        return df_finance