# ==============================================================================
# explore_contract.py - Detective work for the DATA CONTRACT (A2): the assumptions
# that bind everything - grain per table, timezone, and the definitions of
# "account" and "fraud". Each answer becomes a documented assumption. Fully offline.
# Run:  python exploration/explore_contract.py
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

TZ_MARK = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")   # an ISO-8601 offset or a trailing 'Z'


def banner(t):
    print("\n" + "=" * 74 + f"\n {t}\n" + "=" * 74)


# --- Q1: timezone - are the source timestamps UTC, local, or naive? -----------
banner("Q1 - Timezone: what do the source timestamps actually carry?")
raw = {
    "players.created_at": json.load(open(DATA / "players.json", encoding="utf-8"))[0]["created_at"],
    "sessions.timestamp": json.load(open(DATA / "sessions.json", encoding="utf-8"))[0]["timestamp"],
    "transactions.timestamp": pd.read_csv(DATA / "transactions.csv", dtype=str)["timestamp"].iloc[0],
}
for name, sample in raw.items():
    print(f"{name:<24} e.g. {sample!r:<34} tz-marker? {bool(TZ_MARK.search(sample))}")
print("-> no offset / no 'Z' anywhere => the timestamps are NAIVE.")
print("   (players.created_at is date-only: no time-of-day - FTD timing comes from transactions.)")

# --- Q2: grain - what is one row of each table, really? -----------------------
banner("Q2 - Grain: one row = ? (uniqueness + hidden logical duplicates)")
print("players     : rows", len(players), "| unique player_id:", players.player_id.is_unique,
      "-> grain = 1 player")
print("sessions    : rows", len(sessions), "| unique session_id:", sessions.session_id.is_unique,
      "| dup (player,timestamp):", int(sessions.duplicated(["player_id", "timestamp"]).sum()),
      "-> grain = 1 session")
print("transactions: rows", len(tx), "| unique transaction_id:", tx.transaction_id.is_unique,
      "| dup (player,type,amount,timestamp):",
      int(tx.duplicated(["player_id", "type", "amount", "timestamp"]).sum()), "-> grain = 1 transaction")

# --- Q2b: the affiliate grain is the ambiguous one - ANALYZE it, don't assume --
banner("Q2b - Affiliate grain: what is one row, really? (analysis, not assumption)")
print("rows:", len(aff), "| affiliates:", aff.affiliate_id.nunique(), "| players:", aff.player_id.nunique(),
      "| distinct (aff,player) pairs:", aff.groupby(["affiliate_id", "player_id"]).ngroups,
      "| full-row dups:", int(aff.duplicated().sum()))
print("rows per affiliate (min/median/max):",
      aff.groupby("affiliate_id").size().agg(["min", "median", "max"]).to_dict())
print("funnel magnitude - clicks mean:", round(aff.clicks.mean(), 1),
      "(one player makes ~1 click; ~100 => the funnel is AFFILIATE-level, not per-player)")
multi = aff.groupby("player_id").filter(lambda g: len(g) > 1)
differ = int((multi.groupby("player_id").clicks.nunique() > 1).sum())
print("players with >1 row whose clicks DIFFER across rows:", differ, "of", multi.player_id.nunique(),
      "(=> funnel is NOT a property of the player, and NOT a constant affiliate total => not denormalized)")
print("no time/period/campaign column => nothing legitimately separates the ~40 rows per affiliate.")
print("-> CONCLUSION: a CONFLATED grain - affiliate-level funnel metrics on a per-player-tagged row")
print("   with no reporting key. Not a clean dimension, not a valid per-player record. So: never sum")
print("   clicks/registrations/ftd/cpa per row; derive the real FTD from transactions; resolve one")
print("   affiliate per player (ADR-0004).")

# --- Q3: "account" - what identity does one row represent? --------------------
banner("Q3 - Definition of 'account': is player_id the account key?")
print("players:", len(players), "| distinct player_id:", players.player_id.nunique(),
      "| distinct email (lowercased):", players.email.str.lower().nunique())
print("-> 1 player_id = 1 email = 1 ACCOUNT. A natural person may hold several accounts")
print("   (multi-accounting) - inferred from shared ip/device, not a hard key in the data.")

# --- Q4: fraud SCOPE (boundary only - the specific signals belong to the Gold phase) --
banner("Q4 - Fraud scope: what does the available data bound? (signals -> Gold)")
print("transaction types present:", sorted(tx.type.unique()))
print("session context (ip / device)?", {"ip", "device"} <= set(sessions.columns),
      "| affiliate context (ftd / cpa)?", {"ftd", "cpa_value"} <= set(aff.columns))
print("bonus data?", "bonus" in set(tx.type.unique()),
      "| chargeback data?", "chargeback" in set(tx.type.unique()),
      "-> bonus abuse & chargeback fraud are OUT OF SCOPE (no such data).")
print("The specific fraud signals are designed and discovered in the GOLD layer,")
print("not enumerated in the contract.")

# --- Conclusion: the contract (evidence for ADR-0006) ------------------------
banner("Conclusion - the data contract")
print("- Grain: players/sessions/transactions have clean unique-key grains; affiliate is a CONFLATED")
print("  grain (affiliate-level funnel on a per-player-tagged row, no reporting key) -> resolve in Silver.")
print("- Timezone: source timestamps are naive -> treat as UTC (assumption); prod should emit ISO-8601 'Z'.")
print("- Account = player_id (1:1 with email). Person-level identity is a fraud inference (shared ip/device).")
print("- Fraud: bounded to the available data (no bonus/chargeback); the specific signals are a")
print("  Gold-phase design, not enumerated in the contract.")
