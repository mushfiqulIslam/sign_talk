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
| 9. Live API on Verda | `./verda.sh serve root@IP` (key: `SIGN_API_KEY` in `sign_talk/.env`) | Verda GPU |

Steps 5–7 have a Verda version too: `./verda.sh setup|smoke|train|predict|fetch root@IP` (see `verda.sh`). We used Verda; the Modal app is a ready alternative.

First time on a laptop: `uv run --group modal modal setup` (opens a browser to log in to Modal).

## How it is split

- **By signer pair**, never by sentence: test signers `013` and `028`, validation signers `017` and `031`. The model never sees the test signers.
- The English version of a sentence is always in the same split as its Finnish original.
- Station sentences (`station_examples.jsonl`, written by the team, **not checked by a FinSL signer**): 14 train, 3 validation, 3 test, each in Finnish and English.
- Evaluation uses a fixed sample: 72 test sentences in Finnish, the same 72 in English, and the 6 station test rows. Hosted Gemma 4 needs ~30 s per answer because of its thinking step, so the full test set would take hours.

## Model and settings

- `google/gemma-4-E2B-it` (Apache 2.0), LoRA r=16, alpha 32, dropout 0.05 on the language model's attention and MLP projections.
- Learning rate 2e-4, cosine schedule, effective batch 16, 3 epochs, bf16, max 256 tokens, loss on the answer only, no thinking.
- GPU: one NVIDIA A100 80GB on Verda.

## Results

Same 150-row test sample for every model (signers never seen in training). F1 = share of signs right; chrF = letter-level closeness out of 100; "In Signbank" = share of output signs that have a real video, before the check removes the rest.

| Model | F1 | chrF | In Signbank |
|---|---:|---:|---:|
| Gemma 4 E2B, untrained | 0.09 | 18.5 | 19% |
| Gemma 4 26B (hosted), 8 examples in the prompt | 0.43* | 40.7 | 73% |
| Gemma 4 E2B fine-tuned, 3 epochs | 0.56 | 51.9 | 99% |
| Gemma 4 E2B fine-tuned, 2 epochs | 0.55 | 48.5 | 100% |
| **Gemma 4 E2B fine-tuned + 600 template station sentences (live model)** | **0.59** | **54.6** | **99%** |

\* 16 of 150 hosted answers were still empty (the model spends its token budget thinking), so its real score is a bit higher.

Station sentences only (3 per language, so indicative): the live model scores F1 0.96 Finnish / 0.93 English. That is optimistic: the template sentences resemble them.

**Verda run log:** one NVIDIA A100-SXM4-80GB. E2B 3 epochs: 20.7 min; 2 epochs: 14.1 min; with station templates: 23.3 min. Validation loss 6.72 → 0.85 → 0.81 → 1.00 (epoch 3 overfits on loss but scored best on the test sample). About 1 hour of GPU time for all training, plus the live API.

**Live API** (`serve.py`, `./verda.sh serve`): about 1–2.5 s per sentence on the A100. Each reply has the signs, a Signbank link per sign, the signs the Signbank check dropped, and one joined 352×198 video for the sentence (`sentence_video.py`, ffmpeg). Reached over https through a Cloudflare quick tunnel on the Verda machine.

## Data and licences

- **Corpus:** Corpus of Finnish Sign Language (CFinSL), Elicited Narratives parts 1 and 2, University of Jyväskylä, via the Language Bank of Finland (Kielipankki). Licence CC BY-NC-SA 4.0 with personal-data terms (+PRIV).
- **Dictionary and videos:** Finnish Signbank (signbank.csc.fi), CC BY-NC-SA.
- Neither the data nor anything derived from it (dataset files, the Signbank map, model weights, predictions) is in this repository. The code here is MIT; the data stays under its own licence.
- **Privacy:** the corpus contains recordings of real signers. We use it only to train and test this project's model, keep it on team machines, a private Modal volume and the rented Verda GPU machine (`./verda.sh wipe`), never publish it, and delete it after the project.
