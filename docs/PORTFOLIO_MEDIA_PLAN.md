# Portfolio Media Plan

Use visual proof in a sequence. Buyers should see the problem, the custom data work, the training proof, the working inference path, and the dictionary output.

## Best Public Claim

Use this wording:

> I built a custom Sgaw Karen OCR and dictionary-processing pipeline from scratch, including synthetic dataset generation, YOLO training, inference automation, legacy dictionary decoding, and a review workflow for turning OCR output into structured dictionary entries.

For comparison videos, avoid broad model-war claims. Use:

> On my Sgaw Karen test cases, the custom OCR pipeline handles syllable-level recognition and dictionary extraction workflows that general-purpose OCR attempts did not handle reliably.

## Five Recommended Videos

1. **Before/After OCR Demo**
   - Show a scanned Sgaw Karen dictionary page or row.
   - Run the workbench or inference script.
   - Show structured JSON/dictionary output.
   - Caption: `Sgaw Karen scan to structured dictionary entry`

2. **Dataset Creation**
   - Show `1_karen_dataset_gen.py`, class files, generated image examples, and YOLO labels.
   - Show that the data was created for the language rather than downloaded from a ready-made OCR dataset.
   - Caption: `Custom synthetic OCR dataset for Sgaw Karen syllables`

3. **Training and Metrics**
   - Show `036_train_v5.py`, `Metric-v1-v2-Change.csv`, and `v1_results.png`.
   - Mention measured local project metrics only: mAP50 `0.888` to `0.965`, missed syllables `149` to `73`.
   - Caption: `Measured OCR model improvement through targeted retraining`

4. **Paragraph Inference**
   - Show `041_gen_paragraph_data.py` and `040_tile_infer.py`.
   - Use sample images from `assets/proof/samples/`.
   - Caption: `Moving from isolated syllables toward paragraph-level OCR`

5. **Dictionary Pipeline Comparison**
   - Show the same source sample going through a general OCR attempt and then through this pipeline.
   - Keep the claim narrow: "on these test cases."
   - Caption: `Custom pipeline recovers dictionary structure from difficult Sgaw Karen text`

6. **Optional Dictionary Lookup Proof**
   - Show `pipeline/dictionary_processing/local_translator_suite/` running a lookup, cache result, reverse parse, and batch output.
   - Position it as supporting evidence, not the main hero.
   - Caption: `Dictionary lookup and reverse parsing after OCR`

## Thumbnail

Use one clean static thumbnail:

`Karen Scan -> OCR Output -> Dictionary Result`

Avoid a busy code screenshot. Buyers respond faster to visible transformation than to code alone.

## Fiverr/Upwork Description

I built a custom OCR and dictionary-processing pipeline for Sgaw Karen, an underrepresented language with limited digital support and difficult legacy text sources. The project includes synthetic dataset generation, Roboflow/YOLO training, validation analysis, paragraph-level inference, PDF/image preprocessing, legacy KNU font decoding, and a Flask review workflow for turning OCR output into structured dictionary entries.

The pipeline is designed for language-access work where generic OCR often misses script-specific structure. It preserves original dictionary definitions, identifies candidate headwords and examples, supports correction review, and records measurable training progress through validation outputs and proof artifacts.

This repository shows the strongest code and evidence while keeping large generated datasets, model weights, source PDFs, and experimental drafts out of Git.
