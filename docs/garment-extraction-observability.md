# Garment extraction observability

`GET /api/v1/health/metrics/garment-extraction` returns anonymous operational
metrics for garment-only background removal. The response includes lifetime
outcome and garment-category counts for the current backend process, plus
latency and mask-quality summaries over the latest 200 attempts.

The request's own `background_removal.metrics` also includes `duration_ms`.
This measures the complete `ImageService.remove_background` operation: image
loading, model/provider execution, quality validation, and output writes.

The endpoint intentionally stores and exposes no user, item, filename, image,
or request identifiers. It is public like the existing health endpoints.

## MVP limitations

- Metrics are held in memory and reset when the backend process restarts.
- Every worker process has its own snapshot. A deployment with multiple workers
  must scrape each process or replace this collector with a shared telemetry
  backend before using the counts as global totals.
- The bounded 200-sample window prevents unbounded memory growth. Lifetime
  counters remain process-local, while latency and quality summaries describe
  only that recent window.
