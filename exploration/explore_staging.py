# ==============================================================================
# explore_staging.py - Discovery: what did the load ACTUALLY produce, and what
# must the stg_ layer fix? The raw is already in BigQuery, and its types are
# whatever autodetect inferred from the string content - which you CANNOT predict
# (it typed money as FLOAT). So Q1-Q2 query the REAL raw schema; Q3-Q5 measure the
# values offline. Run:  python exploration/explore_staging.py
# ==============================================================================

import csv
import json
import os
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("OTG_DATA_DIR") or REPO / "data")


def banner(t):
    print("\n" + "=" * 76 + f"\n {t}\n" + "=" * 76)


# --- config (same public config.toml as the loader) --------------------------
_cfg = tomllib.loads((REPO / "config.toml").read_text(encoding="utf-8")) if (REPO / "config.toml").exists() else {}


def conf(env, section, key, default):
    return os.environ.get(env) or _cfg.get(section, {}).get(key, default)


PROJECT = conf("OTG_GCP_PROJECT", "gcp", "project", "otg-igaming-case")
RAW = conf("OTG_RAW_DATASET", "bigquery", "raw_dataset", "raw")
KEYFILE = conf("OTG_GCP_KEYFILE", "gcp", "keyfile", "secrets/gcp-keyfile.json")
KEYFILE = KEYFILE if Path(KEYFILE).is_absolute() else str(REPO / KEYFILE)
TABLES = ["players", "sessions", "transactions", "affiliate_cpa_ftd"]

# --- Q1: the REAL raw schema - what did autodetect decide? -------------------
banner("Q1 - Real raw schema in BigQuery (autodetect's guess, MEASURED not assumed)")
try:
    from google.cloud import bigquery
    client = bigquery.Client.from_service_account_json(KEYFILE, project=PROJECT)
    schema = {}
    for t in TABLES:
        cols = client.get_table(f"{PROJECT}.{RAW}.{t}").schema
        schema[t] = {c.name: c.field_type for c in cols}
        typed = {n: ty for n, ty in schema[t].items() if not n.startswith("_")}
        print(f"{t:<18} {typed}")
    print("-> autodetect TYPED the columns from their string content. It is not all-STRING.")
    print("   RED FLAG: transactions.amount =", schema["transactions"]["amount"],
          "(money as FLOAT = rounding risk). cpa_value =", schema["affiliate_cpa_ftd"]["cpa_value"], ".")
    print("   Dates/timestamps came as DATE/TIMESTAMP; ids/text as STRING.")
except Exception as e:  # noqa: BLE001 - offline or no GCP: say so and stop cleanly
    raise SystemExit(f"Q1 needs BigQuery (the raw dataset + {KEYFILE}). Skipped: {e}")

# --- Q2: the cast contract = FIX what autodetect got wrong --------------------
banner("Q2 - Cast contract: standardize, and fix autodetect's mistakes")
TARGET = {
    "amount": "NUMERIC",        # was FLOAT -> money must be NUMERIC (ADR-0006)
    "cpa_value": "NUMERIC",     # was INTEGER -> money must be NUMERIC
    "clicks": "INT64", "registrations": "INT64", "ftd": "INT64",
    "created_at": "DATE",       # already DATE (safe_cast is a robust no-op)
    "timestamp": "TIMESTAMP",   # already TIMESTAMP (safe_cast robust)
}
for t in TABLES:
    fixes = {c: TARGET[c] for c in schema[t] if c in TARGET}
    print(f"{t:<18} cast: {fixes}")
print("-> safe_cast EVERY typed column: robust to autodetect drift AND fixes money (FLOAT/INT -> NUMERIC).")
print("   safe_cast(x as timestamp) works whether autodetect gave TIMESTAMP (no-op) or a STRING (parses).")

# --- Q3: rename + the layer boundary -----------------------------------------
banner("Q3 - Rename to target names (Bronze = rename + cast, nothing else)")
RENAME = {"transactions": {"type": "transaction_type", "timestamp": "txn_ts"},
          "sessions": {"timestamp": "session_ts"}}
for t in TABLES:
    print(f"{t:<18} rename: {RENAME.get(t) or 'none (already snake_case)'}")
print("-> only 'type'/'timestamp' get clearer names; the rest is already snake_case.")
print("   Business rules (email lowercase, real FTD, attribution) are NOT here - they are Silver.")


def values(name, key):
    """All raw values of one column, read from data/ (values equal what was loaded)."""
    f = {"players": "players.json", "sessions": "sessions.json"}.get(name)
    if f:
        return [r[key] for r in json.load(open(DATA / f, encoding="utf-8"))]
    with open(DATA / f"{name}.csv", newline="", encoding="utf-8") as fh:
        return [r[key] for r in csv.DictReader(fh)]


# --- Q4: cast safety - would any value fail the cast? ------------------------
banner("Q4 - Cast safety: any value that safe_cast would turn into NULL?")
import re  # noqa: E402
NUM = re.compile(r"^-?\d+(\.\d+)?$")
amt = values("transactions", "amount")
print(f"amount not numeric : {sum(not NUM.match(v) for v in amt)} of {len(amt)}")
for c in ("clicks", "registrations", "ftd", "cpa_value"):
    v = values("affiliate_cpa_ftd", c)
    print(f"{c:<14} not numeric: {sum(not NUM.match(x) for x in v)} of {len(v)}")
print("-> clean today; safe_cast means a bad value becomes NULL (caught by the not_null test), no crash.")

# --- Q5: test evidence - negatives, future, categories, duplicates, nulls ----
banner("Q5 - Test evidence (structural DQ -> the Bronze test list)")
amtf = [float(v) for v in amt]
print(f"amount <= 0            : {sum(a <= 0 for a in amtf)} of {len(amtf)}   -> test  amount > 0")
for c in ("clicks", "registrations", "ftd", "cpa_value"):
    v = [int(x) for x in values("affiliate_cpa_ftd", c)]
    print(f"{c:<14} < 0      : {sum(x < 0 for x in v)} of {len(v)}   (0 valid) -> test  {c} >= 0")
for name, key in (("players", "created_at"), ("sessions", "timestamp"), ("transactions", "timestamp")):
    print(f"{name}.{key:<11} max {max(v[:10] for v in values(name, key))}  -> test  ts <= current_timestamp()")
print("transaction_type:", sorted(set(values("transactions", "type"))))
print("device          :", sorted(set(values("sessions", "device"))))
print("country         :", sorted(set(values("affiliate_cpa_ftd", "country"))))
for name, pk in (("players", "player_id"), ("sessions", "session_id"), ("transactions", "transaction_id")):
    ids = values(name, pk)
    print(f"{name:<12} dup {pk:<14}: {len(ids) - len(set(ids))}   -> test  unique + not_null")
pairs = list(zip(values("affiliate_cpa_ftd", "affiliate_id"), values("affiliate_cpa_ftd", "player_id")))
print(f"affiliate    dup (aff,player) pairs : {len(pairs) - len(set(pairs))}   -> NO unique (grain -> Silver)")

# --- Conclusion: the Bronze (stg_) contract (evidence for ADR-0010) ----------
banner("Conclusion - the Bronze staging contract, per source")
print("- Autodetect TYPED the raw (measured, not assumed): timestamps->TIMESTAMP, created_at->DATE,")
print("  counts->INTEGER, and amount->FLOAT (a money field! the trap staging must fix).")
print("- stg_ safe_casts every typed column: amount/cpa_value->NUMERIC (never FLOAT), *ts->TIMESTAMP,")
print("  counts->INT64, created_at->DATE. safe_cast is robust to autodetect drift across batches.")
print("- rename: type->transaction_type, timestamp->txn_ts/session_ts; the rest already snake_case.")
print("- staging does rename + cast + audit passthrough ONLY; business rules live in Silver.")
print("- Bronze tests (structural, all pass here = guards): unique/not_null, accepted_values, amount>0,")
print("  counts>=0, no-future-ts, not-null-after-cast.")
print("Hunt-for-more later: a NEW batch where autodetect guesses DIFFERENT types (why we safe_cast).")
