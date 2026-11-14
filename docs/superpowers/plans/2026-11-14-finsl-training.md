# FinSL sign model training: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the CFinSL corpus into a clean Finnish + English → FinSL sign-name dataset, fine-tune Gemma 4 E2B on it on Modal, and serve it from Modal for the app, and measure it against hosted Gemma 4 used with examples in the prompt.

**Architecture:** A small Python package `training/finsl/` holds the pure logic (ELAN parsing, cleaning, signer split, prompt format, metrics, Signbank map). Thin scripts call it: one builds the dataset on the laptop, one Modal app fine-tunes and serves the model, and one evaluates. Data and model files live outside the repo, in `../finsl-data/`, because of their licence.

**Tech Stack:** Python 3.12+, uv, pytest, the standard library for data work; on Modal (A10G GPU): PyTorch, transformers, peft, datasets, accelerate.

**Spec:** `docs/superpowers/specs/2026-11-14-finsl-signs-design.md` (sections "Data preparation", "Signbank dictionary", "Fine-tuning", "Evaluation"). The backend and app parts of the spec get their own plan later.

## Global Constraints

- Output is FinSL only. Input languages: Finnish (`fi`) and English (`en`).
- Corpus and Signbank material are CC BY-NC-SA, and the corpus is +PRIV: no data, video or model output files in the repo. Everything generated goes to `$FINSL_DATA` (default `../finsl-data`, i.e. `/home/mushfiqul/Support/Applications/Junction AI 2026/finsl-data`).
- API key: `GEMMA_API_KEY` in `sign_talk/.env` (git-ignored). Never print or log it.
- The split is by signer pair (the middle field of the session name, e.g. `011` in `CFINSL2014_011_03`), never by sentence.
- Model: Gemma 4 E2B instruction-tuned, LoRA. It must answer with sign names directly, with no thinking text.
- Sign names are written in capitals, separated by single spaces. A fingerspelled word is `FS:word`.
- Demo freeze is 20:00 today. If training isn't done by 18:00, the hosted-Gemma baseline becomes the demo model.

## Review Focus

1. Sessions where the translation tier exists but the hand tiers are empty or misaligned: no crash, the pair is skipped, and the skip is counted.
2. The same sign annotated on both hands at about the same time must appear once, not twice (`MIES MIES`).
3. English and Finnish versions of one sentence must land in the same split. Otherwise the test set leaks into training.
4. Model output with extra text ("Here are the glosses: …", lowercase, commas, thinking text) must still parse to a clean sign list.
5. A `.env` file without `GEMMA_API_KEY`, or a bad key, must give a clear one-line error, never a stack trace showing the key.

Tests for each are in the owning task (marked **RF1–RF5**).

---

## File structure

```
training/
  pyproject.toml            uv project; pytest for tests
  README.md                 how to run each step, Modal steps, challenge write-up notes
  finsl/
    __init__.py
    eaf.py                  ELAN file -> list[Pair]
    clean.py                raw sign names -> clean sign names
    split.py                session name -> "train" | "val" | "test"
    prompt.py               one prompt format, shared by training, evaluation and the backend
    metrics.py              precision, recall, chrF, Signbank coverage
    signbank.py             Signbank dictionary pages -> {sign name: video URL, Finnish words}
    gemini.py               small client for Google AI Studio (Gemini and hosted Gemma), key from .env
  build_dataset.py          corpus -> $FINSL_DATA/dataset/{train,val,test}.jsonl
  translate_english.py      adds English rows using Gemini, cached
  station_examples.jsonl    our own hand-written station sentences (MIT, ours)
  build_signbank.py         -> $FINSL_DATA/signbank.json
  modal_app.py              Modal: LoRA fine-tune, predictions, and the live sign-finder endpoint
  baseline.py               hosted Gemma 4 with examples in the prompt -> predictions.jsonl
  evaluate.py               predictions + test set -> results table (Markdown)
  tests/                    one test file per finsl/ module, with tiny synthetic fixtures
```

A dataset row (JSON Lines) has these fields: `{"text": str, "lang": "fi"|"en", "signs": [str], "session": str, "signer_pair": str, "split": str, "source": "corpus"|"station"}`.

---

### Task 1: Project setup and ELAN parsing

**Files:**
- Create: `training/pyproject.toml`, `training/finsl/__init__.py`, `training/finsl/eaf.py`
- Test: `training/tests/test_eaf.py`, `training/tests/fixtures/tiny.eaf` (hand-made, 2 signers, invented signs)

**Interfaces:**
- Produces: `@dataclass Pair(text: str, signs: list[str], signer: str)`; `read_pairs(path: Path) -> list[Pair]`. It reads tiers `Käännös_{n}` (translation) and `ID_{n}_oik` / `ID_{n}_vas` (right and left hand) for n in 1, 2. A sign belongs to a translation when the sign's midpoint falls inside the translation's time span.

- [ ] **Step 1: Write the failing tests**

```python
def test_reads_translation_with_signs_in_time_order():
    pairs = read_pairs(FIXTURES / "tiny.eaf")
    assert pairs[0] == Pair(text="mies istuu.", signs=["MIES", "ISTUA"], signer="1")

def test_two_handed_sign_counted_once():          # RF2
    # fixture has KAKSI on both hands, 50 ms apart
    assert read_pairs(FIXTURES / "tiny.eaf")[1].signs == ["KAKSI", "POIKA"]

def test_translation_without_signs_is_skipped():  # RF1
    texts = [p.text for p in read_pairs(FIXTURES / "tiny.eaf")]
    assert "ei viittomia." not in texts
```

- [ ] **Step 2: Run** `cd training && uv run pytest tests/test_eaf.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement `read_pairs`** in `finsl/eaf.py` with `xml.etree.ElementTree`. A two-handed duplicate is the same name within 200 ms of the previous one. Start from the working prototype at `/tmp/claude-1000/-home-mushfiqul-Support-Applications-Junction-AI-2026-sign-talk/3b9c930b-238f-4d92-a5c1-fe0c7493691e/scratchpad/eaf_pairs.py`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `git add training && git commit -m "training: ELAN parsing for CFinSL"`

### Task 2: Cleaning sign names

**Files:** Create `training/finsl/clean.py`; Test `training/tests/test_clean.py`

**Interfaces:**
- Produces: `clean_sign(raw: str) -> str | None` (None means drop it), `clean_signs(raw: list[str]) -> list[str]`, `base_name(sign: str) -> str` (removes the variant in brackets: `PIENI(L_alas)` → `PIENI`).

- [ ] **Step 1: Write the failing tests** (values from the spec's cleaning rules)

```python
@pytest.mark.parametrize("raw,clean", [
    ("OS:", None), ("ZZZ", None), ("KÄMMEN-YLÖS_ele", None),
    ("METELI@sbb", "METELI"), ("KAKSI_num@sbb", "KAKSI"), ("KAKSI_num", "KAKSI"),
    ("n-o-j-a_sa", "FS:noja"), ("n-o-j-a", "FS:noja"),
    ("PIENI(L_alas)", "PIENI(L_alas)"), ("RIITA(2T)", "RIITA(2T)"), ("", None),
])
def test_clean_sign(raw, clean): assert clean_sign(raw) == clean

def test_clean_signs_drops_and_keeps_order():
    assert clean_signs(["OS:", "MIES", "ZZZ", "ISTUA"]) == ["MIES", "ISTUA"]

def test_base_name(): assert base_name("PIENI(L_alas)") == "PIENI"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_clean.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with regular expressions. Fingerspelling is single letters joined by `-`, optionally followed by `_` and a suffix. Any other `@…` code and `_num` are stripped. `_ele` means a gesture, so drop it.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit.**

### Task 3: Split by signer pair, and build the Finnish dataset

**Files:** Create `training/finsl/split.py`, `training/build_dataset.py`; Test `training/tests/test_split.py`

**Interfaces:**
- Produces: `signer_pair(session: str) -> str` (`"CFINSL2014_011_03"` → `"011"`); `split_for(pair: str) -> Literal["train","val","test"]` with fixed sets `TEST = {"013", "028"}` and `VAL = {"017", "031"}`, everything else train; `build_dataset.py --data $FINSL_DATA` writes `$FINSL_DATA/dataset/{train,val,test}.jsonl` (fi rows only, `source="corpus"`) and prints counts per split plus the number of skipped pairs.
- Rows with fewer than 2 signs after cleaning are dropped (spec).

- [ ] **Step 1: Write the failing tests**

```python
def test_signer_pair(): assert signer_pair("CFINSL2015_028_05") == "028"
def test_fixed_split():
    assert split_for("013") == "test" and split_for("031") == "val" and split_for("011") == "train"
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** `split.py` and `build_dataset.py` (reads every `*.eaf` under `$FINSL_DATA`, uses Tasks 1–2, writes JSON Lines with `ensure_ascii=False`).
- [ ] **Step 4: Run the tests, then** `uv run python build_dataset.py`. Expected: about 4–7k rows in total, test and val each about 10–15%, and a printed skip count.
- [ ] **Step 5: Commit** (code only; the dataset is outside the repo).

### Task 4: Prompt format and output parsing (shared contract)

**Files:** Create `training/finsl/prompt.py`; Test `training/tests/test_prompt.py`

**Interfaces:**
- Produces: `build_prompt(text: str, lang: str) -> str`; `parse_signs(output: str) -> list[str]`; constant `INSTRUCTION`. The prompt text is fixed:

```
Translate the sentence into Finnish Sign Language (FinSL) sign names, in signing order.
Answer with sign names only, in capitals, separated by spaces. Spell names as FS:name.
Language: {lang}
Sentence: {text}
```

- [ ] **Step 1: Write the failing tests** (RF4)

```python
def test_parse_plain(): assert parse_signs("JUNA-ASEMA HELSINKI LAITURI NELJÄ") == ["JUNA-ASEMA","HELSINKI","LAITURI","NELJÄ"]
def test_parse_noise():
    assert parse_signs("Here are the signs: juna-asema, HELSINKI.\n") == ["JUNA-ASEMA","HELSINKI"]
def test_parse_drops_thinking():
    assert parse_signs("<thought>hmm</thought>MIES ISTUA") == ["MIES","ISTUA"]
def test_parse_keeps_fingerspelling(): assert parse_signs("FS:mika MIES") == ["FS:mika","MIES"]
def test_prompt_has_lang_and_text():
    p = build_prompt("The train leaves.", "en"); assert "Language: en" in p and "Sentence: The train leaves." in p
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Drop any `<thought>…</thought>` block and anything up to the last `:` on a line that has no capital sign name. Split on spaces and commas, strip punctuation, uppercase everything except the `FS:` content, and keep tokens that look like sign names (letters, digits, `-`, brackets, `_`).
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit.**

### Task 5: Google AI Studio client and English rows

**Files:** Create `training/finsl/gemini.py`, `training/translate_english.py`; Test `training/tests/test_gemini.py`

**Interfaces:**
- Produces: `load_key(env_path: Path) -> str` (raises `MissingKey("GEMMA_API_KEY missing in sign_talk/.env")`); `class GeminiError(Exception)` (HTTP status and the server's message, never the key); `english_row(fi_row: dict, english: str) -> dict`; `generate(model: str, prompt: str, key: str, max_tokens: int = 4096, timeout: int = 150) -> str` (non-thought text only; the key goes in the `x-goog-api-key` header). `translate_english.py` adds, for every fi row, an en row with the same `signs`, `session`, `signer_pair` and `split` (RF3). It uses `gemini-2.5-flash` (check that it's in the model list, otherwise use the newest flash model), sends 25 sentences per request as a numbered list, and caches to `$FINSL_DATA/cache/english.json`.

- [ ] **Step 1: Write the failing tests** (RF5, RF3)

```python
def test_missing_key(tmp_path):
    (tmp_path/".env").write_text("OTHER=1\n")
    with pytest.raises(MissingKey, match="GEMMA_API_KEY missing"): load_key(tmp_path/".env")

def test_error_message_never_contains_key(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error":"bad key"}'))
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(GeminiError) as excinfo:
        generate("gemma-4-26b-a4b-it", "hi", key="AIzaSECRET")
    assert "400" in str(excinfo.value) and "AIzaSECRET" not in str(excinfo.value)

def test_english_row_keeps_split_and_signs():
    fi = {"text":"mies istuu.","lang":"fi","signs":["MIES","ISTUA"],"session":"S","signer_pair":"013","split":"test","source":"corpus"}
    en = english_row(fi, "the man sits.")
    assert en["lang"] == "en" and en["split"] == "test" and en["signs"] == fi["signs"]
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** with `urllib.request`. Translation instruction: "Translate each Finnish sentence to natural English. Words in brackets are implied; keep the meaning, drop the brackets. Answer as a numbered list, same numbering."
- [ ] **Step 4: Run the tests, then** `uv run python translate_english.py`. Expected: one en row per fi row; rerunning uses the cache.
- [ ] **Step 5: Commit.**

### Task 6: Signbank map and station examples

**Files:** Create `training/finsl/signbank.py`, `training/build_signbank.py`, `training/station_examples.jsonl`; Test `training/tests/test_signbank.py`, `training/tests/fixtures/signbank_page.html` (a hand-made minimal page with the same link and video patterns, no real content)

**Interfaces:**
- Produces: `parse_dictionary_page(html: str) -> list[Entry]` with `Entry(sign: str, gloss_id: int, video_url: str | None)`; `build_signbank.py` walks `https://signbank.csc.fi/dictionary/?dataset=1&page=N` until no new entries (one request per second, cached under `$FINSL_DATA/cache/signbank/`), and writes `$FINSL_DATA/signbank.json` as `{sign: {"video": url, "base": base_name(sign)}}`; `known(sign: str, bank: dict) -> bool` matches on the exact name or `base_name`.
- `station_examples.jsonl`: 40 rows (20 fi plus the same 20 in en), `source="station"`, split train/val/test as 28/6/6 by sentence id. Every sign must pass `known()` (enforced by a test).

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_page(): e = parse_dictionary_page(FIXTURE)[0]; assert e.sign == "JUNA-ASEMA" and e.video_url.endswith(".mp4")
def test_known_by_base(): assert known("PIENI(L_alas)", {"PIENI": {...}})
def test_station_examples_use_only_known_signs():
    bank = json.load(open(FINSL_DATA/"signbank.json"))
    for row in rows("station_examples.jsonl"): assert all(known(s, bank) for s in row["signs"])
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the parser and crawler.** Write the station sentences, e.g. "Juna Helsinkiin lähtee laiturilta neljä." / "The train to Helsinki leaves from platform four.", using only signs found in `signbank.json`. Words without a sign become `FS:…`.
- [ ] **Step 4: Run** `uv run python build_signbank.py`, **then the tests.** Expected: PASS. Print how many entries there are and what share of corpus signs are known.
- [ ] **Step 5: Commit** (the map is outside the repo; `station_examples.jsonl` is ours and goes in).

### Task 7: Metrics and evaluation report

**Files:** Create `training/finsl/metrics.py`, `training/evaluate.py`; Test `training/tests/test_metrics.py`

**Interfaces:**
- Produces: `sign_prf(pred: list[str], ref: list[str]) -> tuple[float, float, float]` (multiset precision, recall, F1, compared on `base_name`); `chrf(pred: str, ref: str) -> float` (character n-gram F-score, n = 1–6, β = 2, the standard chrF); `coverage(pred, bank) -> float` (share of predicted signs that `known()` accepts). `evaluate.py --pred FILE --name NAME` writes a Markdown table row per language and per source (corpus, station) to `$FINSL_DATA/results/NAME.md`.

- [ ] **Step 1: Write the failing tests**

```python
def test_prf_perfect(): assert sign_prf(["A","B"], ["A","B"]) == (1.0, 1.0, 1.0)
def test_prf_partial(): p, r, f = sign_prf(["A","C"], ["A","B","B"]); assert (p, round(r,3)) == (0.5, 0.333)
def test_prf_empty_pred(): assert sign_prf([], ["A"]) == (0.0, 0.0, 0.0)
def test_chrf_identical(): assert chrf("MIES ISTUA", "MIES ISTUA") == pytest.approx(100.0)
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** with the standard library only.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit.**

### Task 8: Baseline: hosted Gemma 4 with examples in the prompt

**Files:** Create `training/baseline.py`

**Interfaces:**
- Consumes: `build_prompt`, `parse_signs`, `generate`. Produces `$FINSL_DATA/predictions/baseline_gemma4.jsonl` rows `{"text","lang","source","signs_ref","signs_pred"}`.
- Model `gemma-4-26b-a4b-it`. The 8 examples in the prompt come from train rows closest by shared words. Run 4 requests at once, with a 150 s timeout and 1 retry. The test set is all test rows (fi + en + station).

- [ ] **Step 1: Run on 5 rows:** `uv run python baseline.py --limit 5`. Expected: 5 prediction rows, none empty.
- [ ] **Step 2: Run on the full test set in the background, then** `uv run python evaluate.py --pred …/baseline_gemma4.jsonl --name baseline_gemma4`. Expected: the results table.
- [ ] **Step 3: Commit** (code only).

### Task 9: Fine-tune and serve Gemma 4 E2B on Modal

**Files:** Create `training/modal_app.py`, `training/README.md` (Modal section)

**Interfaces:**
- Consumes: `build_prompt` (prompt) and `" ".join(signs)` (answer) from Task 4; dataset files from Tasks 3, 5 and 6, uploaded to a Modal Volume `finsl-data` (`modal volume put finsl-data $FINSL_DATA/dataset /dataset`).
- Produces, in one `modal.App("finsl-signs")`:
  - `train(limit: int | None = None, max_steps: int | None = None)` on `gpu="A10G"`, timeout 2 h: LoRA fine-tune, adapter saved to Volume `finsl-models` at `/models/finsl-gemma4-e2b/`.
  - `predict(split: str = "test", adapter: bool = True) -> list[dict]` on the same GPU: rows like Task 8's; `adapter=False` is the untrained E2B (the spec's comparison "(a)").
  - `class SignFinder` with `@modal.fastapi_endpoint(method="POST")` `signs(body: {"text": str, "lang": str}) -> {"signs": list[str], "ms": int}`. The backend calls this live; `min_containers=0` normally, set to 1 just before the demo so the first request isn't slow.
- Hugging Face token as a Modal Secret `huggingface` (`HF_TOKEN`), from an account that has accepted the Gemma licence; model id checked on huggingface.co/google (Gemma 4 E2B instruction-tuned).
- Settings to start from: LoRA r=16, alpha=32, dropout 0.05 on the attention and MLP projections; learning rate 2e-4; 3 epochs; batch 16 (gradient accumulation if needed); bf16; max length 256; loss on the answer only; chat template with **no thinking** in training and inference.
- Log GPU type, time, cost and final val loss into `README.md` for the Modal challenge write-up.

- [ ] **Step 1: Smoke test:** `uv run modal run modal_app.py::train --limit 64 --max-steps 5`. Expected: loss printed, adapter saved in the Volume.
- [ ] **Step 2: Full run:** `uv run modal run modal_app.py::train`. Expected: val loss lower than at step 0.
- [ ] **Step 3: Predict:** `uv run modal run modal_app.py::predict` and `--no-adapter`; save both under `$FINSL_DATA/predictions/`, then run `evaluate.py --name finetuned_e2b` and `--name base_e2b`. Expected: two results tables.
- [ ] **Step 4: Deploy the endpoint:** `uv run modal deploy modal_app.py`, then `curl -X POST <url> -d '{"text":"Juna lähtee laiturilta neljä.","lang":"fi"}'`. Expected: a sign list, and `ms` under 1000 once warm.
- [ ] **Step 5: Commit** (code and README; no weights).

### Task 10: Results write-up

**Files:** Modify `training/README.md`, `docs/architecture.md` (one line with the headline numbers)

- [ ] **Step 1:** Put the baseline and fine-tuned tables side by side in `training/README.md`, with Finnish, English and station rows, plus the Signbank coverage before the check.
- [ ] **Step 2:** Draft the Modal challenge summary (what was trained, why a laptop couldn't, GPU, time, cost, the result) in `training/README.md`.
- [ ] **Step 3: Commit.**

---

## Who can do what in parallel

- **Laptop, now:** Tasks 1 → 2 → 3 → 4 (no outside accounts needed).
- **Needs the API key (have it):** Tasks 5 and 8.
- **Needs the internet only:** Task 6.
- **Needs Modal (linked with `modal setup`) and a Hugging Face account with the Gemma licence:** Task 9. Get these ready while Tasks 1–8 run.
