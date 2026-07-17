# ==============================================================================
# arch_discovery.py - Architecture-discovery questions (feeds A3 Medallion design).
#
# The explorer becomes the architect: before drawing a star schema, ask the data
# the Kimball questions - grain, dimensions, SCD need, and fan-out risk.
# Run:  python exploration/arch_discovery.py
# ==============================================================================

import os
from pathlib import Path

import pandas as pd

# In-repo sample by default (relative), so it runs on a fresh clone. Override with OTG_DATA_DIR.
DATA_DIR = Path(os.environ.get("OTG_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")

# Safety: fully OFFLINE (local sample, no GCP). Clear message if the sample is missing.
if not (DATA_DIR / "players.json").exists():
    raise SystemExit(f"Sample data not found in {DATA_DIR}. Run from the repo root "
                     f"(the data/ folder is committed), or set OTG_DATA_DIR.")


def q(title):
    print("\n" + "=" * 74 + f"\n  {title}\n" + "=" * 74)


players = pd.read_json(DATA_DIR / "players.json")
sessions = pd.read_json(DATA_DIR / "sessions.json")
tx = pd.read_csv(DATA_DIR / "transactions.csv")
aff = pd.read_csv(DATA_DIR / "affiliate_cpa_ftd.csv")


# Q1 - GRAIN: what does one row of each fact represent? (Kimball step 2)
q("Q1 - Grain: is the candidate key really one row?")
print("transactions:", len(tx), "rows /", tx.transaction_id.nunique(), "distinct id -> grain = 1 transaction")
print("sessions    :", len(sessions), "rows /", sessions.session_id.nunique(), "distinct id -> grain = 1 session")


# Q2 - DIMENSIONS + cardinality (Kimball step 3; also drives cluster/partition)
q("Q2 - Dimensions and their cardinality")
print("players   :", players.player_id.nunique())
print("affiliates:", aff.affiliate_id.nunique())
print("cities    :", players.city.nunique())
print("devices   :", sessions.device.nunique(), sorted(sessions.device.unique()))
print("countries :", aff.country.nunique(), sorted(aff.country.unique()))
print("tx types  :", tx.type.nunique(), sorted(tx.type.unique()))
print("-> low-cardinality columns (device, type) are cluster keys / degenerate dims, not big dims")


# Q3 - SCD need: can we even build history? (is there a change-tracking column?)
q("Q3 - SCD: does dim_player need Type 2?")
print("players columns:", list(players.columns))
print("has 'updated_at'?", "updated_at" in players.columns,
      "-> no change tracking -> dim_player = SCD Type 1 (imposed by the data)")


# Q4 - RELATIONSHIP: is player <-> affiliate 1:1 or many-to-many?
q("Q4 - player <-> affiliate: one-to-one or many-to-many?")
pairs = aff.groupby(["affiliate_id", "player_id"]).ngroups
multi = int((aff.groupby("player_id").affiliate_id.nunique() > 1).sum())
print("distinct (affiliate,player) pairs:", pairs)
print("players under >1 affiliate       :", multi,
      "-> MANY-TO-MANY -> needs attribution resolution (or a bridge table)")


# Q5 - FAN-OUT danger: does joining affiliate to a fact inflate the measures?
q("Q5 - Fan-out: what happens if I naively join transactions x affiliate?")
tx["amount"] = pd.to_numeric(tx.amount)
true_rows, true_sum = len(tx), tx.amount.sum()
joined = tx.merge(aff, on="player_id", how="left")
print(f"before join: {true_rows} rows, amount sum {true_sum:,.2f}")
print(f"after  join: {len(joined)} rows, amount sum {joined.amount.sum():,.2f}")
print(f"-> {len(joined)/true_rows:.1f}x inflation. Resolve attribution in Silver BEFORE any fact join.")


# Q6 - FACT measure range -> NUMERIC precision choice
q("Q6 - Measure range for fct_transactions")
print("amount min/max:", tx.amount.min(), "/", tx.amount.max(), "-> NUMERIC(10,2) is enough")


# YOUR TURN: which attribution rule loses fewer players?
q("YOUR TURN - decide the attribution rule")
print("Compare 'affiliate of the real FTD' vs 'first affiliate seen': how many players")
print("end up with NO affiliate in each? That answer designs int_player_affiliate_attribution.")
