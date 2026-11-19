# sign_talk

Smart glasses for people with hearing loss, built at Junction 2026 for Meta's "AI Glasses for Everyone, Everyday" challenge.

The wearer keeps looking at the people around them while the Meta Ray-Ban Display shows what is being said, and the hearing person hears what the wearer signs.

## What works

- **Captions on the lens:** speech (English or Finnish) from the phone's microphone, shown on the glasses within about a second. Text size up to Extra large.
- **Finnish Sign Language signs:** each finished sentence goes to our fine-tuned Gemma 4 model, which returns the FinSL signs in signing order. The lens shows the sign names and plays the matching Finnish Signbank videos as one joined clip. This shows signs in signing order; it is not interpretation.
- **Gloves to speech:** the wearer signs with Rokoko data gloves. A laptop recognises the signs, Gemini turns them into a sentence, and the phone shows it and speaks it out loud. The phone finds the laptop on the same Wi-Fi by itself.

## Parts

| Folder | What it is | Start here |
|---|---|---|
| `android/` | The Sign Talk phone app (captions, signs, glove link; real or simulated glasses) | `CLAUDE.md` for build steps |
| `training/` | Fine-tuning Gemma 4 on the FinSL corpus, the scores, and the live sign API | [training/README.md](training/README.md) |
| `gloves/` | Glove backend: install on Windows, Mac or Linux, train, run | [gloves/README.md](gloves/README.md) |
| `docs/` | Architecture and design notes | [docs/architecture.md](docs/architecture.md) |

## Data and licences

The code is MIT. The glove sign model (`gloves/gloves-model.joblib`) is trained on the team's own glove recordings and shared under MIT. Recordings made by the team are included in `gloves/sign_dataset/`, also under MIT: 119 short clips of 10 signs (9 Finnish Sign Language signs and a resting hand). Each clip holds only hand and finger joint positions and rotations from the Rokoko gloves, with no audio, video or names. The FinSL corpus, the Signbank videos (CC BY-NC-SA) and the fine-tuned FinSL model are not in this repository; see `training/README.md`.
