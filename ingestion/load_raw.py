# ==============================================================================
# load_raw.py - Ingestion: land the source files into the BigQuery `raw` dataset.
#
# Design (each choice backed by best practice):
#  - Config lives in a committed config.toml (public defaults, documented) so a fresh
#    clone runs with no setup; any value is overridable by an env var (prod/CI). The
#    only secret (the keyfile) stays gitignored - the repo can be open-sourced safely.
#  - Every source is normalized to NDJSON (BigQuery's only JSON shape) and gets two
#    audit columns: _ingested_at, _source_file (immutable-landing practice).
#  - Idempotent load: WRITE_TRUNCATE recreates the table atomically, so a rerun (or
#    a retry after a failure) yields the same result - always safe to run again.
#  - `raw` mirrors the sources 1:1 (no business logic). Bronze stg_ models read it.
#
# Run:  python ingestion/load_raw.py
#   OTG_SKIP_LOAD=1  -> only build the NDJSON (no BigQuery calls); test the conversion first.
# ==============================================================================

import csv
import json
import os
import tomllib                       # stdlib (Python 3.11+): reads config.toml
from datetime import datetime, timezone
from pathlib import Path

# --- Config: committed config.toml (public defaults) with env-var override -----
REPO = Path(__file__).resolve().parent.parent
_cfg = {}
if (REPO / "config.toml").exists():
    with open(REPO / "config.toml", "rb") as f:
        _cfg = tomllib.load(f)


def conf(env_name, section, key, default):
    """Precedence: env var (prod/CI) > config.toml (committed) > built-in default."""
    return os.environ.get(env_name) or _cfg.get(section, {}).get(key, default)


PROJECT = conf("OTG_GCP_PROJECT", "gcp", "project", "otg-igaming-case")
LOCATION = conf("OTG_BQ_LOCATION", "gcp", "location", "US")
RAW_DATASET = conf("OTG_RAW_DATASET", "bigquery", "raw_dataset", "raw")
_keyfile = conf("OTG_GCP_KEYFILE", "gcp", "keyfile", "secrets/gcp-keyfile.json")
_source = conf("OTG_SOURCE_DIR", "source", "dir", "data")
# resolve relative paths against the repo root, so it works from anywhere
KEYFILE = str(Path(_keyfile) if Path(_keyfile).is_absolute() else REPO / _keyfile)
SOURCE_DIR = Path(_source) if Path(_source).is_absolute() else REPO / _source
STAGE_DIR = REPO / "ingestion" / "_ndjson"                             # normalized NDJSON (gitignored)
SKIP_LOAD = os.environ.get("OTG_SKIP_LOAD") == "1"

# source file -> raw table name + format
SOURCES = [
    ("players.json", "players", "json"),
    ("sessions.json", "sessions", "json"),
    ("transactions.csv", "transactions", "csv"),
    ("affiliate_cpa_ftd.csv", "affiliate_cpa_ftd", "csv"),
]


def rows_from(path, fmt):
    """Yield one record dict per row. CSV streams; the small JSON arrays use json.load.
    (At real scale a huge JSON would be streamed with ijson, or already land as NDJSON.)"""
    if fmt == "csv":
        with open(path, newline="", encoding="utf-8") as f:
            yield from csv.DictReader(f)
    else:
        with open(path, encoding="utf-8") as f:
            yield from json.load(f)          # the file is a pretty-printed JSON array


def to_ndjson(src_path, out_path, src_name, fmt):
    """Normalize one source file to NDJSON, adding immutable-landing audit columns.
    Returns the row count. Pure I/O on the given paths -> easy to unit-test."""
    ingested_at = datetime.now(timezone.utc).isoformat()
    n = 0
    # newline="\n": force LF endings (the source files are CRLF on Windows; NDJSON must be
    # consistently newline-delimited). Discovered by exploration/explore_ingestion.py.
    with open(out_path, "w", encoding="utf-8", newline="\n") as w:
        for rec in rows_from(src_path, fmt):
            rec["_ingested_at"] = ingested_at
            rec["_source_file"] = src_name
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def load_ndjson(client, ndjson_path, table):
    """Idempotent load: WRITE_TRUNCATE recreates the table atomically."""
    from google.cloud import bigquery
    table_id = f"{PROJECT}.{RAW_DATASET}.{table}"
    cfg = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,   # <- idempotent
    )
    with open(ndjson_path, "rb") as f:
        client.load_table_from_file(f, table_id, job_config=cfg, location=LOCATION).result()
    print(f"  loaded   {table:<18} {client.get_table(table_id).num_rows:>5} rows -> {table_id}")


def main():
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"source: {SOURCE_DIR}")
    print("== prepare (normalize to NDJSON + audit columns) ==")
    prepared = []
    for src, table, fmt in SOURCES:
        out = STAGE_DIR / f"{table}.ndjson"
        n = to_ndjson(SOURCE_DIR / src, out, src, fmt)
        print(f"  prepared {table:<18} {n:>5} rows -> {out.name}")
        prepared.append((out, table))

    if SKIP_LOAD:
        print("\nOTG_SKIP_LOAD=1 -> skipping BigQuery load (conversion only).")
        return

    from google.cloud import bigquery
    client = bigquery.Client.from_service_account_json(KEYFILE, project=PROJECT)
    client.create_dataset(bigquery.Dataset(f"{PROJECT}.{RAW_DATASET}"), exists_ok=True)
    print(f"\n== load into {PROJECT}.{RAW_DATASET} (WRITE_TRUNCATE, idempotent) ==")
    for out, table in prepared:
        load_ndjson(client, out, table)
    print("\nDone. Bronze staging models can now read the `raw` dataset via source().")


if __name__ == "__main__":
    main()
