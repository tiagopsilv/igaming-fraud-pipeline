# ==============================================================================
# explore_ingestion.py - Discovery: what must the ingestion layer handle?
#
# Before trusting a loader, hunt for everything that could break a load into
# BigQuery. Each question raises the next; the conclusion points every finding to
# where it is handled (the loader, a test, or the volume check). Fully offline.
# Run:  python exploration/explore_ingestion.py
# ==============================================================================

import csv
import io
import json
import os
import re
from pathlib import Path

DATA = Path(os.environ.get("OTG_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
if not (DATA / "players.json").exists():
    raise SystemExit(f"Sample data not found in {DATA}. Run from the repo root, or set OTG_DATA_DIR.")

JSON_FILES = ["players.json", "sessions.json"]
CSV_FILES = ["transactions.csv", "affiliate_cpa_ftd.csv"]
AUDIT = {"_ingested_at", "_source_file"}                 # columns the loader will add
BQ_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")         # BigQuery column-name rule


def banner(t):
    print("\n" + "=" * 72 + f"\n {t}\n" + "=" * 72)


# --- Q1: the crime scene - file-level facts -----------------------------------
banner("Q1 - File-level: size, BOM, newline style, valid UTF-8?")
for f in JSON_FILES + CSV_FILES:
    raw = (DATA / f).read_bytes()
    bom = raw[:3] == b"\xef\xbb\xbf"
    crlf = b"\r\n" in raw
    try:
        raw.decode("utf-8")
        enc = "utf8-ok"
    except UnicodeDecodeError:
        enc = "ENC-ISSUE"
    print(f"{f:<24} {len(raw)/1024:7.1f} KB  {'BOM' if bom else 'no-BOM':<7} "
          f"{'CRLF' if crlf else 'LF':<5} {enc}  starts={raw.lstrip()[:1]!r}")
print("-> CRLF sources: the loader must write NDJSON as LF (newline='\\n').")

# --- Q2: are the JSON records loadable? (array? flat? same schema?) -----------
banner("Q2 - JSON: array vs NDJSON, flat vs nested, schema consistency")
for f in JSON_FILES:
    data = json.load(open(DATA / f, encoding="utf-8"))
    nested = any(isinstance(v, (dict, list)) for r in data for v in r.values())
    schemas = {tuple(sorted(r.keys())) for r in data}
    print(f"{f:<16} {'ARRAY' if isinstance(data, list) else '?':<6} "
          f"{'NESTED' if nested else 'flat':<7} distinct key-sets={len(schemas)}")
print("-> array => must convert to NDJSON; flat + 1 schema => autodetect gives flat columns.")

# --- Q3: are the CSVs loadable? (delimiter, ragged, embedded newlines?) --------
banner("Q3 - CSV: delimiter, ragged rows, embedded newlines/quotes in fields")
for f in CSV_FILES:
    text = open(DATA / f, encoding="utf-8", newline="").read()
    delim = csv.Sniffer().sniff(text[:2000]).delimiter
    rows = list(csv.reader(io.StringIO(text)))
    ncols = len(rows[0])
    ragged = sum(1 for r in rows if len(r) != ncols)
    embedded = sum(1 for r in rows for c in r if "\n" in c or "\r" in c)
    print(f"{f:<24} delim={delim!r} cols={ncols} rows={len(rows)-1} "
          f"ragged={ragged} embedded_newline_fields={embedded}")
print("-> ragged/embedded-newline = 0 => the CSVs load cleanly once headed to NDJSON.")

# --- Q4: will the column names survive BigQuery? ------------------------------
banner("Q4 - Column names: valid for BigQuery? collide with the audit columns?")
cols = {f: list(json.load(open(DATA / f, encoding="utf-8"))[0].keys()) for f in JSON_FILES}
cols.update({f: next(csv.reader(open(DATA / f, encoding="utf-8", newline=""))) for f in CSV_FILES})
for f, cs in cols.items():
    bad = [c for c in cs if not BQ_NAME.match(c)]
    clash = [c for c in cs if c in AUDIT]
    print(f"{f:<24} invalid={bad or 'none'}  collide_with_audit={clash or 'none'}")
print("-> no invalid names, no collision => safe to add _ingested_at / _source_file.")

# --- Q5: volume baseline (feeds an ingestion volume check) --------------------
banner("Q5 - Volume baseline (expected row counts per source)")
for f in JSON_FILES:
    print(f"{f:<24} {len(json.load(open(DATA / f, encoding='utf-8')))}")
for f in CSV_FILES:
    print(f"{f:<24} {sum(1 for _ in open(DATA / f, encoding='utf-8')) - 1}")

# --- Conclusion: what the ingestion must handle (evidence for ADR-0005) -------
banner("Conclusion - what the ingestion must handle")
print("- JSON arrays -> convert to NDJSON.                         (loader)")
print("- CRLF sources -> write NDJSON as LF.                       (loader: newline='\\n')")
print("- flat JSON, 1 schema, no ragged/embedded newlines         => a clean autodetect load.")
print("- column names valid, no audit-column collision            => safe to add audit columns.")
print("- volume baseline 600/4000/1800/2000                       (future ingestion volume check).")
print("Hunt-for-more later: schema drift in new batches (a renamed or dropped column), truncated files, volume swings.")
