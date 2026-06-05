# File Audit

This folder started as a working research directory. The public repo should show the final, credible work without publishing raw training dumps, virtualenv dependencies, source PDFs, or unsafe API-key experiments.

## Best Versions To Keep Public

| Area | Best file or folder | Why it is the strongest version |
| --- | --- | --- |
| Dictionary workbench | `app.py` | Most complete dictionary UI/API concept; now has verified Flask routes for search, status, entry edits, promotion, batch image/PDF jobs, and re-analysis. |
| Syllable dataset | `pipeline/ocr_training/1_karen_dataset_gen.py` | Strongest proof of custom data generation; builds Sgaw Karen syllable combinations into YOLO format. |
| Paragraph dataset | `pipeline/ocr_training/041_gen_paragraph_data.py` | Most impressive dataset step because it moves from isolated glyphs to line/paragraph layout. |
| Latest training | `pipeline/ocr_training/036_train_v5.py` | Latest visible model-training script in the folder. |
| Tiled inference | `pipeline/ocr_training/040_tile_infer.py` | Strongest inference demo path for larger paragraph images. |
| Validation/gap analysis | `pipeline/ocr_training/016_run_full_validation_export.py`, `017_analyze_detection_gaps.py`, `032_true_gap_analysis.py` | Shows measurement, failure analysis, and targeted improvement work. |
| Legacy source decoding | `pipeline/dictionary_processing/042_build_KNU_decoder.py` | High-value work because it handles KNU legacy font extraction and Unicode conversion. |
| Dictionary page prep | `pipeline/dictionary_processing/043_pdf_page_splitter_zoom.py`, `split_rows_from_dict_images.py` | Best PDF/image preprocessing version. |
| Dictionary sorting | `pipeline/dictionary_processing/046_sort_engine.py` | Most credible language-specific logic: consonant, tone, vowel, medial sort order and safe correction propagation. |
| Imported local translator suite | `pipeline/dictionary_processing/local_translator_suite/` | Best useful import from the standalone dictionary-builder repo; adds local scrape/cache lookup, reverse parsing, batch text handling, and a mini-LM seed plan without replacing the main OCR workbench. |
| Proof assets | `assets/proof/` | Selected charts, predictions, metrics, and static dictionary output suitable for GitHub and portfolio media. |

## Archived Or Ignored

| Files/folders | Decision | Reason |
| --- | --- | --- |
| `.venv/` | Ignored | Installed dependencies should never be committed. |
| `karendataset/`, `dict_images/`, `dict_rows/`, `karen_dict_pages/`, `app_data/` | Ignored | Generated data and raw OCR working outputs are too large/noisy for a portfolio repo. |
| `dataset_part_*.bin`, `karen_dataset_yolov8.zip` | Ignored | Large dataset packaging artifacts. |
| `*.pt` model weights | Ignored | Better distributed as GitHub Releases or external artifacts, not normal Git blobs. |
| Raw PDFs | Ignored | Source/reference material, not core implementation. |
| `ideas_attempts/archived_builders/` | Ignored | Superseded Streamlit, AI Studio, Firebase, one-off Gemini, agent, and template experiments. |
| `bootstrap_ocr.py`, `gemini_dict_ocr.py` | Archived/ignored | Superseded and contained hard-coded API-key patterns. Do not publish. |
| Nested `s'gaw-karen-dictionary-builder/` and `karen_dict_template/` | Archived/ignored | Useful attempts, but less credible as final work than the Python OCR/dictionary pipeline. |
| `otpayt02/Karen-Web-Scraper` source repo | Reference only | Useful conceptually for web lookup and Gemini fallback, but the TypeScript/AI Studio scaffold is less polished than the Python pipeline. No final code import. |
| `otpayt02/S-gaw-Karen-AI-ML-OCR-Language-Recognition` source repo | Reference only | Contains README/license positioning, not implementation code stronger than this repo. |
| Generated lookup logs and copied music-site samples from `S-gaw-Karen-Dictionary-Builder` | Left out | Good private history, but too noisy and generated for a clean public portfolio. |

## Best Dictionary Builder

The best public dictionary builder is the root `app.py` plus the dictionary processing scripts:

- `app.py` for the Flask review and batch-processing surface.
- `042_build_KNU_decoder.py` for legacy-source conversion.
- `043_pdf_page_splitter_zoom.py` and `split_rows_from_dict_images.py` for input preparation.
- `046_sort_engine.py` for Sgaw Karen-aware dictionary ordering and correction behavior.
- `local_translator_suite/` as the strongest imported side workflow for scrape/cache lookup, reverse parsing, and batch text auditing.

The React/Firebase builder is visually more app-like, but it reads as an AI Studio prototype and depends on Firebase setup. The Streamlit builder is easy to demo but only covers one-image extraction. For a serious portfolio piece, the Python pipeline is more credible because it shows data generation, OCR training, inference, extraction, and review.

See `docs/SOURCE_REPOS.md` for the related GitHub repo consolidation audit.
