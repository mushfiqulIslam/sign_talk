"""Turns glove frames into numbers a classifier can use: 1-second windows of joint angles and hand speed."""
from collections.abc import Iterator

import numpy as np

ANGLE_ENDINGS = ("_flexion", "_adduction", "_pronation", "_ulnarDeviation")
HAND_VELOCITY = ("LeftHand_velocity_", "RightHand_velocity_")
WINDOW = 60  # frames: 1 s at the gloves' 60 frames a second
STEP = 15    # a new decision every 0.25 s


def feature_columns(columns: list[str]) -> list[str]:
    """Joint angles (how bent and turned each finger and wrist is) plus how fast each hand moves.
    Hand position is left out so the signer can stand anywhere."""
    angles = [c for c in columns if c.endswith(ANGLE_ENDINGS)]
    speed = [c for c in columns if c.startswith(HAND_VELOCITY)]
    return angles + speed


def window_features(w: np.ndarray) -> np.ndarray:
    """Average pose, how much it varies, and how it changed from start to end of the window."""
    w = np.asarray(w)
    return np.concatenate([w.mean(0), w.std(0), w[-1] - w[0]])


def windows(frames: np.ndarray, size: int = WINDOW, step: int = STEP) -> Iterator[tuple[int, np.ndarray]]:
    for start in range(0, len(frames) - size + 1, step):
        yield start, frames[start:start + size]


# ---- model trained on the CSV recordings (one file per sign, sign repeated) ----

HELD_OUT = 0.3  # the last 30% of every recording is never trained on: it scores the model and is replayed in the demo


def _read(path) -> tuple[list[str], np.ndarray]:
    import pandas as pd

    df = pd.read_csv(path)
    cols = feature_columns(list(df.columns))
    return cols, df[cols].to_numpy(dtype=np.float32)


def train(data_dir) -> dict:
    """Random forest on 1-second windows. Returns the model plus its accuracy on unseen repetitions."""
    from pathlib import Path

    from sklearn.ensemble import RandomForestClassifier

    x_tr, y_tr, x_te, y_te, replay, cols = [], [], [], [], {}, None
    for path in sorted(Path(data_dir).glob("*.csv")):
        label = path.stem
        c, frames = _read(path)
        if cols is None:
            cols = c
        elif c != cols:
            raise ValueError(f"{path.name} has different columns from the other recordings")
        split = int(len(frames) * (1 - HELD_OUT))
        for _, w in windows(frames[:split]):
            x_tr.append(window_features(w)); y_tr.append(label)
        for _, w in windows(frames[split:]):
            x_te.append(window_features(w)); y_te.append(label)
        replay[label] = frames[split:]
    if len(replay) < 2:
        raise ValueError(f"Need recordings of at least 2 signs (one .csv per sign) in {data_dir}")
    clf = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(x_tr, y_tr)
    accuracy = float((clf.predict(x_te) == np.array(y_te)).mean()) if x_te else float("nan")
    clf.n_jobs = 1  # live guesses are one window at a time: starting every core per guess is slower
    return {"clf": clf, "labels": sorted(replay), "columns": cols, "accuracy": accuracy, "replay": replay}


def predict(model: dict, window: np.ndarray) -> tuple[str, float]:
    model["clf"].n_jobs = 1
    probs = model["clf"].predict_proba([window_features(window)])[0]
    i = int(probs.argmax())
    return str(model["clf"].classes_[i]), float(probs[i])


def save(model: dict, path) -> None:
    import joblib
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load(path) -> dict:
    import joblib

    return joblib.load(path)


# ---- using the model on new glove data ----

def row_vector(columns: list[str], row: dict) -> np.ndarray | None:
    """One live frame (column name -> value) as the model's vector; None if a column is missing."""
    try:
        return np.array([float(row[c]) for c in columns], dtype=np.float32)
    except (KeyError, TypeError, ValueError):
        return None


def read_recording(path, columns: list[str]) -> np.ndarray:
    """A new CSV recording (same export as the training files), as the model's columns."""
    import pandas as pd

    df = pd.read_csv(path)
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{path} lacks {len(missing)} column(s) the model needs, e.g. {', '.join(missing[:3])}")
    return df[columns].to_numpy(dtype=np.float32)


def detect(model: dict, frames: np.ndarray, **decoder_args) -> list[str]:
    """All signs in a recording, in order (offline, as fast as possible)."""
    from decoder import Decoder

    d = Decoder(**decoder_args)
    signs = []
    for start, w in windows(frames):
        label, prob = predict(model, w)
        signs += [v for kind, v in d.push(label, prob, (start + WINDOW) / 60) if kind == "sign"]
    return signs


def phrase_test(model: dict, phrases: int = 200, seed: int = 0, frames_per_sign: int = 150, **decoder_args) -> dict:
    """Chains held-out stretches of 2-4 random signs, as if signed in a row, and checks the
    backend reads back exactly that phrase. Harder than single windows: signs run into each other."""
    rng = np.random.default_rng(seed)
    labels = model["labels"]
    exact, found, total, examples = 0, 0, 0, []
    for _ in range(phrases):
        k = int(rng.integers(2, min(4, len(labels)) + 1))
        phrase = [str(x) for x in rng.choice(labels, size=k, replace=False)]
        parts = []
        for s in phrase:
            rec = model["replay"][s]
            start = int(rng.integers(0, max(1, len(rec) - frames_per_sign)))
            parts.append(rec[start:start + frames_per_sign])
        got = detect(model, np.concatenate(parts), **decoder_args)
        exact += got == phrase
        found += sum(1 for s in phrase if s in got)
        total += len(phrase)
        if got != phrase and len(examples) < 5:
            examples.append((phrase, got))
    if not examples:
        examples.append((phrase, got))
    return {"phrases": phrases, "exact": exact / phrases, "signs_found": found / total, "examples": examples}
