# Garment-only extraction for Wardrowbe

Research for [theEvgene/wardrowbe#2](https://github.com/theEvgene/wardrowbe/issues/2), performed 2026-08-25. The repository checkout inspected for this note is Wardrowbe 1.8.2 at `f100e54e353495d9b459e6b215299cc9af4e05df`.

## Recommendation

Build the first vertical slice around rembg's existing `u2net_cloth_seg` ONNX model, exposed as an explicit **garment-only** operation for worn-on-person tops, bottoms, and full-body garments. Keep the current generic `u2net` operation unchanged as a separate scene-background-removal path. Do not silently fall back from failed garment isolation to a generic person-shaped foreground: a rejected garment mask must leave the stored image untouched and return a low-confidence/unsupported outcome that the UI can explain.

This is the smallest CPU-capable option because Wardrowbe already installs `rembg[cpu]`, caches a rembg session, and runs inference outside the async event loop. `u2net_cloth_seg` is already distributed through rembg and uses the same ONNX Runtime dependency rather than adding PyTorch and Transformers. Its source model was trained specifically to parse clothing from human portraits into upper-body, lower-body, and full-body classes at 768×768; the source repository reports a 165 MB checkpoint. [rembg model list](https://github.com/danielgatis/rembg#models), [cloth model source](https://github.com/levindabhi/cloth-segmentation#techinal-details), [ONNX Runtime CPU documentation](https://onnxruntime.ai/docs/get-started/with-python.html#install-onnx-runtime)

This first slice should not claim that mannequin, hanger, and flat-lay support is solved. Those inputs are outside the model's documented human-portrait training domain. Add all four photo modes to a committed evaluation fixture set now, retain generic foreground removal for non-person scenes, and make automatic routing a later change only after measured acceptance thresholds exist.

## Current Wardrowbe integration boundary

Wardrowbe's `BackgroundRemovalProvider.remove()` currently returns only an RGBA image. `RembgProvider` lazily creates and caches a session, while `ImageService.remove_background()` owns the durable behavior: the first `_orig.jpg` backup wins, the accepted RGBA result is composited onto a color, and original/medium/thumbnail files are replaced together. Restore regenerates all sizes from the backup and then deletes it. The endpoint stores or clears `original_image_path`. [provider source](https://github.com/Anyesh/wardrowbe/blob/f100e54e353495d9b459e6b215299cc9af4e05df/backend/app/services/background_removal.py), [image service source](https://github.com/Anyesh/wardrowbe/blob/f100e54e353495d9b459e6b215299cc9af4e05df/backend/app/services/image_service.py), [API source](https://github.com/Anyesh/wardrowbe/blob/f100e54e353495d9b459e6b215299cc9af4e05df/backend/app/api/items.py)

The useful architectural consequence is that model selection and mask validation can remain inside the provider/pipeline, while backup/restore stays in `ImageService`. The provider contract does need to become richer than `Image -> Image`: it must carry the model/version, selected garment class, quality metrics, outcome (`accepted`, `low_confidence`, `unsupported`, `failed`), and warning. Only an `accepted` result should reach `_save_all_sizes()`.

The current backup is copied before inference. For a rejected result, either defer creation until after validation but before the first overwrite, or delete a newly created, unreferenced backup on rejection. In both designs, preserve the tested rule that a pre-existing first backup is never overwritten and that restore remains byte/source consistent.

## Why generic foreground removal keeps the person

The default U²-Net is a salient-object detector: its task is to isolate the visually salient foreground, not assign semantic clothing classes. The original paper describes U²-Net as a salient object detection architecture and reports a 176.3 MB full model (the paper's 30 FPS figure is on a GTX 1080 Ti, not a CPU benchmark). A person wearing a shirt is therefore one coherent foreground object, so removing only the scene background is expected behavior. [U²-Net paper](https://arxiv.org/abs/2005.09007), [official U²-Net repository](https://github.com/xuebinqin/U-2-Net)

Human/clothing parsing instead assigns each pixel to semantic regions such as upper clothes, pants, dress, face, and arms. That semantic distinction is what permits removal of the wearer while retaining the garment. [SCHP paper](https://arxiv.org/abs/1910.09777)

## Options

| Option | Clothing classes and fit | CPU/dependency impact | Confidence and fallback | Licensing and operational risk | Decision |
|---|---|---|---|---|---|
| Existing generic rembg `u2net` | One salient-foreground mask. Good baseline for isolated flat-lay objects, but deliberately cannot distinguish garment from person, mannequin, or hanger. | Already installed; ONNX Runtime CPU; U²-Net family is about 176 MB. | Soft mask exists, but it measures foreground saliency rather than garment identity. | rembg code is MIT and U²-Net code is Apache-2.0; rembg warns that model weights have independent licenses. | Keep as scene-background path and non-person fallback, never label its person-shaped result as garment isolation. |
| rembg `u2net_cloth_seg` | Four-way network output: background plus upper, lower, and full-body clothing. Trained on 45k iMaterialist Fashion 2019 images collapsed from 42 labels to three garment groups. Best fit for the reported worn-person failure. | No new inference framework. rembg runs the converted ONNX model at 768×768; source checkpoint is 165 MB, so image size, cold-start time, and CPU latency should be benchmarked locally. | rembg applies `argmax` and returns masks, not calibrated confidence. Use mask-quality gates and an explicit rejection outcome. | rembg and the linked cloth repository are MIT; the underlying U²-Net repo is Apache-2.0. Because rembg explicitly separates weight licensing from its own license, retain notices and verify the converted weight/dataset terms before redistribution. | Recommended first slice. |
| `mattmdjaga/segformer_b2_clothes` | 18 ATR labels, including upper clothes, skirt, pants, dress, belt, shoes, body parts, bag, and scarf. Better semantic detail than three broad classes. The card reports mean IoU 0.69; class IoUs vary from 0.29 (scarf) to 0.84 (pants/bag). | Adds PyTorch + Transformers. The model has 27.4M parameters and a 109 MB safetensors file; the repository is 549 MB because it also contains duplicate weights and training artifacts. CPU inference is possible but must be measured. | Logits permit per-pixel softmax summaries, though those are not automatically calibrated probabilities. | The model card says `License: other` and links to NVIDIA's SegFormer license, whose section 3.3 limits use to non-commercial research/evaluation. | Do not adopt for a generally distributable product without legal clearance or differently licensed weights. |
| SCHP (LIP/ATR) | Fine-grained human parsing. LIP has 20 labels (upper clothes, dress, coat, pants, jumpsuit, skirt, body parts, etc.); ATR has 18. The authors report 59.36 LIP mIoU and 82.29 ATR mIoU. | Custom PyTorch inference and preprocessing. The official environment is Python 3.8, PyTorch 1.5.1, CUDA 10.1, and OpenCV 4.4, far from Wardrowbe's Python 3.11 slim image. | The extractor can save logits, allowing confidence summaries and class unions. | Repository code is MIT, but pretrained checkpoint terms are not separately stated. Old CUDA-oriented dependencies and maintenance cost dominate. | Strong research baseline, poor first production slice. Revisit only if the three-class model fails the fixture matrix. |

Primary sources for the table: [rembg's model and weight-license documentation](https://github.com/danielgatis/rembg#models), [`u2net_cloth_seg` implementation](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2net_cloth_seg.py), [rembg mask composition](https://github.com/danielgatis/rembg/blob/main/rembg/bg.py), [cloth model repository and MIT license](https://github.com/levindabhi/cloth-segmentation), [SegFormer clothes model card and files](https://huggingface.co/mattmdjaga/segformer_b2_clothes), [SegFormer model configuration](https://huggingface.co/mattmdjaga/segformer_b2_clothes/blob/main/config.json), [NVIDIA SegFormer license](https://github.com/NVlabs/SegFormer/blob/master/LICENSE), [SegFormer paper](https://arxiv.org/abs/2105.15203), [SCHP repository](https://github.com/GoGoDuck912/Self-Correction-Human-Parsing), [SCHP environment](https://github.com/GoGoDuck912/Self-Correction-Human-Parsing/blob/master/environment.yaml), and [SCHP MIT license](https://github.com/GoGoDuck912/Self-Correction-Human-Parsing/blob/master/LICENSE).

## Important rembg behavior

`u2net_cloth_seg` must be called with exactly one `cloth_category` (`upper`, `lower`, or `full`). If the category is omitted, its session returns all three masks. rembg then creates one cutout per mask and concatenates those cutouts vertically, changing the image dimensions and making the result unsuitable for Wardrowbe's current overwrite flow. [cloth-session source](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2net_cloth_seg.py#L615-L730), [rembg composition source](https://github.com/danielgatis/rembg/blob/main/rembg/bg.py#L1475-L1576)

Wardrowbe already has a reusable type-to-body-role map in `backend/app/utils/clothing.py`. Map `base_top`, `mid_layer`, and `outer_layer` to `upper`; `bottom` to `lower`; and `full_body` to `full`. Footwear, socks, neckwear, and general accessories are unsupported by this three-class model and must not be guessed. [Wardrowbe role map](https://github.com/Anyesh/wardrowbe/blob/f100e54e353495d9b459e6b215299cc9af4e05df/backend/app/utils/clothing.py)

## Confidence and safe fallback

The rembg cloth session converts network output directly with `argmax`, resizes the class map, and exposes no probability score. Therefore, call the first-slice checks **quality gates**, not model confidence. Useful deterministic diagnostics are:

- selected-mask area as a fraction of the frame (reject empty/tiny and near-full-frame masks);
- largest connected-component area divided by total mask area (reject heavily fragmented masks);
- border-touch fraction (flag masks that appear to be leaked background);
- overlap of the selected cloth mask with the generic foreground mask (reject implausible cloth pixels outside the photographed foreground);
- output dimensions and non-empty alpha bounds;
- selected class and item type/role agreement.

Thresholds must come from Wardrowbe's fixture set, not be invented from a single photograph. Save diagnostics and the exact provider/model/version with the processing outcome. Do not describe heuristic scores as probabilities.

Fallback semantics should be explicit:

1. **Garment-only requested, accepted cloth mask:** save all sizes and preserve/set the original backup.
2. **Garment-only requested, low-quality or unsupported:** do not overwrite any image; return an actionable warning and diagnostics.
3. **Scene background removal requested:** retain the current generic provider behavior.
4. **Later automatic mode:** route to garment-only only after photo-mode fixtures demonstrate acceptable behavior; otherwise choose the generic operation while clearly naming it as scene-background removal.

This avoids the current misleading outcome where HTTP 200 means only that a provider returned an image, even if the person remains.

## Smallest viable vertical slice

1. Add a typed extraction result and an explicit mode (`scene` versus `garment`) without changing restore semantics.
2. Add a cached `u2net_cloth_seg` session next to the cached generic session. Pass one explicit `cloth_category`, derived from the existing item role.
3. Implement deterministic quality metrics and an `accepted` gate. On rejection, return without calling `_save_all_sizes()`; make backup creation transactional as described above.
4. Preserve transparent RGBA inside the provider. Keep solid-color compositing in `ImageService`, as today.
5. Return processing metadata/warnings to the endpoint and UI; log provider, model, package version, class, outcome, latency, and quality metrics without logging user image content.
6. Start with two golden integration fixtures: the known worn T-shirt regression and one clearly isolated non-person garment. Unit-test category mapping, the no-category concatenation guard, rejection/no-overwrite, first-backup-wins, thumbnail consistency, and restore. Then add mannequin, hanger, lower-body, full-body, occlusion, and ambiguous multi-garment fixtures before enabling automatic routing.

## Validation plan and decision gate

Measure cold and warm CPU latency, peak resident memory, mask acceptance/rejection, garment retention, and person/mannequin/hanger leakage on the same Docker CPU limits used by self-hosters. There is no trustworthy official CPU latency number for this exact converted cloth model, so local measurement is required.

Advance beyond the first slice only if the worn-person fixtures reliably remove body pixels without materially cutting away the selected garment. If mannequin/hanger/flat-lay results are weak, keep generic foreground removal for those modes and investigate a separately licensed fine-grained parser or a purpose-trained/quantized ONNX model. Do not move to the examined SegFormer checkpoint merely for better labels because its linked license is non-commercial; do not move to SCHP unless the accuracy gain justifies owning an old custom PyTorch stack.
