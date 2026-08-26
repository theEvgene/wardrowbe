# Same-garment identity for a self-hosted CPU deployment

Date: 2026-08-26  
Scope: [Wardrowbe issue #3](https://github.com/theEvgene/wardrowbe/issues/3)

## Recommendation

Use a conservative, review-only candidate pipeline:

1. Keep the current perceptual hash path for exact and near-exact copies.
2. Generate an L2-normalized **DINOv2 ViT-S/14** image embedding for each primary and additional image in the background worker.
3. Retrieve same-user candidates by cosine similarity, then gate/rank them with trusted structured metadata (`type`, `subtype`, color, pattern, material, brand).
4. Show likely pairs to the user and require **Merge** or **Keep separate**. Never auto-merge an embedding match, regardless of its score.
5. Represent a confirmed duplicate as a reversible alias of a canonical item. Keep both records, files, and histories; recommendation and pairing queries use canonical records only.

DINOv2 ViT-S/14 is the best MVP default because it is an image-only 21M-parameter backbone with a 384-dimensional output, explicitly supports nearest-neighbor image retrieval, has Apache-2.0 model licensing, and has an 88.2 MB safetensors checkpoint. Those properties are documented by Meta's [model card](https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md#model-details) and [official Hugging Face repository](https://huggingface.co/facebook/dinov2-small/tree/main). It still needs calibration on Wardrowbe photos: neither the model card nor its generic retrieval capability establishes a universal “same physical garment” threshold.

## What exists now

Wardrowbe already has useful foundations:

- `ClothingItem.image_hash` stores a 16-character pHash, while `ItemImage` already models up to four additional photos for one item ([model](../../backend/app/models/item.py)).
- Single and bulk uploads calculate pHash before storage ([upload API](../../backend/app/api/items.py)).
- `find_duplicate_by_hash()` currently performs equality comparison; its `threshold` argument is unused, so resized/recompressed images with a nearby but non-identical hash are not actually covered ([item service](../../backend/app/services/item_service.py)).
- The item already has structured identity hints: type, subtype, colors, primary color, pattern, material, style, brand, tags, and whether the tagging was automatic or manual ([model](../../backend/app/models/item.py)).
- Wear/wash history, outfit membership, pair scores, source-item references, and user exclusion lists all refer to item IDs. Destructively deleting one record during a merge would therefore be risky.

This matches the reported failure: pHash is meant to recognize images that look nearly identical, not a physical object photographed from a different side. The ImageHash project's own rationale makes that distinction and measures hash difference with Hamming distance ([ImageHash README](https://github.com/JohannesBuchner/imagehash#rationale)). The issue's observed distance of 20 is therefore useful as a negative result for this specific pHash stage, not as evidence that the garments differ.

## Candidate visual signals

| Signal | Identity value | Weight / dependency impact | License | CPU and deployment implications | Decision |
|---|---|---|---|---|---|
| Existing pHash | Strong for the same file and content-preserving transforms; weak across viewpoints, folds, occlusion, or worn versus flat-lay photos. | Already installed (`imagehash`, Pillow, NumPy/SciPy transitive path); 64-bit hash. | ImageHash code is BSD-2-Clause. | Very cheap. Compare Hamming distance rather than only SQL equality. | Retain as stage 1. It may block an upload as an exact/near-exact image duplicate, but it must not decide cross-angle garment identity. |
| DINOv2 ViT-S/14 | Generic visual features; official model card lists nearest-neighbor image retrieval as a direct use. Its image-only representation is better aligned with instance candidate retrieval than a text classifier. | 21M parameters, 384 dimensions, 88.2 MB safetensors. Standard integration adds PyTorch and Transformers, which are materially larger than Wardrowbe's base Pillow stack. | Apache-2.0 for the model and repository ([model card](https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md#model-description), [license](https://raw.githubusercontent.com/facebookresearch/dinov2/main/LICENSE)). | Run asynchronously after upload, one image at a time or in small batches. Published sources do not provide a representative x86 self-hosted CPU latency, so image-build size, cold start, peak RSS, and per-image latency must be measured on the target host before enabling by default. | **Recommended MVP visual signal.** Package as an optional CPU feature and pin model revision plus preprocessing version. |
| FashionCLIP 2.0 (ViT-B/32) | Fashion-domain embeddings are attractive, but the model card says training images are standard product photos on white backgrounds without humans and warns that deployment requires context-specific study. That distribution is a poor match for Wardrowbe's worn, hanger, and casual photos. | 605 MB safetensors; PyTorch + Transformers. The project's convenience package additionally lists pandas, pyarrow, datasets, matplotlib, Annoy, and other dependencies ([requirements](https://github.com/patrickjohncyh/fashion-clip/blob/master/requirements.txt)). | Model repository declares MIT ([model repository](https://huggingface.co/patrickjohncyh/fashion-clip/tree/main)). | Much larger download/RAM footprint than DINOv2-S. CPU behavior for Wardrowbe's photo distribution is not established. | Benchmark later as a challenger, not the MVP default. Its domain label does not outweigh its size and documented catalog-photo bias. |
| MobileCLIP / MobileCLIP2 S0 | Very small image tower: the official table lists 11.4M image parameters and low iPhone latency. | Requires PyTorch, torchvision, timm, and OpenCLIP in the official setup ([requirements](https://github.com/apple/ml-mobileclip/blob/main/requirements.txt)). | Code is MIT, but the released model weights are limited to non-commercial research; product development and commercial product/service use are expressly excluded ([model license](https://raw.githubusercontent.com/apple/ml-mobileclip/main/LICENSE_MODELS)). | Published latency is for Apple mobile hardware, not Wardrowbe's self-hosted x86 CPU. | **Reject for product integration.** The weights' license is incompatible with a generally usable product path even though the architecture is efficient. |
| Structured metadata only | Useful for eliminating impossible pairs and prioritizing plausible ones, but common garments can share every tag. AI-generated metadata can also disagree across angles. | No new model or runtime dependency; fields already exist. | No additional model license. | Negligible compute. | Required second signal, never sufficient by itself. |

### Why not make the embedding score an automatic merge rule?

An embedding is a learned similarity representation, not a physical-identity proof. Two mass-market black T-shirts can be closer than front/back photos of one distinctive jacket. FashionCLIP itself documents out-of-distribution limitations, while DINOv2 documents generic retrieval rather than garment-instance verification. A high score can therefore prioritize review but cannot safely mutate user data.

## Proposed scoring pipeline

### 1. Normalize each image into repeatable views

Persist embeddings per image, not only per item. For each photo generate:

- a standard RGB medium-image embedding;
- when issue #2 produced an accepted transparent garment cutout, a garment-crop embedding composited on a fixed neutral background;
- model ID, immutable model revision/checksum, preprocessing version, source image ID, and creation timestamp.

Do not silently substitute one representation for another: model and preprocessing changes invalidate score comparability and require re-embedding. A cutout may improve background invariance, but known segmentation leakage means it must remain only one candidate signal.

For a new item versus an existing canonical item, compare against every image of that canonical item and its confirmed aliases. Use the maximum image-pair similarity to find candidates, but show the actual best-matching photo pair in review so the user can understand the suggestion.

### 2. Candidate retrieval

For the MVP, a user's wardrobe is small enough to load that user's normalized 384-float vectors and compute exact cosine similarities in the worker. At 32-bit precision, the vector payload is about 1,536 bytes per image before row/index overhead. This avoids changing the stock PostgreSQL image.

If collections later make this slow, pgvector supports cosine distance, exact nearest-neighbor search by default, and HNSW/IVFFlat approximate indexes; its documented `vector` storage is `4 * dimensions + 8` bytes ([pgvector README](https://github.com/pgvector/pgvector#querying)). Adding pgvector now would expand self-hosting and migration requirements without evidence that Wardrowbe needs ANN scale.

### 3. Metadata compatibility

Apply metadata after visual retrieval. Treat only user-confirmed/manual values as hard evidence; AI values are soft evidence.

- Hard veto when both manually confirmed types map to incompatible body roles (for example shoes versus upper body).
- Strong positive for exact manual type/subtype and brand matches.
- Soft positive/negative for normalized color-family overlap, pattern, and material.
- Missing values are neutral, not mismatches.
- AI conflicts lower rank or request review; they do not suppress a visually strong candidate.
- Never use style, season, or formality as identity evidence: many unrelated garments share them.

Do not collapse the signals into an unexplained “AI confidence.” Persist and return the image cosine score, metadata contributions/vetoes, model revision, and threshold revision separately.

## Threshold calibration

There is no defensible universal cosine threshold. Calibrate on Wardrowbe's actual input distribution before shipping:

1. Build consented fixtures grouped by physical garment: front/back, folded/unfolded, hanger, flat-lay, worn, different lighting, and resized/recompressed copies.
2. Add hard negatives deliberately: same type/color/material/brand, near-identical basics, multipacks, patterned items with similar layouts, and one person wearing different garments.
3. Split by **physical garment**, not by photo. All photos of one garment must stay in one split to prevent identity leakage.
4. Record pHash Hamming distance, maximum DINO cosine similarity, each metadata feature, and the human label for every pair.
5. Choose a `T_review` from the calibration precision-recall curve. Precision measures resistance to false match suggestions and recall measures how many true matches are surfaced; scikit-learn's official definition and threshold output are documented in [`precision_recall_curve`](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html).
6. Optimize for high recall subject to a tolerable review queue, then freeze the threshold and evaluate once on the held-out garment set. Report pair-level precision/recall plus candidate-level recall@K.
7. Keep an “uncertain” band rather than manufacturing certainty: below `T_review` no suggestion; at/above it user review. Do **not** define an embedding-only auto-merge threshold.

The reported blue-shorts pair must become a positive fixture. Its pHash distance of 20 establishes that stage 1 missed it; its DINO score must be measured rather than assumed. Every threshold change should carry a revision and regression tests for both false positives and false negatives.

### Local calibration snapshot (2026-08-26)

The confirmed front/back blue-shorts pair was measured locally with the pinned `facebook/dinov2-small` revision and slow Transformers 4.52.3 image processor. The user photos were not committed to the repository.

- Confirmed positive: cosine `0.894604` (pHash Hamming distance `20`).
- Six distinct same-type T-shirt pairs: maximum cosine `0.749401`; the other scores were `0.745989`, `0.357405`, `0.283792`, `0.198111`, and `0.143698`.
- CPU smoke measurement: 384 dimensions, approximately `3.6–4.0 s` cold load plus first image and `0.08–0.15 s` per warm image on the development host.
- Initial `T_review`: `0.85`. This creates a review suggestion only and remains configurable as `GARMENT_MATCHING_REVIEW_THRESHOLD`.

This is a minimal calibration set, not evidence of production-level recall. The repository therefore freezes matcher-boundary vectors in tests, records model/preprocessing revisions with every vector, and must accumulate more user-confirmed positives and same-type hard negatives before changing the threshold.

## Safe canonical-item and review design

### Data model

Add three concepts rather than overloading `image_hash`:

1. `item_image_embeddings`
   - `item_image_id` (or explicit primary-image reference), `embedding`, `model`, `model_revision`, `preprocess_revision`, timestamps;
   - one active embedding per image and version, with older versions replaceable/rebuildable.
2. `duplicate_match_candidates`
   - ordered pair of same-user item IDs, status (`pending`, `merged`, `kept_separate`), best image pair, pHash distance if available, cosine score, metadata evidence, threshold revision, timestamps;
   - unique pair constraint; ownership and self-pair checks;
   - kept-separate pairs are not proposed again unless the user explicitly resets the decision or a materially changed matcher revision requires fresh review.
3. `ClothingItem.canonical_item_id`
   - nullable self-reference; `NULL` means canonical, non-null means confirmed alias;
   - constrain aliases to the same user and prevent chains/cycles in the service: always point directly to a root canonical item.

### Review flow

1. Upload and store the new item normally. Exact/near-exact pHash copies can retain the existing blocking behavior.
2. After tagging and embedding, create zero or more pending candidates. Do not archive, hide, delete, or merge anything yet.
3. Show side-by-side photos, structured differences, and two explicit actions:
   - **Merge into this item**: user chooses the canonical record and resolves conflicting editable metadata.
   - **Keep separate**: durable negative label; both items remain active and the pair is not suggested again.
4. On merge, set the losing record's `canonical_item_id`, archive it with a duplicate reason, and make all of its primary/additional photos visible in the canonical gallery. Keep its files and event rows intact.
5. Aggregate wear/wash history and counters through the canonical root instead of destructively rewriting every foreign key. Resolve historical outfit item IDs to the canonical record for current display, while preserving the original event record for auditability.
6. Exclude rows with non-null `canonical_item_id` from current pairing/recommendation candidate queries. Pending candidates remain separate: hiding one before confirmation would silently conflate similar garments.
7. Provide **Undo merge**: clear the alias, unarchive it, restore its own gallery visibility, and invalidate/recompute affected aggregate caches. This makes an erroneous human decision recoverable.

For photo preservation, the existing `ItemImage` relationship can be surfaced as an aggregate gallery across the root and aliases. A later cleanup migration may physically reparent image rows, but that is unnecessary and riskier for the MVP.

## Implementation sequence

1. **Fix and test pHash near-duplicate behavior.** Parse stored hashes and compare Hamming distance within the user scope; calibrate a dedicated near-identical-image threshold using recompression/resize fixtures. Keep this threshold independent from garment identity.
2. **Add schema and domain service.** Introduce canonical aliases, candidate decisions, image embeddings, root resolution, cycle prevention, and canonical-only query helpers.
3. **Add optional embedding worker.** Pin DINOv2-S model/revision; lazy-load once per worker; bounded CPU concurrency; persist failures without blocking item creation.
4. **Add candidate generation and API.** Exact cosine scan per user, metadata evidence, idempotent candidate rows, list/detail endpoints.
5. **Add review UI and reversible merge transaction.** Include conflict resolution, gallery aggregation, history aggregation, and undo.
6. **Update pairing/recommendation queries.** Centralize `canonical_item_id IS NULL` filtering so no candidate pool accidentally counts aliases.
7. **Calibrate before enabling by default.** Ship fixtures and metrics with the threshold configuration. Measure backend image-size increase, model download, cold start, peak RSS, and CPU latency on the minimum supported host.

## Required tests

- Byte-identical, resized, and recompressed files are blocked by pHash; different-angle positives are not expected to pass pHash.
- Positive identity fixtures cover front/back, worn/flat-lay, hanger, folds, lighting, and additional-image matching.
- Hard negatives cover visually similar garments and metadata-identical basics.
- Candidate threshold boundary tests use frozen embeddings or a tiny deterministic fake; separate model smoke tests verify real preprocessing/output dimensions.
- AI metadata conflict cannot hard-veto a true candidate; manual incompatible type can.
- No pending candidate changes item visibility or recommendations.
- Merge preserves every file, additional image, wear/wash event, outfit reference, and user metadata choice.
- Canonical-only pairing/recommendation queries return one physical garment.
- Keep-separate decisions are idempotent and suppress repeated review noise.
- Cross-user candidates and merges are impossible.
- Concurrent merge decisions cannot create cycles, chains, or two canonical roots.
- Undo restores both independent records and candidate behavior.
- Model/preprocessing/threshold revision changes trigger controlled re-embedding/re-evaluation.

## Decision

Adopt **DINOv2 ViT-S/14 embeddings + trusted structured metadata + mandatory human review**, with pHash retained as a separate exact/near-exact image stage. Use a reversible canonical alias instead of deleting or physically collapsing records. Defer pgvector until measured collection size or latency requires it, and do not adopt MobileCLIP weights under their current research-only license. FashionCLIP remains a benchmark challenger only after Wardrowbe has a representative, garment-level fixture set.
