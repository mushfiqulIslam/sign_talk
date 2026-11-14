"""signtalk-gloves: glove signs -> sentence -> phone over Wi-Fi, as one system.

  signtalk-gloves train --data ~/Downloads/gestures       train the CSV model (once)
  signtalk-gloves run                                      replay recorded signs (demo-safe)
  signtalk-gloves run --source file --file sentence.csv    signs in a new CSV recording
  signtalk-gloves run --source udp                         live frames (CSV columns as JSON, UDP 9100)
  signtalk-gloves run --source studio                      live gloves from Rokoko Studio
  signtalk-gloves eval | detect sentence.csv               check the model

The phone app finds this laptop on the same Wi-Fi by itself (or type its address in the Gloves card).
"""
import argparse
import collections
import sys
import threading
import time
from pathlib import Path

import decoder as dec
import sentence
import socket

from phone_link import Beacon, PhoneLink, laptop_addresses

HERE = Path(__file__).resolve().parent
TRAINED_MODEL = Path.home() / ".signtalk" / "gloves-model.joblib"


def default_model() -> Path:
    """The model shipped next to the scripts (a shared bundle), else the one `train` saved."""
    bundled = HERE / "gloves-model.joblib"
    return bundled if bundled.is_file() else TRAINED_MODEL
# Each tap of "Play glove demo" on the phone plays the next phrase.
DEFAULT_DEMO = "me,study,Aalto,university/nice,meet/good,day"
REPLAY_FRAMES = 150  # 2.5 s of each sign


class Pipeline:
    """Recogniser guesses -> signs and sentences -> phone."""

    def __init__(self, link: PhoneLink, use_model: bool = True):
        self.link, self.use_model = link, use_model
        self.decoder = dec.Decoder()

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


class GloveMonitor:
    """Says whether glove data is arriving: every 2 s in the terminal and on the phone."""

    def __init__(self, link: PhoneLink, source: str, start: float | None = None):
        self.link, self.source = link, source
        self.started = time.time() if start is None else start
        self.window_start = self.started
        self.count, self.last = 0, None
        self.last_guess: tuple[str, float] | None = None

    def frame(self, t: float) -> None:
        self.count += 1
        self.last = t

    def guess(self, label: str, prob: float) -> None:
        self.last_guess = (label, prob)

    def report(self, now: float) -> str:
        if self.last is None or now - self.last >= 3:
            quiet = int(now - (self.last if self.last is not None else self.started))
            line = f"gloves: NO DATA for {quiet} s. Is the glove stream on and sent to {self.source}?"
            self.link.send({"type": "gloves", "receiving": False, "text": "Gloves: no data from the gloves"})
        else:
            rate = round(self.count / max(now - self.window_start, 1e-6))
            line = f"gloves: receiving {rate} frames/s"
            if self.last_guess:
                line += f" · last guess: {self.last_guess[0].upper()} ({self.last_guess[1]:.2f})"
            self.link.send({"type": "gloves", "receiving": True, "text": f"Gloves: receiving data ({rate} frames/s)"})
        self.count, self.window_start = 0, now
        return line

    def start(self, every_s: float = 2.0) -> None:
        def loop():
            while True:
                time.sleep(every_s)
                print(self.report(time.time()))

        threading.Thread(target=loop, daemon=True).start()


class FrameFeed:
    """Glove frames in (60 a second) -> a guess every 0.25 s -> the pipeline."""

    def __init__(self, model: dict, pipe: Pipeline, monitor: "GloveMonitor | None" = None):
        import csv_signs

        self.csv_signs, self.model, self.pipe, self.monitor = csv_signs, model, pipe, monitor
        self.window = collections.deque(maxlen=csv_signs.WINDOW)
        self.n = 0

    def push(self, frame) -> None:
        self.window.append(frame)
        self.n += 1
        if len(self.window) == self.csv_signs.WINDOW and self.n % self.csv_signs.STEP == 0:
            label, prob = self.csv_signs.predict(self.model, list(self.window))
            if self.monitor:
                self.monitor.guess(label, prob)
            self.pipe.guess(label, prob, time.time())
        else:
            self.pipe.tick(time.time())

    def finish(self) -> None:
        """Hands rest: let the sentence close."""
        end = time.time()
        while time.time() - end < self.pipe.decoder.gap_s + 0.3:
            self.pipe.tick(time.time())
            time.sleep(0.1)
        self.pipe.flush()
        self.window.clear()


def play_realtime(feed: "FrameFeed", frames) -> None:
    t0 = time.time()
    for k, frame in enumerate(frames):
        feed.push(frame)
        time.sleep(max(0.0, t0 + k / 60 - time.time()))
    feed.finish()


def run_file(args, link: PhoneLink, pipe: Pipeline) -> None:
    import csv_signs

    model = csv_signs.load(args.model)
    frames = csv_signs.read_recording(args.file, model["columns"])
    print(f"{args.file}: {len(frames) / 60:.1f} s of glove data. Press Enter or 'Play glove demo' on the phone to play it.")
    requested = threading.Event()
    link.on_command = lambda m: requested.set() if m.get("type") == "replay" else None
    threading.Thread(target=lambda: [requested.set() for _ in iter(sys.stdin.readline, "")], daemon=True).start()
    while True:
        requested.wait()
        requested.clear()
        print(f"\n--- playing {args.file}")
        link.send({"type": "status", "text": f"Signing: {Path(args.file).name}"})
        play_realtime(FrameFeed(model, pipe), frames)


def run_udp(args, link: PhoneLink, pipe: Pipeline) -> None:
    """Live frames from any glove tool: one JSON object per UDP packet (or a list of them),
    with the same column names as the training CSVs."""
    import json
    import socket as so

    import csv_signs

    model = csv_signs.load(args.model)
    monitor = GloveMonitor(link, f"UDP port {args.udp_port} on this laptop")
    monitor.start()
    feed = FrameFeed(model, pipe, monitor)
    sock = so.socket(so.AF_INET, so.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.udp_port))
    sock.settimeout(0.25)
    print(f"Waiting for glove frames on UDP port {args.udp_port} ({len(model['columns'])} columns, same names as the CSVs).")
    bad, last = 0, time.time()
    while True:
        try:
            data, _ = sock.recvfrom(1 << 20)
        except so.timeout:
            pipe.tick(time.time())
            continue
        last = time.time()
        try:
            rows = json.loads(data)
        except json.JSONDecodeError:
            continue
        for row in rows if isinstance(rows, list) else [rows]:
            v = csv_signs.row_vector(model["columns"], row) if isinstance(row, dict) else None
            if v is None:
                bad += 1
                if bad in (1, 100, 1000):
                    have = set(row) if isinstance(row, dict) else set()
                    missing = [c for c in model["columns"] if c not in have]
                    print(f"!! frame skipped: missing {len(missing)} column(s), e.g. {', '.join(missing[:3])}")
                continue
            monitor.frame(time.time())
            feed.push(v)


def run_replay(args, link: PhoneLink, pipe: Pipeline) -> None:
    import csv_signs

    model = csv_signs.load(args.model)
    phrases = [[s.strip() for s in p.split(",") if s.strip()] for p in args.demo.split("/")]
    for p in phrases:
        for s in p:
            if s not in model["replay"]:
                sys.exit(f"'{s}' is not a trained sign. Trained: {', '.join(model['labels'])}")
    print(f"Signs: {', '.join(model['labels'])}  (accuracy on unseen repetitions: {model['accuracy']:.0%})")
    print("Replay mode: NOT listening to the gloves. For live gloves start with --source studio (Rokoko Studio)"
          " or --source udp (frames with the CSV's columns).")
    link.send({"type": "gloves", "receiving": None, "text": "Gloves: replay mode (recordings, not live gloves)"})
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
        play_realtime(FrameFeed(model, pipe), frames)


def run_studio(args, link: PhoneLink, pipe: Pipeline) -> None:
    from signs import SignModel, frame_to_array, load_dataset
    from studio import StudioReceiver

    try:
        model = SignModel(load_dataset())
        print(f"Live signs: {model.summary()}")
    except ValueError:
        model = None
        print("!! No live recordings yet (run record.py with the gloves on: each sign ~10 times, plus 'rest').")
        print("   Showing only whether glove data arrives; no signs will be recognised.")
    monitor = GloveMonitor(link, f"Rokoko Studio > Livestreaming > Custom: this laptop, UDP port {args.studio_port}, JSON")
    monitor.start()
    rx = StudioReceiver(port=args.studio_port)
    print(f"Listening for Rokoko Studio on UDP port {args.studio_port}. Sign, then rest your hands to finish a sentence.")
    window = collections.deque(maxlen=30)
    try:
        for n, joints in enumerate(rx.frames()):
            monitor.frame(time.time())
            window.append(frame_to_array(joints))
            if model is None or len(window) < 30 or n % 5:
                pipe.tick(time.time())
                continue
            label, _ = model.predict(list(window))
            monitor.guess(label or "no match", 1.0 if label else 0.0)
            pipe.guess(label, 1.0 if label else 0.0, time.time())
    finally:
        rx.close()


def main() -> None:
    ap = argparse.ArgumentParser(prog="signtalk-gloves", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train", help="train the sign model from CSV recordings (one file per sign)")
    t.add_argument("--data", required=True, help="folder of <sign>.csv files")
    t.add_argument("--model", type=Path, default=TRAINED_MODEL)
    r = sub.add_parser("run", help="recognise signs and send sentences to the phone")
    r.add_argument("--source", choices=["replay", "file", "udp", "studio"], default="replay",
                   help="replay: held-out recordings; file: a new CSV recording; udp: live frames with the CSV's columns; "
                        "studio: Rokoko Studio live stream (needs record.py recordings)")
    r.add_argument("--file", help="CSV recording for --source file")
    r.add_argument("--udp-port", type=int, default=9100, help="for --source udp")
    r.add_argument("--model", type=Path, default=None)
    r.add_argument("--demo", default=DEFAULT_DEMO, help="phrases to replay, signs by comma, phrases by /")
    r.add_argument("--port", type=int, default=8765, help="the phone connects to this port")
    r.add_argument("--studio-port", type=int, default=14043)
    r.add_argument("--name", default=socket.gethostname(), help="name the phone shows for this laptop")
    r.add_argument("--host", help="the laptop address to put in the QR code (if the guess is wrong; see ipconfig)")
    r.add_argument("--no-qr", action="store_true", help="don't open the QR page in the browser")
    r.add_argument("--no-gemini", action="store_true", help="plain words instead of a Gemini sentence")
    e = sub.add_parser("eval", help="score the model on random phrases of held-out signs")
    e.add_argument("--model", type=Path, default=None)
    e.add_argument("--phrases", type=int, default=200)
    d = sub.add_parser("detect", help="print the signs found in a CSV recording")
    d.add_argument("file")
    d.add_argument("--model", type=Path, default=None)
    b = sub.add_parser("bundle", help="make a zip to share: backend + model + start scripts (no API keys)")
    b.add_argument("--model", type=Path, default=TRAINED_MODEL)
    b.add_argument("--out", type=Path, default=Path.home() / "Downloads" / "SignTalk-Gloves.zip")
    args = ap.parse_args()
    if getattr(args, "model", None) is None:
        args.model = default_model()
    if args.cmd == "bundle":
        import bundle

        bundle.make(args.model, args.out)
        return

    if args.cmd == "eval":
        import csv_signs

        r = csv_signs.phrase_test(csv_signs.load(args.model), phrases=args.phrases)
        print(f"{r['phrases']} phrases of 2-4 signs: {r['exact']:.0%} read back exactly, {r['signs_found']:.0%} of signs found")
        for said, got in r["examples"]:
            print(f"  signed {' '.join(said)} -> read {' '.join(got)}")
        return
    if args.cmd == "detect":
        import csv_signs

        model = csv_signs.load(args.model)
        signs = csv_signs.detect(model, csv_signs.read_recording(args.file, model["columns"]))
        print(" ".join(s.upper() for s in signs) or "(no signs found)")
        return
    if getattr(args, "source", None) == "file" and not args.file:
        ap.error("--source file needs --file <recording.csv>")
    if args.cmd == "train":
        import csv_signs

        print(f"Training on {args.data} ...")
        model = csv_signs.train(args.data)
        csv_signs.save(model, args.model)
        print(f"Signs: {', '.join(model['labels'])}\nAccuracy on unseen repetitions: {model['accuracy']:.1%}\nSaved {args.model}")
        return

    link = PhoneLink(port=args.port)
    link.start()
    beacon = Beacon(name=args.name, port=link.port)
    beacon.start()
    print(f"Announcing '{args.name}' on the Wi-Fi: the app finds this laptop by itself.")
    addresses = [args.host] if args.host else laptop_addresses()
    if not addresses:
        print("!! Couldn't find this laptop's Wi-Fi address. Is Wi-Fi on? Start again with --host <IPv4 from ipconfig>.")
    elif len(addresses) > 1:
        print(f"Addresses found: {', '.join(addresses)}. Using {addresses[0]} for the QR code "
              "(wrong one? start again with --host <Wi-Fi IPv4 from ipconfig>).")
    if addresses and not args.no_qr:
        import qr_page

        if qr_page.show(addresses[0], link.port, args.name):
            print("Opened a QR code in the browser: Sign Talk > Gloves > Scan QR.")
    if addresses:
        print(f"Or type the address in the Gloves card: {addresses[0]}  (port {link.port})")
    pipe = Pipeline(link, use_model=not args.no_gemini)
    try:
        {"replay": run_replay, "file": run_file, "udp": run_udp, "studio": run_studio}[args.source](args, link, pipe)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        beacon.stop()
        link.stop()


if __name__ == "__main__":
    main()
