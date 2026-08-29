# MVP traceability matrix

Status values are **ready**, **partial**, **absent**, and **outside MVP**. The weighted completion score counts ready as 1, partial as 0.5, and absent as 0. This matrix reconstructs the 40-use-case baseline recorded in Epic #18 and maps every row to its implementation evidence.

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

## Completion

- Before Epic #2: 22 ready, 10 partial, 8 absent = **67.5% weighted completion**.
- After Epic #2: 40 ready, 0 partial, 0 absent = **100% of the approved 40-use-case MVP**.

The following product directions remain **outside MVP** and are not included in the 40-row denominator: extracting multiple garments from one person photo, full-body person analysis, virtual try-on, avatar/body rendering, weather or activity planning, conversational styling, purchase recommendations, and wardrobe gap analysis.
