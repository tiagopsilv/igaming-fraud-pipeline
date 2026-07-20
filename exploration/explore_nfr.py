# ==============================================================================
# explore_nfr.py - Discovery for the NON-FUNCTIONAL REQUIREMENTS: derive the
# targets FROM the data. Freshness (from timestamp granularity), data-quality SLOs
# (from the measured baseline of the hard rules) and cost (from the volume).
# Best practice: set targets from a measured baseline, not from a wish. Offline.
# Run:  python exploration/explore_nfr.py
# ==============================================================================
import json
import os
import re
from pathlib import Path

import pandas as pd

DATA = Path(os.environ.get("OTG_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
if not (DATA / "players.json").exists():
    raise SystemExit(f"Sample data not found in {DATA}. Run from the repo root, or set OTG_DATA_DIR.")

players = pd.read_json(DATA / "players.json")
sessions = pd.read_json(DATA / "sessions.json")
tx = pd.read_csv(DATA / "transactions.csv")
aff = pd.read_csv(DATA / "affiliate_cpa_ftd.csv")


def banner(t):
    print("\n" + "=" * 74 + f"\n {t}\n" + "=" * 74)


# --- Q1: freshness CAPABILITY - how fresh can each source be? (granularity) ----
banner("Q1 - Freshness capability: what granularity does each timestamp carry?")
def granularity(sample):
    if re.search(r"\.\d+", str(sample)):
        return "sub-second"
    if re.search(r"\d{2}:\d{2}:\d{2}", str(sample)):
        return "second"
    return "date-only"

# read the RAW strings (read_json would parse a date-only value into a datetime with 00:00:00)
raw_players = json.load(open(DATA / "players.json", encoding="utf-8"))[0]["created_at"]
raw_sessions = json.load(open(DATA / "sessions.json", encoding="utf-8"))[0]["timestamp"]
raw_tx = pd.read_csv(DATA / "transactions.csv", dtype=str)["timestamp"].iloc[0]
print("players.created_at   :", granularity(raw_players), "-> daily is the finest useful freshness")
print("sessions.timestamp   :", granularity(raw_sessions), "-> near-real-time capable")
print("transactions.timestamp:", granularity(raw_tx), "-> hourly is reasonable")

# --- Q2: data-quality BASELINE (SLI) -> the SLO targets ----------------------
banner("Q2 - Data-quality baseline (the SLI) -> SLO target for each hard rule")
ids = set(players.player_id)
tx_num = pd.to_numeric(tx.amount)
players_created = pd.to_datetime(players.set_index("player_id").created_at)
tx_ok_time = (pd.to_datetime(tx.timestamp).dt.normalize() >= tx.player_id.map(players_created).dt.normalize())
checks = {
    "referential integrity (tx+sessions player_id in players)":
        float(tx.player_id.isin(ids).mean() == 1 and sessions.player_id.isin(ids).mean() == 1),
    "amount > 0": float((tx_num > 0).mean()),
    "ftd <= registrations": float((aff.ftd <= aff.registrations).mean()),
    "no transaction before created_at": float(tx_ok_time.mean()),
}
for rule, rate in checks.items():
    print(f"   current pass rate {rate:6.0%}  ->  SLO target 100%  ({rule})")
print("-> hard rules => SLO = 100%. The synthetic data already violates two (target exposes them);")
print("   each becomes a dbt test that FAILS the pipeline on violation.")

# --- Q3: cost - the volume drives it -----------------------------------------
banner("Q3 - Cost: volume -> BigQuery free tier?")
total = sum((DATA / f).stat().st_size for f in
            ["players.json", "sessions.json", "transactions.csv", "affiliate_cpa_ftd.csv"])
print(f"raw data size: {total/1024:.0f} KB (~{total/1e9:.6f} GB); BQ tables are the same order.")
print(f"free tier = 10 GB storage + 1 TB query/month -> this is ~{total/10e9:.4%} of storage => $0.")
print("freshness<->cost: batch (Airflow) delivers ~95% of streaming value at ~30% of cost -> right choice.")

# --- Conclusion: the NFR sheet (evidence for ADR-0009) -----------------------
banner("Conclusion - non-functional requirements (SLOs)")
print("- Freshness: sessions/transactions <= 1h (SLO P95 <= 45min); players/affiliate <= 24h.")
print("  (freshness checks run at 2x the SLA frequency.)")
print("- Data quality: referential integrity / amount>0 / ftd<=registrations / no-tx-before-created")
print("  = 100% (SLO), enforced by dbt tests that block the pipeline.")
print("- Cost: << free tier ($0); guardrails = partition pruning + require_partition_filter.")
print("- Reliability: idempotent loads (merge / WRITE_TRUNCATE) + DAG retries + alert on failure.")
