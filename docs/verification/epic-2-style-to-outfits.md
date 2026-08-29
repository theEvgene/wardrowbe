# Epic #2 verification: detected style to N outfits

## Real local-model path

The current `main` implementation was deployed over the existing local PostgreSQL, Redis, and wardrobe volumes. No persistent volume was deleted or recreated.

The browser-driven full-stack smoke passed through public interfaces:

`upload → gemma3:4b metadata → automatic u2net_cloth_seg extraction → metadata review → detected styles → style selection → N=2 → persisted outfits → composite previews`

Observed result:

```json
{
  "status": "passed",
  "garment_model": "u2net_cloth_seg",
  "garment_category": "upper",
  "mask_area_ratio": 0.09611256917317708,
  "metrics_scope": "shared_redis",
  "duplicate_model": "facebook/dinov2-small",
  "duplicate_decision": "kept_separate",
  "composite_items": 3,
  "detected_styles": [{"style": "casual", "item_count": 4}],
  "style_generation_model": "gemma3:4b",
  "style_generation_latency_ms": 3439,
  "generated_outfits": 2
}
```

The model initially exposed two repair cases: nested local-model JSON wrappers and conflicting body slots caused by an ambiguous static schema example. Regression coverage now verifies bounded parsing, role-labelled prompts, a server-computed whitelist of complete core item sets, unknown-ID rejection, completeness, diversity, and atomic rollback.

## Runtime model cache

The Docker image caches both `u2net` and `u2net_cloth_seg` under `/opt/rembg` before switching to the non-root runtime user. The build retries interrupted downloads up to five times, and both ONNX files were verified readable as `appuser`. This prevents the worker from downloading a 176 MB model on its first extraction request.

## Deterministic verification

- Backend: **576 passed, 17 skipped**, 0 failures. Skips are opt-in licensed/model fixture cases.
- Frontend Vitest: **165 passed**, 0 failures.
- TypeScript: passed with `tsc --noEmit`.
- i18n key, locale parity, and untranslated-string scans: passed.
- Ruff lint: passed; changed Python files pass Ruff formatting.
- Production Next.js build: passed.
- Production Playwright browser happy path: **1 passed**, 0 failures. The scenario covers onboarding, upload with automatic safe extraction enabled, detected-style selection, exact-N generation, persistence, and composite previews.
- Real local full-stack smoke with `gemma3:4b`: passed.

The final GitHub Actions evidence and immutable run URL are recorded in the closure comment on issue #23 so this document does not require a follow-up commit after each CI run.
