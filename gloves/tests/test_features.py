import numpy as np
import pandas as pd

from csv_signs import feature_columns, window_features, windows


def test_columns_are_joint_angles_and_hand_velocity():
    cols = ["Timestamp", "LeftHand_position_x", "LeftHand_velocity_x", "RightWrist_flexion",
            "RightWrist_flexion_velocity", "LeftDigit2Metacarpophalangeal_ulnarDeviation"]
    assert feature_columns(cols) == ["RightWrist_flexion", "LeftDigit2Metacarpophalangeal_ulnarDeviation",
                                     "LeftHand_velocity_x"]


def test_window_features_are_mean_std_and_change():
    w = np.array([[0.0, 1.0], [2.0, 1.0], [4.0, 1.0]])
    f = window_features(w)
    assert f.tolist() == [2.0, 1.0, np.std([0, 2, 4]), 0.0, 4.0, 0.0]


def test_windows_slide_over_frames():
    a = np.arange(200).reshape(100, 2).astype(float)
    starts = [s for s, _ in windows(a, size=60, step=15)]
    assert starts == [0, 15, 30]


def test_window_can_be_a_list_of_frames():
    f = window_features([np.array([0.0, 1.0]), np.array([2.0, 1.0])])
    assert f.tolist() == [1.0, 1.0, 1.0, 0.0, 2.0, 0.0]
