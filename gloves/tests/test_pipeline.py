"""End-to-end check with the pretend glove: stream -> record -> train -> recognise.
Run:  python tests/test_pipeline.py"""
import os, sys, tempfile, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fake_studio, signs
from studio import StudioReceiver

PORT = 15077

def main():
    state, stop = {"pose": "rest"}, threading.Event()
    rx = StudioReceiver(port=PORT)
    threading.Thread(target=fake_studio.run, args=("127.0.0.1", PORT, state, stop), daemon=True).start()
    frames = rx.frames()
    take = lambda n: [signs.frame_to_array(next(frames)) for _ in range(n)]
    poses = ["rest", "fist", "point", "peace", "open"]
    with tempfile.TemporaryDirectory() as d:
        for pose in poses:
            state["pose"] = pose
            take(10)  # let the pose settle
            for _ in range(5):
                signs.save_sample(pose, take(30), dataset_dir=d)
        model = signs.SignModel(signs.load_dataset(d))
        print("trained on:", model.summary())
        ok = 0
        for pose in poses:
            state["pose"] = pose
            take(10)
            label, dist = model.predict(take(30))
            print(f"  live {pose:6s} -> {label} ({dist:.1f})")
            ok += label == pose
    stop.set(); rx.close()
    print(f"{ok}/{len(poses)} correct")
    sys.exit(0 if ok == len(poses) else 1)

main()
