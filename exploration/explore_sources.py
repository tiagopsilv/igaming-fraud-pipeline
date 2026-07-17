# ==============================================================================
# explore_sources.py - Broad first-contact discovery (one-time, NOT the pipeline).
#
# Day-0 orientation: get to know the data and form early hypotheses. We pretend we
# know nothing and let it talk - each ACT answers one question and raises the next.
# Deeper flags it surfaces (money, affiliate) are pursued and ENFORCED later, in the
# layer they belong to - Bronze cast / dbt test / Gold signal / observability - not here.
# Discovery only; pandas is fine for ~1 MB but does NOT scale (at scale: SQL in the warehouse).
# Run:  python exploration/explore_sources.py
# ==============================================================================

import os
from pathlib import Path

import pandas as pd

# Reads the in-repo sample by default (relative to this script), so it runs on a fresh clone.
# Override with OTG_DATA_DIR to point elsewhere (e.g. another local folder).
DATA_DIR = Path(os.environ.get("OTG_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")

# Safety: this script is fully OFFLINE (local sample, no GCP). If the sample is missing,
# fail with a clear message instead of a stack trace - it always runs, or tells you why.
if not (DATA_DIR / "players.json").exists():
    raise SystemExit(f"Sample data not found in {DATA_DIR}. Run from the repo root "
                     f"(the data/ folder is committed), or set OTG_DATA_DIR.")


def act(title):
    """Print a section banner so the output reads like a story."""
    print("\n" + "=" * 74 + f"\n  {title}\n" + "=" * 74)


def profile(name, df, what, grain):
    """Get to know one source: what it is, its grain, and a per-column breakdown -
    dtype (type), distinct (cardinality), nulls, example values, and for a
    low-cardinality column its category counts / for a numeric one its range."""
    print(f"\n-- {name}: {df.shape[0]} rows x {df.shape[1]} cols")
    print(f"   WHAT IT IS: {what}")
    print(f"   GRAIN     : {grain}")
    for col in df.columns:
        s = df[col]
        examples = list(pd.Series(s.dropna().unique())[:3])
        print(f"   {col:<15} dtype={str(s.dtype):<8} distinct={s.nunique():<5} "
              f"nulls={int(s.isna().sum())}  e.g. {examples}")
        if pd.api.types.is_numeric_dtype(s):
            print(f"       range: {s.min()} .. {s.max()} (mean {s.mean():.2f})")
        elif s.nunique() <= 8:
            print(f"       categories: {s.value_counts().to_dict()}")


# Load the 4 sources. read_json handles the pretty-printed JSON arrays.
players = pd.read_json(DATA_DIR / "players.json")
sessions = pd.read_json(DATA_DIR / "sessions.json")
tx = pd.read_csv(DATA_DIR / "transactions.csv")
aff = pd.read_csv(DATA_DIR / "affiliate_cpa_ftd.csv")


# --------------------------------------------------------------------------
# ATO 0 - Know the base: what is each file, what is each column, how do they link?
# Goal: come out UNDERSTANDING the data before hunting for problems.
# Covers the checklist too: counts, types, nulls, cardinality.
# --------------------------------------------------------------------------
act("ATO 0 - Know the base: what each file is and what each column means")

# One entry per source: its business meaning + grain (what one row represents).
SOURCES = [
    ("players", players, "player registration - who the gamblers are",
     "1 row = 1 player"),
    ("sessions", sessions, "access logs - player behavior (ip / device / when)",
     "1 row = 1 session"),
    ("transactions", tx, "money movements: deposit / withdraw / bet",
     "1 row = 1 transaction"),
    ("affiliate", aff, "acquisition by affiliate (clicks / registrations / ftd / cpa)",
     "1 row = 1 affiliate record (grain is AMBIGUOUS - see ATO 1 and 6)"),
]
for name, df, what, grain in SOURCES:
    print(f"\nsample of {name}:")
    print(df.head(2).to_string())
    profile(name, df, what, grain)

# File format check: a JSON that starts with '[' is a pretty-printed ARRAY, not
# NDJSON -> bq load --source_format=NEWLINE_DELIMITED_JSON would FAIL on it.
print("\nfile format check:")
for f in ["players.json", "sessions.json"]:
    first = open(DATA_DIR / f, encoding="utf-8").read(1)
    print(f"   {f}: starts with {first!r} -> "
          f"{'ARRAY, must convert to NDJSON before bq load' if first == '[' else 'NDJSON ok'}")

# How the 4 files connect: player_id is the spine that stitches everything.
print("\nhow they connect (player_id is the spine):")
ids0 = set(players.player_id)
all_linked = bool(sessions.player_id.isin(ids0).all()
                  and tx.player_id.isin(ids0).all()
                  and aff.player_id.isin(ids0).all())
print("   every child player_id exists in players?", all_linked)
print("   sessions per player (min/mean/max)    :",
      sessions.groupby("player_id").size().agg(["min", "mean", "max"]).round(1).to_dict())
print("   transactions per player (min/mean/max):",
      tx.groupby("player_id").size().agg(["min", "mean", "max"]).round(1).to_dict())
print("   affiliates per player (max)           :",
      int(aff.groupby("player_id").affiliate_id.nunique().max()),
      "-> the same player appears under many affiliates (conflated grain)")


# --------------------------------------------------------------------------
# ATO 1 - Are the keys trustworthy? (uniqueness + referential integrity)
# --------------------------------------------------------------------------
act("ATO 1 - Are the keys trustworthy?")
print("player_id unique?     ", players.player_id.is_unique)
print("session_id unique?    ", sessions.session_id.is_unique)
print("transaction_id unique?", tx.transaction_id.is_unique)

# Referential integrity: does every child player_id exist in players (no orphans)?
ids = set(players.player_id)
print("orphan sessions (player_id not in players):", int((~sessions.player_id.isin(ids)).sum()))
print("orphan transactions (player_id not in players):", int((~tx.player_id.isin(ids)).sum()))

# The affiliate file has no obvious key. Do (affiliate, player) pairs even hold?
pairs = aff.groupby(["affiliate_id", "player_id"]).ngroups
print(f"affiliate rows={len(aff)} but distinct (affiliate,player) pairs={pairs}"
      f"  -> {len(aff) - pairs} duplicated pairs. Grain is unclear!")


# --------------------------------------------------------------------------
# ATO 2 - Is anything missing / off? (coverage + email quirk)
# --------------------------------------------------------------------------
act("ATO 2 - Coverage and per-field quirks")
print("players with NO session    :", len(ids - set(sessions.player_id)))
print("players with NO transaction:", len(ids - set(tx.player_id)))
print("players NOT in affiliate   :", len(ids - set(aff.player_id)))
print("(remember: nulls were ZERO everywhere in ATO 0 -> first smell of synthetic data)")

# Email casing: mixing UPPER/lower breaks joins/dedup unless normalized.
upper = (players.email != players.email.str.lower()).sum()
print(f"\nemails with UPPERCASE letters: {upper} ({upper / len(players):.0%})"
      f"  -> normalize to lowercase in Silver")
print(f"distinct emails: {players.email.nunique()} of {len(players)}"
      f"  -> {'no real duplicates (normalization, not dedup)' if players.email.nunique() == len(players) else 'DUPLICATES'}")


# --------------------------------------------------------------------------
# ATO 3 - Do the timelines agree? (windows + tx before created_at)
# --------------------------------------------------------------------------
act("ATO 3 - Time windows per source")
players["created_at"] = pd.to_datetime(players.created_at)
sessions["ts"] = pd.to_datetime(sessions.timestamp)
tx["ts"] = pd.to_datetime(tx.timestamp)
for name, s in [("players.created_at", players.created_at),
                ("sessions.timestamp", sessions.ts),
                ("tx.timestamp", tx.ts)]:
    print(f"{name:<20}: {s.min().date()} -> {s.max().date()}  ({(s.max()-s.min()).days} days)")

# Temporal integrity: transactions dated BEFORE the account was created (impossible).
created_of_tx = tx.player_id.map(players.set_index("player_id").created_at)
before = (tx.ts.dt.normalize() < created_of_tx.dt.normalize()).sum()
print(f"transactions BEFORE the player's created_at: {int(before)} ({before/len(tx):.0%})"
      f"  -> impossible; DQ finding + assumption")


# --------------------------------------------------------------------------
# ATO 4 - Does the money make sense? (business logic + amount typing)
# --------------------------------------------------------------------------
act("ATO 4 - Does the money make sense?")
# Money arrives untyped in the CSV: check the RAW text before pandas guesses.
raw_amount = pd.read_csv(DATA_DIR / "transactions.csv", dtype=str).amount
print(f"amount in the raw file is TEXT, e.g. {raw_amount.iloc[0]!r}"
      f"  -> cast to NUMERIC (money), never FLOAT")

print("\ncount by type:\n", tx.type.value_counts().to_string())
print("\ntotal amount by type:\n", tx.groupby("type").amount.sum().to_string())

money = tx.pivot_table(index="player_id", columns="type", values="amount",
                       aggfunc="sum", fill_value=0)
for c in ["deposit", "withdraw", "bet"]:
    if c not in money:
        money[c] = 0
print("\nplayers who WITHDREW but never DEPOSITED:", int(((money.withdraw > 0) & (money.deposit == 0)).sum()))
print("players who BET but never DEPOSITED     :", int(((money.bet > 0) & (money.deposit == 0)).sum()))
print("players who withdrew MORE than deposited:", int((money.withdraw > money.deposit).sum()))
print("players who deposited but NEVER bet     :", int(((money.deposit > 0) & (money.bet == 0)).sum()))
print("-> impossible in a real balance system: the data is random.")
print("   (early flag -> pursued in Gold as fraud signals + as anomaly monitors in observability)")


# --------------------------------------------------------------------------
# ATO 5 - Can we catch multi-accounting? (IP / device)
# --------------------------------------------------------------------------
act("ATO 5 - Multi-accounting: players per IP vs IPs per player")
players_per_ip = sessions.groupby("ip").player_id.nunique()
print("distinct IPs:", sessions.ip.nunique(), "of", len(sessions), "sessions")
print("IPs shared by >1 player:", int((players_per_ip > 1).sum()),
      " -> 'players per IP' finds almost nothing")
ips_per_player = sessions.groupby("player_id").ip.nunique()
dev_per_player = sessions.groupby("player_id").device.nunique()
print("players on >1 IP    :", int((ips_per_player > 1).sum()), " (max IPs for one player:", int(ips_per_player.max()), ")")
print("players on >1 device:", int((dev_per_player > 1).sum()),
      " -> device alone is noise; the natural signal here is IP velocity per player")


# --------------------------------------------------------------------------
# ATO 6 - Is the affiliate telling the truth? (claim vs reality)
# --------------------------------------------------------------------------
act("ATO 6 - Affiliate claims vs financial reality")
n = len(aff)
print(f"rows ftd > registrations   : {(aff.ftd > aff.registrations).sum()} ({(aff.ftd > aff.registrations).mean():.0%})")
print(f"rows registrations > clicks: {(aff.registrations > aff.clicks).sum()} ({(aff.registrations > aff.clicks).mean():.0%})")
print(f"rows ftd > 0 but registrations == 0: {int(((aff.ftd > 0) & (aff.registrations == 0)).sum())}")

# Conflated grain: same player under many affiliates -> attribution is ambiguous.
aff_per_player = aff.groupby("player_id").affiliate_id.nunique()
print("players under >1 affiliate :", int((aff_per_player > 1).sum()), " -> pick an attribution rule and document it")

# The key cross-check: REAL FTD (a real deposit) vs what the affiliate CLAIMS.
real_ftd = set(tx[tx.type == "deposit"].player_id)
claimed_ftd = set(aff.groupby("player_id").ftd.sum().loc[lambda s: s > 0].index)
ghost = claimed_ftd - real_ftd
print(f"\naffiliate CLAIMS ftd for : {len(claimed_ftd)} players")
print(f"players with a REAL deposit: {len(real_ftd)} players")
print(f"=> GHOST FTDs (claimed, no real deposit): {len(ghost)}  <- the affiliate-fraud shape")

print("\nnaive SUM of cpa_value (WRONG, overcounts):", int(aff.cpa_value.sum()),
      "-> CPA is paid once per acquired player, not per row")
print("   (early flag -> attribution resolved in Silver; affiliate-fraud signal built in Gold)")


# --------------------------------------------------------------------------
# Closing - where these findings go (this was discovery, NOT the pipeline)
# --------------------------------------------------------------------------
act("Closing - each finding has a home in the pipeline")
print("type/format fixes (amount, dates, JSON->NDJSON)                 -> ingestion + Bronze stg_ models")
print("recurring assertions (ftd<=reg, no tx before created_at, ref-int) -> dbt tests")
print("ongoing profiling (nulls, volume, anomaly, schema drift)         -> observability")
print("design conclusions (grain, attribution, fan-out)                 -> ADRs + Silver/Gold models")
print("\nThis was the FIRST pass, not the last: more risks and fraud emerge as each layer is built.")
print("Your turn: add a question, e.g. 'which affiliate has the most ghost FTDs?'")
