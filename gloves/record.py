"""Record examples of each sign from Rokoko Studio (same flow as rokoko_datacollector.py).

Usage:  python record.py
Record a sign called "rest" too (hands relaxed): the recogniser learns to ignore it.
"""

import time

from signs import DATASET_DIR, frame_to_array, save_sample
from studio import DEFAULT_PORT, StudioReceiver

FRAMES_PER_SAMPLE = 80  # 30 frames is about half a second at 60 fps


def record_one(frames_iter, n=FRAMES_PER_SAMPLE):
    return [frame_to_array(next(frames_iter)) for _ in range(n)]


def main():
    rx = StudioReceiver(port=DEFAULT_PORT)
    frames = rx.frames()
    print("ROKOKO SIGN RECORDER")
    print(f"Listening on UDP port {DEFAULT_PORT}. Saving to {DATASET_DIR}\n")
    try:
        while True:
            sign = input("Sign name to record (or 'quit'): ").strip().lower()
            if sign == "quit":
                break
            if not sign:
                continue
            count = int(input(f"How many repetitions of '{sign}'? [10]: ") or 10)
            input("Press Enter when ready, then sign when told to.")
            for i in range(count):
                print(f"[{i + 1}/{count}] get ready...")
                time.sleep(2.0)
                # Throw away frames that queued up while we waited.
                rx.sock.setblocking(False)
                try:
                    while rx.sock.recv(65535):
                        pass
                except (BlockingIOError, OSError):
                    pass
                rx.sock.settimeout(0.5)
                print("  SIGN NOW")
                path = save_sample(sign, record_one(frames))
                print(f"  saved {path}")
                time.sleep(2.0)
            print(f"Done with '{sign}'.\n")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        rx.close()


if __name__ == "__main__":
    main()
