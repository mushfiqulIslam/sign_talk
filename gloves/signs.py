"""Hand-shape features, the recorded sign dataset, and a simple nearest-match recogniser.

Features are finger rotations relative to the hand, so they don't depend on where
the person stands or which way they face. Recordings are saved raw (joint positions
and rotations), so the features can change later without recording again.
"""

import glob
import os
import time

import numpy as np

from studio import HAND_JOINTS, SIDES

_HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(_HERE, "sign_dataset")
REST_LABEL = "rest"  # record your neutral hand as "rest"; it is never output as a word


def quat_to_matrix(q):
    x, y, z, w = q
    n = np.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def frame_to_array(joints):
    """Joints dict -> (len(HAND_JOINTS), 7) array; missing joints are NaN."""
    out = np.full((len(HAND_JOINTS), 7), np.nan, dtype=np.float32)
    for i, name in enumerate(HAND_JOINTS):
        if name in joints:
            out[i] = joints[name]
    return out


def frame_features(raw):
    """(J, 7) raw frame -> 1-D feature vector (finger rotations in hand space + palm tilt)."""
    feats = []
    per_side = len(HAND_JOINTS) // len(SIDES)
    for s in range(len(SIDES)):
        block = raw[s * per_side : (s + 1) * per_side]
        hand = block[0]
        if np.isnan(hand[3:]).any():
            feats.append(np.zeros(3 + 9 * (per_side - 1)))
            continue
        r_hand = quat_to_matrix(hand[3:])
        side_feats = [r_hand.T @ np.array([0.0, 1.0, 0.0])]  # world "up" seen from the hand
        for joint in block[1:]:
            if np.isnan(joint[3:]).any():
                side_feats.append(np.zeros(9))
            else:
                side_feats.append((r_hand.T @ quat_to_matrix(joint[3:])).ravel())
        feats.append(np.concatenate(side_feats))
    return np.concatenate(feats)


def sequence_vector(raw_frames, points=5):
    """(T, J, 7) frames -> one vector: the mean shape plus a few evenly spaced snapshots,
    so both held signs and short movements can be told apart."""
    f = np.array([frame_features(fr) for fr in raw_frames])
    idx = np.linspace(0, len(f) - 1, points).round().astype(int)
    return np.concatenate([f.mean(axis=0)] + [f[i] for i in idx])


def save_sample(sign, raw_frames, dataset_dir=DATASET_DIR):
    sign_dir = os.path.join(dataset_dir, sign)
    os.makedirs(sign_dir, exist_ok=True)
    path = os.path.join(sign_dir, f"{sign}_{int(time.time() * 1000)}.npz")
    np.savez_compressed(path, frames=np.array(raw_frames, dtype=np.float32), joints=np.array(HAND_JOINTS))
    return path


def load_dataset(dataset_dir=DATASET_DIR):
    samples = []
    for path in sorted(glob.glob(os.path.join(dataset_dir, "*", "*.npz"))):
        data = np.load(path)
        if list(data["joints"]) != HAND_JOINTS:
            print(f"skipping {path}: recorded with a different joint list")
            continue
        samples.append((os.path.basename(os.path.dirname(path)), data["frames"]))
    return samples


class SignModel:
    """1-nearest-neighbour on sequence vectors, with a per-sign 'too far' threshold."""

    def __init__(self, samples):
        if not samples:
            raise ValueError(f"No recordings found in {DATASET_DIR}. Record some signs first.")
        self.labels = [label for label, _ in samples]
        x = np.array([sequence_vector(frames) for _, frames in samples])
        self.mean, self.std = x.mean(axis=0), x.std(axis=0) + 1e-3
        self.x = (x - self.mean) / self.std
        self.threshold = {}
        for label in set(self.labels):
            # How far each recording is from its nearest sibling: a live sign much
            # further than that from every recording is treated as "no match".
            # Compute distances in one matrix operation for quick startup on larger datasets.
            idx = [i for i, l in enumerate(self.labels) if l == label]
            if len(idx) > 1:
                x = self.x[idx]
                norm2 = np.einsum("ij,ij->i", x, x)
                d2 = norm2[:, None] + norm2[None, :] - 2.0 * (x @ x.T)
                np.maximum(d2, 0.0, out=d2)
                np.fill_diagonal(d2, np.inf)
                nearest = np.sqrt(d2.min(axis=1))
                self.threshold[label] = 2.0 * float(nearest.max())
            else:
                self.threshold[label] = np.inf

    def predict(self, raw_frames):
        v = (sequence_vector(raw_frames) - self.mean) / self.std
        d = np.linalg.norm(self.x - v, axis=1)
        i = int(d.argmin())
        label = self.labels[i]
        if d[i] > self.threshold[label]:
            return None, float(d[i])
        return label, float(d[i])

    def summary(self):
        counts = {l: self.labels.count(l) for l in sorted(set(self.labels))}
        return ", ".join(f"{l} ({n})" for l, n in counts.items())
