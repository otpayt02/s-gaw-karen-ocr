# Sgaw Karen OCR and Dictionary Pipeline

This repository is a portfolio-ready cleanup of a custom OCR and dictionary-processing project for Sgaw Karen, an underrepresented language with limited off-the-shelf OCR and translation support.

The work combines synthetic dataset generation, YOLO training/inference, legacy dictionary processing, KNU font decoding, Gemini-assisted dictionary extraction, and a Flask review workbench for turning OCR output into structured dictionary entries.

This is also the consolidation point for the earlier Karen language repos under `otpayt02`: web-scraper experiments, OCR-language positioning notes, and the standalone Sgaw Karen dictionary builder. Only the useful final material was kept here; generated logs, large samples, and early scaffolds were left out.

## Highlights

- Generated a Roboflow/YOLO-style syllable dataset for thousands of Sgaw Karen syllable patterns.
- Trained and fine-tuned OCR models across multiple versions; local project metrics record mAP50 moving from `0.888` in v1 to `0.965` in v2.
- Built paragraph-level dataset generation so the OCR model can move beyond isolated syllables toward real text lines.
- Built dictionary tooling for PDF page rendering, row splitting, KNU legacy-font decoding, entry extraction, correction logging, sort-order handling, and dictionary review.
- Curated proof assets are in `assets/proof/`; large datasets, model weights, PDFs, and raw generated images are intentionally excluded from Git.

## Best Versions

The most portfolio-worthy implementation is the combined pipeline below:

- `app.py` - Flask dictionary workbench with health/status/search/edit/batch routes.
- `pipeline/ocr_training/1_karen_dataset_gen.py` - synthetic syllable dataset generator.
- `pipeline/ocr_training/036_train_v5.py` - latest visible training script in the folder.
- `pipeline/ocr_training/041_gen_paragraph_data.py` - paragraph-level dataset generator.
- `pipeline/ocr_training/040_tile_infer.py` - tiled paragraph inference script.
- `pipeline/dictionary_processing/042_build_KNU_decoder.py` - KNU legacy-font decoder.
- `pipeline/dictionary_processing/043_pdf_page_splitter_zoom.py` - high-resolution dictionary PDF splitter.
- `pipeline/dictionary_processing/046_sort_engine.py` - Sgaw Karen dictionary sort and safe correction logic.
- `pipeline/dictionary_processing/local_translator_suite/` - imported local translator/dictionary suite with scrape/cache lookup, reverse parsing, batch processing, and a mini language-model seed plan.

Older single-image OCR scripts, Streamlit prototypes, Firebase/AI Studio drafts, and unsafe hard-coded-key attempts were moved under `ideas_attempts/` and are ignored.

## Run The Workbench

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
$env:GEMINI_API_KEY="your_key_here"
python app.py
```

Then open `http://127.0.0.1:5000`.

The app can search existing entries from `karen_dict_full.json` without an API key. Batch OCR and re-analysis require `GEMINI_API_KEY`.

## Proof Assets

- `assets/proof/training/Metric-v1-v2-Change.csv` - mAP and missed-syllable improvement summary.
- `assets/proof/training/v1_results.png` - YOLO training curves.
- `assets/proof/training/v1_confusion_matrix.png` - validation confusion matrix.
- `assets/proof/training/v1_val_batch0_pred.jpg` - model prediction proof image.
- `assets/proof/dictionary/karen_dict_PAGE.html` - exported dictionary-review artifact.
- `assets/proof/samples/` - sample OCR/test images.

## Documentation

- `docs/FILE_AUDIT.md` explains which scattered files are best, which are archived, and which are local-only.
- `docs/ARCHITECTURE.md` describes the pipeline from source image to OCR output to dictionary entry.
- `docs/SOURCE_REPOS.md` documents the consolidation from the related Karen language GitHub repos.
- `docs/PORTFOLIO_MEDIA_PLAN.md` gives Upwork/Fiverr video proof recommendations and captions.
- `docs/SECURITY.md` documents the ignore policy and the exposed-key cleanup warning.
