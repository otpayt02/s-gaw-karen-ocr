# Security Notes

This repo intentionally excludes secrets, local run state, generated data, and model checkpoints.

## Important

Two archived prototype scripts contained hard-coded Gemini API-key patterns before cleanup:

- `ideas_attempts/archived_builders/bootstrap_ocr.py`
- `ideas_attempts/archived_builders/gemini_dict_ocr.py`

They are ignored and must not be published. Treat any key that ever appeared in those local files as exposed and rotate it in the provider dashboard.

The Roboflow upload/training helpers also had a hard-coded Roboflow key during the local audit. The public files now read `ROBOFLOW_API_KEY` from the environment, but that old Roboflow key should also be treated as exposed and rotated.

## Public Code Rule

The public app uses:

```powershell
$env:GEMINI_API_KEY="your_key_here"
$env:ROBOFLOW_API_KEY="your_roboflow_key_here"
python app.py
```

No real API keys should be committed to GitHub. `.env`, `.env.*`, local certificates, virtualenvs, logs, and local run-state JSON files are ignored.

## Large Artifacts

Model weights (`*.pt`) and full datasets are excluded from Git. If a public artifact is needed later, publish it as a GitHub Release asset, Hugging Face model/dataset, or another explicit artifact store.
