"""
Columnar storage for the entity tables a save's checkers iterate.

Each entity is written as fixed-width columns, one uncompressed ``.npy`` per field,
which the reader memory-maps. The layout is declared in ``save_schema.toml``.

The columns are a cache sitting beside the blobs they were derived from; a save
without them still works, because every reader falls back to the dict path.
"""

import json
import os
import tomllib

import numpy as np

SCHEMA_PATH = "./src/save_schema.toml"
COLUMN_DIR = "columns"

# Schema type names (i32, f64) -> numpy dtypes.
DTYPES = {
    "i8": np.int8, "i16": np.int16, "i32": np.int32, "i64": np.int64,
    "u8": np.uint8, "u32": np.uint32, "u64": np.uint64,
    "f32": np.float32, "f64": np.float64, "bool": np.bool_,
}
# Bump on any schema shape change; caches written under an older version are ignored.
FORMAT_VERSION = 2

_SCHEMA = None


def schema():
    """The parsed schema, read once per process."""
    global _SCHEMA
    if _SCHEMA is None:
        with open(SCHEMA_PATH, "rb") as f:
            _SCHEMA = tomllib.load(f)
    return _SCHEMA


def entity_schema(entity):
    return schema()["entity"][entity]


def _column_dir(save_folder, entity):
    return os.path.join(save_folder, COLUMN_DIR, entity)


def _at(record, path):
    """Follow a declared path into a record, or None if any step is missing."""
    node = record
    for step in path:
        if not isinstance(node, dict):
            return None
        node = node.get(step)
        if node is None:
            return None
    return node


# Which of the two shapes a bounded array was written in, stored per row.
# 0 = absent, 1 = indexed map (carries ``index0``), 2 = {field_type: list, value: [...]}
FORM_ABSENT, FORM_INDEXED, FORM_LIST = 0, 1, 2


def _flag_name(spec, key):
    """The presence-flag column for a record key: the declared name, or a generated one."""
    return spec.get("presence", {}).get(key, f"{key}__present")


def _record_keys(spec):
    """Every top-level record key the schema stores, mapped to ``(kind, name)``.

    Arrays and side tables are keyed by the record key they live under rather than
    their declared name -- ``interest_group_support`` lives under
    ``interest_group_support_data``.
    """
    kinds = {}
    for name, field in spec["fields"].items():
        if "path" in field:
            kinds.setdefault(field["path"][0], ("group", field["path"][0]))
        else:
            kinds[name] = ("field", name)
    for name, array in spec.get("arrays", {}).items():
        kinds[array["path"][0]] = ("array", name)
    for name, side in spec.get("side", {}).items():
        kinds[side["path"][0]] = ("side", name)
    return kinds


def build_columns(database, entity):
    """Turn an id -> record mapping into ``(columns, vocabs, ids)``.

    Rows keep the database's iteration order. Three kinds of declaration are handled:

      fields  -- one scalar per row, read off the record or from a declared ``path``
      arrays  -- a bounded slot list, one 2-D column of that width
      side    -- a ragged key -> value map, as three parallel arrays
    """
    spec = entity_schema(entity)
    fields = spec["fields"]
    arrays = spec.get("arrays", {})
    sides = spec.get("side", {})
    presence = spec.get("presence", {})

    records = [(k, v) for k, v in database.items() if isinstance(v, dict)]
    n = len(records)

    columns, vocabs, vocab_index = {}, {}, {}
    for name, field in fields.items():
        if field["type"] == "dict":
            columns[name] = np.full(n, -1, np.int32)
            vocabs[name] = []
            vocab_index[name] = {}
        else:
            columns[name] = np.full(n, field.get("default", 0), DTYPES[field["type"]])
    for name, array in arrays.items():
        columns[name] = np.full((n, array["slots"]), array.get("default", 0),
                                DTYPES[array["type"]])
        # Shape, index0 and list length as written, since the list form is often
        # shorter than the slot count.
        columns[f"{name}__form"] = np.zeros(n, np.int8)
        columns[f"{name}__index0"] = np.full(n, -1, np.int32)
        columns[f"{name}__len"] = np.zeros(n, np.int16)
    kinds = _record_keys(spec)
    for key in kinds:
        columns[_flag_name(spec, key)] = np.zeros(n, bool)
    for flag in presence.values():
        columns.setdefault(flag, np.zeros(n, bool))

    side_rows = {name: ([], [], []) for name in sides}

    ids = np.empty(n, np.int64)
    for i, (key, record) in enumerate(records):
        ids[i] = int(key)
        for name, field in fields.items():
            raw = _at(record, field["path"]) if "path" in field else record.get(name)
            if raw is None:
                continue
            if field["type"] == "dict":
                code = vocab_index[name].get(raw)
                if code is None:
                    code = vocab_index[name][raw] = len(vocabs[name])
                    vocabs[name].append(raw)
                columns[name][i] = code
            elif field["type"].startswith(("i", "u")):
                columns[name][i] = int(raw)
            else:
                columns[name][i] = float(raw)
        for name, array in arrays.items():
            node = _at(record, array["path"])
            if not isinstance(node, dict):
                continue
            slots = array["slots"]
            if "value" in node and isinstance(node["value"], list):
                listed = node["value"]
                if len(listed) > slots:
                    raise ValueError(
                        f"{entity}.{name} has {len(listed)} entries but the schema "
                        f"declares {slots} slots; widen it rather than truncating")
                columns[f"{name}__form"][i] = FORM_LIST
                columns[f"{name}__len"][i] = len(listed)
                for slot, value in enumerate(listed):
                    columns[name][i, slot] = float(value)
            else:
                columns[f"{name}__form"][i] = FORM_INDEXED
                if (index0 := node.get("index0")) is not None:
                    columns[f"{name}__index0"][i] = int(index0)
                for slot_key, value in node.items():
                    if slot_key.isdigit():
                        columns[name][i, int(slot_key)] = float(value)
        for name, side in sides.items():
            node = _at(record, side["path"])
            if not isinstance(node, dict):
                continue
            rows, keys, values = side_rows[name]
            for entry_key, value in node.items():
                rows.append(i)
                keys.append(int(entry_key))
                values.append(float(value))
        for key in kinds:
            columns[_flag_name(spec, key)][i] = key in record
        for source, flag in presence.items():
            columns[flag][i] = source in record

    for name, side in sides.items():
        rows, keys, values = side_rows[name]
        columns[f"{name}__row"] = np.asarray(rows, np.int32)
        columns[f"{name}__key"] = np.asarray(keys, DTYPES[side["key"]])
        columns[f"{name}__value"] = np.asarray(values, DTYPES[side["value"]])
    return columns, vocabs, ids


def write_columns(save_folder, entity, database):
    """Write one entity's columns beside its blobs. Best-effort: never raises."""
    try:
        columns, vocabs, ids = build_columns(database, entity)
        out = _column_dir(save_folder, entity)
        os.makedirs(out, exist_ok=True)
        np.save(os.path.join(out, "_id.npy"), ids)
        for name, array in columns.items():
            np.save(os.path.join(out, f"{name}.npy"), array)
        with open(os.path.join(out, "_meta.json"), "w") as f:
            json.dump({"version": FORMAT_VERSION, "rows": len(ids), "vocabs": vocabs}, f)
        return True
    except Exception as e:
        print(f"Column cache for {entity} not written ({type(e).__name__}: {e}); "
              "the dict path still applies")
        return False


def load_columns(save_folder, entity):
    """Memory-map an entity's columns as ``(columns, vocabs, ids)``.

    None means no usable cache: missing, written under another FORMAT_VERSION, or
    unreadable. Callers fall back to the dict path.
    """
    out = _column_dir(save_folder, entity)
    meta_path = os.path.join(out, "_meta.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        if meta.get("version") != FORMAT_VERSION:
            return None
        columns = {}
        for name in os.listdir(out):
            if name.endswith(".npy") and name != "_id.npy":
                columns[name[:-4]] = np.load(os.path.join(out, name), mmap_mode="r")
        ids = np.load(os.path.join(out, "_id.npy"), mmap_mode="r")
        return columns, meta["vocabs"], ids
    except Exception:
        return None


def code_of(vocabs, field, value):
    """The int code a dictionary-encoded string was stored as, or -1 if unseen."""
    try:
        return vocabs[field].index(value)
    except (KeyError, ValueError):
        return -1


# ---------------------------------------------------------------------------
# Reconstruction
# ---------------------------------------------------------------------------

def _text(value):
    """A stored scalar back as the string the tree holds.

    Floats are formatted positionally, never in scientific notation.
    """
    if isinstance(value, (bool, np.bool_)):
        return "yes" if value else "no"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return np.format_float_positional(float(value), trim="-")


def rebuild_record(row, columns, vocabs, entity):
    """The record at ``row``, rebuilt from the columns.

    Keys are emitted in the schema's ``order``, filtered by this row's presence flags.
    """
    spec = entity_schema(entity)
    fields = spec["fields"]
    arrays = spec.get("arrays", {})
    kinds = _record_keys(spec)
    # record key -> the flat fields lifted out of it, for reassembling sub-objects.
    groups = {}
    for name, field in fields.items():
        if "path" in field:
            groups.setdefault(field["path"][0], []).append((name, field))

    def scalar(name, field):
        if field["type"] == "dict":
            code = int(columns[name][row])
            return vocabs[name][code] if code >= 0 else None
        return _text(columns[name][row])

    record = {}
    for key in spec.get("order", list(kinds)):
        kind = kinds.get(key)
        if kind is None or not bool(columns[_flag_name(spec, key)][row]):
            continue
        which, name = kind
        if which == "field":
            value = scalar(key, fields[key])
            if value is not None:
                record[key] = value
        elif which == "group":
            sub = {}
            for member, field in groups[key]:
                value = scalar(member, field)
                if value is not None:
                    sub[field["path"][-1]] = value
            record[key] = sub
        elif which == "array":
            rebuilt = _rebuild_array(row, name, arrays[name], columns)
            if rebuilt is not None:
                record[key] = rebuilt
        elif which == "side":
            record[key] = _rebuild_side(row, name, columns)
    return record


def _rebuild_array(row, name, array, columns):
    """One bounded slot list, in whichever of the two shapes it was written."""
    form = int(columns[f"{name}__form"][row])
    if form == FORM_ABSENT:
        return None
    values = columns[name][row]
    if form == FORM_LIST:
        length = int(columns[f"{name}__len"][row])
        node = {"field_type": "list", "value": [_text(v) for v in values[:length]]}
    else:
        node = {}
        index0 = int(columns[f"{name}__index0"][row])
        if index0 >= 0:
            node["index0"] = str(index0)
        default = array.get("default", 0)
        for slot, value in enumerate(values):
            if float(value) != float(default):
                node[str(slot)] = _text(value)
    # Re-nest under any intermediate path steps the array sits beneath.
    path = array["path"]
    for step in reversed(path[1:]):
        node = {step: node}
    return node


def _rebuild_side(row, name, columns):
    """One ragged key -> value map, from the side table's three arrays."""
    rows = columns[f"{name}__row"]
    keys = columns[f"{name}__key"]
    values = columns[f"{name}__value"]
    where = np.nonzero(np.asarray(rows) == row)[0]
    return {str(int(keys[j])): _text(values[j]) for j in where}


def validate_roundtrip(database, entity, columns=None, vocabs=None, limit=None):
    """Rebuild every record from the columns and diff it against the tree.

    Returns ``[(id, {missing, extra, changed})]`` for records that did not
    reproduce; empty when every record round-trips.
    """
    if columns is None:
        columns, vocabs, _ids = build_columns(database, entity)
    records = [(k, v) for k, v in database.items() if isinstance(v, dict)]
    if limit is not None:
        records = records[:limit]
    problems = []
    for row, (key, original) in enumerate(records):
        rebuilt = rebuild_record(row, columns, vocabs, entity)
        if rebuilt == original:
            continue
        missing = [k for k in original if k not in rebuilt]
        extra = [k for k in rebuilt if k not in original]
        changed = [k for k in original if k in rebuilt and rebuilt[k] != original[k]]
        problems.append((key, {"missing": missing, "extra": extra, "changed": changed}))
    return problems
