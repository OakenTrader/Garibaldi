"""
Statistics of one save.

``compare`` follows a statistic across the saves of a campaign. This module is its
counterpart for a statistic that is a spread inside one save: how a country's people
divide over standard of living. The checker writes it for every save, as a CSV with a
row per country and bin; the plot reads the latest save's. It holds no plotting code,
so the arithmetic can be tested without a figure.

A checker offers one by listing it in its ``distributions``; the batch pass reads
that list.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Distribution:
    """
    A per-country spread of people over the bins of a statistic.

    key:        the name the plot is saved under
    input_file: the per-save CSV, one row per country and bin that holds anyone
    column:     the selectable statistic it is drawn with
    label:      what the plot calls it
    cap:        the last bin, which also holds everything above it
    value:      the CSV column holding the bin
    weight:     the CSV column holding the people in it
    """
    key: str
    input_file: str
    column: str
    label: str
    cap: int
    value: str = "sol"
    weight: str = "population"


def population_shares(frame, distribution):
    """
    Each country's people as shares of its total, per bin.

    frame: the rows of the distribution's CSV. Countries are identified as
        ``plot_stat`` does, by ``(tag, country)``: two ids with the same tag and name
        are one country.

    Returns ``{(tag, country): shares}`` with ``shares`` of length ``cap + 1`` summing
    to 1. A country with nobody in it is left out.
    """
    shares = dict()
    for (tag, country), rows in frame.groupby(["tag", "country"], sort=False):
        people = np.zeros(distribution.cap + 1)
        np.add.at(people, rows[distribution.value].clip(0, distribution.cap).to_numpy(int),
                  rows[distribution.weight].to_numpy(float))
        if people.sum() > 0:
            shares[(tag, country)] = people / people.sum()
    return shares
