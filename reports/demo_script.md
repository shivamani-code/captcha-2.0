# SwipeTCHA — Mentor Demo Script

**Estimated time:** 8–12 minutes  
**Prerequisites:** Backend running locally, browser open to `index.html`

---

## Before You Start

```bash
# 1. Start the backend
cd swipecha/smartcaptcha/backend
uvicorn app:main --reload --port 8000

# 2. Open the frontend in browser
# Open: swipecha/index.html (or http://localhost:5500 if using Live Server)
```

Confirm the backend is alive:
```
GET http://localhost:8000/
→ {"status": "backend alive", "model_loaded": true, "features": [...10 features...]}
```

---

## Demo Flow

### 🎤 Opening (30 seconds)

> "SwipeTCHA is a next-generation CAPTCHA system that detects bots by analysing how people actually move their mouse — not by asking them to identify blurry images. Let me show you how it works."

---

### Step 1: Show the CAPTCHA Widget (1 minute)

**Do:** Open the browser, show the SwipeTCHA widget on the page.

**Say:**
> "This is our CAPTCHA widget. When the page loads, it automatically requests a unique challenge token from the backend. That token expires in 5 minutes and can only be used once — this prevents replay attacks where someone tries to reuse an old verification."

**Point to the slider/swipe area.**

> "The user simply swipes or interacts with this element. Behind the scenes, we're recording 10 behavioral signals as they move their mouse."

---

### Step 2: Perform a Human Swipe (1 minute)

**Do:** Perform a natural, slightly curved swipe gesture on the widget.

**Say:**
> "Watch what happens when I swipe naturally..."

**Result:** ✅ Green checkmark / "Human verified" message appears

> "The system accepted my input with high confidence. Let me show you what data was collected."

**Open browser DevTools → Network tab → click the `/verify` request → show Payload:**

```json
{
  "challenge_id": "a3f2...",
  "avg_mouse_speed": 0.47,
  "mouse_path_entropy": 0.71,
  "micro_jitter_variance": 0.52,
  "acceleration_curve": 0.63,
  ...
}
```

> "The backend received all 10 features along with the challenge token. It ran those through our Random Forest model — 200 decision trees — and returned a prediction."

**Show the response:**
```json
{
  "prediction": "Human",
  "confidence": 0.9842,
  "gate": "ml"
}
```

---

### Step 3: Explain the ML Model (2 minutes)

**Say:**
> "Our model was trained on a merged dataset of 6,366 labelled examples: synthetic human patterns, real human recordings, and simulated bot profiles."

**Open `model_metrics.json` or read from the validation report:**

> "The model achieves:"

| Metric | Score |
|---|---|
| Accuracy | 99.50% |
| Precision | 99.64% |
| Recall | 99.40% |
| F1 Score | 99.52% |
| ROC-AUC | 99.99% |

> "5-fold cross-validation shows consistent performance with very low variance — so this isn't just overfitting to one test split."

**Show feature importance:**

> "The most important features are `acceleration_curve` at 28.75%, `mouse_path_entropy` at 15.7%, and `micro_jitter_variance` at 13%. These all measure natural human imperfection in movement — tremors, slight corrections, irregular timing — that bots simply can't fake convincingly."

---

### Step 4: Show Bot Rejection (1 minute)

**Open browser DevTools → Console tab and paste:**

```javascript
// Simulate a bot attempt
fetch('http://localhost:8000/challenge')
  .then(r => r.json())
  .then(({challenge_id}) =>
    fetch('http://localhost:8000/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        challenge_id,
        avg_mouse_speed: 2.8,
        mouse_path_entropy: 0.04,
        click_delay: 0.01,
        task_completion_time: 0.3,
        idle_time: 0.0,
        micro_jitter_variance: 0.01,
        acceleration_curve: 0.02,
        curvature_variance: 0.01,
        overshoot_correction_ratio: 0.0,
        timing_entropy: 0.02
      })
    })
  )
  .then(r => r.json())
  .then(console.log);
```

**Expected result:**
```json
{
  "prediction": "Bot",
  "confidence": 1.0,
  "gate": "hard_rule"
}
```

**Say:**
> "The system immediately identified this as a bot — and notice the `gate` field says `hard_rule`. Before even running the ML model, we apply a deterministic rule that catches the most obvious automation: unrealistically fast speed, zero entropy path, instant clicks, no jitter. All 6 must be true simultaneously to avoid false positives."

---

### Step 5: Show Security System (1 minute)

**Paste in DevTools console:**

```javascript
// Try to verify without a challenge ID
fetch('http://localhost:8000/verify', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({avg_mouse_speed: 0.5})
}).then(r => r.json()).then(console.log);
```

**Result:** `{"detail": "Missing challenge_id"}` (HTTP 400)

```javascript
// Try with a fake challenge ID
fetch('http://localhost:8000/verify', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({challenge_id: 'fakeid123', avg_mouse_speed: 0.5})
}).then(r => r.json()).then(console.log);
```

**Result:** `{"detail": "Invalid or expired challenge_id"}` (HTTP 403)

**Say:**
> "Direct API calls without a valid challenge token are rejected. This means attackers can't just call `/verify` directly with fabricated feature values — they need a real, non-expired, non-reused token from the CAPTCHA flow. It's simple but effective."

---

### Step 6: Show the Automated Test Results (1 minute)

**Open `reports/validation_report.md` in the browser or a markdown viewer.**

**Say:**
> "We also ran a full automated stress test — 15 human-like attempts and 15 bot-like attempts. Every single human was accepted, every single bot was rejected. All 4 security scenarios also passed."

**Show the summary table:**

| Type | Attempts | Accepted | Rejected |
|---|---|---|---|
| Human-like | 15 | 15 | 0 |
| Bot-like | 15 | 0 | 15 |

---

### 🎤 Closing (30 seconds)

> "SwipeTCHA combines three layers of protection: a challenge-token system to prevent direct API abuse, a deterministic rule to catch obvious bots instantly, and a 99.5%-accurate machine learning model for everything in between. The full pipeline — from mouse movement to classification — happens in real time with no user friction beyond a simple swipe."

---

## Q&A Preparation

**Q: What if someone trains their own ML model to mimic human movements?**
> The system can be retrained with new examples — including samples of the adversarial bot — improving resistance over time. The `merge_data.py` script makes this straightforward.

**Q: Why Random Forest instead of a neural network?**
> Random Forest is highly interpretable (we can see feature importance), trains in seconds, requires no GPU, and achieves near-perfect accuracy on this dataset. Neural networks would add complexity without meaningful benefit here.

**Q: Is the in-memory challenge store production-ready?**
> For a demonstration and local deployment, yes. For production at scale, you'd replace the dictionary with Redis or a similar fast cache. The interface and logic would remain identical.

**Q: What data was used to train the model?**
> 6,366 samples from three sources: programmatically generated synthetic human patterns with realistic noise, recorded human interaction data, and simulated bot profiles. The merge script de-duplicates rows and balances classes.

**Q: Could a bot just slow down to fool the model?**
> The `mouse_path_entropy`, `micro_jitter_variance`, and `curvature_variance` features measure the *texture* of movement, not just speed. A slow bot still moves in perfectly straight lines with no tremor — those features expose it.

---

## Files for Mentor Review

| File | Purpose |
|---|---|
| `reports/validation_report.md` | Complete metrics + test results |
| `reports/stress_results.json` | Raw stress test output |
| `smartcaptcha/ml/model_metrics.json` | Full model evaluation |
| `smartcaptcha/ml/feature_importance.json` | Feature importance scores |
| `smartcaptcha/backend/app.py` | Backend with security + ML |
| `smartcaptcha/ml/train_model.py` | Model training pipeline |
| `smartcaptcha.js` | Frontend behavioral analytics |
