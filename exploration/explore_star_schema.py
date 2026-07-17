# ==============================================================================
# explore_star_schema.py - Detective work for the Gold star schema (A3 Medallion):
# which entities become dimensions vs facts, each fact's grain and measure, the
# BigQuery physical design (partition + cluster), and materialization by size.
# Fully offline. Run:  python exploration/explore_star_schema.py
# ==============================================================================
import os
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


# --- Q1: dimensions vs facts (cardinality + descriptive-or-measure) -----------
banner("Q1 - Dimension or fact? (cardinality + descriptive vs measure)")
print("dim candidates (descriptive entities):")
print("  dim_player   :", players.player_id.nunique(), "players; attrs:",
      [c for c in players.columns if c != "player_id"])
print("  dim_affiliate:", aff.affiliate_id.nunique(), "affiliates (resolved in Silver)")
print("low-cardinality categoricals (degenerate dims / attributes):")
print("  device:", sorted(sessions.device.unique()), "| tx type:", sorted(tx.type.unique()),
      "| cities:", players.city.nunique(), "| affiliate countries:", sorted(aff.country.unique()))
print("-> descriptive entities => dims (player, affiliate, date); tiny categoricals => degenerate dims.")

# --- Q2: facts - grain, measure, and the BigQuery physical design -------------
banner("Q2 - Facts: grain, measure, partition + cluster")
tx["d"] = pd.to_datetime(tx.timestamp).dt.date
sessions["d"] = pd.to_datetime(sessions.timestamp).dt.date
print("fct_transactions: grain = 1 transaction | measure = amount | rows:", len(tx),
      "| date span (days):", (max(tx.d) - min(tx.d)).days,
      "| player_id cardinality:", tx.player_id.nunique())
print("fct_sessions    : grain = 1 session | attrs = ip/device | rows:", len(sessions),
      "| date span (days):", (max(sessions.d) - min(sessions.d)).days,
      "| player_id cardinality:", sessions.player_id.nunique())
print("-> partition by DATE(timestamp) (day granularity, matches the date-range filters);")
print("   cluster by player_id (the most-used join/filter key). Highest-card, most-filtered first.")

# --- Q3: referential integrity (every fact FK exists in its dim) --------------
banner("Q3 - Referential integrity: facts -> dim_player")
ids = set(players.player_id)
print("transactions.player_id all in dim_player?", tx.player_id.isin(ids).all(),
      "| sessions.player_id all in dim_player?", sessions.player_id.isin(ids).all())
print("-> enforced later by dbt relationships tests.")

# --- Q4: materialization by size ---------------------------------------------
banner("Q4 - Materialization by size")
print("dims are tiny  -> player:", players.player_id.nunique(), "| affiliate:", aff.affiliate_id.nunique(),
      "=> full TABLE, no partition needed.")
print("facts are the big / growing ones => partition + cluster + incremental.")

# --- Conclusion: the Gold star schema + physical design (evidence for ADR-0007) --
banner("Conclusion - Gold star schema + physical design")
print("- Dimensions: dim_player (SCD-1), dim_affiliate, dim_date. Degenerate dims: transaction_type, device.")
print("- Facts: fct_transactions & fct_sessions -> partition DATE(timestamp), cluster player_id;")
print("         fct_fraud_signals -> grain = 1 player.")
print("- Materialization: staging = view, intermediate = table, marts = table; facts incremental")
print("  (merge for transactions = money/idempotent; insert_overwrite for sessions = high-volume events).")
