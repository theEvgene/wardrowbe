# Outfit acceptance benchmark

The benchmark in `backend/tests/fixtures/outfit_acceptance/cases.json` is
privacy-safe: it contains only synthetic item metadata and symbolic IDs, never
personal wardrobe photos. It protects the two known failure modes from the
user's capsule scenario while keeping Canvas-like combinations accepted.

Run locally from `backend/`:

```bash
PYTHONPATH=. python scripts/evaluate_outfit_acceptance.py
```

Current result on the four-case fixture:

- baseline structural validation: `0.5` (2/4)
- deterministic compatibility guardrails: `1.0` (4/4)
- optional embedding reranker: not enabled; it remains a separately measurable
  experiment and is not required for the deterministic MVP path

The service applies the same guardrails both to model proposals and to its
deterministic fallback. The generated context records the compact-capsule
plan and reuse summary so API consumers can explain the trade-off.
