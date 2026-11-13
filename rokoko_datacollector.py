import socket
import json
import os
import time
import numpy as np

# --- Configuration ---
UDP_IP = "127.0.0.1"
UDP_PORT = 14043          # Must match Rokoko Studio Custom Streaming port
FRAMES_PER_SAMPLE = 30    # Number of frames per sign recording (e.g., ~0.5 - 1 second)
OUTPUT_DIR = "sign_dataset"

# Create output folder if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_hand_features(joints_data):
    """
    Extracts and normalizes joint data from the Rokoko JSON stream.
    To make the model robust, we extract joint positions/orientations 
    and flatten them into a single 1D feature vector for that frame.
    """
    frame_features = []
    
    # Depending on JSON v3/v4 structure, filter or parse joints
    for joint in joints_data:
        # Pull name, position (x, y, z), and rotation quaternion (x, y, z, w)
        pos = joint.get("position", [0.0, 0.0, 0.0])
        rot = joint.get("rotation", [0.0, 0.0, 0.0, 1.0])
        
        # Focus heavily on hand/finger joints if present
        name = joint.get("name", "").lower()
        if "hand" in name or "finger" in name or "thumb" in name or "wrist" in name:
            frame_features.extend(pos + rot)
            
    return frame_features

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.5)

    print("==================================================")
    print("      ROKOKO SIGN LANGUAGE DATA COLLECTOR         ")
    print("==================================================")
    print(f"Listening on {UDP_IP}:{UDP_PORT}\n")

    try:
        while True:
            sign_name = input("Enter the sign name you want to record (or 'quit' to exit): ").strip()
            if sign_name.lower() == 'quit':
                break
            if not sign_name:
                continue

            samples_to_record = int(input(f"How many repetitions of '{sign_name}' do you want to record? [Default 10]: ") or 10)
            
            print(f"\nGet ready! We will record {samples_to_record} samples of '{sign_name}'.")
            print("Press Enter when ready, then perform the sign when prompted.")
            input()

            sign_dir = os.path.join(OUTPUT_DIR, sign_name)
            os.makedirs(sign_dir, exist_ok=True)
            
            recorded_count = 0
            
            for sample_idx in range(samples_to_record):
                print(f"\n[Sample {sample_idx + 1}/{samples_to_record}] 🔴 RECORDING in 1 second...")
                time.sleep(1.0)
                print(f"👉 SIGN NOW! ({FRAMES_PER_SAMPLE} frames)...")

                sequence_buffer = []
                
                # Capture exact number of frames for this sign repetition
                while len(sequence_buffer) < FRAMES_PER_SAMPLE:
                    try:
                        data, _ = sock.recvfrom(65535)
                        packet = json.loads(data.decode('utf-8'))
                        
                        scene = packet.get("scene", {})
                        actors = scene.get("actors", [])
                        
                        for actor in actors:
                            joints = actor.get("body", {}).get("joints", [])
                            if joints:
                                features = extract_hand_features(joints)
                                if features:
                                    sequence_buffer.append(features)
                                    break
                    except (socket.timeout, json.JSONDecodeError):
                        continue

                # Save sample as a NumPy array file shape: (FRAMES_PER_SAMPLE, feature_dim)
                if len(sequence_buffer) == FRAMES_PER_SAMPLE:
                    sample_array = np.array(sequence_buffer, dtype=np.float32)
                    timestamp = int(time.time() * 1000)
                    filename = os.path.join(sign_dir, f"{sign_name}_{timestamp}.npy")
                    np.save(filename, sample_array)
                    recorded_count += 1
                    print(f"✅ Saved sample to {filename}")
                else:
                    print("⚠️ Recording interrupted or timed out. Skipping sample.")
                
                time.sleep(0.5) # Brief break between repetitions

            print(f"\n🎉 Finished recording '{sign_name}': {recorded_count} successful samples saved to '{sign_dir}/'\n")

    except KeyboardInterrupt:
        print("\n🛑 Exiting data collector.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()