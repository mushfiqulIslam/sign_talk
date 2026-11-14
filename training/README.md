# FinSL sign model: training

Turns a spoken Finnish or English sentence into **Finnish Sign Language (FinSL) sign names in signing order**, for example
`Juna Helsinkiin lähtee laiturilta neljä.` → `MATKUSTAA-JUNALLA HELSINKI LÄHTEÄ LAITURI NELJÄ`.
The app then shows the matching Signbank videos on the glasses.

This is **not sign-language interpretation**: word signs in signing order leave out facial grammar, use of space and classifiers.

## Steps

All data and model files go to `../../finsl-data/` (outside the repo, see *Data and licences*).

| Step | Command | Where |
|---|---|---|
| Tests | `uv run pytest` | laptop |
| 1. Corpus → Finnish dataset (split by signer) | `uv run python build_dataset.py` | laptop |
| 2. English versions (Gemini, cached) | `uv run python translate_english.py` | laptop, needs `GEMMA_API_KEY` in `sign_talk/.env` |
| 3. Signbank sign → video map | `uv run python build_signbank.py` | laptop |
| 4. Baseline: hosted Gemma 4, examples in prompt | `uv run python baseline.py` | laptop |
| 5. Upload dataset to Modal | `uv run --group modal modal volume put finsl-data ../../finsl-data/dataset /dataset` | laptop |
| 6. Fine-tune | `uv run --group modal modal run modal_app.py::train` | Modal GPU |
| 7. Predictions | `uv run --group modal modal run modal_app.py::predict_local` (and `--no-adapter`) | Modal GPU |
| 8. Scores | `uv run python evaluate.py --pred ../../finsl-data/predictions/NAME.jsonl --name NAME` | laptop |
| 9. Live endpoint | `uv run --group modal modal deploy modal_app.py` | Modal |

First time on a laptop: `uv run --group modal modal setup` (opens a browser to log in to Modal).

## How it is split

- **By signer pair**, never by sentence: test signers `013` and `028`, validation signers `017` and `031`. The model never sees the test signers.
- The English version of a sentence is always in the same split as its Finnish original.
- Station sentences (`station_examples.jsonl`, written by the team, **not checked by a FinSL signer**): 14 train, 3 validation, 3 test, each in Finnish and English.
- Evaluation uses a fixed sample: 72 test sentences in Finnish, the same 72 in English, and the 6 station test rows. Hosted Gemma 4 needs ~30 s per answer because of its thinking step, so the full test set would take hours.

## Model and settings

- `google/gemma-4-E2B-it` (Apache 2.0), LoRA r=16, alpha 32, dropout 0.05 on the language model's attention and MLP projections.
- Learning rate 2e-4, cosine schedule, effective batch 16, 3 epochs, bf16, max 256 tokens, loss on the answer only, no thinking.
- GPU: one NVIDIA L40S on Modal.

## Results

*(filled in after the runs: base E2B, hosted Gemma 4 with examples, fine-tuned E2B)*

## Data and licences

- **Corpus:** Corpus of Finnish Sign Language (CFinSL), Elicited Narratives parts 1 and 2, University of Jyväskylä, via the Language Bank of Finland (Kielipankki). Licence CC BY-NC-SA 4.0 with personal-data terms (+PRIV).
- **Dictionary and videos:** Finnish Signbank (signbank.csc.fi), CC BY-NC-SA.
- Neither the data nor anything derived from it (dataset files, the Signbank map, model weights, predictions) is in this repository. The code here is MIT; the data stays under its own licence.
- **Privacy:** the corpus contains recordings of real signers. We use it only to train and test this project's model, keep it on team machines and a private Modal volume, never publish it, and delete it after the project.
