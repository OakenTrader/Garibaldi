from scripts.checkers.check_base import Checker
from scripts.checkers.checkers_functions import get_country_name
from scripts.helpers.utility import retrieve_from_tree, load_def
import pandas as pd

finance_columns = ["GDP", "money", "money_percentage", "credit", "debt_percentage", "cash_reserve_limit", "ownership_levels"]

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
    
    requirements = ["pops", "country_manager", "building_manager", "states"]
    output = {"finance.csv":["GDP", "money", "money_percentage", "credit", "debt_percentage", "cash_reserve_limit", "ownership_levels"],}

    def __init__(self):
        super().__init__()
    
    def execute_check(self, cache: dict):
        save_data = cache["save_data"]
        localization = cache["localization"]
        save_date = cache["metadata"]["save_date"]
        players = [str(p[0]) for p in cache["metadata"]["players"]]
        address = cache["address"]

        countries = save_data["country_manager"]["database"]
        states = save_data["states"]["database"]
        buildings = save_data["building_manager"]["database"]

        df_finance = []

        """get definition from defines/00_defines.txt GOLD_RESERVE_LIMIT_FACTOR = 0.2"""
        defines = load_def("defines/00_defines.txt", "Common Directory")["NEconomy"]
        def_gold_reserve_limit_factor = float(defines["GOLD_RESERVE_LIMIT_FACTOR"])
        def_min_credit_base = float(defines["COUNTRY_MIN_CREDIT_BASE"])
        def_min_credit_scale = float(defines["COUNTRY_MIN_CREDIT_SCALED"])
        ownership_buildings = ["building_financial_district", "building_manor_house", "building_company"]

        for building_key, building in buildings.items():
            if not isinstance(building, dict):
                continue
            if "cash_reserves" in building:
                if building["state"] not in states:
                    continue
                cash_reserve = building["cash_reserves"]
                country = countries[states[building["state"]]["country"]]
                if "data_building_reserves" not in country:
                    country["data_building_reserves"] = 0
                country["data_building_reserves"] += float(cash_reserve)
                "add ownership levels to the country if the building is financial_district or company"
                if any(building["building"] in b for b in ownership_buildings):
                    levels = building["levels"]
                    if "ownership_levels" not in country:
                        country["ownership_levels"] = 0
                    country["ownership_levels"] += int(levels)

        
        
        """Loop through countries and calculate the money and money_percentage"""
        for country_key, country in countries.items():
            if not isinstance(country, dict):
                continue
            if "data_building_reserves" not in country:
                continue
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
            building_cash_reserves = country["data_building_reserves"]
            gdp = (credit - def_min_credit_base - building_cash_reserves) / def_min_credit_scale
            cash_reserve_limit = gdp * def_gold_reserve_limit_factor
            money_percentage = money/(gdp + 0.00001)
            debt_percentage = principal/(credit + 0.00001)
            if principal > 0:
                money = -principal
            df_finance.append({
                "id": country_key,
                "tag": country["definition"],
                "country": get_country_name(country, localization),
                "GDP": gdp,
                "money": money,
                "money_percentage": money_percentage,
                "credit": credit,
                "debt_percentage": debt_percentage,
                "cash_reserve_limit": cash_reserve_limit,
                "ownership_levels": country["ownership_levels"] if "ownership_levels" in country else 0
            })

        df_finance = pd.DataFrame(df_finance, columns=["id", "tag", "country", "GDP", "money", "money_percentage", "credit", "debt_percentage", "cash_reserve_limit", "ownership_levels"])
        df_finance = df_finance.sort_values(by='GDP', ascending=False)

        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            year, month, day = save_date
            df_finance.to_csv(f"{address}/finance.csv", sep=",", index=False)
            with open(f"{address}/finance.txt", "w") as file:
                file.write(f"{day}/{month}/{year}\n")
                df_finance.to_string(buf=f"{address}/finance.txt", encoding="utf-8")
        
        print(f"Finished checking finance on {day}/{month}/{year}")

        return df_finance