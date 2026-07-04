"""
SwipeTCHA — Random Forest Training Script (10-feature schema)

Trains on synthetic_captcha_data.csv (10 behavioral features).
Outputs:
  - captcha_model.pkl         (trained model)
  - model_metrics.json        (accuracy, precision, recall, f1, confusion matrix)
  - feature_importance.json   (per-feature importance ranking)
"""

import json
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
    classification_report,
)

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
DATA_FILE  = "merged_behavior_data.csv"
MODEL_FILE = "captcha_model.pkl"

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
]

data = pd.read_csv(DATA_FILE)

# Validate all expected columns are present
missing = [c for c in FEATURE_COLUMNS if c not in data.columns]
if missing:
    raise ValueError(f"Missing columns in dataset: {missing}")

X = data[FEATURE_COLUMNS]
y = data["label"]

print(f"\n{'='*60}")
print(f"  SwipeTCHA Model Training — 10-Feature Schema")
print(f"{'='*60}")
print(f"  Dataset    : {DATA_FILE}")
print(f"  Samples    : {len(data)} ({(y == 1).sum()} human, {(y == 0).sum()} bot)")
print(f"  Features   : {len(FEATURE_COLUMNS)}")

# ---------------------------------------------------------------------------
# 2. Train / test split (stratified)
# ---------------------------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

print(f"  Train set  : {len(X_train)} samples")
print(f"  Test set   : {len(X_test)} samples")

# ---------------------------------------------------------------------------
# 3. Train Random Forest
# ---------------------------------------------------------------------------
model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_split=4,
    min_samples_leaf=2,
    class_weight="balanced",   # handles slight class imbalance
    random_state=42,
    n_jobs=-1,
)

model.fit(X_train, y_train)
print(f"\n  Model trained: {model.n_estimators} trees, max_depth={model.max_depth}")

# ---------------------------------------------------------------------------
# 4. Evaluate on held-out test set
# ---------------------------------------------------------------------------
y_pred      = model.predict(X_test)
y_proba     = model.predict_proba(X_test)[:, 1]   # P(human)

accuracy    = accuracy_score(y_test, y_pred)
precision   = precision_score(y_test, y_pred, zero_division=0)
recall      = recall_score(y_test, y_pred, zero_division=0)
f1          = f1_score(y_test, y_pred, zero_division=0)
auc         = roc_auc_score(y_test, y_proba)
cm          = confusion_matrix(y_test, y_pred).tolist()

print(f"\n{'-'*60}")
print(f"  HOLD-OUT TEST SET METRICS")
print(f"{'-'*60}")
print(f"  Accuracy  : {accuracy:.4f}  ({accuracy*100:.2f}%)")
print(f"  Precision : {precision:.4f}")
print(f"  Recall    : {recall:.4f}")
print(f"  F1 Score  : {f1:.4f}")
print(f"  ROC-AUC   : {auc:.4f}")
print(f"\n  Confusion Matrix (rows=actual, cols=predicted):")
print(f"                Pred Bot  Pred Human")
print(f"  Actual Bot  :  {cm[0][0]:>6}    {cm[0][1]:>6}")
print(f"  Actual Human:  {cm[1][0]:>6}    {cm[1][1]:>6}")

print(f"\n  Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Bot", "Human"]))

# ---------------------------------------------------------------------------
# 5. Stratified 5-fold cross-validation
# ---------------------------------------------------------------------------
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_results = cross_validate(
    model, X, y, cv=cv,
    scoring=["accuracy", "precision", "recall", "f1", "roc_auc"],
    return_train_score=False,
    n_jobs=-1,
)

print(f"{'-'*60}")
print(f"  5-FOLD CROSS-VALIDATION SCORES")
print(f"{'-'*60}")
for metric in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
    scores = cv_results[f"test_{metric}"]
    print(f"  {metric:<12}: {scores.mean():.4f} ± {scores.std():.4f}")

# ---------------------------------------------------------------------------
# 6. Feature importance
# ---------------------------------------------------------------------------
importances = model.feature_importances_
feature_importance = dict(
    sorted(
        zip(FEATURE_COLUMNS, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )
)

print(f"\n{'-'*60}")
print(f"  FEATURE IMPORTANCE RANKING")
print(f"{'-'*60}")
for rank, (feat, imp) in enumerate(feature_importance.items(), 1):
    bar = "#" * int(imp * 60)
    print(f"  {rank:>2}. {feat:<35} {imp:.4f}  {bar}")

# ---------------------------------------------------------------------------
# 7. Save model and metrics
# ---------------------------------------------------------------------------
joblib.dump(model, MODEL_FILE)
print(f"\n  [OK] Model saved -> {MODEL_FILE}")

metrics = {
    "dataset": DATA_FILE,
    "n_samples": len(data),
    "n_features": len(FEATURE_COLUMNS),
    "features": FEATURE_COLUMNS,
    "n_estimators": model.n_estimators,
    "max_depth": model.max_depth,
    "test_set": {
        "accuracy":  round(accuracy,  4),
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "roc_auc":   round(auc,       4),
        "confusion_matrix": cm,
    },
    "cross_validation_5fold": {
        metric: {
            "mean": round(float(cv_results[f"test_{metric}"].mean()), 4),
            "std":  round(float(cv_results[f"test_{metric}"].std()),  4),
        }
        for metric in ["accuracy", "precision", "recall", "f1", "roc_auc"]
    },
    "feature_importance": {k: round(v, 6) for k, v in feature_importance.items()},
}

with open("model_metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)
print(f"  [OK] Metrics saved -> model_metrics.json")

with open("feature_importance.json", "w") as f:
    json.dump(feature_importance, f, indent=2)
print(f"  [OK] Feature importance saved -> feature_importance.json")
print(f"\n{'='*60}\n")
