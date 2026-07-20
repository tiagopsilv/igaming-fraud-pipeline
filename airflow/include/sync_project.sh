#!/usr/bin/env bash
# Copy the single-source-of-truth dbt project (and the ingestion code it orchestrates) into the
# Astro project so the image/containers are self-contained. The dbt project is EDITED and TESTED
# at repo-root ../dbt; this makes a build-time copy under include/ (which is gitignored). Run this
# before `astro dev start` / `astro dev restart` whenever the dbt project or ingestion changes.
#
# IMPORTANT: load_raw.py resolves REPO = <its parent>/.. = include/, and reads config.toml and the
# data/ folder RELATIVE TO REPO. So include/ must MIRROR the repo root: ingestion/, data/,
# config.toml as siblings (not nested inside ingestion/).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # .../airflow/include
repo="$(cd "$here/../.." && pwd)"                         # repo root

echo "Syncing dbt project + ingestion into include/ (mirroring the repo layout) ..."
rm -rf "$here/dbt" "$here/ingestion" "$here/data" "$here/config.toml"

# dbt project. Drop target/logs (env-specific), but KEEP dbt_packages: the bind-mount hides the
# image's installed packages, so the mounted copy must carry them or dbt errors "run dbt deps".
# dbt_packages is portable (package source only). If it is missing (fresh clone), run `dbt deps`
# in ../dbt first.
mkdir -p "$here/dbt"
cp -r "$repo/dbt/." "$here/dbt/"
rm -rf "$here/dbt/target" "$here/dbt/logs"
if [ ! -d "$here/dbt/dbt_packages" ] || [ -z "$(ls -A "$here/dbt/dbt_packages" 2>/dev/null)" ]; then
  echo "WARNING: dbt_packages not found - run 'dbt deps' in ../dbt before starting Airflow."
fi

# ingestion code + the public config and sample data it reads, placed so REPO=include resolves them
cp -r "$repo/ingestion" "$here/ingestion"
rm -rf "$here/ingestion/__pycache__" "$here/ingestion/_ndjson"
cp "$repo/config.toml" "$here/config.toml"
mkdir -p "$here/data" && cp -r "$repo/data/." "$here/data/"

echo "Done. include/ mirrors the repo: ingestion/, data/, config.toml, dbt/ (secrets/ stays separate)."
