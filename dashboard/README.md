# Beacon AI analytics

Open `/admin/dashboard/` after signing in through Beacon's normal login. Only active superusers can view it; ordinary users and staff receive HTTP 403. Responses are never cached. This path is deliberately fixed even when Django's admin path is customized.

This implementation uses deterministic simulated telemetry for all six features. No live traffic, prompt text, invoices or personal data are collected. Filters select 7/14/30 days and provider. The demonstration regenerates relative to today's local date.

## Question → widget → data

| Question | Widget | Required telemetry |
|---|---|---|
| S1: Which feature has the slowest tail? | p50/p95 grouped bars and shrunk-mean table | Feature, latency_ms |
| S2: How often and why does fallback occur? | Daily outcome chart and fallback KPI | Timestamp, outcome (success/timeout/invalid JSON/provider down/slow mode) |
| S3: Does input length predict latency? | Scatter with Pearson correlation | Input characters, latency, feature |
| U1: Does usage mix change after week one? | Cohort bars | Feature, user, account age at call |
| U2: What questions are common or declined? | Topic counts and decline rates | Ask topic cluster, declined flag |
| U3: Do low grades lead to retries or abandonment? | Retry/return line chart | Grade <60, same-skill retry within 24h, next-day activity |
| C1: What are tokens and dollars per call? | KPIs, feature cost bars, token table | Input/output tokens, model prices |
| C2: Does token share match usage share? | Grouped share bars | Feature call counts, token totals |
| C3: How close are caps and what would 10× usage cost? | Capacity progress bars and projection | Hourly site/user calls, caps, cost |

Percentiles use linear interpolation. The histogram reveals skew; trailing seven-day means smooth volume and spend (partial windows at the start). Pearson r measures association, not causality. Shrunk latency means add 20 pseudo-observations at the overall mean. Rates show their denominators; empty data returns zero counts and undefined correlation. Synthetic follow-up outcomes are fully observed, avoiding right censoring. Cohort bars show counts rather than propensity-adjusted rates.

Illustrative pricing is $0.15/M input and $0.60/M output tokens, uniformly applied to both simulated providers. It is not current vendor pricing. Cap gauges show peak calendar hours in filtered data, not the app's actual rolling enforcement counters. The 10× forecast assumes unchanged unit price and feature mix. Production instrumentation would need request events, true token usage/pricing, account-age joins and linked follow-up events before replacing this dataset.

## Reviewer and deployment

Create the assignment reviewer on each database by setting `DASHBOARD_REVIEWER_PASSWORD` to the assignment password and running `python manage.py create_dashboard_reviewer`. The command creates `mohitg2` as a superuser and refuses to overwrite an existing account unless you explicitly pass `--update-existing`. It is an explicit command, never a startup hook or migration.

Run `python manage.py test dashboard`, then deploy using the existing `scripts/deploy_pythonanywhere.sh` workflow, create the reviewer on production and reload the web app. No schema migration or new dependency is needed. The dashboard URL on the team mirror will be `https://simonhwang1998.pythonanywhere.com/admin/dashboard/` once deployed.

For submission, capture the full dashboard with filters visible. The Print / save PDF button opens browser printing; the full dashboard is longer than the 1.5-page report limit. Use the existing P1-A10 analytics plan with selected screenshots to compose that report. Do not submit simulated results as measurements of the real system.
