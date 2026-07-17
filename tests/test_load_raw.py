# tests/test_load_raw.py - unit tests for the ingestion loader (pytest).
# Cover the pure logic: config precedence, record reading, and NDJSON conversion
# (audit columns, LF endings, valid-JSON lines). No BigQuery is touched.
import json
import sys
from pathlib import Path

# Put ingestion/ on the path so `import load_raw` works both under pytest and when this
# file is run directly. (pyrightconfig.json resolves it for the editor's analyzer.)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))
import load_raw  # noqa: E402


# --- config precedence: env var > config.toml > built-in default ---------------
def test_conf_env_var_wins(monkeypatch):
    monkeypatch.setenv("OTG_GCP_PROJECT", "from-env")
    assert load_raw.conf("OTG_GCP_PROJECT", "gcp", "project", "fallback") == "from-env"


def test_conf_falls_back_to_config_toml(monkeypatch):
    monkeypatch.delenv("OTG_GCP_PROJECT", raising=False)
    monkeypatch.setattr(load_raw, "_cfg", {"gcp": {"project": "from-toml"}})
    assert load_raw.conf("OTG_GCP_PROJECT", "gcp", "project", "fallback") == "from-toml"


def test_conf_uses_default(monkeypatch):
    monkeypatch.delenv("OTG_ANYTHING", raising=False)
    monkeypatch.setattr(load_raw, "_cfg", {})
    assert load_raw.conf("OTG_ANYTHING", "sec", "key", "the-default") == "the-default"


# --- reading records from each source format -----------------------------------
def test_rows_from_csv(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    assert list(load_raw.rows_from(p, "csv")) == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]


def test_rows_from_json_array(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    assert list(load_raw.rows_from(p, "json")) == [{"a": 1}, {"a": 2}]


# --- the core conversion: audit columns, LF, valid NDJSON ----------------------
def test_to_ndjson_adds_audit_columns(tmp_path):
    src = tmp_path / "players.json"
    src.write_text('[{"player_id": "pl_1"}, {"player_id": "pl_2"}]', encoding="utf-8")
    out = tmp_path / "players.ndjson"
    n = load_raw.to_ndjson(src, out, "players.json", "json")
    assert n == 2
    recs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert all(r["_source_file"] == "players.json" for r in recs)
    assert all("_ingested_at" in r for r in recs)
    assert recs[0]["player_id"] == "pl_1"


def test_to_ndjson_writes_lf_not_crlf(tmp_path):
    """Sources are CRLF on Windows; the NDJSON must be LF-only (BigQuery-safe)."""
    src = tmp_path / "s.csv"
    src.write_text("a,b\r\n1,2\r\n", encoding="utf-8")   # CRLF source on purpose
    out = tmp_path / "s.ndjson"
    load_raw.to_ndjson(src, out, "s.csv", "csv")
    data = out.read_bytes()
    assert b"\r\n" not in data and b"\n" in data


def test_to_ndjson_every_line_is_valid_json(tmp_path):
    """The NDJSON contract: one complete JSON object per line."""
    src = tmp_path / "s.json"
    src.write_text('[{"x": 1}, {"x": 2}, {"x": 3}]', encoding="utf-8")
    out = tmp_path / "s.ndjson"
    load_raw.to_ndjson(src, out, "s.json", "json")
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        json.loads(line)   # raises if a line is not valid JSON
