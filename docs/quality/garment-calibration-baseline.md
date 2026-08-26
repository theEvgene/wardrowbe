# Garment extraction calibration baseline

Measured on 2026-08-27 from the production backend image on the local CPU runtime.
The source manifest contains nine redistributable CC0 photographs with per-file
provenance and SHA-256 checksums. The corpus covers upper, lower and full garments,
including isolated museum objects, worn clothing, occlusion, low contrast and
complex backgrounds.

## Result

| Measure | Result |
|---|---:|
| Manifest samples | 9 |
| Expected outcomes matched | 9/9 |
| Accepted | 2 |
| Rejected as low quality | 7 |
| Cold model/session start | 56.76 s |
| Warm median inference | 2.67 s |
| Warm p95 inference | 9.05 s |

The high rejection rate is intentional for this first calibration corpus: most
samples are difficult negatives and protect the product from presenting an unsafe
cutout. It is not an estimate of production-user acceptance rate.

The semantic-leakage gate was additionally checked against the private user photo
that originally exposed the problem. It changed from an accepted connected mask
to `low_quality` with `semantic_leakage_risk=1.0`; that private source image is not
stored in the repository.

## Reproduce

```bash
docker build -t wardrowbe/backend:calibration backend
docker run --rm --entrypoint python \
  -v "$PWD/backend/tests/fixtures/garment_calibration:/fixtures:ro" \
  wardrowbe/backend:calibration \
  -m scripts.calibrate_garment_extraction --fixtures /fixtures --strict
```

The optional `Licensed Real-photo Model Calibration` GitHub Actions job runs the
same strict command when `run_model_calibration` is selected in a manual dispatch.
