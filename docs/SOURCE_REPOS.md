# Source Repo Consolidation

This repository is the public cornerstone project for the Sgaw Karen OCR work. The related GitHub repos were audited as source material, but only the parts that strengthen this portfolio project were imported.

## Destination

| Repo | Decision |
| --- | --- |
| `otpayt02/s-gaw-karen-ocr` | Canonical public repo for the combined OCR, dictionary extraction, and portfolio proof assets. |

## Audited Source Repos

| Source repo | Latest audited commit | What was kept | What was left behind |
| --- | --- | --- | --- |
| `otpayt02/S-gaw-Karen-Dictionary-Builder` | `a8fb7999e7e5532b5cbe77b97b90d5686b62a094` | Imported the runnable local translator/dictionary suite under `pipeline/dictionary_processing/local_translator_suite/`. This keeps the Flask app, static UI, HTML template, requirements, mini-LM seed plan, and one tiny clean input fixture. | Generated lookup logs, bad backup JSON, reverse cache data, large copied music-site samples, and run outputs were not imported. They are useful as private history, not portfolio code. |
| `otpayt02/Karen-Web-Scraper` | `14633c41d0e4f127633954da739a9d06be70fb1f` | Used as design evidence for the web lookup idea: Glosbe lookup, KarenDictionary lookup, cached attempts, and LLM fallback routing. No code was imported into the final repo. | The repo is an AI Studio/Vite TypeScript app with generated scaffolding and a Gemini-specific server. It is less coherent than the Python pipeline here, so it should remain a reference/attempt rather than final portfolio code. |
| `otpayt02/S-gaw-Karen-AI-ML-OCR-Language-Recognition` | `011a26c97222128d8615762f22a7f5ec38daa8db` | No code import. Its language-access positioning is already represented more credibly by this repo's README, architecture docs, OCR scripts, metrics, and proof assets. | The repo only contains a README and license, so it is not a stronger implementation source than the current OCR pipeline. |

## Best Versions After Consolidation

The strongest public implementation remains the OCR/dictionary pipeline in this repo:

- `app.py` for OCR-assisted dictionary review, image/PDF batch jobs, search, entry editing, and correction workflows.
- `pipeline/ocr_training/1_karen_dataset_gen.py`, `036_train_v5.py`, `041_gen_paragraph_data.py`, and `040_tile_infer.py` for dataset generation, training, and inference proof.
- `pipeline/dictionary_processing/042_build_KNU_decoder.py`, `043_pdf_page_splitter_zoom.py`, and `046_sort_engine.py` for legacy dictionary handling and Sgaw Karen-specific ordering.
- `pipeline/dictionary_processing/local_translator_suite/` for the best imported dictionary-builder side project: local scraping, caching, reverse parsing, batch text processing, and a mini-LM seed plan.

## Portfolio Positioning

Do not present the old repos as separate flagship projects. Present this repo as the combined cornerstone project and mention the older repos only as source-history evidence if needed:

> I consolidated my earlier Sgaw Karen OCR, scraper, and dictionary-builder experiments into one portfolio-ready repository. The final version keeps the strongest OCR training, dictionary extraction, local lookup, and proof assets while leaving generated data, large samples, and early prototypes out of Git.
