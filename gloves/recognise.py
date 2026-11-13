"""Live sign recognition: Rokoko Studio stream -> recognised word printed as text.

Usage:  python recognise.py            (Studio streaming to this laptop on port 14043)
"""

import argparse
import collections
import time

from signs import REST_LABEL, SignModel, frame_to_array, load_dataset
from studio import DEFAULT_PORT, StudioReceiver

WINDOW = 30  # frames looked at for each guess, the same length as a recording
EVERY = 5  # guess every 5 frames
AGREE = 3  # the same guess this many times in a row before we output it
COOLDOWN_S = 1.5  # don't repeat the same word within this time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--verbose", action="store_true", help="print every guess")
    args = ap.parse_args()

    model = SignModel(load_dataset())
    print(f"Loaded signs: {model.summary()}")
    rx = StudioReceiver(port=args.port)
    print(f"Listening for Rokoko Studio on UDP port {args.port}. Make a sign...\n")

    window = collections.deque(maxlen=WINDOW)
    streak_label, streak = None, 0
    last_word, last_time = None, 0.0
    try:
        for n, joints in enumerate(rx.frames()):
            window.append(frame_to_array(joints))
            if len(window) < WINDOW or n % EVERY:
                continue
            label, dist = model.predict(list(window))
            if args.verbose:
                print(f"  guess: {label} (distance {dist:.1f})")
            streak = streak + 1 if label == streak_label else 1
            streak_label = label
            if streak != AGREE or label in (None, REST_LABEL):
                continue
            now = time.time()
            if label == last_word and now - last_time < COOLDOWN_S:
                continue
            last_word, last_time = label, now
            print(f">>> {label.upper()}")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        rx.close()


if __name__ == "__main__":
    main()
