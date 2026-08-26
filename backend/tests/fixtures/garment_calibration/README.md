# Real-photo garment calibration set

This directory contains a small, deliberately mixed calibration set for the
`u2net_cloth_seg` integration. It is separate from the generated acceptance
fixtures in `../garment_extraction`: these files are real photographs and are
used to expose both current successes and current model limits.

Every file is published as CC0 1.0 on its linked Wikimedia Commons file page.
The exact page, creator, intended scenario, expected baseline outcome and
SHA-256 digest are recorded in `manifest.json`. The JPEG files are Wikimedia
thumbnail derivatives retrieved through the MediaWiki image-info API on
2026-08-27; no image is covered by the repository's source-code license.

Run the real model and emit a machine-readable performance/quality report:

```bash
cd backend
python scripts/calibrate_garment_extraction.py \
  --strict \
  --output garment-calibration-report.json
```

`--strict` checks the documented baseline outcomes. A `low_quality` expectation
is not a claim that the input is bad: it records a known model limitation or a
case that should be rejected conservatively instead of returning a misleading
cutout. The set is for evaluation, not model training.

Wikimedia notes that freely licensed media can still be subject to non-copyright
restrictions such as personality rights. Keep this set small, do not infer or
store identities, and review the linked file pages before redistributing it in
another context.
