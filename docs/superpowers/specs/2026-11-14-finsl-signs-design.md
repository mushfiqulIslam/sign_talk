# FinSL signs on the lens: design

Date: 2026-11-14 (Junction, Saturday). Demo freeze 20:00 today.

## Intent and why

A Finnish deaf or hard-of-hearing wearer sees **Finnish Sign Language (FinSL) signs** on the glasses lens for what people around them say, in **Finnish or English**. The captions stay too. The signs are extra help for people whose first language is FinSL, not a replacement for the text.

The team also wants to enter two bonus challenges with this work:
- **Best Use of Verda:** "use Verda for something a laptop can't do; document the process and post a summary in their Discord channel". Here that is fine-tuning a model on Verda GPUs.
- **Best Use of Gemma:** "innovative use of Gemma open models". Here that is a fine-tuned Gemma doing the speech-to-sign step.

The team chose to spend the full day on it.

## Goals
- Spoken Finnish or English sentence → a sequence of FinSL signs → a short sign video on the (mock) lens, with the caption text before and after it.
- A small Gemma model fine-tuned on Verda, trained on real FinSL data (the CFinSL corpus) to turn a sentence into FinSL sign names ("glosses") in sign order.
- Only signs that exist in Finnish Signbank are ever shown. Any other word is fingerspelled with the finger alphabet, or shown as text.
- A measured result: fine-tuned Gemma against a no-training baseline on held-out data.
- A short write-up of the Verda process for their Discord channel.

## Non-goals
- Not sign-language interpretation. Word signs in sign order leave out facial grammar, use of space and classifiers. The pitch says this plainly.
- No other sign languages (ASL, BSL). The input can be English; the output is always FinSL.
- No sign-to-text in this work. The glove feature (option B) is separate and comes later.
- No signing avatar or generated video. Only Signbank's recorded videos are shown.

## Anti-goals (failure even if it technically works)
- Showing a sign that doesn't exist, or the wrong sign, as if it were correct. The Signbank check exists to prevent this.
- Captions getting slower or disappearing because of the sign feature. Captions keep working even if the sign service is down.
- Any corpus or Signbank video ending up in the public MIT-licensed repo.
- Claiming the system translates sign language.

## Constraints
- **Time:** the feature must work end to end by 20:00. After that, no new features.
- **Data licences:** the corpus (CFinSL Elicited Narratives, parts 1 and 2) and the Signbank videos are both CC BY-NC-SA. They are non-commercial, need credit and must be shared alike. The corpus is also +PRIV: it contains personal data (the signers' faces), so it may be used only for this project, and the project must publish a short privacy notice. The data lives outside the repo, in `../finsl-data/`, and the repo holds only code and links.
- **Corpus contents:** 50 sessions of retold cartoons, a short video and picture books, from 21+ signers. Roughly 150 sentence pairs per session, so about 4–7k pairs in total. The subjects are everyday narration, not stations.
- **Lens video limits** (Meta Display Access Toolkit, Android 1.0): MP4 only, at most 400 px per side and 70,000 pixels in total, one video at a time, in a full-screen player. The source is a URL (https only), a byte array or a stream. Signbank videos are 1280×720 and must be shrunk, e.g. to 352×198.
- **Glasses:** real glasses currently fail to open the display (`SERVICE_NOT_FOUND`, see `../glasses-error-log.txt`). The demo runs on the mock glasses, viewed in Chrome. The design must not depend on the real glasses.
- **App today:** phone microphone → Android `SpeechRecognizer` (English/Suomi switch) → `Transcript` → `GlassesLink.draw()` text on the lens. There is no backend connection yet.

## Approaches considered
1. **Fine-tuned Gemma + Signbank check (chosen).** LoRA fine-tune of a small Gemma on Verda using the corpus pairs (plus English versions). The backend then drops any sign name not in Signbank, falling back to fingerspelling or text. The most work, but the strongest for both bonus challenges, and the only option that guarantees no invented signs.
2. **Fine-tuned Gemma, raw output.** Saves about an hour, but sign names with no video would appear as gaps or errors on the lens. Rejected because of the anti-goal above.
3. **No training, examples in the prompt.** Gemma or Gemini with the closest corpus pairs in the prompt. Fast to build, but it doesn't use Verda for something a laptop can't do. **Built anyway as the comparison baseline**, and kept as the fallback if the fine-tuned model isn't ready or the Verda server is unreachable during the demo.

Chosen by the team: approach 1, with approach 3 as the baseline. Input languages: Finnish and English.

## How it works

```
phone mic → SpeechRecognizer (fi-FI or en-US) → finished sentence
   → WebSocket → laptop backend
        → Gemma (fine-tuned, served on Verda) → sign names, e.g. JUNA-ASEMA LAITURI NELJÄ
        → Signbank check: keep known signs, fingerspell or skip the rest
        → build one short MP4 for the sentence (clips joined, shrunk to 352×198)
   → phone ← {signs, video bytes}
   → lens: caption text → sign video (full screen) → back to caption text
```

### 1. Data preparation (laptop)
- Source: `../finsl-data/` (being downloaded now): annotation files, metadata and one preview video per session, plus `pairs.jsonl` built from the `Käännös_N` (translation) and `ID_N_oik` / `ID_N_vas` (right and left hand) tiers.
- Cleaning rules (first version; the reviewing friends may refine them):
  - drop `OS:` (pointing), `ZZZ` (unclear) and pure gestures (`_ele`);
  - strip annotation codes such as `@sbb` but keep the sign name;
  - keep numbers (`KAKSI_num` → `KAKSI`);
  - turn fingerspelled words (`n-o-j-a`) into `FS:noja`;
  - keep variant markers like `PIENI(L_alas)` for the Signbank lookup, and also store the base name `PIENI`;
  - drop pairs that are empty after cleaning, and fragments shorter than two signs.
- **English pairs:** Gemini translates each Finnish sentence into English, and the English sentence gets the same sign list. Corpus translations put implied words in brackets ("(Hän) istuu"); Gemini keeps the meaning and drops the brackets.
- **Station examples:** 30–60 hand-written announcement sentences in Finnish and English with sign lists built only from signs that exist in Signbank. These are marked as hand-made. If someone who signs FinSL checks them, record that.
- **Split by signer, not by sentence**, so the test set has signers the model never saw: about 80% train, 10% validation, 10% test. The station examples are split the same way.

### 2. Signbank dictionary (laptop, once)
- Build `signbank.json`: sign name → video URL, plus its Finnish equivalents, by reading the public dictionary pages (`https://signbank.csc.fi/dictionary/?keyword=…` and the gloss pages). Videos are at `https://a3s.fi/signbank_data/media/glossvideo/…mp4`.
- Fetch politely: one request at a time, a short pause between requests, cached on disk.
- The dataset filter `dataset=1` (VKK corpus) matches the CFinSL sign names. Other datasets (Kipo, FinSSL) are ignored.
- Also fetch the finger-alphabet letter videos, for fingerspelling.

### 3. Fine-tuning (Verda)
- Model: a small instruction-tuned **Gemma** (about 1–4B parameters), whichever current Gemma release fits a single Verda GPU comfortably. The builder picks the exact model.
- Method: LoRA (a cheap kind of fine-tuning), with input "sentence + language" and output a space-separated list of sign names.
- Keep the training script, settings, run time, GPU type and cost: they go into the Verda Discord summary.
- Output: LoRA weights saved off the Verda machine as well, so nothing is lost when the server is stopped.

### 4. Serving and backend (laptop + Verda)
- Gemma runs on Verda behind a small HTTP endpoint during development and the demo. The laptop backend calls it.
- The backend lives in this repo as `backend/` (Python, FastAPI and WebSockets, building on Friday's `../server.py`). It:
  - accepts `{"text", "lang"}` per finished sentence from the phone;
  - calls Gemma (or the baseline prompt if Gemma doesn't respond within about 3 seconds);
  - checks every sign name against `signbank.json`;
  - builds the sentence video: download or cache each clip, shrink to 352×198, join them, and optionally speed up by about 1.25× with `ffmpeg` (install it; it isn't on the laptop now);
  - replies `{"signs": [...], "video": <mp4 bytes>, "fallback_words": [...]}`.
- Clip and sentence videos are cached on disk. The cache folder is git-ignored.

### 5. App changes (Android)
- The `Captioner` passes each **finished** sentence (not partial ones), with its language, to a new WebSocket client for the laptop backend.
- `GlassesLink` gains a "play signs" step: send the video with `VideoPlayer(VideoSource` bytes, `VideoCodec.MP4)`, wait for `ENDED`, then redraw the caption text.
- **Signs: on/off** switch on the phone screen, off by default until the backend is connected. With signs off or the backend unreachable, the app behaves exactly as it does now.
- If a new sentence finishes while a sign video is playing, it queues behind it. Only the newest pending sentence is kept, so the lens never falls far behind.

### 6. Evaluation (laptop)
- On the test set, compare (a) base Gemma with no training, (b) the prompt-only baseline, and (c) fine-tuned Gemma.
- Measures:
  - **sign precision and recall** against the corpus sign list;
  - **chrF** on the sign sequence;
  - **share of output signs that exist in Signbank**, before the check.
- Report Finnish and English input separately, plus the station examples separately.
- One table for the deck and the Verda post.

## Decided by the team
- FinSL output only. Finnish and English input.
- Fine-tuned Gemma with the Signbank check. The prompt-only version is the baseline.
- The whole day goes to this. The friends review the downloaded data first.
- The data stays in `../finsl-data/`, outside the repo.

## My calls (please check)
- Signs are shown **after** each finished sentence, as one joined video, because the lens plays one full-screen video at a time. Caption text stays the main view.
- Gemma is served on Verda for the demo, with the prompt-only baseline (Gemini) as the automatic fallback.
- The test set is split by signer.
- Video size 352×198, about 1.25× speed.
- The "Signs" switch is off by default.

## Left to the builder
- The exact Gemma model and LoRA settings.
- Prompt format, and how many station examples to write.
- How to build the Signbank map (page structure, pagination).
- The video joining details (fades, a short gap between signs).
- The privacy notice wording, credits in the README and deck, and the Discord post text.

## Open risks
- Narration data versus station sentences: expect weak results on station vocabulary. That's the reason for the hand-written examples, and the evaluation reports them separately.
- Sign videos are slow compared with speech: about 1–3 seconds per sign, so a 5-sign sentence plays for 5–15 seconds. The queue drops older sentences.
- Venue Wi-Fi: both the Verda endpoint and Signbank downloads need the internet. Cache the demo sentences' videos in advance.
- Some common words (`raide`, `lähteä`) had no direct Signbank keyword hit and need synonyms or fingerspelling.
