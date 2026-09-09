# NEPSE Intelligence Data Contract

`dashboard/data/latest.json` is the single dashboard input. Daily briefing automation should update it only with verified data.

## Required top-level fields

- `updated_label`: human-readable snapshot time/status
- `market.nepse`: numeric NEPSE index
- `market.change_pct`: daily percentage change
- `market.turnover`: formatted turnover value
- `market.breadth`: advancers/decliners summary
- `market.note`: concise market interpretation
- `sectors[]`: `{name, change_pct}`
- `setups[]`: `{symbol, bias, setup, entry, target, invalidation, confidence}`
- `scenarios`: `base`, `bull`, `bear`, each with `probability`; plus `note`
- `review`: `{score, reviewed, score_label}`
- `counterpoint`: strongest argument against the current thesis

## Rules

1. Never invent missing prices.
2. Preserve the original prediction when reviewing it.
3. Confidence is evidence strength, not guaranteed profit probability.
4. Every active trade setup needs an invalidation condition.
5. Archived daily briefings remain immutable; corrections should be explicit.
