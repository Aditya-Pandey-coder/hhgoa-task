# Implementation assumptions

- The official dataset is discovered from `data/`, `dataset/`, or `input/`; filenames are not assumed.
- Raw transaction IDs are preserved. Demo IDs are prefixed `DEMO-` and are never presented as official cases.
- When a source does not provide `card_id`, the loader uses an existing card_id/card key if present, otherwise a stable customer/card tuple or `UNKNOWN-CARD` fallback.
- Missing live TigerGraph and LLM services use deterministic local logic.
- Evidence requests are not simulated in the minimum Tier A path; initial and final actions are identical unless source fields explicitly provide a response.
- `FILE_REPORT` is emitted only when fraud probability is at least 0.70 and a report condition is present.
- A fraud episode is the flagged transaction plus nearby transactions on the same card within 72 hours that match the simple fraud-window rule.
