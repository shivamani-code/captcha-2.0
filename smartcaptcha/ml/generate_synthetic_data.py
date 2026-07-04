import csv
import numpy as np

# ---------------------------------------------------------------------------
# Synthetic data generator — SwipeTCHA (10-feature schema)
#
# Feature ranges are calibrated to realistic human vs bot behavioral
# distributions for a horizontal slider drag (~300-700px track).
#
# Human ranges are intentionally wider and partially overlap with bots to
# produce a non-trivially separable dataset (closer to real-world data).
# ---------------------------------------------------------------------------

NUM_HUMANS = 800
NUM_BOTS   = 600
OUTPUT_FILE = "synthetic_captcha_data.csv"

RNG = np.random.default_rng(seed=42)


def generate_human() -> dict:
    """
    Realistic human behavioral profile for a slider drag.
    """
    speed = float(RNG.uniform(100.0, 600.0))          # px/s
    if RNG.random() < 0.1:
        speed = float(RNG.uniform(550.0, 800.0))

    return {
        "avg_mouse_speed":           round(speed,                                                  4),
        "mouse_path_entropy":        round(float(RNG.uniform(0.25, 0.90)),                         4),
        "click_delay":               round(float(RNG.uniform(0.5, 3.0)),                           4),
        "task_completion_time":      round(float(RNG.uniform(0.6, 4.0)),                           4),
        "idle_time":                 round(float(RNG.uniform(0.0, 0.8)),                           4),
        "micro_jitter_variance":     round(float(RNG.uniform(5.0, 120.0)),                         4),
        "acceleration_curve":        round(float(RNG.uniform(800.0, 6000.0)),                      4),
        "curvature_variance":        round(float(RNG.uniform(0.0005, 0.12)),                       4),
        "overshoot_correction_ratio":round(float(RNG.beta(1.5, 12) * 0.25),                       4),
        "timing_entropy":            round(float(RNG.uniform(0.45, 0.98)),                         4),
        "label": 1,
    }


def generate_bot() -> dict:
    """
    Realistic automation behavioral profile.
    """
    bot_type = RNG.choice(["naive", "padded", "sophisticated"],
                          p=[0.40, 0.35, 0.25])

    if bot_type == "naive":
        return {
            "avg_mouse_speed":            round(float(RNG.uniform(1200.0, 3000.0)), 4),
            "mouse_path_entropy":         round(float(RNG.uniform(0.0, 0.06)),  4),
            "click_delay":                round(float(RNG.uniform(0.01, 0.15)), 4),
            "task_completion_time":       round(float(RNG.uniform(0.08, 0.5)),  4),
            "idle_time":                  round(float(RNG.uniform(0.0, 0.02)),  4),
            "micro_jitter_variance":      round(float(RNG.uniform(0.0, 0.2)),   4),
            "acceleration_curve":         round(float(RNG.uniform(0.0, 80.0)),  4),
            "curvature_variance":         round(float(RNG.uniform(0.0, 0.0008)),4),
            "overshoot_correction_ratio": round(float(RNG.uniform(0.0, 0.005)), 4),
            "timing_entropy":             round(float(RNG.uniform(0.0, 0.08)),  4),
            "label": 0,
        }

    elif bot_type == "padded":
        return {
            "avg_mouse_speed":            round(float(RNG.uniform(800.0, 1500.0)), 4),
            "mouse_path_entropy":         round(float(RNG.uniform(0.02, 0.18)), 4),
            "click_delay":                round(float(RNG.uniform(0.1, 0.8)),   4),
            "task_completion_time":       round(float(RNG.uniform(0.5, 2.0)),   4),
            "idle_time":                  round(float(RNG.uniform(0.0, 0.15)),  4),
            "micro_jitter_variance":      round(float(RNG.uniform(0.0, 0.6)),   4),
            "acceleration_curve":         round(float(RNG.uniform(0.0, 150.0)), 4),
            "curvature_variance":         round(float(RNG.uniform(0.0, 0.003)), 4),
            "overshoot_correction_ratio": round(float(RNG.uniform(0.0, 0.015)), 4),
            "timing_entropy":             round(float(RNG.uniform(0.05, 0.22)), 4),
            "label": 0,
        }

    else:  # sophisticated
        return {
            "avg_mouse_speed":            round(float(RNG.uniform(400.0, 900.0)),  4),
            "mouse_path_entropy":         round(float(RNG.uniform(0.08, 0.35)), 4),
            "click_delay":                round(float(RNG.uniform(0.3, 1.5)),   4),
            "task_completion_time":       round(float(RNG.uniform(0.8, 3.0)),   4),
            "idle_time":                  round(float(RNG.uniform(0.0, 0.4)),   4),
            "micro_jitter_variance":      round(float(RNG.uniform(0.0, 2.0)),   4),
            "acceleration_curve":         round(float(RNG.uniform(50.0, 500.0)), 4),
            "curvature_variance":         round(float(RNG.uniform(0.0, 0.008)), 4),
            "overshoot_correction_ratio": round(float(RNG.uniform(0.0, 0.04)),  4),
            "timing_entropy":             round(float(RNG.uniform(0.08, 0.38)), 4),
            "label": 0,
        }


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
    "label",
]

with open(OUTPUT_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS)
    writer.writeheader()
    for _ in range(NUM_HUMANS):
        writer.writerow(generate_human())
    for _ in range(NUM_BOTS):
        writer.writerow(generate_bot())

print(f"Synthetic data generated: {NUM_HUMANS} human + {NUM_BOTS} bot = {NUM_HUMANS + NUM_BOTS} total rows")
print(f"Output: {OUTPUT_FILE}")
print(f"Features: {FEATURE_COLUMNS[:-1]}")
