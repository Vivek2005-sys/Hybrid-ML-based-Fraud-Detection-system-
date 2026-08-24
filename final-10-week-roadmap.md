# Final Project Roadmap — 10 Weeks (Extended, Detailed)
## Hybrid AI-Based Fraud Detection System

Extended from the 8-week version to give more breathing room per week, with a detailed day-by-day breakdown, explicit "what you'll be able to do by end of week" checkpoints, and Week 1's tech stack broken down precisely so you know what unlocks what.

---

## Complete System Workflow (unchanged — this is what you're building)

```
                            ┌─────────────────────────┐
                            │   POSTMAN (demo driver)  │
                            └────────────┬─────────────┘
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  │                      │                       │
         POST /customers          POST /transactions      GET /analytics/*
        (onboard, no behavior)    (score in real time)    (dashboard data)
                  │                      │                       │
                  ▼                      ▼                       │
         ┌─────────────────────────────────────────┐             │
         │              FastAPI Backend              │             │
         │  1. Save customer (identity only)          │             │
         │     OR save raw transaction                │             │
         │  2. Observation Engine: query THIS          │             │
         │     customer's history, compute snapshot    │             │
         │     (cold-start: 0-history = neutral)        │            │
         │  3. Rule Engine: evaluate JSON rules        │             │
         │  4. Feature Builder: flatten to ML vector   │             │
         │  5. ML Model: predict_proba() (XGBoost)     │             │
         │  6. Hybrid Risk Engine: combine scores       │             │
         │  7. SHAP: explain the ML contribution        │             │
         │  8. Save transaction + score + explanation  │             │
         └────────────────────┬──────────────────────┘             │
                              ▼                                     │
                     ┌─────────────────┐                            │
                     │   PostgreSQL     │◄───────────────────────────┘
                     │ customers, transactions, rule_triggers,       │
                     │ ml_predictions, risk_scores                   │
                     └────────┬─────────┘
                              ▼
                  ┌───────────────────────┐
                  │   Streamlit Dashboard  │
                  │  Live Txns | Details   │
                  │  Rules vs Hybrid | ML  │
                  └───────────────────────┘
```

**Proof sequence (unchanged, this is your demo script)**:
1. `POST /customers` → onboard "Priya" (identity only)
2. `POST /transactions` × 15-20 → normal spending, baseline builds live
3. Case A (obvious fraud) → both Rules and Hybrid catch it
4. Case B (evasive fraud, ₹49,000 under every threshold) → **Rules score 0.0, Hybrid catches it** ← headline result
5. Case C (normal transaction) → both correctly stay quiet
6. *(Optional)* new customer, fraud on transaction #2 → cold-start limitation shown honestly

---

# WEEK 1 — Tech Stack Foundation (No Project Code Until Day 5-6)

This week's ONLY job is to make Weeks 2-10 possible. Do not skip ahead to building things — every topic below is a direct prerequisite for a specific later week, mapped explicitly so you know *why* you're learning each one.

## Exact Tech Stack Focus, Day by Day

### Day 1 — Python Refresh (only if needed — skip if your self-test from earlier scored well)
- OOP: classes, `__init__`, `self`, inheritance, composition (you have dedicated practice exercises for this already)
- `@dataclass` and the mutable-default-argument behavior
- List/dict comprehensions, f-strings, `try/except`
- **Unlocks**: Week 2 (data generation code), Week 4 (Observation Engine classes)

### Day 2 — SQL Basics (Tier 1 + Tier 2)
- `CREATE TABLE`, data types, `PRIMARY KEY`/`FOREIGN KEY`, `INSERT INTO`
- `SELECT`, `WHERE`, `ORDER BY`, `JOIN`, `GROUP BY`, aggregate functions (`COUNT`, `AVG`, `STDDEV`)
- `CREATE INDEX` — specifically understand *why* `(customer_id, timestamp)` needs one
- **Unlocks**: Week 2 (schema creation), Week 3 (EDA queries)

### Day 3 — SQL Window Functions (Tier 3 — the one genuinely new, critical topic)
- `OVER (PARTITION BY ... ORDER BY ...)`
- `RANGE BETWEEN INTERVAL '15 minutes' PRECEDING AND CURRENT ROW` (time-based rolling windows)
- `LAG()` for previous-row lookups
- `AVG()`/`STDDEV() OVER (... ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)` (running stats excluding current row)
- Practice these against a small sample table you create by hand (10-15 rows) so you can verify the output makes sense before trusting it on real data
- **Unlocks**: Week 4 (Observation Engine — this IS the Observation Engine's core mechanism)

### Day 4 — Docker & PostgreSQL Setup
- Install Docker Desktop, understand images vs. containers vs. volumes
- Write a minimal `docker-compose.yml` with one Postgres service
- Connect to it from your host machine using a GUI client (DBeaver/pgAdmin) or `psql`
- **Unlocks**: Week 2 (where your data actually lives), every week after

### Day 5 — FastAPI + SQLAlchemy
- FastAPI official tutorial: path operations, Pydantic request/response models, running with `uvicorn`
- SQLAlchemy basics: declarative models, `Session`, basic `.query()`/`.add()`/`.commit()`
- Connect FastAPI to your Dockerized Postgres from Day 4
- **Unlocks**: Week 1's own deliverable (skeleton API), Week 7 (full API layer)

### Day 6 — Postman + Wire-Up Test
- Build a Postman collection: one POST request with a JSON body
- Build ONE throwaway FastAPI endpoint (`POST /ping`) that writes a row to Postgres, confirm Postman → FastAPI → Postgres works end-to-end
- **This is your Week 1 proof-of-life** — if this loop works, every later week is just adding logic inside a pattern you've already proven

### Not needed this week (learn just-in-time later)
- Streamlit → Week 8
- SHAP → Week 7
- XGBoost/LightGBM tuning specifics → Week 6 (you've already used these once, low risk)

## ✅ End of Week 1 — You should be able to:
- [ ] Explain any class in `generate_data.py` line by line
- [ ] Write a `CREATE TABLE` with correct types, keys, and an index
- [ ] Write a window function query with `PARTITION BY` and explain what it's doing, using dummy data
- [ ] Run `docker-compose up` and have Postgres reachable
- [ ] Send a Postman POST request that a FastAPI endpoint receives and writes to Postgres
- [ ] Have your GitHub repo initialized with the folder structure from the architecture roadmap

---

# WEEK 2 — Data Generation (Corrected, Full-Scale)

## Detailed Tasks
- **Day 1-2**: Rewrite `generate_data.py` with the customer/transaction separation fix — behavioural simulation parameters stay internal to the generator; the `customers` table written to Postgres contains ONLY identity fields (customer_id, persona_type, account_open_date, home_lat/lng, primary_device_id)
- **Day 3**: Scale up generation to 3,000-5,000 customers, 6+ months of history. Test-run at 500 first (as before) to confirm no regressions, then scale up
- **Day 4**: Re-tune fraud injection — target ~0.3-1% prevalence (oversampled from realistic ~0.05-0.1%), rotate through your 3 archetypes (Velocity Burst, Paced/Evasive Velocity, Amount Escalation), 2-4 episodes per fraud customer
- **Day 5**: Batch-load both tables into Postgres (`COPY` command or SQLAlchemy bulk insert — NOT row-by-row), create the `(customer_id, timestamp)` index
- **Day 6-7**: Buffer/catch-up — this almost always takes longer than expected at full scale; don't schedule Week 3 work into this time

## ✅ End of Week 2 — You should have:
- [ ] `customers` table in Postgres: 3,000-5,000 rows, identity fields only
- [ ] `transactions` table in Postgres: likely 1.5M-3M+ rows depending on final scale, properly indexed
- [ ] A documented, defensible fraud prevalence rate (know the exact number and why it's oversampled)
- [ ] Query performance sanity-checked (a simple `SELECT COUNT(*) WHERE customer_id = X` should return near-instantly)

---

# WEEK 3 — EDA + Rule Engine

## Detailed Tasks
- **Day 1-2**: Adapt `eda.py` to read from Postgres instead of CSV (swap `pd.read_csv` for `pd.read_sql`). Rerun all 10 charts on the full-scale dataset
- **Day 3**: Write up EDA findings — this becomes report Section 16 content directly, don't defer this writing
- **Day 4**: Finalize the JSON rule catalog (the 8 rules already defined) — move `RULES_CONFIG` into actual `.json` files under `rule_engine/rules/`, or a `rule_definitions` Postgres table if you want it fully data-driven
- **Day 5**: Wire `evaluate_rules()` to pull real per-transaction field values (amount, txn_count_15m, is_new_device, etc.) computed via simple filtered SQL queries (not window functions yet — that's Week 4)
- **Day 6-7**: Run the Rule Engine against your ENTIRE fraud-labeled dataset. Compute per-archetype recall for rules alone. This is your **baseline number** — you cannot prove ML adds value without this reference point captured first

## ✅ End of Week 3 — You should have:
- [ ] EDA charts + summary regenerated on full-scale data, written into your report draft
- [ ] 8 rules defined as JSON, loaded and evaluable via `evaluate_rules()`
- [ ] A table: **Rules-only recall, per fraud archetype**, on your full dataset (e.g., Velocity Burst ~90%+, Amount Escalation ~70-80%, Paced/Evasive Velocity — should be very low, near 0%, proving the gap exists)
 
---

# WEEK 4 — Observation Engine (Production Version, in Postgres)

## Detailed Tasks
- **Day 1-2**: Write the batch/training version of Observation Engine metrics as raw SQL using window functions (velocity counts via `RANGE BETWEEN INTERVAL`, gap via `LAG()`, running z-score via `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING`) — run this once to materialize a full features table for training
- **Day 3**: Write the real-time/single-lookup version as a Python function (`get_observation_snapshot(customer_id, timestamp)`) using simple filtered aggregate queries — this is what the FastAPI endpoint will call per-transaction
- **Day 4**: Explicitly implement and test cold-start handling — verify a customer with 0, 1, and 2 prior transactions returns sensible neutral defaults, not `NULL`/crashes
- **Day 5**: Add merchant/device diversity (correlated subquery pattern) and burstiness (variance of recent gaps)
- **Day 6-7**: Validate — spot-check the SQL-computed metrics against a few transactions by hand-calculating expected values, confirm they match

## ✅ End of Week 4 — You should have:
- [ ] A working `observation_engine.sql` (batch, window-function-based) for generating training features
- [ ] A working `observation_engine.py` module (`get_observation_snapshot()`) for real-time single-transaction lookups
- [ ] Verified cold-start behavior (new customer → neutral scores, not errors)
- [ ] Confidence explaining the difference between `RANGE` and `ROWS` window frames, and why real-time uses simple filtered queries instead of window functions

---

# WEEK 5 — Feature Engineering + Model Training

## Detailed Tasks
- **Day 1**: Build the Feature Builder — takes Observation Engine output, flattens into the ML-ready vector (reuse the `FEATURE_COLS` structure from `train_model.py`, now sourced from Postgres/SQL instead of pandas rolling)
- **Day 2**: Materialize the full training feature table (one row per historical transaction, features "as they looked at that point in time" — no leakage)
- **Day 3**: Chronological train/test split on the full dataset, class-weighting setup
- **Day 4**: Train Logistic Regression (baseline), Random Forest, XGBoost
- **Day 5**: Train LightGBM — this time properly tuned (`min_child_samples`, `num_leaves` adjusted for your imbalance ratio; it underperformed badly untuned on the small demo run, don't repeat that)
- **Day 6-7**: Compare all 4 models on AUC-PR/ROC-AUC/Recall, select champion, serialize it (`joblib`/`pickle`) with a metadata file (metrics, training date, feature list)

## ✅ End of Week 5 — You should have:
- [ ] A reproducible feature-materialization pipeline (Postgres → feature table)
- [ ] 4 trained models with a comparison table on your FULL dataset (numbers will differ from the 500-customer demo — expect them, don't panic if AUC-PR shifts)
- [ ] A serialized champion model ready to be loaded by FastAPI
- [ ] LightGBM specifically re-validated as competitive (not the outlier it was before)

---

# WEEK 6 — Hybrid Risk Engine + Explainability + THE Proof (Most Important Week)

## Detailed Tasks
- **Day 1**: Implement the Hybrid Risk Engine — weighted combination of Rule Score + ML Score + Behaviour Score → final score + category (Low/Medium/High/Critical)
- **Day 2**: Integrate SHAP for the champion model — global feature importance + per-transaction local explanations
- **Day 3**: Build and run **Case A (obvious fraud)** through the full pipeline — confirm both Rules and Hybrid catch it (sanity check)
- **Day 4**: Build and run **Case B (evasive fraud)** — confirm Rules score 0.0, Hybrid catches it. This is your single most important test of the entire project
- **Day 5**: Build and run **Case C (normal transaction)** — confirm both correctly stay quiet (precision check, not just recall)
- **Day 6-7**: Run the FULL per-archetype recall comparison (Rules-only vs. Hybrid) across your entire labeled dataset — this produces the headline results table for your report

## ✅ End of Week 6 — You should have:
- [ ] A working Hybrid Risk Engine combining all 3 score sources
- [ ] SHAP explanations generating correctly for individual transactions
- [ ] Cases A/B/C all run and documented with actual output (screenshots/logs)
- [ ] **The headline table**: Rules-only Recall vs. Hybrid Recall, broken down by fraud archetype — this is the single most important artifact in your whole project

---

# WEEK 7 — Rule Engine + Observation Engine + Everything Wired Into FastAPI

## Detailed Tasks
- **Day 1-2**: Build `POST /customers` — validates and saves identity-only customer records
- **Day 3-4**: Build `POST /transactions` — wires ALL 8 pipeline stages together (save raw txn → Observation Engine → Rule Engine → Feature Builder → ML → Hybrid score → SHAP → save result), returns the full JSON verdict
- **Day 5**: Add `try/except` error handling around the pipeline (malformed input, unknown customer_id, etc.) so Postman demos don't crash the API mid-presentation
- **Day 6**: Build `GET /analytics/*` endpoints your dashboard will need (summary stats, model performance data)
- **Day 7**: End-to-end test via Postman: onboard a customer, send 15-20 normal transactions, then Cases A/B/C — confirm the API returns correct, sensible verdicts every time

## ✅ End of Week 7 — You should have:
- [ ] Working `POST /customers` and `POST /transactions` endpoints, tested via Postman
- [ ] The full 8-stage pipeline running inside one API call, end-to-end, no manual script-running required
- [ ] Error handling that keeps the API alive under bad input
- [ ] A Postman collection saved and ready for demo day

---

# WEEK 8 — Streamlit Dashboard

## Detailed Tasks
- **Day 1**: Learn Streamlit basics (this is genuinely fine to start fresh here — `st.title`, `st.dataframe`, `st.metric`, `st.sidebar`, basic charts)
- **Day 2-3**: Build **Live Transactions** page — reads directly from Postgres (`pd.read_sql`), color-coded by risk category, refresh button or simple polling loop
- **Day 3-4**: Build **Transaction Details** page — the explainability view (rule triggers + SHAP top features + behaviour narrative), this is your most important dashboard page
- **Day 5-6**: Build **Rules vs. Hybrid Comparison** page — visualizes Week 6's headline table, plus the timeline chart showing when each system would/wouldn't have flagged the evasive fraud sequence
- **Day 7**: Build **Model Performance** page — comparison table, ROC/PR curves, feature importance chart (reuse Week 5's outputs)

## ✅ End of Week 8 — You should have:
- [ ] 4 working Streamlit pages, all reading live from Postgres
- [ ] A demo-able dashboard where sending a Postman request visibly updates what you see in Streamlit
- [ ] The Rules vs. Hybrid page specifically polished — this is what you'll spend the most time on during your actual presentation

---

# WEEK 9 — Integration, Customer Onboarding Flow, Cold-Start Case, Docker

## Detailed Tasks
- **Day 1-2**: Build the full onboarding-to-fraud demo sequence end-to-end via Postman collection (onboard → 15-20 normal txns → Case A → Case B → Case C), scripted and repeatable
- **Day 3**: Build the optional cold-start demo case (new customer, fraud attempt on transaction #2) — confirm it behaves as expected (weaker detection, correctly attributed to lack of history) and document this as an explicit, honest limitation
- **Day 4-5**: Docker Compose final integration — FastAPI + Postgres + Streamlit all launchable with one `docker-compose up`, environment variables via `.env`, seed script to load your dataset on first run
- **Day 6-7**: Full run-through rehearsal — time yourself doing the entire demo sequence, fix anything that breaks or feels slow

## ✅ End of Week 9 — You should have:
- [ ] The complete demo sequence working reliably, repeatably, end-to-end
- [ ] Cold-start case demonstrated and documented honestly
- [ ] One-command Docker startup for the whole system
- [ ] A rehearsed run-through with timing (know how long your demo actually takes)

---

# WEEK 10 — Report Writing, Polish, Final Rehearsal

## Detailed Tasks
- **Day 1-2**: Assemble the full report from your running draft (kept since Week 1 per the report-mapping document) — Introduction through Conclusion, all 22 sections
- **Day 3**: Finalize Literature Review + Research Gap sections using the paper research already done, cross-check citation style with your guide
- **Day 4**: Compile Appendices — dataset samples, data dictionary, code snippets, model outputs, graphs, screenshots (should mostly already be collected if you followed the "collect continuously" advice)
- **Day 5**: Final Scope and Limitations pass — be explicit and honest about what's oversampled, what's synthetic, what the cold-start limitation is
- **Day 6**: Full demo rehearsal in front of a friend/family member, time it, prepare answers to likely viva questions ("why hybrid over pure ML," "why synthetic data," "what would you do with more time," "walk me through the ₹49,000 case")
- **Day 7**: Buffer day — fix whatever broke in rehearsal, final submission prep

## ✅ End of Week 10 — You should have:
- [ ] Complete, submitted report (all 22 sections)
- [ ] Rehearsed, timed demo you can deliver confidently
- [ ] Prepared answers to the hardest likely questions about your project
- [ ] Working system, submitted and ready to present

---

## Non-Negotiable Priority Order (unchanged — if any week runs short, cut in this order, never from the top)

1. ✅ Data generation + EDA (Weeks 2-3) — cannot cut
2. ✅ Rule Engine + Observation Engine (Weeks 3-4) — cannot cut
3. ✅ ML training + Hybrid Risk Engine + the A/B/C proof (Weeks 5-6) — cannot cut, this is your thesis
4. ✅ Transaction Details + Rules vs. Hybrid dashboard pages (Week 8) — cannot cut, this is your evidence
5. ⚠️ Customer onboarding cold-start demo case (Week 9) — valuable but droppable
6. ⚠️ Live Transactions polish, auto-refresh feel (Week 8) — droppable
7. ⚠️ Model Performance / Analytics pages (Week 8) — droppable
8. ❌ Anything not on this roadmap (extra archetypes, crypto scope, React, extra dashboard pages) — already correctly cut in earlier discussion, stay cut
