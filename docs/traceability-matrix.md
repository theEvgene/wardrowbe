# Product traceability matrix

Status values are **ready**, **partial**, **absent**, and **outside current goal**. The weighted completion score counts ready as 1, partial as 0.5, and absent as 0. The original 40-row reconstruction in Epic #18 incorrectly omitted context-aware generation and conversational refinement that the product requirements had already named. Rows 41–56 correct that denominator; the earlier 100% claim applies only to the accidentally narrowed Epic #2 subset.

| # | Use case | Before Epic #2 | After Epic #2 | Evidence |
|---:|---|---|---|---|
| 1 | Run the application as a self-hosted stack | ready | ready | Compose frontend, backend, PostgreSQL, Redis, worker |
| 2 | Log in and complete onboarding without false dashboard errors | ready | ready | #6; browser E2E |
| 3 | Upload one wardrobe item | ready | ready | item API and browser/full-stack smoke |
| 4 | Bulk-upload wardrobe items | ready | ready | bulk item API tests |
| 5 | Store original, medium, and thumbnail image variants | ready | ready | image service tests |
| 6 | Tag an uploaded item asynchronously | ready | ready | tagging worker tests; real Gemma smoke |
| 7 | Recover stale or interrupted tagging work | ready | ready | stale recovery and tagging durability tests |
| 8 | Reject exact duplicate images | ready | ready | duplicate and item API tests |
| 9 | Detect recompressed or near-identical images | ready | ready | pHash duplicate tests |
| 10 | Review a probable same-garment match | ready | ready | #3; duplicate review API/UI |
| 11 | Merge two records under a canonical garment | ready | ready | duplicate merge tests |
| 12 | Keep similar garments separate durably | ready | ready | duplicate keep-separate tests; real smoke |
| 13 | Preserve canonical lineage and associated images | ready | ready | duplicate service tests |
| 14 | Store structured AI classification metadata | ready | ready | tagging schemas and worker tests |
| 15 | Review, correct, and confirm AI metadata with provenance | ready | ready | #7; metadata review tests |
| 16 | Remove an ordinary scene background | ready | ready | background removal tests |
| 17 | Extract a garment from a person/mannequin/hanger image | ready | ready | #2, #9, #14, #15; real smoke |
| 18 | Reject low-quality or semantically unsafe masks | ready | ready | extraction quality/leakage tests |
| 19 | Preserve and expose a transparent garment cutout | ready | ready | extraction API and composite tests |
| 20 | Undo a processed-image replacement safely | ready | ready | image undo/replace tests |
| 21 | Exclude archived aliases from active wardrobe candidates | ready | ready | item, pairing, detected-style and style-generation tests |
| 22 | See all pieces together in a deterministic composite preview | ready | ready | #5; frontend and browser E2E |
| 23 | Use and verify a local Gemma runtime | partial | ready | `gemma3:4b` real full-stack smoke |
| 24 | Observe factual style values produced for real wardrobe photos | partial | ready | real smoke detected `casual`; model also produced `classic` in diagnostic runs |
| 25 | Handle styles dynamically rather than from a hardcoded catalog | partial | ready | #19; `/styles/detected` and selector |
| 26 | Default the requested outfit count to 3 | partial | ready | #21; request schema and UI tests |
| 27 | Request a parameterized outfit count N | partial | ready | #21; supported range 1–20 |
| 28 | Restrict style generation to the current user's active canonical items | partial | ready | style service query and integration tests |
| 29 | Validate complete body slots for every generated outfit | partial | ready | style service adversarial tests |
| 30 | Reject model item references outside the candidate wardrobe | partial | ready | style service adversarial tests |
| 31 | Persist generated style outfits in the normal Outfit collection | partial | ready | `target_style` migration and API tests |
| 32 | Run the Epic path automatically in CI | partial | ready | #23; backend, frontend and Playwright jobs in `.github/workflows/ci.yml` |
| 33 | Automatically run safe garment extraction after upload/tagging | absent | ready | #20; single/bulk API and worker tests |
| 34 | List normalized styles detected in the current wardrobe | absent | ready | #19; detected-style API tests |
| 35 | Select exactly one detected style in the UI | absent | ready | #19; frontend selector tests |
| 36 | Generate outfits without a mandatory source item | absent | ready | #21; `generate-by-style` contract |
| 37 | Enforce diversity across the generated batch | absent | ready | #21/#22; key-piece set validation |
| 38 | Persist exactly N outfits atomically or persist none | absent | ready | #21/#22; transaction and adversarial tests |
| 39 | Generate a real style batch with local `gemma3:4b` | absent | ready | #23 real smoke: 2 valid outfits in 3,439 ms |
| 40 | Complete upload → metadata → extraction → styles → N outfits → composites | absent | ready | backend integration, browser E2E and real full-stack smoke |
| 41 | Select the date for which outfits are generated | partial | partial | `Outfit.scheduled_for` exists, but style batches always default to today and expose no date control |
| 42 | Resolve weather for the selected date and saved location | partial | partial | current/daily weather APIs exist, but selected-date weather is not connected to style generation |
| 43 | Persist the weather snapshot actually used for each generated Outfit | partial | partial | `Outfit.weather_data` is used by the legacy recommendation path, not by style batches |
| 44 | Describe the activity the outfit must support | absent | absent | no activity field, generation contract, or UI |
| 45 | Apply saved comfort, color, layering, variety, and repeat preferences to style batches | partial | partial | legacy recommendation prompt uses preferences; `StyleOutfitService` currently uses only AI endpoint settings |
| 46 | Add free-form per-request outfit constraints | absent | absent | no style-batch constraint contract or UI |
| 47 | Require selected wardrobe items in every requested outfit | partial | partial | legacy `/suggest` accepts include IDs; style batches do not |
| 48 | Exclude selected wardrobe items from the request | partial | partial | legacy `/suggest` accepts exclude IDs; style batches do not |
| 49 | Enforce request constraints without weakening current-user active-canonical guards | partial | partial | candidate ownership guards exist; context/constraint conflict validation does not |
| 50 | Review the date, weather, activity, and constraints actually used by generation | partial | partial | weather and date response fields exist, but the style form does not submit or persist a complete generation context |
| 51 | Refine a generated Outfit with a natural-language instruction | absent | absent | no refinement endpoint or service |
| 52 | Preserve the original Outfit and link every conversational revision as a new version | absent | absent | generic replacement lineage exists, but no conversational revision contract uses it |
| 53 | Continue a multi-turn refinement from the latest Outfit while retaining prior context | absent | absent | no persisted refinement history or multi-turn UI |
| 54 | Reject hallucinated, incomplete, conflicting, unchanged, or unauthorized refinements | absent | absent | Epic #2 validation is batch-only; no refinement validation path exists |
| 55 | Refine an Outfit through a localized conversational UI with retryable errors | absent | absent | no conversational controls on generated Outfit cards |
| 56 | Complete context → N outfits → multi-turn refinement → composites through API, browser, CI, and real local model | absent | absent | no combined Epic #3/#4 verification path |

## Completion

- Before Epic #2, using the corrected 56-row denominator: 22 ready, 18 partial, 16 absent = **55.4% weighted completion**.
- After Epic #2 / before Epic #3: 40 ready, 8 partial, 8 absent = **78.6% weighted completion**.
- Target after Epic #3 and Epic #4: 56 ready, 0 partial, 0 absent = **100% of the corrected approved scope**.

The following product directions remain **outside the current Epic #3/#4 goal** and are not included in the 56-row denominator: extracting multiple garments from one person photo, full-body person analysis, virtual try-on, avatar/body rendering, purchase recommendations, and wardrobe gap analysis.
