# Dashboard - iGaming Fraud & Performance

The Power BI report that closes the pipeline, built on the Gold star schema in BigQuery. Four pages:
**Fraud Overview**, **Acquisition & Retention**, **Affiliate Metrics**, **Financial Signals**.

- **Deliverable:** `dashboard/igaming_fraud_dashboard.pbix` (open in Power BI Desktop).
- **Connection:** Import mode over the Gold marts in BigQuery.
- **Theme:** custom light/neutral palette, tuned for contrast and legibility.

---

## 1. Data model (what feeds it)
Power BI connects to BigQuery in **Import mode** over the Gold marts (`analytics` dataset). It is a
**star schema** (ADR-0007/0014): dimensions filter facts, one direction.

```
        dim_date -+         +- dim_affiliate
                  v         v
   dim_player -> fct_transactions   agg_affiliate_performance
        |     -> fct_sessions
        +----->  fct_fraud_signals
```

**Relationships** (single-direction, dim -> fact):
| From (1) | To (*) | Key |
|---|---|---|
| dim_player[player_id] | fct_transactions[player_id] | player_id |
| dim_player[player_id] | fct_sessions[player_id] | player_id |
| dim_player[player_id] | fct_fraud_signals[player_id] | player_id |
| dim_affiliate[affiliate_id] | agg_affiliate_performance[affiliate_id] | affiliate_id |
| dim_date[date_day] | fct_transactions[txn_date] | date |
| dim_date[date_day] | fct_sessions[session_date] | date |

`dim_date` is marked as the date table (enables the retention time-intelligence). `fct_fraud_signals` is
a per-player snapshot with no date grain, so date does not filter the fraud page (the fraud slicer is
`risk_score`, which does).

---

## 2. Where the calculations live (Gold vs semantic model)
Rule: **row-level business logic lives in Gold (dbt); dynamic aggregation lives in the model.** A number
that must respond to a slicer is a measure; an attribute of a row is a Gold column.

**Computed in Gold (dbt), single source of truth:**
- `fct_fraud_signals`: the 5 core + 5 secondary signal flags, `risk_score` (0-5), `value_at_risk`, and
  `risk_tier` (Critical/High/Medium/Low/No alert, bucketed from `risk_score` in SQL, tested with
  `accepted_values`).
- `dim_player`: `is_qualified_ftd`, `is_one_and_done` (exactly one deposit), acquisition attribution.
- `agg_affiliate_performance`: `roi`, `cpa_owed`, `real_revenue`, `qualified_ftds`, `ghost_ftds`.

**Measures (dynamic, in `_Measures`):** sums, distinct counts and ratios that must aggregate under the
current filter (deposits, active players, FTD rate, house margin, etc.), plus the retention
time-intelligence (`Retention Rate` via `INTERSECT` + `DATEADD`, which is by definition filter-context
dependent). `risk_tier` and `is_one_and_done` are **columns**, not measures, so they slice and never
recompute.

---

## 3. Design system
A clean, neutral, light layout, high-contrast for screen and print.

- **Palette (semantic):**
  - Surfaces: page `#F4F5F7`, cards `#FFFFFF`, borders `#E3E6EA`, text `#1A2230` / `#5A6472`.
  - `#2563EB` blue: primary / neutral metrics.
  - `#0E9F6E` green: positive (revenue, qualified).
  - `#F59E0B` amber: attention / medium risk.
  - `#E5484D` red: critical / negative (value at risk, ghost, house loss).
- **Risk reads as a label, not only colour:** the `risk_tier` Gold column (Critical/High/Medium/Low/No
  alert) shows in the investigation table, so it works for colour-blind users and in print.
- **Typography:** Segoe UI (built-in). Card value 18px for currency (fits the full amount), 30px for
  short counts and ratios; titles ~12px.
- **Layout:** 1280 x 720 (16:9). Six KPI cards across the top band, then charts and the investigation
  table below.

---

## 4. The four pages

### Page 1 - Fraud Overview
Question: **how much money is at risk and who is suspicious?**

| Visual | Type | Field / measure |
|---|---|---|
| 6 KPI cards | Card | `Players Scanned`, `Suspicious Accounts`, `% Suspicious`, `Value at Risk`, `High-Risk Value at Risk`, `Avg Risk Score` |
| Accounts under investigation | Table | `player_id`, `city`, `acquisition_country`, `risk_tier` (Gold column), `Avg Risk Score`, `Value at Risk` |
| Players flagged by signal | Clustered bar | axis `Signal Type[Signal]` (all 10 signals, sorted core-first), value `Signal Player Count`; title notes the top 5 core signals drive the risk score |
| Value at risk by country | Clustered column | axis `dim_player[acquisition_country]`, value `Value at Risk` |
| Filter by risk score | Slicer | `fct_fraud_signals[risk_score]` (0-5) |

`Value at Risk` is total withdrawals under the current filter; `High-Risk Value at Risk` restricts it to
`risk_score >= 2` (the high-confidence set). Use the risk-score slicer to move between them.

### Page 2 - Acquisition & Retention
Question: **who is coming in, and do they stay?**

| Visual | Type | Field / measure |
|---|---|---|
| 6 KPI cards | Card | `Registered Players`, `FTD (Depositors)`, `FTD Rate`, `Turnover`, `ARPU`, `% One-and-Done` |
| Monthly retention rate | Line | axis `dim_date[year_month]`, value `Retention Rate` (returning players, month over month) |
| First-time depositors by country | Clustered column | axis `dim_player[acquisition_country]`, value `FTD (Depositors)` |
| Acquisition & value by country | Table | `acquisition_country`, `Registered Players`, `FTD (Depositors)`, `FTD Rate`, `ARPU` |

### Page 3 - Affiliate Metrics
Question: **which affiliates pay off, and which are gaming the CPA?**

| Visual | Type | Field / measure |
|---|---|---|
| 6 KPI cards | Card | `Qualified FTDs`, `Ghost FTDs`, `Ghost-FTD Rate`, `CPA Owed`, `Real Revenue`, `Affiliate ROI` |
| Affiliate performance detail | Table | `affiliate_id`, `qualified_ftds`, `ghost_ftds`, `cpa_owed`, `real_revenue`, `roi` |
| Qualified vs ghost FTDs by affiliate | Clustered column | axis `affiliate_id`, values `Qualified FTDs`, `Ghost FTDs` |
| ROI by affiliate | Clustered bar | axis `affiliate_id`, value `Affiliate ROI` |

The raw funnel (clicks/registrations) is conflated-grain (ADR-0006), so this page leads with the
attributed metrics and does not sum the raw funnel.

### Page 4 - Financial Signals
Question: **is the money flow healthy, or anomalous?**

| Visual | Type | Field / measure |
|---|---|---|
| 6 KPI cards | Card | `Total Deposits`, `Total Withdrawals`, `Net Deposit (House)`, `House Margin %`, `Total Bets`, `Active Players` |
| Deposits vs withdrawals over time | Line | axis `dim_date[date_day]`, values `Total Deposits`, `Total Withdrawals` |
| Total bets by country | Clustered column | axis `dim_player[acquisition_country]`, value `Total Bets` |
| Financials by country | Table | `acquisition_country`, `Total Deposits`, `Total Withdrawals`, `Net Deposit (House)`, `Total Bets` |
| Filter by date | Slicer | `dim_date[date_day]` |

---

## 5. Interactivity
- **Cross-filtering** is on by default: click a bar to filter the table and cards on the page.
- **Slicers** filter the page they sit on: `risk_score` on Fraud, `date_day` on Financial.
- **Risk as a label:** the `risk_tier` column surfaces the tier in text, so risk is legible without colour.

---

## 6. Metrics coverage (glossary -> dashboard)
Most glossary terms are concepts, channels, products or roles, not metrics. Every glossary metric the four
sources support is here; the rest are not computable from the data (see Limitations).

| Glossary term | Measure | Page |
|---|---|---|
| **FTD** (new depositors) | `FTD (Depositors)` | Acquisition / Affiliate |
| **Qualified FTD** | `Qualified FTDs` | Affiliate |
| **CPA** | `CPA Owed` | Affiliate |
| **ROI** | `Affiliate ROI` | Affiliate |
| **Conversion rate** (registered -> FTD) | `FTD Rate` | Acquisition |
| **ARPU** | `ARPU` (proxy, see below) | Acquisition |
| **Retention** (month over month) | `Retention Rate` | Acquisition |
| **Turnover** (total wagered) | `Turnover` (= Total Bets) | Acquisition / Financial |
| **Net Deposit** | `Net Deposit (House)` | Financial |
| **One-and-done** | `% One-and-Done` (from Gold `is_one_and_done`) | Acquisition |
| fraud signals | `Suspicious Accounts`, `Value at Risk`, `risk_tier`, per-signal | Fraud Overview |

### Limitations (explicit)
Some glossary metrics cannot be computed from the four sources:
- **NGR / GGR / RevShare**: need bonus, tax and per-bet outcome (win/loss) data the sources lack.
- **LTV**: needs a longer horizon than the sample window (ARPU and month-over-month retention are computed;
  LTV proper is a roadmap item).
- **Chargeback / Rollover / Bonus abuse**: no such data (fraud scope bounded in ADR-0006).

`ARPU` uses `Real Revenue` (affiliate-attributed net revenue) over active players, so it reads for the
acquired base rather than the whole book; stated as a proxy, not NGR.

---

## 7. Open
Open `dashboard/igaming_fraud_dashboard.pbix` in Power BI Desktop. It carries the imported Gold data, so
it renders the four pages standalone. To refresh against a live warehouse, point the BigQuery connection at
your project and use **Home > Refresh** (the Gold columns `risk_tier` and `is_one_and_done` must exist, so
run the pipeline after any change to the fraud/player models).
