"""Receive hand data from Rokoko Studio's Custom Streaming (JSON over UDP).

In Rokoko Studio: Livestreaming > Custom > IP 127.0.0.1 (same laptop), port 14043,
data format JSON. Works on Windows, macOS and Linux; needs only the Python standard
library (plus the optional `lz4` package if Studio sends compressed packets).
"""

import json
import os
import socket
import time

DEFAULT_PORT = 14043

SIDES = ("left", "right")
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")
SEGMENTS = ("Proximal", "Medial", "Distal")
# The joints we use, in a fixed order: per side, the hand plus 15 finger joints.
HAND_JOINTS = [
    name
    for side in SIDES
    for name in [f"{side}Hand"] + [f"{side}{f}{s}" for f in FINGERS for s in SEGMENTS]
]

_HERE = os.path.dirname(os.path.abspath(__file__))
FIRST_PACKET_FILE = os.path.join(_HERE, "first_packet.json")


def _decode_bytes(data):
    """Studio sends plain JSON, or LZ4-compressed JSON if compression is switched on."""
    if data[:1] in (b"{", b"["):
        return json.loads(data.decode("utf-8"))
    try:
        import lz4.block
        import lz4.frame
    except ImportError as e:
        raise ValueError(
            "Packet is not plain JSON. Turn off compression in Studio's Custom stream, "
            "or install lz4 (pip install lz4)."
        ) from e
    try:
        text = lz4.frame.decompress(data)
    except Exception:
        text = lz4.block.decompress(data, uncompressed_size=16 * 1024 * 1024)
    return json.loads(text.decode("utf-8"))


def _vec(value, keys):
    """Accept {"x":..,"y":..} dicts or plain [x, y, ...] lists."""
    if isinstance(value, dict):
        return [float(value.get(k, 0.0)) for k in keys]
    return [float(v) for v in value]


def parse_packet(packet):
    """Return {joint_name: [px, py, pz, qx, qy, qz, qw]} for the first actor with gloves.

    Handles the Studio JSON v3 layout (scene.actors[].body as a dict of named joints)
    and a list layout (body.joints = [{"name":..., "position":..., "rotation":...}]).
    """
    actors = packet.get("scene", {}).get("actors", [])
    for actor in actors:
        body = actor.get("body", {})
        items = []
        if isinstance(body.get("joints"), list):
            items = [(j.get("name", ""), j) for j in body["joints"]]
        elif isinstance(body, dict):
            items = [(k, v) for k, v in body.items() if isinstance(v, dict)]
        joints = {}
        lower = {n.lower(): n for n in HAND_JOINTS}
        for name, j in items:
            canonical = lower.get(str(name).lower())
            if canonical is None or "rotation" not in j:
                continue
            pos = _vec(j.get("position", [0, 0, 0]), "xyz")
            rot = _vec(j["rotation"], "xyzw")
            joints[canonical] = pos + rot
        if joints:
            return joints
    return {}


class StudioReceiver:
    """Yields one joints dict per Studio frame. Prints a hint if nothing arrives."""

    def __init__(self, host="0.0.0.0", port=DEFAULT_PORT, timeout=0.5):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.settimeout(timeout)
        self.port = port
        self._saved_first = False
        self._warned_empty = False

    def frames(self):
        last_data = time.time()
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                if time.time() - last_data > 3:
                    print(f"... no data on UDP port {self.port}. Is Studio's Custom stream on?")
                    last_data = time.time()
                continue
            last_data = time.time()
            try:
                packet = _decode_bytes(data)
            except ValueError as e:
                print(f"!! {e}")
                continue
            if not self._saved_first:
                with open(FIRST_PACKET_FILE, "w") as f:
                    json.dump(packet, f, indent=1)
                print(f"(saved the first Studio packet to {FIRST_PACKET_FILE})")
                self._saved_first = True
            joints = parse_packet(packet)
            if not joints:
                if not self._warned_empty:
                    print("!! Data arrives but no hand joints found. Check first_packet.json.")
                    self._warned_empty = True
                continue
            yield joints

    def close(self):
        self.sock.close()
