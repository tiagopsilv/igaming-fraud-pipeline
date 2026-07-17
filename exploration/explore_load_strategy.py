# ==============================================================================
# explore_load_strategy.py - Detective work for the LOAD STRATEGY (E4): for each
# source, does the data support incremental loading? We look for a watermark (a
# timestamp to filter new rows), a unique key (for an idempotent merge), and a
# change-tracking column (updated_at). That decides full vs incremental. Offline.
# Run:  python exploration/explore_load_strategy.py
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


# --- Q1: control fields - what does each source give us to load incrementally? --
banner("Q1 - Control fields: watermark, unique key, change-tracking (updated_at)?")
print("players     : unique key?", players.player_id.is_unique,
      "| watermark: created_at (DATE-only) | updated_at?", "updated_at" in set(players.columns))
print("sessions    : unique key?", sessions.session_id.is_unique,
      "| watermark: timestamp (event time) | updated_at?", "updated_at" in set(sessions.columns))
print("transactions: unique key?", tx.transaction_id.is_unique,
      "| watermark: timestamp | updated_at?", "updated_at" in set(tx.columns))
print("affiliate   : unique key? False (conflated grain)",
      "| watermark: NONE (no date column) | updated_at?", "updated_at" in set(aff.columns))

# --- Q2: nature + volume - what KIND of load does each one need? --------------
banner("Q2 - Nature + volume")
print("players     : dimension         | rows", len(players), "| immutable, no change tracking")
print("sessions    : append-only event | rows", len(sessions), "| high volume, event-time")
print("transactions: financial ledger  | rows", len(tx), "| append; id + time => idempotent merge")
print("affiliate   : aggregate/report  | rows", len(aff), "| restated; no date => no watermark")

# --- Q3: the incremental strategy where the data supports it ------------------
banner("Q3 - Incremental strategy (only where the data supports it)")
print("sessions     -> INCREMENTAL insert_overwrite (day partition): append-only, high volume, no unique key.")
print("transactions -> INCREMENTAL merge on transaction_id: money -> a rerun must NOT duplicate (idempotent).")
print("players      -> FULL refresh: small dim; no updated_at to drive incremental (SCD-2 in production).")
print("affiliate    -> FULL refresh: small; no date column for a watermark (a restated report).")

# --- Conclusion: the E4 load-strategy table (evidence for ADR-0008) -----------
banner("Conclusion - load strategy per source (the E4 table)")
print(f"{'source':<13}{'frequency':<16}{'load':<14}{'control field':<30}justification")
print(f"{'players':<13}{'daily':<16}{'full':<14}{'-':<30}small dim, no updated_at")
print(f"{'sessions':<13}{'hourly/near-RT':<16}{'incremental':<14}{'timestamp':<30}high-volume append event")
print(f"{'transactions':<13}{'hourly/daily':<16}{'incremental':<14}{'transaction_id + timestamp':<30}financial ledger, idempotent")
print(f"{'affiliate':<13}{'daily':<16}{'full':<14}{'-':<30}restated aggregate, no date column")
