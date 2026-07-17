# ==============================================================================
# compare_attribution.py - Which affiliate attribution rule should Silver use?
#
# Context: the affiliate source has NO timestamp and a conflated grain (one player
# appears under many affiliates), so a true time-based last-touch is impossible.
# We compare deterministic, computable rules and gate on a REAL first deposit.
# Run:  python exploration/compare_attribution.py
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

players = pd.read_json(DATA_DIR / "players.json")
tx = pd.read_csv(DATA_DIR / "transactions.csv")
aff = pd.read_csv(DATA_DIR / "affiliate_cpa_ftd.csv")

# A player's REAL first deposit = they have any 'deposit' transaction. This is the
# ground truth for "did this player actually convert?" - independent of what the
# affiliate file claims.
real_ftd = set(tx[tx.type == "deposit"].player_id)


def report(name, credited):
    print(f"\n{name}")
    print(f"   players attributed : {credited.player_id.nunique()}")
    print(f"   total CPA implied  : {credited.cpa_value.sum():,}")


print("players total:", len(players),
      "| in affiliate file:", aff.player_id.nunique(),
      "| real FTD (real deposit):", len(real_ftd))

# R1 - naive: the first affiliate row seen for each player.
r1 = aff.drop_duplicates("player_id", keep="first")
report("R1 - first affiliate by file order (naive)", r1)

# R2 - the affiliate that CLAIMS the FTD (ftd > 0), with a deterministic tiebreak:
#      highest cpa_value, then lowest affiliate_id.
claim = aff[aff.ftd > 0].sort_values(
    ["player_id", "cpa_value", "affiliate_id"], ascending=[True, False, True])
r2 = claim.drop_duplicates("player_id", keep="first")
report("R2 - affiliate claiming the FTD, deterministic tiebreak", r2)

# R3 - R2 but only for players with a REAL deposit. No real FTD => no CPA.
#      This is the anti-fraud gate: ghost FTDs get credited nothing.
r3 = r2[r2.player_id.isin(real_ftd)]
report("R3 - claim-FTD gated on a real deposit (CHOSEN)", r3)

print("\nwhy R3:")
print("   ghost FTDs excluded (claimed, no real deposit):", len(set(r2.player_id) - real_ftd))
print("   CPA overcount avoided vs R2                   :", f"{r2.cpa_value.sum() - r3.cpa_value.sum():,}")
print("   real-FTD players with no affiliate to credit  :", len(real_ftd - set(aff.player_id)))

# How solid is the tiebreak? Count the real-FTD players where >1 affiliate claims the FTD
# (the rows where the deterministic tiebreak actually decides). This is the known limit of R3:
# without a timestamp the winner is a proxy, not ground truth (documented in ADR-0004).
_claims = aff[aff.ftd > 0].groupby("player_id").affiliate_id.nunique()
print("   real-FTD players claimed by >1 affiliate (tiebreak decides):",
      int((_claims[_claims.index.isin(real_ftd)] > 1).sum()))
