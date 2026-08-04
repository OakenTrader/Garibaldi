"""
Declarative aggregation over save entities.

A checker declares what it wants summed and grouped. Two executors sit behind that
declaration:

  * columns  -- vectorised over the memory-mapped ``.npy`` tables
  * records  -- one pass over the nested dicts, for saves with no column cache

Identical requests from different checkers are deduplicated and computed once.
Column and record sums may differ in the last ULP.
"""

import numpy as np

from src.helpers.columnar import entity_schema, load_columns


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

class Expr:
    """A value or predicate, evaluable against columns or against one record."""

    def __add__(self, other): return BinOp("+", self, _wrap(other))
    def __sub__(self, other): return BinOp("-", self, _wrap(other))
    def __mul__(self, other): return BinOp("*", self, _wrap(other))
    def __gt__(self, other): return BinOp(">", self, _wrap(other))
    def __lt__(self, other): return BinOp("<", self, _wrap(other))
    def __eq__(self, other): return BinOp("==", self, _wrap(other))
    def __and__(self, other): return BinOp("&", self, _wrap(other))
    def __invert__(self): return Not(self)
    def __hash__(self): return hash(self.key())

    def key(self):
        """Structural identity, used to deduplicate equal requests."""
        raise NotImplementedError


def _wrap(value):
    return value if isinstance(value, Expr) else Const(value)


class Const(Expr):
    def __init__(self, value): self.value = value
    def key(self): return ("const", self.value)
    def eval_columns(self, ctx): return self.value
    def eval_record(self, record, ctx): return self.value


class Field(Expr):
    """A schema field. ``scaled`` applies the schema's ``scale`` factor.

    An absent field reads as the schema default on both routes.
    """

    def __init__(self, name, scaled=False):
        self.name = name
        self.scaled = scaled

    def key(self): return ("field", self.name, self.scaled)

    def eval_columns(self, ctx):
        array = np.asarray(ctx.columns[self.name])
        return array * ctx.scale(self.name) if self.scaled else array

    def eval_record(self, record, ctx):
        spec = ctx.field_spec(self.name)
        raw = record.get(self.name)
        if raw is None:
            return spec.get("default", 0)
        if spec["type"] == "dict":
            return raw
        value = int(raw) if spec["type"].startswith(("i", "u")) else float(raw)
        return value * ctx.scale(self.name) if self.scaled else value


class Present(Expr):
    """Whether the record carried this field, as distinct from carrying the default.

    Reads the schema's presence-flag column on the column route.
    """

    def __init__(self, name): self.name = name
    def key(self): return ("present", self.name)

    def eval_columns(self, ctx):
        return np.asarray(ctx.columns[ctx.presence_flag(self.name)])

    def eval_record(self, record, ctx):
        return self.name in record


class BinOp(Expr):
    OPS = {
        "+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b,
        ">": lambda a, b: a > b, "<": lambda a, b: a < b, "==": lambda a, b: a == b,
        "&": lambda a, b: a & b,
    }

    def __init__(self, op, left, right):
        self.op, self.left, self.right = op, left, right

    def key(self): return ("op", self.op, self.left.key(), self.right.key())

    def eval_columns(self, ctx):
        left = self.left.eval_columns(ctx)
        right = self.right.eval_columns(ctx)
        # A dict-encoded column holds int codes, so a comparison against a literal
        # string is translated through the vocabulary first.
        if isinstance(self.left, Field) and isinstance(self.right, Const):
            if ctx.field_spec(self.left.name)["type"] == "dict":
                right = ctx.encode(self.left.name, self.right.value)
        return self.OPS[self.op](left, right)

    def eval_record(self, record, ctx):
        left = self.left.eval_record(record, ctx)
        right = self.right.eval_record(record, ctx)
        if self.op == "&":
            return bool(left) and bool(right)
        return self.OPS[self.op](left, right)


class Not(Expr):
    def __init__(self, inner): self.inner = inner
    def key(self): return ("not", self.inner.key())
    def eval_columns(self, ctx): return ~self.inner.eval_columns(ctx)
    def eval_record(self, record, ctx): return not self.inner.eval_record(record, ctx)


class Call(Expr):
    """Arbitrary Python over one record. Record route only: it cannot vectorise."""

    def __init__(self, fn, name=None):
        self.fn = fn
        # ``name`` is the identity used for deduplication; two lambdas never collide.
        self._name = name or getattr(fn, "__qualname__", repr(fn))

    def key(self): return ("call", self._name)

    def eval_columns(self, ctx):
        raise NotImplementedError(
            f"Call({self._name}) has no column form; the entity it is declared over "
            "must be evaluated on the record route")

    def eval_record(self, record, ctx):
        return self.fn(record, ctx)


class Emit(Call):
    """A ``Call`` returning ``{subkey: value}``: one record contributing to many keys.

    The aggregate's result nests one level deeper, ``{group: {subkey: total}}``. A
    record emitting nothing joins no group.
    """


def F(name, scaled=False):
    return Field(name, scaled)


def present(name):
    return Present(name)


# ---------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------

class Agg:
    """One requested aggregate: sum ``value`` over ``entity``, grouped by ``by``.

    ``by`` is a field name or an expression. ``where`` filters records, ``negate``
    negates each group's total after summing.
    """

    def __init__(self, entity, by, name, value, where=None, negate=False,
                 attach=None):
        self.entity, self.by, self.name = entity, by, name
        self.value, self.where, self.negate = value, where, negate
        # (topic, field): write each group's total onto that record in save_data
        # when this stage finishes, for later stages to read.
        self.attach = attach

    def key(self):
        by = self.by.key() if isinstance(self.by, Expr) else self.by
        return (self.entity, by, self.name, self.value.key(),
                self.where.key() if self.where is not None else None, self.negate,
                self.attach)


# ---------------------------------------------------------------------------
# Evaluation context
# ---------------------------------------------------------------------------

class _Context:
    def __init__(self, entity, columns=None, vocabs=None):
        self.entity = entity
        self.spec = entity_schema(entity)
        self.columns = columns
        self.vocabs = vocabs or {}
        self._presence = {src: flag for src, flag in self.spec.get("presence", {}).items()}

    def encode(self, name, value):
        """The int code a dict-encoded string was stored as, or -1 if the save had none."""
        try:
            return self.vocabs[name].index(value)
        except (KeyError, ValueError):
            return -1

    def field_spec(self, name):
        return self.spec["fields"][name]

    def scale(self, name):
        return self.spec["fields"][name].get("scale", 1)

    def presence_flag(self, name):
        flag = self._presence.get(name)
        if flag is None:
            raise KeyError(
                f"{self.entity}.{name} is used with present() but has no presence flag "
                f"in the schema; add it under [entity.{self.entity}.presence]")
        return flag


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _run_columns(entity, aggs, columns):
    cols, vocabs, _ids = columns
    ctx = _Context(entity, cols, vocabs)
    results = {}
    for by, group in _by_field(aggs):
        keys = np.asarray(cols[by])
        unique, index = np.unique(keys, return_inverse=True)
        size = len(unique)
        labels = [str(k) for k in unique.tolist()]
        for agg in group:
            values = np.asarray(agg.value.eval_columns(ctx))
            if agg.where is not None:
                mask = np.asarray(agg.where.eval_columns(ctx))
                values = np.where(mask, values, values.dtype.type(0))
            is_float = values.dtype.kind == "f"
            summed = np.bincount(index, values, size)
            bucket = results.setdefault(agg.name, {})
            for i, label in enumerate(labels):
                total = summed[i]
                total = -total if agg.negate else total
                bucket[label] = float(total) if is_float else int(total)
    return results


def _run_records(entity, aggs, database, payload=None):
    """One pass over the records, evaluating every requested aggregate."""
    ctx = _Context(entity)
    ctx.payload = payload or {}
    results = {agg.name: {} for agg in aggs}
    for record in database.values():
        if not isinstance(record, dict):
            continue
        for agg in aggs:
            if agg.where is not None and not agg.where.eval_record(record, ctx):
                continue
            # An expression `by` derives the group; a string `by` reads a field.
            group = (agg.by.eval_record(record, ctx) if isinstance(agg.by, Expr)
                     else record.get(agg.by))
            if group is None:
                continue
            value = agg.value.eval_record(record, ctx)
            if isinstance(agg.value, Emit):
                if not value:
                    continue
                bucket = results[agg.name].setdefault(group, {})
                for subkey, amount in value.items():
                    bucket[subkey] = bucket.get(subkey, 0) + amount
                continue
            results[agg.name][group] = results[agg.name].get(group, 0) + value
    for agg in aggs:
        if agg.negate:
            results[agg.name] = {g: -v for g, v in results[agg.name].items()}
    return results


def _by_field(aggs):
    grouped = {}
    for agg in aggs:
        grouped.setdefault(agg.by, []).append(agg)
    return grouped.items()


def _needs_records(aggs):
    """A Call anywhere in an aggregate forces the record route for its entity."""
    def walk(node):
        if isinstance(node, Call):
            return True
        return any(walk(child) for attr in ("left", "right", "inner")
                   if isinstance(child := getattr(node, attr, None), Expr))
    for agg in aggs:
        for node in (agg.value, agg.where, agg.by):
            if isinstance(node, Expr) and walk(node):
                return True
    return False


# Entities are traversed in dependency order, so an aggregate over a later entity
# may use the results of an earlier one.
STAGE_ORDER = ["pop", "building", "state", "country"]


def run_aggregates(aggs, address, save_data=None, payload=None):
    """Compute every declared aggregate, deduplicated, columns where available.

    Returns ``{name: {group_key: total}}`` with group keys as strings, matching the
    save databases' own keys so a caller can look the group straight up.
    """
    unique = {}
    for agg in aggs:
        unique.setdefault(agg.key(), agg)
    by_entity = {}
    for agg in unique.values():
        by_entity.setdefault(agg.entity, []).append(agg)

    results = {}
    ordered = sorted(by_entity, key=lambda e: STAGE_ORDER.index(e)
                     if e in STAGE_ORDER else len(STAGE_ORDER))
    for entity in ordered:
        entity_aggs = by_entity[entity]
        columns = None if _needs_records(entity_aggs) else load_columns(address, entity)
        if columns is not None:
            results.update(_run_columns(entity, entity_aggs, columns))
        else:
            topic = entity_schema(entity)["source"].split(".")[0]
            database = save_data[topic]["database"]
            results.update(_run_records(entity, entity_aggs, database, payload))
        # Materialise this stage onto the tree before the next stage reads it.
        for agg in entity_aggs:
            if agg.attach is None:
                continue
            attach_topic, field = agg.attach
            target = save_data[attach_topic]["database"]
            for group, value in results[agg.name].items():
                record = target.get(group)
                if isinstance(record, dict):
                    record[field] = value
    return results
