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
    return {"clf": clf, "labels": sorted(replay), "columns": cols, "accuracy": accuracy, "replay": replay}


def predict(model: dict, window: np.ndarray) -> tuple[str, float]:
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
