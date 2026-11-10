"""
The engine's pop growth, rebuilt from the game's defines and the save.

A save stores neither a birth rate nor a mortality. The engine computes both for every
pop, once a month of game time (``CPop::CalcGrowthUpdateData``): a base rate that is a
piecewise-linear curve of the pop's standard of living (SoL), scaled by ``1 + the sum of
its modifiers``. ``growth_curves`` rebuilds the curves from the ``NPops``
``POP_GROWTH_*`` defines, and ``state_growth`` the modifiers from the save.

What is rebuilt of the modifiers (read off the game binary and checked against the
engine's own results for every pop of a 1836 world):

  birth:     the laws' ``state_birth_rate_mult`` (rights of women), minus 0.4 times the
             state's unemployment, plus 0.5 times how far the state is under
             ``LOW_POP_THRESHOLD`` pops per arable land, minus 0.1 times the pop's
             literacy, and the starvation penalty.
  mortality: the laws' ``state_mortality_mult``, ``state_mortality_wealth_mult`` (times
             the pop's SoL) and ``state_<profession>_mortality_mult``; for a pop with a
             workplace, the ``working_conditions`` static modifier of its building group
             and of every group above it, and the building's production methods; and the
             starvation penalty.

Also rebuilt: a state's devastation (its ``state_region_devastation`` modifier, in force at
devastation / 100), the ``multiplier`` and linear decay of timed modifiers, and, from the
politics of the country, the growth modifiers of the traits its interest groups have
switched on (``enabled_traits``; doubled for an influential group and halved for a marginal one) and of
institutions (the active law's ``institution_modifier`` and the institution's own
``modifier``, times the institution's level, in incorporated states only; the workplace
safety institution scales ``working_conditions``). Pollution is the state region's
``pollution`` over ``POLLUTION_MAX`` times the ``state_region_pollution_health`` modifier,
less what the health laws and the sewerage technology take off (``state_pollution_reduction_health_mult``).

Also rebuilt: the modifiers of a state region's traits (malaria and the like); for
``state_non_homeland_mortality_mult`` they reach only pops whose culture has no homeland in
the region.

What is not: character traits, companies and the like. They are real, a few per cent of
mortality for an affected country, and the save does not hold the engine's total. A rate
from here is therefore close to the engine's, not equal.
"""

import ast
import re
from decimal import Decimal, ROUND_DOWN

import numpy as np

# Declared by the checkers that use the curves, so the defines are parsed once.
DEFINES_FILE = "defines/00_defines.txt"

# The engine's fixed-point numbers hold five decimals. Every define is one, and so is
# every step of a ``@[formula]``: the engine cuts each result toward zero at the fifth
# decimal. That matters here. The slope of the mortality line from the equilibrium to
# the growth-max SoL is (0.00112 - 0.0045) / 10 = -0.000338 exactly, and -0.00033 in the
# game; the line from there to the stable SoL is -0.000067 exactly and -0.00006 in the
# game. Read off the engine, that is up to 7% of a pop's mortality.
FIXED_SCALE = 100_000


def _fixed_mul(left, right):
    product = left * right
    return abs(product) // FIXED_SCALE * (1 if product >= 0 else -1)


def _engine_rate(base, multiplier):
    """A pop's monthly rate: the base rate times its multiplier, cut toward zero at the fifth
    decimal like every fixed-point product of the engine. The cut loses half a unit of 0.00001
    on average, which is 1% of the lowest base rate (0.00045 from SoL 25) and 0.1% of the highest."""
    return np.floor(base * multiplier * FIXED_SCALE + 1e-6) / FIXED_SCALE


def _fixed_div(left, right):
    quotient = abs(left) * FIXED_SCALE // abs(right)
    return quotient * (1 if (left >= 0) == (right >= 0) else -1)


class DefineValues:
    """Numbers out of a parsed defines file, where a value may be a script variable.

    The defines file declares ``@name = 0.0045`` variables and ``@[a*b/c]`` formulas
    over them, and the ``NPops`` entries are written as ``@name``. The parser keeps all
    of these as text, so ``value`` resolves one: a plain number, ``@name`` or
    ``@[formula]``. Formulas are plus, minus, times, divide, brackets and the names of
    other variables.

    Arithmetic is the engine's: fixed point with five decimals, cut toward zero after
    each step (see ``FIXED_SCALE``). ``value`` returns the resulting number as a float;
    ``fixed`` returns it as the integer count of 0.00001.
    """

    def __init__(self, defines):
        self._variables = {key[1:]: raw for key, raw in defines.items()
                           if isinstance(key, str) and key.startswith("@")}
        self._resolved = dict()
        self._resolving = set()

    def value(self, raw):
        return self.fixed(raw) / FIXED_SCALE

    def fixed(self, raw):
        text = str(raw).strip()
        if text.startswith("@["):
            return self._evaluate(ast.parse(text[2:-1], mode="eval").body)
        if text.startswith("@"):
            return self._variable(text[1:])
        return int((Decimal(text) * FIXED_SCALE).to_integral_value(rounding=ROUND_DOWN))

    def _variable(self, name):
        if name not in self._resolved:
            if name not in self._variables:
                raise KeyError(f"The defines have no variable '@{name}'")
            if name in self._resolving:
                raise ValueError(f"The define variable '@{name}' is defined in terms of itself")
            self._resolving.add(name)
            try:
                self._resolved[name] = self.fixed(self._variables[name])
            finally:
                self._resolving.discard(name)
        return self._resolved[name]

    def _evaluate(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return self.fixed(repr(node.value))
        if isinstance(node, ast.Name):
            return self._variable(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = self._evaluate(node.left), self._evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return _fixed_mul(left, right)
            return _fixed_div(left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            operand = self._evaluate(node.operand)
            return -operand if isinstance(node.op, ast.USub) else operand
        raise ValueError(f"Unsupported define formula: {ast.dump(node)}")


def growth_curves(defines):
    """
    The base birth and mortality curves, per month, from a parsed ``00_defines.txt``.

    Returns ``(first, birth, mortality)``: ``birth[i]`` and ``mortality[i]`` are the
    rates of a pop whose SoL is ``first + i``, for every SoL from
    ``QUALITY_OF_LIFE_MIN`` to ``QUALITY_OF_LIFE_MAX``.

    Both follow the engine: the segment is chosen by comparing the SoL against the
    thresholds with ``<``, so a pop on a threshold takes the segment above it.
    """
    values = DefineValues(defines)

    def pops(key):
        return values.value(defines["NPops"][key])

    first = int(values.value(defines["NEconomy"]["QUALITY_OF_LIFE_MIN"]))
    last = int(values.value(defines["NEconomy"]["QUALITY_OF_LIFE_MAX"]))
    sol = np.arange(first, last + 1, dtype=float)

    birth = np.where(
        sol < pops("POP_GROWTH_TRANSITION_SOL"),
        pops("POP_GROWTH_MAX_BIRTHRATE") + sol * pops("POP_GROWTH_BIRTHRATE_PRETRANSITION_SLOPE"),
        np.where(sol < pops("POP_GROWTH_STABLE_SOL"),
                 sol * pops("POP_GROWTH_BIRTHRATE_TRANSITION_SLOPE")
                 + pops("POP_GROWTH_BIRTHRATE_TRANSITION_INTERCEPT"),
                 pops("POP_GROWTH_MIN_BIRTHRATE")))

    mortality = np.where(
        sol < pops("POP_GROWTH_EQUILIBRIUM_SOL"),
        pops("POP_GROWTH_MAX_MORTALITY") + sol * pops("POP_GROWTH_MORTALITY_STARVING_SLOPE"),
        np.where(sol < pops("POP_GROWTH_MAX_SOL"),
                 sol * pops("POP_GROWTH_MORTALITY_EQUILIBRIUM_TO_GROWTH_MAX_SLOPE")
                 + pops("POP_GROWTH_MORTALITY_EQUILIBRIUM_TO_GROWTH_MAX_INTERCEPT"),
                 np.where(sol < pops("POP_GROWTH_STABLE_SOL"),
                          sol * pops("POP_GROWTH_MORTALITY_GROWTH_MAX_TO_STABLE_SLOPE")
                          + pops("POP_GROWTH_MORTALITY_GROWTH_MAX_TO_STABLE_INTERCEPT"),
                          pops("POP_GROWTH_MIN_MORTALITY"))))
    return first, birth, mortality


# The pop table columns ``pop_growth`` reads. A caller building the table from the save's
# tree needs only these.
POP_FIELDS = ("location", "workforce", "dependents", "workplace", "type", "previous_quality_of_life",
              "num_literate", "food_security_state", "food_security_starvation", "loyalists_and_radicals",
              "culture")

# Declared by the checker that uses ``state_growth``, so each is parsed once.
GROWTH_DEFINITIONS = (DEFINES_FILE, "laws", "buildings", "building_groups", "production_methods",
                      "static_modifiers", "interest_group_traits", "institutions", "technology/technologies",
                      "state_traits", "power_bloc_principles", "power_bloc_identities", "subject_types",
                      "harvest_condition_types")
# Save topics ``context_of`` reads; the checker lists them in its requirements.
CONTEXT_TOPICS = ("interest_groups", "institutions", "technology", "state_region_manager", "cultures",
                  "power_bloc_manager", "pacts", "harvest_condition_manager")

# `loyalists_and_radicals` is a pop's NET count of politically aligned individuals:
# positive => loyalists, negative => radicals. Fixed-point, shown by the melter as
# raw / 100000, so multiply back to recover the count. Not a per-capita rate.
LOYALTY_SCALE = 100000

# NPops.LOW_POP_THRESHOLD. Not read from the defines: the file has two NPops blocks and
# the parser keeps only the last, which does not hold this one.
LOW_POP_THRESHOLD = 5000
# NPolitics: POWERFUL_IG_TRAIT_BONUS (influential group: its traits count 1 + this) and
# MARGINAL_IG_TRAIT_PENALTY (marginal group: 1 - this).
POWERFUL_IG_TRAIT_BONUS = 1.0
# NState.DEVASTATION_MAX: the ``state_region_devastation`` modifier is in force at devastation / this.
DEVASTATION_MAX = 100.0
# NEconomy.POLLUTION_MAX: a state region's ``pollution`` in the save over this is its pollution
# impact, the share in force of the ``state_region_pollution_health`` modifier.
POLLUTION_MAX = 255.0
MARGINAL_IG_TRAIT_PENALTY = 0.5
STARVATION_BIRTH = {"starvation": -0.7, "severe_starvation": -0.9}
STARVATION_MORTALITY = {"starvation": 0.6, "severe_starvation": 1.0}
# ``static_modifiers.working_conditions`` entries: building_group_bg_X_<profession>_mortality_mult
_WORKING_CONDITIONS = re.compile(r"building_group_(bg_[a-z_]+?)_([a-z]+)_mortality_mult$")
_PM_MORTALITY = re.compile(r"building_([a-z]+)_mortality_mult$")
_GROUP_MORTALITY = re.compile(r"building_group_(bg_[a-z_]+?)(?:_([a-z]+))?_mortality_mult$")


def _wanted(key, professions):
    """Whether a modifier key is one of the growth modifiers rebuilt here."""
    if key in ("state_birth_rate_mult", "state_mortality_mult", "state_mortality_wealth_mult",
               "building_working_conditions_mult", "state_pollution_reduction_health_mult",
               "state_mortality_turmoil_mult", "state_non_homeland_mortality_mult"):
        return True
    match = re.fullmatch(r"(state|building)_([a-z]+)_mortality_mult", key)
    if match and match.group(2) in professions:
        return True
    return key.startswith("building_group_") and key.endswith("_mortality_mult")


def context_of(save_data):
    """The ``context`` argument of ``pop_growth`` from loaded save topics: the politics (interest
    groups, institutions), the technologies, the traits and pollution of each state region and the
    cultures (for their homelands)."""
    return {topic: save_data[topic]["database"] for topic in CONTEXT_TOPICS}


def _listed(value):
    """The names in a save list, which the extractor stores as ``{"value": [...]}``."""
    value = value.get("value", []) if isinstance(value, dict) else value
    return [value] if isinstance(value, str) else list(value or [])


def _trait_scale(group):
    """How strongly an interest group's traits count: influential, marginal or neither."""
    if group.get("influence_type") == "influential":
        return 1 + POWERFUL_IG_TRAIT_BONUS
    if group.get("influence_type") is None and group.get("influence_type_reason") == "below_marginalization_threshold":
        return 1 - MARGINAL_IG_TRAIT_PENALTY
    return 1.0


_MONTH_START = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)   # the game has no leap years


def _day(date):
    """Day number of a game date, ``"1837.6.26"`` or ``(1837, 6, 26)``; the calendar has 365 days."""
    year, month, day = (int(float(part)) for part in (date.split(".") if isinstance(date, str) else date)[:3])
    return year * 365 + _MONTH_START[month - 1] + day


def _timed_scale(entry, today):
    """The share of a timed modifier in force: its ``multiplier``, and for ``decay = linear``
    the part of its span (``start_date`` to ``end_date``) that is left on ``today``."""
    scale = float(entry.get("multiplier") or 1)
    if entry.get("decay") == "linear" and today is not None and entry.get("start_date") and entry.get("end_date"):
        start, end = _day(entry["start_date"]), _day(entry["end_date"])
        scale *= min(1.0, max(0.0, (end - _day(today)) / max(end - start, 1)))
    return scale


def _bloc_members(countries, context, definitions):
    """The active power bloc each country belongs to: ``(bloc of each country, the active blocs)``.

    A country that is a core member of a bloc says so (``power_bloc_as_core``). One that joined
    (``power_bloc_join_date``, and has not left since) without being core is a subject that
    followed its overlord in, so it belongs to its overlord's bloc. The save lists no members.
    """
    blocs = {str(key): bloc for key, bloc in ((context or {}).get("power_bloc_manager") or {}).items()
             if isinstance(bloc, dict) and bloc.get("status") == "active"}
    subject_actions = {name.removeprefix("subject_type_") for name in (definitions.get("subject_types") or {})}
    overlord = dict()
    for pact in ((context or {}).get("pacts") or {}).values():
        if isinstance(pact, dict) and pact.get("action") in subject_actions:
            targets = pact.get("targets") or {}
            overlord[str(targets.get("second"))] = str(targets.get("first"))

    def member(record):
        join, leave = record.get("power_bloc_join_date"), record.get("power_bloc_leave_date")
        return join is not None and (leave is None or _day(leave) < _day(join))

    def bloc_of(country, depth=0):
        record = countries.get(country)
        if not isinstance(record, dict) or not member(record):
            return None
        if str(record.get("power_bloc_as_core")) in blocs:
            return str(record["power_bloc_as_core"])
        return bloc_of(overlord[country], depth + 1) if country in overlord and depth < 8 else None

    found = {country: bloc for country in countries if (bloc := bloc_of(str(country)))}
    return found, blocs


def _modifier_sums(states, countries, laws, definitions, professions, context=None, today=None):
    """The growth modifiers in force, by country and by state.

    Returns ``(by_country, by_state)``, each ``{id: {modifier: sum}}`` with string ids. A
    country gets the modifiers of its active laws, its researched technologies and its
    timed modifiers, and of the traits its interest groups have switched on (their
    ``enabled_traits``, see ``_trait_scale``). A state gets those of its own timed modifiers, the
    ``state_region_devastation`` modifier at its devastation, the modifiers of the harvest
    conditions (earthquake, drought and so on) in force in its region, each times its intensity,
    the modifiers of its region's traits
    (unless the owner has a technology that disables them), the ``state_region_pollution_health``
    modifier at its region's pollution impact (less what the health laws and technologies take
    off it) and, if it is fully incorporated, those of its country's institutions (the active
    law's ``institution_modifier`` and the institution's own ``modifier``, times the
    institution's level). The engine adds both to a state's own total. A timed modifier counts
    by its ``multiplier`` and, if it decays, by what is left of it on ``today`` (the save's
    date; none means no decay is applied).
    """
    by_country, by_state = dict(), dict()

    def add(into, owner, block, scale=1.0):
        if not isinstance(block, dict):
            return
        totals = into.setdefault(owner, dict())
        for key, value in block.items():
            if _wanted(key, professions):
                totals[key] = totals.get(key, 0.0) + float(value) * scale

    by_institution = dict()
    levels = dict()
    for record in ((context or {}).get("institutions") or {}).values():
        if isinstance(record, dict) and record.get("institution"):
            levels[(str(record.get("country")), record["institution"])] = float(record.get("investment") or 0)
    for (country, name), level in levels.items():
        add(by_institution, country, ((definitions.get("institutions") or {}).get(name) or {}).get("modifier"), level)

    for law in laws.values():
        if isinstance(law, dict) and law.get("active") == "yes":
            country = str(law.get("country"))
            definition = definitions["laws"].get(law.get("law")) or {}
            add(by_country, country, definition.get("modifier"))
            add(by_institution, country, definition.get("institution_modifier"),
                levels.get((country, definition.get("institution")), 0.0))

    # Power blocs: the identity and the principles of a country's bloc give it modifiers as a
    # member, and as the leader or as a follower.
    found, blocs = _bloc_members(countries, context, definitions)
    sources = {**(definitions.get("power_bloc_identities") or {}), **(definitions.get("power_bloc_principles") or {})}
    for country, bloc_id in found.items():
        bloc = blocs[bloc_id]
        names = [bloc.get("identity"), *_listed(bloc.get("principles"))]
        for source in (sources.get(name) for name in names):
            if isinstance(source, dict):
                add(by_country, country, source.get("member_modifier"))
                add(by_country, country, source.get("leader_modifier" if str(bloc.get("leader")) == country
                                                    else "non_leader_modifier"))

    traits = definitions.get("interest_group_traits") or {}
    for group in ((context or {}).get("interest_groups") or {}).values():
        if isinstance(group, dict):
            scale = _trait_scale(group)
            for name in _listed(group.get("enabled_traits")):
                trait = traits.get(name)
                if isinstance(trait, dict):
                    add(by_country, str(group.get("country")), trait.get("modifier"), scale)

    techs = definitions.get("technology/technologies") or {}
    researched = dict()
    for record in ((context or {}).get("technology") or {}).values():
        if isinstance(record, dict):
            researched[str(record.get("country"))] = set(_listed(record.get("acquired_technologies")))
            for name in researched[str(record.get("country"))]:
                add(by_country, str(record.get("country")), (techs.get(name) or {}).get("modifier"))

    static = definitions["static_modifiers"]
    for into, records in ((by_country, countries), (by_state, states)):
        for owner, record in records.items():
            if not isinstance(record, dict):
                continue
            timed = (record.get("timed_modifiers") or {}).get("modifiers")
            for entry in (timed.values() if isinstance(timed, dict) else ()):
                if isinstance(entry, dict):
                    add(into, str(owner), static.get(entry.get("modifier")), _timed_scale(entry, today))
    for key, state in states.items():
        if isinstance(state, dict) and state.get("devastation"):
            add(by_state, str(key), static.get("state_region_devastation"), float(state["devastation"]) / DEVASTATION_MAX)
        if isinstance(state, dict) and float(state.get("incorporation") or 0) >= 1:
            for name, value in by_institution.get(str(state.get("country")), {}).items():
                totals = by_state.setdefault(str(key), dict())
                totals[name] = totals.get(name, 0.0) + value

    # A state region's traits (malaria and the like) act on its state, unless the owner has researched
    # a technology that disables the trait.
    state_traits = definitions.get("state_traits") or {}
    region_traits = {region.get("template"): _listed(region.get("traits"))
                     for region in ((context or {}).get("state_region_manager") or {}).values()
                     if isinstance(region, dict)}
    for key, state in states.items():
        if not isinstance(state, dict):
            continue
        for name in region_traits.get(state.get("region"), ()):
            trait = state_traits.get(name)
            if isinstance(trait, dict) and not researched.get(str(state.get("country")), set()) & set(_listed(trait.get("disabling_technologies"))):
                add(by_state, str(key), trait.get("modifier"))

    # Harvest conditions (earthquake, drought and the like) act on every state of their region
    # while they last, by their intensity.
    kinds = definitions.get("harvest_condition_types") or {}
    scale_of = dict()
    for entry in ((context or {}).get("harvest_condition_manager") or {}).values():
        if not isinstance(entry, dict):
            continue
        for part in (entry.get("province_sets") or {}).values():
            if isinstance(part, dict) and part.get("start_date"):
                start, length = _day(part["start_date"]), float(part.get("duration") or 0)
                if today is None or start <= _day(today) < start + length:
                    key = (entry.get("state_region_template"), entry.get("type"))
                    scale_of[key] = scale_of.get(key, 0.0) + float(part.get("intensity") or 0)
    for key, state in states.items():
        if isinstance(state, dict):
            for (region, kind), scale in scale_of.items():
                if region == state.get("region"):
                    add(by_state, str(key), (kinds.get(kind) or {}).get("modifier"), scale)

    # Pollution comes last: what the health laws and technologies take off it is in the totals now.
    pollution = {region.get("template"): float(region.get("pollution") or 0) / POLLUTION_MAX
                 for region in ((context or {}).get("state_region_manager") or {}).values()
                 if isinstance(region, dict)}
    for key, state in states.items():
        impact = pollution.get(state.get("region")) if isinstance(state, dict) else None
        if impact:
            relief = sum((mods or {}).get("state_pollution_reduction_health_mult", 0.0)
                         for mods in (by_country.get(str(state.get("country"))), by_state.get(str(key))))
            add(by_state, str(key), static.get("state_region_pollution_health"), impact * max(0.0, 1.0 + relief))
    return by_country, by_state


def _building_mortality(buildings, states, by_country, by_state, definitions, professions):
    """Per building, the mortality modifier of each profession working in it.

    Returns ``(ids, table)``: ``ids`` the sorted building ids and ``table[i, p]`` the
    modifier for profession ``p`` in building ``ids[i]``. It is the sum of
      - ``working_conditions`` for the building's group and each group above it,
      - the ``unscaled`` ``building_<profession>_mortality_mult`` of its production methods,
      - the building-group and building modifiers of the country and the state it stands in
        (a group's modifier reaches the groups below it).
    """
    column = {p: i for i, p in enumerate(professions)}
    groups = definitions["building_groups"]
    base = dict()                 # group -> {profession index: working conditions}
    block = (definitions["static_modifiers"].get("working_conditions") or {})
    for key, value in block.items():
        match = _WORKING_CONDITIONS.match(key)
        if match and match.group(2) in column:
            base.setdefault(match.group(1), dict())[column[match.group(2)]] = float(value)

    def chain(group):
        found, seen = [], set()
        while group and group not in seen:
            seen.add(group)
            found.append(group)
            group = (groups.get(group) or {}).get("parent_group")
        return found

    pm_total = dict()
    for name, pm in definitions["production_methods"].items():
        unscaled = ((pm or {}).get("building_modifiers") or {}).get("unscaled") or {}
        found = {column[m.group(1)]: float(v) for key, v in unscaled.items()
                 if (m := _PM_MORTALITY.match(key)) and m.group(1) in column}
        if found:
            pm_total[name] = found

    def modifier_row(mods, above):
        """Row of profession modifiers from ``building_*`` keys of ``mods`` for groups ``above``."""
        row = np.zeros(len(professions))
        for key, value in mods.items():
            if key.startswith("building_group_"):
                match = _GROUP_MORTALITY.match(key)
                if not match or match.group(1) not in above:
                    continue
                if match.group(2) is None:
                    row += value
                elif match.group(2) in column:
                    row[column[match.group(2)]] += value
            else:
                match = _PM_MORTALITY.match(key)
                if match and match.group(1) in column:
                    row[column[match.group(1)]] += value
        return row

    group_of = {name: (b or {}).get("building_group") for name, b in definitions["buildings"].items()}
    chains = dict()
    ids, rows = [], []
    for key, building in buildings.items():
        if not isinstance(building, dict):
            continue
        group = group_of.get(building.get("building"))
        if group not in chains:
            chains[group] = chain(group)
        above = chains[group]
        row = np.zeros(len(professions))
        state = str(building.get("state"))
        owner = str((states.get(state) or {}).get("country"))
        # Workplace safety and the like scale the working conditions, not the methods' hazards.
        safety = max(0.0, 1.0 + sum((mods or {}).get("building_working_conditions_mult", 0.0)
                                    for mods in (by_country.get(owner), by_state.get(state))))
        for g in above:
            for p, value in base.get(g, {}).items():
                row[p] += value * safety
        methods = building.get("production_methods")
        for name in (methods.get("value", []) if isinstance(methods, dict) else []):
            for p, value in pm_total.get(name, {}).items():
                row[p] += value
        for mods in (by_country.get(owner), by_state.get(state)):
            if mods:
                row += modifier_row(mods, set(above))
        ids.append(int(key))
        rows.append(row)
    order = np.argsort(ids)
    return np.asarray(ids, dtype=np.int64)[order], np.asarray(rows).reshape(-1, len(professions))[order]


def state_growth(columns, vocabs, states, countries, laws, buildings, definitions, context=None, today=None):
    """
    Births and deaths a month's growth is due, per state.

    columns, vocabs: the pop table, as ``columnar.load_columns`` or ``build_columns``
        return it. states, countries, laws, buildings: the save's ``states``,
        ``country_manager``, ``laws`` and ``building_manager`` databases. definitions: the
        manager's, holding ``GROWTH_DEFINITIONS``. context: ``context_of`` of the save's
        ``interest_groups`` and ``institutions``; without it neither is counted. today: the
        save's date, for the decay of timed modifiers.

    Returns ``{"births": {state id: count}, "deaths": {state id: count}}`` with state
    ids as strings, the keys of the aggregates the demographics checker reads.
    """
    pops = pop_growth(columns, vocabs, states, countries, laws, buildings, definitions, context, today)
    return {"births": _by_state(pops["location"], pops["births"]),
            "deaths": _by_state(pops["location"], pops["deaths"])}


def pop_growth(columns, vocabs, states, countries, laws, buildings, definitions, context=None, today=None):
    """
    The same, per pop: ``state_growth`` before it is summed.

    Returns arrays over the pop table's rows: ``location`` (state id, -1 for none),
    ``births`` and ``deaths`` for one month, and ``birth_mult`` and ``mortality_mult``,
    the ``1 + modifiers`` the base rates were scaled by.
    """
    first, birth_curve, mortality_curve = growth_curves(definitions[DEFINES_FILE])
    professions = list(vocabs["type"])

    location = np.asarray(columns["location"]).astype(np.int64)
    workforce = np.asarray(columns["workforce"]).astype(float)
    size = workforce + np.asarray(columns["dependents"]).astype(float)
    workplace = np.asarray(columns["workplace"])
    kind = np.asarray(columns["type"])
    sol = np.asarray(columns["previous_quality_of_life"]).astype(np.int64)
    present = location >= 0

    count = max(int(max((int(k) for k in states), default=-1)), int(location.max(initial=-1))) + 1
    arable = np.zeros(count)
    for key, state in states.items():
        if isinstance(state, dict) and state.get("country") is not None:
            arable[int(key)] = float(state.get("arable_land") or 0)

    # State level: unemployment and how thinly the land is settled.
    at = np.where(present, location, 0)
    population = np.bincount(at, np.where(present, size, 0.0), count)
    workers = np.bincount(at, np.where(present, workforce, 0.0), count)
    jobless = np.bincount(at, np.where(present & (workplace < 0), workforce, 0.0), count)
    unemployment = jobless / np.maximum(workers, 1.0)
    # Turmoil is the share of a state's people who are radicals (CState::CalcTurmoilAndLoyalists).
    radicals = np.maximum(0.0, -np.asarray(columns["loyalists_and_radicals"]).astype(float)) * LOYALTY_SCALE
    turmoil = np.bincount(at, np.where(present, radicals, 0.0), count) / np.maximum(population, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        low_pop = np.where(arable > 0, np.maximum(0.0, (LOW_POP_THRESHOLD - population / arable)
                                                  / LOW_POP_THRESHOLD), 0.0)

    # Modifiers from laws and timed modifiers, as one total per state.
    by_country, by_state = _modifier_sums(states, countries, laws, definitions, professions, context, today)
    keys = ["state_birth_rate_mult", "state_mortality_mult", "state_mortality_wealth_mult",
            "state_mortality_turmoil_mult", "state_non_homeland_mortality_mult"]
    in_force = np.zeros((count, len(keys)))
    by_profession = np.zeros((count, len(professions)))
    for key, state in states.items():
        if not isinstance(state, dict) or state.get("country") is None:
            continue
        for mods in (by_country.get(str(state["country"])), by_state.get(str(key))):
            for name, value in (mods or {}).items():
                if name in keys:
                    in_force[int(key), keys.index(name)] += value
                else:
                    match = re.fullmatch(r"state_([a-z]+)_mortality_mult", name)
                    if match and match.group(1) in professions:
                        by_profession[int(key), professions.index(match.group(1))] += value

    # Pop level.
    literacy = np.asarray(columns["num_literate"]) / np.maximum(workforce, 1.0)
    food = np.asarray(columns["food_security_state"])
    starvation = np.asarray(columns["food_security_starvation"]).astype(float)
    # A pop with no food security record has code -1, which must read as "not starving"
    # and not as the last entry of the vocabulary: the appended 0 is what -1 lands on.
    starving_birth = np.append([STARVATION_BIRTH.get(f, 0.0) for f in vocabs["food_security_state"]], 0.0)[food] * starvation
    starving_mortality = np.append([STARVATION_MORTALITY.get(f, 0.0) for f in vocabs["food_security_state"]], 0.0)[food] * starvation

    ids, table = _building_mortality(buildings, states, by_country, by_state, definitions, professions)
    row = np.clip(np.searchsorted(ids, workplace), 0, max(len(ids) - 1, 0))
    building = np.zeros(len(location))
    if len(ids):
        employed = present & (workplace >= 0) & (ids[row] == workplace)
        building = np.where(employed, table[row, kind], 0.0)

    birth_mult = (1 + in_force[at, 0] - 0.4 * unemployment[at]
                  + 0.5 * low_pop[at] - 0.1 * literacy + starving_birth)
    away = _non_homeland(np.asarray(columns["culture"]).astype(np.int64), location, states, (context or {}).get("cultures"))
    mortality_mult = (1 + in_force[at, 1] + sol * in_force[at, 2] + turmoil[at] * in_force[at, 3]
                      + away * in_force[at, 4] + by_profession[at, kind] + building + starving_mortality)

    index = np.clip(sol - first, 0, len(birth_curve) - 1)
    births = size * _engine_rate(birth_curve[index], np.maximum(birth_mult, 0.0))
    deaths = size * _engine_rate(mortality_curve[index], np.maximum(mortality_mult, 0.0))
    return {"location": location, "births": births, "deaths": deaths,
            "birth_mult": birth_mult, "mortality_mult": mortality_mult}


def _non_homeland(culture, location, states, cultures):
    """Per pop, whether its culture has no homeland in its state's region.

    A culture lists its homeland regions as ``core_states``; one with none has no homeland
    anywhere. Without the cultures every pop counts as at home.
    """
    result = np.zeros(len(culture), dtype=bool)
    if not cultures:
        return result
    homelands = {str(key): set(_listed(record.get("core_states"))) for key, record in cultures.items()
                 if isinstance(record, dict)}
    known = (location >= 0) & (culture >= 0)
    pairs, inverse = np.unique(np.column_stack([culture[known], location[known]]), axis=0, return_inverse=True)
    away = np.array([(states.get(str(state)) or {}).get("region") not in homelands.get(str(kind), set())
                     for kind, state in pairs], dtype=bool)
    result[known] = away[np.ravel(inverse)]
    return result


def _by_state(location, values):
    keep = location >= 0
    totals = np.bincount(location[keep], values[keep])
    return {str(state): float(total) for state, total in enumerate(totals) if total}
