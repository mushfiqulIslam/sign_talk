"""Look at what Rokoko Studio is sending, before recording anything.

Usage:
  python inspect_stream.py          layout of the data, then live finger bend angles
  python inspect_stream.py --raw    print one complete packet as JSON and stop
  python inspect_stream.py --joints print every joint's position and rotation once and stop
"""

import argparse
import json
import socket
import time

import numpy as np

from signs import quat_to_matrix
from studio import DEFAULT_PORT, FINGERS, SIDES, _decode_bytes, parse_packet


def describe(value, indent=0, max_items=6):
    """Print the shape of a JSON value: keys, list lengths and example values."""
    pad = "  " * indent
    if isinstance(value, dict):
        keys = list(value)
        for k in keys[:max_items]:
            v = value[k]
            if isinstance(v, (dict, list)):
                kind = f"{{{len(v)} keys}}" if isinstance(v, dict) else f"[{len(v)} items]"
                print(f"{pad}{k}: {kind}")
                describe(v, indent + 1, max_items)
            else:
                print(f"{pad}{k}: {v!r}")
        if len(keys) > max_items:
            print(f"{pad}... {len(keys) - max_items} more keys: {', '.join(keys[max_items:])}")
    elif isinstance(value, list) and value:
        print(f"{pad}[0]:")
        describe(value[0], indent + 1, max_items)


def receive_one(sock):
    while True:
        try:
            data, addr = sock.recvfrom(65535)
            return _decode_bytes(data), addr, len(data)
        except socket.timeout:
            print("... waiting for data (is Studio's Custom stream on, port right?)")


def bend_degrees(joints, side, finger):
    """Angle between the back of the hand and the finger's first segment."""
    hand, prox = joints.get(f"{side}Hand"), joints.get(f"{side}{finger}Proximal")
    if not hand or not prox:
        return None
    r = quat_to_matrix(hand[3:]).T @ quat_to_matrix(prox[3:])
    return float(np.degrees(np.arccos(np.clip((np.trace(r) - 1) / 2, -1, 1))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--joints", action="store_true")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(2)
    print(f"Listening on UDP port {args.port}...")

    packet, addr, size = receive_one(sock)
    print(f"\nFirst packet: {size} bytes from {addr[0]}")
    if args.raw:
        print(json.dumps(packet, indent=1))
        return

    print("\n--- Layout of one packet ---")
    describe(packet)
    joints = parse_packet(packet)
    print(f"\n--- Hand joints we understood: {len(joints)} of 32 ---")
    print(", ".join(sorted(joints)) or "NONE: check the layout above and tell Claude")

    if args.joints:
        for name in sorted(joints):
            p, q = joints[name][:3], joints[name][3:]
            print(f"{name:24s} pos {np.round(p, 3)}  rot {np.round(q, 3)}")
        return

    print("\n--- Live finger bend (degrees, 0 = straight). Ctrl+C to stop ---")
    print("      " + "  ".join(f"{s[0].upper()}:{f[:3]:>5s}" for s in SIDES for f in FINGERS))
    frames, t0, last = 0, time.time(), 0.0
    try:
        while True:
            packet, _, _ = receive_one(sock)
            joints = parse_packet(packet)
            frames += 1
            now = time.time()
            if now - last < 0.2:
                continue
            last = now
            cells = []
            for s in SIDES:
                for f in FINGERS:
                    d = bend_degrees(joints, s, f)
                    cells.append(f"{'-':>7s}" if d is None else f"{d:7.0f}")
            fps = frames / (now - t0)
            print(f"{fps:4.0f}fps " + " ".join(cells))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
