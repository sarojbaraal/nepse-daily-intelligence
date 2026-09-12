# NEPSE Intelligence Data Contract

`dashboard/data/latest.json` is the single dashboard input. Daily briefing automation should update it only with verified data.

## Required top-level fields

- `updated_label`: human-readable snapshot time/status
- `market.nepse`: numeric NEPSE index
- `market.change_pct`: daily percentage change
- `market.turnover`: formatted turnover value
- `market.breadth`: `{up, down, flat, sample_size, sample_type}`. `up`/`down`/`flat` are `null` when no price sample was available — never default to `0`, since `0` implies a real flat/no-movers reading. `sample_type` is `"full"` only when computed from the complete Parse price list (~250-300 scrips); `"partial"` means it came from a fallback top-stocks sample (~20 scrips) and must be labeled as such in the UI, not presented as full-market breadth.
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
6. `market.turnover` and `market.breadth` are `null`/absent when unknown, never `0`. A `0` in either field is a real market reading, not a "data missing" placeholder — the pipeline and the dashboard must not conflate the two.
