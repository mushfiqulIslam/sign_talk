"""Pretend Rokoko Studio: sends made-up glove data in Studio's JSON format, so the
recorder and recogniser can be tested without gloves.

Usage:  python fake_studio.py          then type a pose number + Enter to switch hand shape
        python fake_studio.py --pose fist   (fixed pose, no keyboard)
"""

import argparse
import json
import math
import random
import socket
import threading
import time

from studio import DEFAULT_PORT, FINGERS, SEGMENTS, SIDES

# Curl per finger (0 = straight, 1 = fully bent), thumb first.
POSES = {
    "rest": [0.2, 0.2, 0.25, 0.3, 0.3],
    "fist": [0.8, 1.0, 1.0, 1.0, 1.0],
    "point": [0.8, 0.0, 1.0, 1.0, 1.0],
    "peace": [0.8, 0.0, 0.0, 1.0, 1.0],
    "open": [0.0, 0.0, 0.0, 0.0, 0.0],
}


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ]


def axis_angle(axis, angle):
    s = math.sin(angle / 2)
    return [axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2)]


def make_packet(pose, t):
    body = {}
    sway = 0.05 * math.sin(t * 1.3)  # the hand drifts a little, like a real one
    for side in SIDES:
        hand_q = quat_mul(axis_angle([0, 1, 0], 0.6 + sway), axis_angle([1, 0, 0], -0.3))
        body[f"{side}Hand"] = {
            "position": {"x": 0.3 if side == "right" else -0.3, "y": 1.2, "z": 0.2},
            "rotation": dict(zip("xyzw", hand_q)),
        }
        for f, finger in enumerate(FINGERS):
            curl = POSES[pose][f] + random.gauss(0, 0.03)
            q = hand_q
            for s, seg in enumerate(SEGMENTS):
                q = quat_mul(q, axis_angle([1, 0, 0], curl * (1.4 if s == 0 else 1.1)))
                body[f"{side}{finger}{seg}"] = {
                    "position": {"x": 0.0, "y": 1.2, "z": 0.25 + 0.03 * s},
                    "rotation": dict(zip("xyzw", q)),
                }
    return {
        "version": "3,0",
        "fps": 60,
        "scene": {"timestamp": t, "actors": [{"name": "FakeActor", "body": body}], "props": []},
    }


def run(host, port, state, stop, fps=60):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t0 = time.time()
    while not stop.is_set():
        t = time.time() - t0
        sock.sendto(json.dumps(make_packet(state["pose"], t)).encode(), (host, port))
        time.sleep(1 / fps)
    sock.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--pose", choices=POSES, help="send one fixed pose")
    args = ap.parse_args()

    state = {"pose": args.pose or "rest"}
    stop = threading.Event()
    threading.Thread(target=run, args=(args.host, args.port, state, stop), daemon=True).start()
    names = list(POSES)
    print(f"Sending fake Studio data to {args.host}:{args.port}")
    try:
        if args.pose:
            while True:
                time.sleep(1)
        while True:
            print("Poses: " + "  ".join(f"{i + 1}={n}" for i, n in enumerate(names)))
            choice = input(f"[now: {state['pose']}] pose number: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(names):
                state["pose"] = names[int(choice) - 1]
    except (KeyboardInterrupt, EOFError):
        stop.set()


if __name__ == "__main__":
    main()
