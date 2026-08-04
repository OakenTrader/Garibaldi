"""
Turning the checker registry into the statistics tree.

The tree is never hardcoded. One category per registered checker, one leaf per
column that checker declares, both read from the checker classes themselves — so
registering a checker in ``manager.ALL_CHECKERS`` is all it takes to give it a
category, with no edit here or in the page.

Two leaf sets cannot come from class attributes and are resolved per campaign,
which is why the tree is rebuilt whenever the campaign changes:

- **Goods** declares the single key ``goods_produced``, but one line per good is
  wanted. The goods are whatever the campaign recorded, read from the CSV header
  so a mod's goods appear without touching its ``common/goods``.
- **Companies** has fixed columns, but the lines within each figure are companies,
  which vary per campaign and per mod.
"""

import os

from src.checkers.manager import file_keys, registered_checkers
from src.helpers.plotter import csv_value_columns, goods_in_campaign
from src.helpers.utility import iter_save_folders


class Leaf:
    """One selectable statistic."""

    def __init__(self, column, label, input_file, checker):
        self.column = column
        self.label = label
        self.input_file = input_file
        self.checker = checker

    def __repr__(self):
        return f"Leaf({self.column!r}, {self.input_file!r})"


class Category:
    def __init__(self, name, checker, leaves):
        self.name = name
        self.checker = checker
        self.leaves = leaves


def available_files(campaign_folder):
    """Output files that at least one save in the campaign actually has.

    Used to grey out — rather than hide — a stat that exists but has not been
    parsed yet, so it is visible that the statistic is available in principle.
    """
    found = set()
    try:
        folders = list(iter_save_folders(campaign_folder, need_metadata=False))
    except OSError:
        return found
    for save_folder, _, _ in folders:
        try:
            found.update(f for f in os.listdir(save_folder) if f.endswith(".csv"))
        except OSError:
            continue
    return found


def build_categories(campaign_folder):
    """The full category/leaf tree for one campaign, in registry order.

    Normally one category per checker, but a checker can hand one of its output
    files to a category of its own via ``file_categories`` — goods production is
    written by CheckPrestige yet is nothing to do with prestige.
    """
    grouped = {}   # label -> [order, checker, leaves]
    # A key naming a whole file is not a leaf; its file's columns are, and they come
    # from the CSV header below.
    whole_files = file_keys()
    for checker in registered_checkers():
        for input_file, columns in checker.output.items():
            label, order = checker.file_categories.get(
                input_file, (checker.category_name(), checker.sort_order)
            )
            entry = grouped.setdefault(label, [order, checker, []])
            for column in columns:
                if column in whole_files:
                    continue
                entry[2].append(Leaf(column, checker.label_for(column), input_file, checker))
            if input_file in checker.header_columns:
                # Columns the checker cannot declare up front — the campaign's
                # goods, its income and expense slots — come from the CSV header.
                for column in _header_columns(campaign_folder, input_file):
                    entry[2].append(Leaf(column, checker.label_for(column), input_file, checker))

    categories = []
    for label, (order, checker, leaves) in sorted(grouped.items(), key=lambda kv: (kv[1][0], kv[0])):
        if leaves:
            categories.append(Category(label, checker, leaves))
    return categories


def _header_columns(campaign_folder, filename):
    try:
        if filename == "goods_produced.csv":
            # Goods keep their defines fallback, so the category is still listed
            # before a campaign has been parsed.
            return goods_in_campaign(campaign_folder)
        return csv_value_columns(campaign_folder, filename)
    except Exception:
        # No parsed save yet, or no game defines configured: that category simply
        # comes up empty rather than breaking the whole tree.
        return []
