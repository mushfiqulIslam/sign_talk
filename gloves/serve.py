"""signtalk-gloves: glove signs -> sentence -> phone over Wi-Fi, as one system.

  signtalk-gloves train --data ~/Downloads/gestures       train the CSV model (once)
  signtalk-gloves run                                      replay recorded signs (demo-safe)
  signtalk-gloves run --source studio                      live gloves from Rokoko Studio

Then in the phone app: Gloves > laptop address > Connect.
"""
import argparse
import collections
import sys
import threading
import time
from pathlib import Path

import decoder as dec
import sentence
from phone_link import PhoneLink, laptop_addresses

DEFAULT_MODEL = Path.home() / ".signtalk" / "gloves-model.joblib"
# Each tap of "Play glove demo" on the phone plays the next phrase.
DEFAULT_DEMO = "me,study,Aalto,university/nice,meet/good,day"
REPLAY_FRAMES = 150  # 2.5 s of each sign


class Pipeline:
    """Recogniser guesses -> signs and sentences -> phone."""

    def __init__(self, link: PhoneLink, use_model: bool = True):
        self.link, self.use_model = link, use_model
        self.decoder = dec.Decoder(need=3, min_prob=0.6, gap_s=2.0)

    def guess(self, label: str | None, prob: float, t: float) -> None:
        self._handle(self.decoder.push(label or dec.REST, prob, t))
        self._handle(self.decoder.tick(t))

    def tick(self, t: float) -> None:
        self._handle(self.decoder.tick(t))

    def flush(self) -> None:
        self._handle(self.decoder.flush())

    def _handle(self, events) -> None:
        for kind, value in events:
            if kind == "sign":
                fi, en = sentence.WORDS.get(value, (value, value))
                print(f">>> {value.upper()}  ({fi} / {en})")
                self.link.send({"type": "sign", "sign": value, "fi": fi, "en": en})
            else:
                threading.Thread(target=self._sentence, args=(value,), daemon=True).start()

    def _sentence(self, signs: list[str]) -> None:
        started = time.time()
        s = sentence.make(signs) if self.use_model else sentence._plain(signs)
        ms = int((time.time() - started) * 1000)
        print(f"=== {' '.join(x.upper() for x in signs)}\n    fi: {s['fi']}\n    en: {s['en']}   ({s['by']}, {ms} ms)")
        self.link.send({"type": "sentence", "signs": signs, "fi": s["fi"], "en": s["en"], "by": s["by"], "ms": ms})


def run_replay(args, link: PhoneLink, pipe: Pipeline) -> None:
    import csv_signs

    model = csv_signs.load(args.model)
    phrases = [[s.strip() for s in p.split(",") if s.strip()] for p in args.demo.split("/")]
    for p in phrases:
        for s in p:
            if s not in model["replay"]:
                sys.exit(f"'{s}' is not a trained sign. Trained: {', '.join(model['labels'])}")
    print(f"Signs: {', '.join(model['labels'])}  (accuracy on unseen repetitions: {model['accuracy']:.0%})")
    requested = threading.Event()
    link.on_command = lambda m: requested.set() if m.get("type") == "replay" else None
    threading.Thread(target=lambda: [requested.set() for _ in iter(sys.stdin.readline, "")], daemon=True).start()
    print("Press Enter here, or 'Play glove demo' on the phone, to sign the next phrase.")
    n = 0
    while True:
        requested.wait()
        requested.clear()
        phrase = phrases[n % len(phrases)]
        n += 1
        print(f"\n--- replaying: {' '.join(phrase)}")
        link.send({"type": "status", "text": f"Signing: {' '.join(phrase)}"})
        frames = []
        for i, s in enumerate(phrase):
            rec = model["replay"][s]
            start = (n * 37 + i * 53) % max(1, len(rec) - REPLAY_FRAMES)  # a different stretch each time
            frames.extend(rec[start:start + REPLAY_FRAMES])
        window = collections.deque(maxlen=csv_signs.WINDOW)
        t0 = time.time()
        for k, frame in enumerate(frames):
            window.append(frame)
            if len(window) == csv_signs.WINDOW and k % csv_signs.STEP == 0:
                label, prob = csv_signs.predict(model, list(window))
                pipe.guess(label, prob, time.time())
            time.sleep(max(0.0, t0 + k / 60 - time.time()))  # real time, 60 frames a second
        end = time.time()
        while time.time() - end < pipe.decoder.gap_s + 0.3:  # the signer's hands rest
            pipe.tick(time.time())
            time.sleep(0.1)
        pipe.flush()


def run_studio(args, link: PhoneLink, pipe: Pipeline) -> None:
    from signs import SignModel, frame_to_array, load_dataset
    from studio import StudioReceiver

    model = SignModel(load_dataset())
    print(f"Live signs: {model.summary()}")
    rx = StudioReceiver(port=args.studio_port)
    print(f"Listening for Rokoko Studio on UDP port {args.studio_port}. Sign, then rest your hands to finish a sentence.")
    window = collections.deque(maxlen=30)
    try:
        for n, joints in enumerate(rx.frames()):
            window.append(frame_to_array(joints))
            if len(window) < 30 or n % 5:
                pipe.tick(time.time())
                continue
            label, _ = model.predict(list(window))
            pipe.guess(label, 1.0 if label else 0.0, time.time())
    finally:
        rx.close()


def main() -> None:
    ap = argparse.ArgumentParser(prog="signtalk-gloves", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train", help="train the sign model from CSV recordings (one file per sign)")
    t.add_argument("--data", required=True, help="folder of <sign>.csv files")
    t.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    r = sub.add_parser("run", help="recognise signs and send sentences to the phone")
    r.add_argument("--source", choices=["replay", "studio"], default="replay")
    r.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    r.add_argument("--demo", default=DEFAULT_DEMO, help="phrases to replay, signs by comma, phrases by /")
    r.add_argument("--port", type=int, default=8765, help="the phone connects to this port")
    r.add_argument("--studio-port", type=int, default=14043)
    r.add_argument("--no-gemini", action="store_true", help="plain words instead of a Gemini sentence")
    args = ap.parse_args()

    if args.cmd == "train":
        import csv_signs

        print(f"Training on {args.data} ...")
        model = csv_signs.train(args.data)
        csv_signs.save(model, args.model)
        print(f"Signs: {', '.join(model['labels'])}\nAccuracy on unseen repetitions: {model['accuracy']:.1%}\nSaved {args.model}")
        return

    link = PhoneLink(port=args.port)
    link.start()
    print("Phone: Sign Talk > Gloves > enter " + " or ".join(f"{ip}" for ip in laptop_addresses()) + f"  (port {link.port})")
    pipe = Pipeline(link, use_model=not args.no_gemini)
    try:
        (run_studio if args.source == "studio" else run_replay)(args, link, pipe)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        link.stop()


if __name__ == "__main__":
    main()
