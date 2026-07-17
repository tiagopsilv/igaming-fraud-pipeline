# Architecture

The pipeline lands four heterogeneous sources into BigQuery, models them through a Medallion
architecture with dbt, and serves fraud and financial signals to Power BI. Airflow orchestrates the run.

```mermaid
flowchart LR
    subgraph SRC["Sources (data/)"]
        P[players.json]
        S[sessions.json]
        T[transactions.csv]
        A[affiliate_cpa_ftd.csv]
    end

    N["load_raw.py<br/>arrays to NDJSON<br/>audit cols, LF, idempotent (ADR-0005)"]
    RAW[("BigQuery: raw<br/>1:1 with source")]

    subgraph BRONZE["Bronze - staging (views)"]
        STG["stg_*<br/>cast types, amount to NUMERIC, UTC"]
    end
    subgraph SILVER["Silver - intermediate (tables)"]
        INT["int_*<br/>email lowercase, real FTD,<br/>affiliate attribution (ADR-0004), DQ"]
    end
    subgraph GOLD["Gold - marts (star schema, ADR-0007)"]
        DIM["dim_player (SCD1)<br/>dim_affiliate, dim_date"]
        FCT["fct_transactions, fct_sessions<br/>partition by date, cluster by player_id"]
        FRAUD["fct_fraud_signals<br/>multi-account, AML, affiliate ghost-FTD"]
    end

    BI["Power BI<br/>Fraud / Affiliate / Financial"]
    AIR["Airflow + Cosmos<br/>ingest to dbt build to publish"]

    SRC --> N --> RAW --> STG --> INT
    INT --> DIM
    INT --> FCT
    DIM --> FRAUD
    FCT --> FRAUD
    DIM --> BI
    FCT --> BI
    FRAUD --> BI
    AIR -.orchestrates.-> N
    AIR -.orchestrates.-> STG
```

**How to read it.** Raw files land in `raw` untouched (idempotent load). Bronze casts types and
timezone. Silver conforms and applies the business rules (the affiliate attribution that removes the
209 ghost FTDs, ADR-0004). Gold is a star schema; the facts are partitioned by date and clustered by
`player_id` to keep BigQuery cheap. Only Gold feeds the dashboard. Airflow runs ingestion, then a
`dbt build`, then publishes.

**Load cadence** is per source (ADR-0008): sessions/transactions are incremental, players/affiliate
are full. Freshness, quality and cost targets are in ADR-0009.
