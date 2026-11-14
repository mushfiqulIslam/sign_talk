import numpy as np
import pandas as pd

import csv_signs


def fake_recording(path, wave, n=900):
    t = np.arange(n) / 60
    df = pd.DataFrame({
        "Timestamp": (t * 1000).astype(int),
        "RightWrist_flexion": 30 * np.sin(wave * t),
        "RightDigit2Metacarpophalangeal_flexion": 20 * np.cos(wave * t) + wave,
        "RightHand_velocity_x": np.cos(wave * t),
        "RightHand_position_x": np.zeros(n),
    })
    df.to_csv(path, index=False)


def test_train_learns_signs_and_keeps_unseen_frames_for_replay(tmp_path):
    fake_recording(tmp_path / "me.csv", wave=2)
    fake_recording(tmp_path / "day.csv", wave=7)
    model = csv_signs.train(tmp_path)
    assert model["labels"] == ["day", "me"]
    assert model["accuracy"] > 0.9  # on the held-out last 30%
    assert model["replay"]["me"].shape[1] == 3  # the 3 feature columns, position left out
    assert len(model["replay"]["me"]) == 900 - int(900 * 0.7)


def test_recogniser_names_a_window(tmp_path):
    fake_recording(tmp_path / "me.csv", wave=2)
    fake_recording(tmp_path / "day.csv", wave=7)
    model = csv_signs.train(tmp_path)
    label, prob = csv_signs.predict(model, model["replay"]["day"][:60])
    assert label == "day" and prob > 0.5


def test_save_and_load(tmp_path):
    fake_recording(tmp_path / "me.csv", wave=2)
    fake_recording(tmp_path / "day.csv", wave=7)
    path = tmp_path / "m.joblib"
    csv_signs.save(csv_signs.train(tmp_path), path)
    assert csv_signs.load(path)["labels"] == ["day", "me"]
