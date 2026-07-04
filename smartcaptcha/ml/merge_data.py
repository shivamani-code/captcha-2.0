import json
import re
import math
import os
import pandas as pd
import numpy as np

# Feature Column Definition
FEATURE_COLUMNS = [
    "avg_mouse_speed",
    "mouse_path_entropy",
    "click_delay",
    "task_completion_time",
    "idle_time",
    "micro_jitter_variance",
    "acceleration_curve",
    "curvature_variance",
    "overshoot_correction_ratio",
    "timing_entropy",
    "label"
]

def variance(values):
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((x - mean) ** 2 for x in values) / (n - 1)

def shannon_entropy(probs):
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log2(p)
    return h

def safe_divide(n, d):
    if d == 0:
        return 0.0
    return n / d

def compute_features(coords, times, label, is_bot):
    if len(coords) < 3:
        return None

    # click_delay: time to first movement (capped at 5s)
    click_delay = safe_divide(times[0], 1000.0)
    if click_delay > 5.0:
        click_delay = 1.0 + (times[0] % 2000) / 1000.0 # moderate realistic fallback
    elif click_delay < 0.05:
        click_delay = 0.05

    dx_list = []
    dy_list = []
    segment_speeds = []
    segment_dt = []
    angles = []
    total_distance = 0.0
    total_time = 0.0

    for i in range(1, len(coords)):
        dt_ms = times[i] - times[i-1]
        if dt_ms <= 0:
            continue
        
        dx = coords[i][0] - coords[i-1][0]
        dy = coords[i][1] - coords[i-1][1]
        dist = math.hypot(dx, dy)

        total_distance += dist
        total_time += dt_ms

        speed = dist / (dt_ms / 1000.0)
        segment_speeds.append(speed)
        segment_dt.append(dt_ms)
        dx_list.append(dx)
        dy_list.append(dy)
        angles.append(math.atan2(dy, dx))

    if len(segment_speeds) < 2:
        return None

    task_completion_time = total_time / 1000.0
    avg_mouse_speed = safe_divide(total_distance, task_completion_time)

    # idle_time
    idle_time_ms = sum(dt for dt in segment_dt if dt > 120)
    idle_time = idle_time_ms / 1000.0

    # mouse_path_entropy
    direction_bins = 12
    direction_counts = [0] * direction_bins
    for a in angles:
        normalized = (a + math.pi) / (2 * math.pi)
        idx = min(direction_bins - 1, max(0, int(normalized * direction_bins)))
        direction_counts[idx] += 1
    direction_total = sum(direction_counts)
    direction_probs = [safe_divide(c, direction_total) for c in direction_counts]
    mouse_path_entropy = safe_divide(shannon_entropy(direction_probs), math.log2(direction_bins))

    # micro_jitter_variance
    micro_jitter_variance = variance(dx_list) + variance(dy_list)

    # acceleration_curve
    accelerations_abs = []
    for i in range(1, len(segment_speeds)):
        dv = segment_speeds[i] - segment_speeds[i-1]
        dt_s = segment_dt[i] / 1000.0
        if dt_s > 0:
            accelerations_abs.append(abs(dv / dt_s))
    acceleration_curve = sum(accelerations_abs) / len(accelerations_abs) if accelerations_abs else 0.0

    # curvature_variance
    curvatures = []
    for i in range(1, len(angles)):
        da = angles[i] - angles[i-1]
        wrapped = math.atan2(math.sin(da), math.cos(da))
        seg_len = math.hypot(dx_list[i], dy_list[i])
        if seg_len > 0:
            curvatures.append(abs(wrapped) / seg_len)
    curvature_variance = variance(curvatures)

    # overshoot_correction_ratio
    forward = sum(dx for dx in dx_list if dx >= 0)
    backward = sum(abs(dx) for dx in dx_list if dx < 0)
    overshoot_correction_ratio = safe_divide(backward, forward)

    # timing_entropy
    timing_bins = 10
    timing_counts = [0] * timing_bins
    timing_entropy = 0.0
    if segment_dt:
        min_dt = min(segment_dt)
        max_dt = max(segment_dt)
        range_dt = max_dt - min_dt
        for dt in segment_dt:
            norm = safe_divide(dt - min_dt, range_dt) if range_dt > 0 else 0.0
            idx = min(timing_bins - 1, max(0, int(norm * timing_bins)))
            timing_counts[idx] += 1
        timing_total = sum(timing_counts)
        timing_probs = [safe_divide(c, timing_total) for c in timing_counts]
        timing_entropy = safe_divide(shannon_entropy(timing_probs), math.log2(timing_bins))

    return {
        "avg_mouse_speed": round(avg_mouse_speed, 4),
        "mouse_path_entropy": round(mouse_path_entropy, 4),
        "click_delay": round(click_delay, 4),
        "task_completion_time": round(task_completion_time, 4),
        "idle_time": round(idle_time, 4),
        "micro_jitter_variance": round(micro_jitter_variance, 4),
        "acceleration_curve": round(acceleration_curve, 4),
        "curvature_variance": round(curvature_variance, 4),
        "overshoot_correction_ratio": round(overshoot_correction_ratio, 4),
        "timing_entropy": round(timing_entropy, 4),
        "label": label
    }

def segment_session(coords, times, label, is_bot):
    if len(coords) < 15 or len(times) < 15:
        return []

    segments = []
    curr_coords = [coords[0]]
    curr_times = [times[0]]

    # Split trajectory on gaps > 500ms
    for i in range(1, len(coords)):
        if times[i] - times[i-1] > 500:
            if len(curr_coords) >= 15:
                feats = compute_features(curr_coords, curr_times, label, is_bot)
                if feats:
                    segments.append(feats)
            curr_coords = []
            curr_times = []
        curr_coords.append(coords[i])
        curr_times.append(times[i])

    if len(curr_coords) >= 15:
        feats = compute_features(curr_coords, curr_times, label, is_bot)
        if feats:
            segments.append(feats)

    return segments

def load_phase1_labels():
    labels = {}
    paths = [
        r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase1\annotations\humans_and_advanced_bots\train',
        r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase1\annotations\humans_and_advanced_bots\test',
        r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase1\annotations\humans_and_moderate_bots\train',
        r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase1\annotations\humans_and_moderate_bots\test',
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        sess_id, lbl = parts[0], parts[1]
                        labels[sess_id] = 1 if lbl == 'human' else 0
    return labels

def main():
    print("Starting behavioral dataset merge and pipeline creation...")

    # 1. Parse Phase 1
    phase1_labels = load_phase1_labels()
    print(f"Loaded {len(phase1_labels)} session labels for Phase 1.")

    p1_dirs = [
        r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase1\data\mouse_movements\humans_and_advanced_bots',
        r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase1\data\mouse_movements\humans_and_moderate_bots'
    ]

    all_features = []

    for d in p1_dirs:
        if not os.path.exists(d):
            continue
        print(f"Processing Phase 1 directory: {os.path.basename(d)}")
        for sess_id in os.listdir(d):
            sess_dir = os.path.join(d, sess_id)
            if not os.path.isdir(sess_dir):
                continue
            
            label = phase1_labels.get(sess_id, 0) # default bot if label missing
            is_bot = (label == 0)

            json_path = os.path.join(sess_dir, "mouse_movements.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path) as f:
                        data = json.load(f)
                        times = [int(x) for x in data['mousemove_times'].split(',') if x]
                        coords = [(int(x), int(y)) for x, y in re.findall(r'\[(\d+),(\d+)\]', data['mousemove_total_behaviour'])]
                        
                        feats = segment_session(coords, times, label, is_bot)
                        all_features.extend(feats)
                except Exception as e:
                    print(f"Error reading session {sess_id}: {e}")

    # 2. Parse Phase 2
    p2_files = [
        (r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase2\data\mouse_movements\humans\mouse_movements_humans.json', 1, False),
        (r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase2\data\mouse_movements\bots\mouse_movements_advanced_bots.json', 0, True),
        (r'c:\Users\hpman\Desktop\files\web_bot_detection_dataset\phase2\data\mouse_movements\bots\mouse_movements_moderate_bots.json', 0, True)
    ]

    for path, label, is_bot in p2_files:
        if not os.path.exists(path):
            continue
        print(f"Processing Phase 2 file: {os.path.basename(path)}")
        try:
            with open(path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if 'mousemove_times' in data and 'mousemove_total_behaviour' in data:
                        # Parse time strings (e.g. "[(t0)][(t1)]..." or comma-separated integers)
                        # We see phase 2 times look like comma separated or bracketed lists
                        times_str = data['mousemove_times']
                        times = [int(x) for x in re.findall(r'\d+', times_str)]
                        coords = [(int(x), int(y)) for x, y in re.findall(r'\[(\d+),(\d+)\]', data['mousemove_total_behaviour'])]
                        
                        feats = segment_session(coords, times, label, is_bot)
                        all_features.extend(feats)
        except Exception as e:
            print(f"Error parsing file {path}: {e}")

    # Create real behavior DataFrame
    real_df = pd.DataFrame(all_features)
    print(f"Extracted {len(real_df)} behavioral gesture samples from the real dataset.")

    # 3. Load Synthetic Dataset
    syn_path = "synthetic_captcha_data.csv"
    if os.path.exists(syn_path):
        syn_df = pd.read_csv(syn_path)
        print(f"Loaded {len(syn_df)} synthetic samples.")
    else:
        syn_df = pd.DataFrame(columns=FEATURE_COLUMNS)
        print("No synthetic dataset found. Merged dataset will consist of real data only.")

    # 4. Combine Datasets
    merged_df = pd.concat([syn_df, real_df], ignore_index=True)
    
    # 5. Prevent duplicate rows
    initial_len = len(merged_df)
    merged_df.drop_duplicates(subset=FEATURE_COLUMNS[:-1], inplace=True)
    dups_removed = initial_len - len(merged_df)
    print(f"Combined dataset: {len(merged_df)} total samples (Removed {dups_removed} duplicates).")

    # 6. Save final training dataset
    merged_df.to_csv("merged_behavior_data.csv", index=False)
    print("Saved merged dataset to merged_behavior_data.csv")

if __name__ == "__main__":
    main()
