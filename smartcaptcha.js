(function () {
  const root = document.getElementById('smartcaptcha-root') || document.getElementById('slider');
  const statusEl = document.getElementById('smartcaptcha-status') || document.getElementById('result');
  const resetBtn = document.getElementById('smartcaptcha-reset');
  const VERIFY_ENDPOINT = 'http://localhost:8000/verify';
  const CHALLENGE_ENDPOINT = 'http://localhost:8000/challenge';
  const FEATURE_COLUMNS = [
    'avg_mouse_speed',
    'mouse_path_entropy',
    'click_delay',
    'task_completion_time',
    'idle_time',
    'micro_jitter_variance',
    'acceleration_curve',
    'curvature_variance',
    'overshoot_correction_ratio',
    'timing_entropy',
  ];

  function setStatus(text) {
    if (!statusEl) return;
    statusEl.textContent = text;
  }

  function nowMs() {
    return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
  }

  function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
  }

  function randInt(min, max) {
    const a = Math.ceil(min);
    const b = Math.floor(max);
    return Math.floor(a + Math.random() * (b - a + 1));
  }

  function randFloat(min, max) {
    return min + (max - min) * Math.random();
  }

  function sampleOne(values) {
    return values[randInt(0, values.length - 1)];
  }

  // SAFE HARDENING (F): precompute timing noise once per page load (no randomness during drag)
  function createTimingNoiseSeq(len, minMs, maxMs) {
    const seq = new Int16Array(len);
    for (let i = 0; i < seq.length; i++) {
      const sign = Math.random() < 0.5 ? -1 : 1;
      seq[i] = sign * randInt(minMs, maxMs);
    }
    return seq;
  }

  function createNoisyNowMs(config, noiseSeq) {
    let lastReported = nowMs();
    let idx = 0;
    const mask = (noiseSeq.length - 1);
    return function noisyNowMs() {
      const base = nowMs();

      const jitter = noiseSeq[idx & mask];
      idx = (idx + 1) | 0;
      const candidate = base + jitter;

      const minStepMs = 8;
      const maxStepMs = 250;

      const next = Math.max(lastReported + minStepMs, Math.min(candidate, lastReported + maxStepMs));
      lastReported = next;
      return next;
    };
  }

  const sessionConfig = Object.freeze({
    // SAFE HARDENING (A): continuous width randomization, applied once per page load.
    // We compute the final px width after the track is rendered (needs CSS layout), using this precomputed U.
    trackWidthU: randFloat(0, 1),
    trackWidthMinPx: 300,
    trackWidthMaxPxCap: 700,
    // SAFE HARDENING (E): hidden logical offset, does not move the thumb visually
    startBiasPx: (Math.random() < 0.5 ? -1 : 1) * randInt(5, 15),
    // SAFE HARDENING (D): continuous threshold space, fixed per load
    completionFactor: randFloat(0.90, 0.99),
    // SAFE HARDENING (B): drift tolerance (used only for internal scoring)
    driftTolPx: randFloat(6, 10),
    driftMinSpanPx: randFloat(0.8, 1.8),
    microDevRatioMin: randFloat(0.02, 0.06),
    angleChangeMinRad: randFloat(0.0015, 0.0065),
    entropyMin: randFloat(0.015, 0.055),
    flatDyEpsPx: randFloat(0.12, 0.42),
    signChangeMax: randInt(0, 1),
    flatDyRatioMin: randFloat(0.85, 0.97),
    patternVariant: randInt(0, 5),
    // SAFE MODE MULTI-SHAPE (logical only): chosen once per page load
    shapeMode: sampleOne(['straight', 'upward', 'downward', 'curve']),
    shapeYOffsetPx: randFloat(6, 12),
    shapeTolerancePx: randFloat(8, 14),
    // SAFE HARDENING (F): timing noise bounds
    timingNoiseMinMs: 40,
    timingNoiseMaxMs: 120,
  });

  const timingNoiseSeq = createTimingNoiseSeq(4096, sessionConfig.timingNoiseMinMs, sessionConfig.timingNoiseMaxMs);
  const noisyNowMs = createNoisyNowMs(sessionConfig, timingNoiseSeq);

  function snapshotPointerEvent(evt) {
    if (evt.touches && evt.touches.length) {
      return { clientX: evt.touches[0].clientX, clientY: evt.touches[0].clientY };
    }
    if (evt.changedTouches && evt.changedTouches.length) {
      return { clientX: evt.changedTouches[0].clientX, clientY: evt.changedTouches[0].clientY };
    }
    return { clientX: evt.clientX, clientY: evt.clientY };
  }

  function getClientX(evt) {
    if (evt.touches && evt.touches.length) return evt.touches[0].clientX;
    if (evt.changedTouches && evt.changedTouches.length) return evt.changedTouches[0].clientX;
    return evt.clientX;
  }

  function safeDivide(n, d) {
    if (!Number.isFinite(n) || !Number.isFinite(d) || d === 0) return 0;
    return n / d;
  }

  function mean(values) {
    if (!values.length) return 0;
    let s = 0;
    for (const v of values) s += v;
    return s / values.length;
  }

  function variance(values) {
    if (values.length < 2) return 0;
    const m = mean(values);
    let s = 0;
    for (const v of values) {
      const d = v - m;
      s += d * d;
    }
    return s / (values.length - 1);
  }

  function shannonEntropy(probs) {
    let h = 0;
    for (const p of probs) {
      if (p <= 0) continue;
      h -= p * Math.log2(p);
    }
    return h;
  }

  function normalizeEntropyBits(hBits, binCount) {
    if (binCount <= 1) return 0;
    const max = Math.log2(binCount);
    return safeDivide(hBits, max);
  }

  function buildVerifyPayload(features) {
    const payload = {};
    for (const key of FEATURE_COLUMNS) {
      const v = features && Object.prototype.hasOwnProperty.call(features, key) ? features[key] : 0;
      payload[key] = Number.isFinite(v) ? v : 0;
    }
    return payload;
  }

  function computeFeatures(session) {
    const events = Array.isArray(session?.events) ? session.events : [];
    const moveEvents = events.filter((e) => e && e.type === 'move' && Number.isFinite(e.t_ms));
    if (moveEvents.length < 3) {
      return null;
    }

    // SAFE HARDENING (B/C): capture slight y-drift and micro deviation stats (no curve/geometry)
    const y0 = moveEvents[0].y;
    let yMin = y0;
    let yMax = y0;
    let yWithinTolCount = 0;
    let microYMoveCount = 0;
    let absDySum = 0;

    function getExpectedYOffset(xProgress) {
      if (sessionConfig.shapeMode === 'upward') return xProgress * sessionConfig.shapeYOffsetPx;
      if (sessionConfig.shapeMode === 'downward') return -xProgress * sessionConfig.shapeYOffsetPx;
      if (sessionConfig.shapeMode === 'curve') return Math.sin(xProgress * Math.PI) * sessionConfig.shapeYOffsetPx;
      return 0;
    }

    const click_delay = safeDivide(
      (session.interaction_started_at_ms ?? 0) - (session.widget_shown_at_ms ?? 0),
      1000
    );
    const task_completion_time = safeDivide(
      (session.interaction_ended_at_ms ?? 0) - (session.interaction_started_at_ms ?? 0),
      1000
    );

    let totalDistance = 0;
    let totalTime = 0;

    let dxSum = 0;
    let dySum = 0;

    const segmentSpeeds = [];
    const segmentDt = [];
    const dxList = [];
    const dyList = [];
    const angles = [];
    const dySigns = [];

    for (let i = 1; i < moveEvents.length; i++) {
      const a = moveEvents[i - 1];
      const b = moveEvents[i];
      const dtMs = b.t_ms - a.t_ms;
      if (!Number.isFinite(dtMs) || dtMs <= 0) continue;

      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.hypot(dx, dy);

      yMin = Math.min(yMin, b.y);
      yMax = Math.max(yMax, b.y);
      if (Math.abs(b.y - y0) <= sessionConfig.driftTolPx) yWithinTolCount += 1;
      absDySum += Math.abs(dy);
      if (Math.abs(dy) >= 0.35) microYMoveCount += 1;

      dxSum += dx;
      dySum += dy;

      totalDistance += dist;
      totalTime += dtMs;

      const speed = dist / (dtMs / 1000);
      segmentSpeeds.push(speed);
      segmentDt.push(dtMs);
      dxList.push(dx);
      dyList.push(dy);

      if (Math.abs(dy) >= sessionConfig.flatDyEpsPx) dySigns.push(dy > 0 ? 1 : -1);

      angles.push(Math.atan2(dy, dx));
    }

    const avg_mouse_speed = safeDivide(totalDistance, totalTime / 1000);

    const idleGapThresholdMs = 120;
    let idle_time_ms = 0;
    let micro_pause_count = 0;
    for (let i = 1; i < moveEvents.length; i++) {
      const dtMs = moveEvents[i].t_ms - moveEvents[i - 1].t_ms;
      if (dtMs > idleGapThresholdMs) idle_time_ms += dtMs;
      if (dtMs >= 80 && dtMs <= 240) micro_pause_count += 1;
    }
    const idle_time = idle_time_ms / 1000;

    const directionBins = 12;
    const directionCounts = new Array(directionBins).fill(0);
    for (const a of angles) {
      const normalized = (a + Math.PI) / (2 * Math.PI);
      const idx = Math.min(directionBins - 1, Math.max(0, Math.floor(normalized * directionBins)));
      directionCounts[idx] += 1;
    }
    const directionTotal = directionCounts.reduce((s, c) => s + c, 0);
    const directionProbs = directionCounts.map((c) => safeDivide(c, directionTotal));
    const mouse_path_entropy = normalizeEntropyBits(shannonEntropy(directionProbs), directionBins);

    let xMin = moveEvents[0].x;
    let xMax = moveEvents[0].x;
    for (const e of moveEvents) {
      if (e.x < xMin) xMin = e.x;
      if (e.x > xMax) xMax = e.x;
    }
    const xSpan = Math.max(1, xMax - xMin);

    let devSum = 0;
    let devSqSum = 0;
    let devCount = 0;
    for (const e of moveEvents) {
      const xp = clamp(safeDivide(e.x - xMin, xSpan), 0, 1);
      const expectedY = y0 + getExpectedYOffset(xp);
      const dev = Math.abs(e.y - expectedY);
      devSum += dev;
      devSqSum += dev * dev;
      devCount += 1;
    }
    const path_deviation_mean_px = safeDivide(devSum, devCount);
    const meanSq = safeDivide(devSqSum, devCount);
    const path_deviation_std_px = Math.sqrt(Math.max(0, meanSq - path_deviation_mean_px * path_deviation_mean_px));

    let flatDyCount = 0;
    for (const dy of dyList) {
      if (Math.abs(dy) < sessionConfig.flatDyEpsPx) flatDyCount += 1;
    }
    const flat_dy_ratio = safeDivide(flatDyCount, Math.max(1, dyList.length));

    let dySignChanges = 0;
    for (let i = 1; i < dySigns.length; i++) {
      if (dySigns[i] !== dySigns[i - 1]) dySignChanges += 1;
    }

    let angleChangeAbsSum = 0;
    for (let i = 1; i < angles.length; i++) {
      const da = angles[i] - angles[i - 1];
      const wrapped = Math.atan2(Math.sin(da), Math.cos(da));
      angleChangeAbsSum += Math.abs(wrapped);
    }
    const angle_change_mean = safeDivide(angleChangeAbsSum, Math.max(1, angles.length - 1));

    const micro_jitter_variance = variance(dxList) + variance(dyList);

    const speed_variance = variance(segmentSpeeds);
    const speed_mean = mean(segmentSpeeds);
    const speed_cv = safeDivide(Math.sqrt(speed_variance), speed_mean);

    const accelerationsAbs = [];
    for (let i = 1; i < segmentSpeeds.length; i++) {
      const dv = segmentSpeeds[i] - segmentSpeeds[i - 1];
      const dtS = (segmentDt[i] ?? 0) / 1000;
      if (!Number.isFinite(dtS) || dtS <= 0) continue;
      accelerationsAbs.push(Math.abs(dv / dtS));
    }
    const acceleration_curve = mean(accelerationsAbs);

    const curvatures = [];
    for (let i = 1; i < angles.length; i++) {
      const da = angles[i] - angles[i - 1];
      const wrapped = Math.atan2(Math.sin(da), Math.cos(da));
      const segLen = Math.hypot(dxList[i] ?? 0, dyList[i] ?? 0);
      if (segLen <= 0) continue;
      curvatures.push(Math.abs(wrapped) / segLen);
    }
    const curvature_variance = variance(curvatures);

    let forward = 0;
    let backward = 0;
    for (const dx of dxList) {
      if (dx >= 0) forward += dx;
      else backward += Math.abs(dx);
    }
    const overshoot_correction_ratio = safeDivide(backward, forward);

    const timingBins = 10;
    const timingCounts = new Array(timingBins).fill(0);
    const dtValues = [];
    for (const dtMs of segmentDt) {
      if (Number.isFinite(dtMs) && dtMs > 0) dtValues.push(dtMs);
    }
    let timing_entropy = 0;
    if (dtValues.length) {
      const minDt = Math.min(...dtValues);
      const maxDt = Math.max(...dtValues);
      const range = maxDt - minDt;
      for (const dtMs of dtValues) {
        const normalized = range > 0 ? (dtMs - minDt) / range : 0;
        const idx = Math.min(timingBins - 1, Math.max(0, Math.floor(normalized * timingBins)));
        timingCounts[idx] += 1;
      }
      const timingTotal = timingCounts.reduce((s, c) => s + c, 0);
      const timingProbs = timingCounts.map((c) => safeDivide(c, timingTotal));
      timing_entropy = normalizeEntropyBits(shannonEntropy(timingProbs), timingBins);
    }

    const featureVector = {
      avg_mouse_speed,
      mouse_path_entropy,
      click_delay,
      task_completion_time,
      idle_time,
      micro_jitter_variance,
      acceleration_curve,
      curvature_variance,
      overshoot_correction_ratio,
      timing_entropy,
      micro_pause_ratio: safeDivide(micro_pause_count, segmentDt.length),
      speed_cv,
      straightness_ratio: safeDivide(totalDistance, Math.hypot(dxSum, dySum)),
      // SAFE HARDENING (B/C): internal-only (not sent to backend)
      y_span_px: yMax - yMin,
      y_micro_dev_ratio: safeDivide(microYMoveCount, segmentDt.length),
      y_abs_dy_mean: safeDivide(absDySum, segmentDt.length),
      y_within_tol_ratio: safeDivide(yWithinTolCount, Math.max(1, moveEvents.length - 1)),
      angle_change_mean,
      flat_dy_ratio,
      dy_sign_change_count: dySignChanges,
      path_deviation_mean_px,
      path_deviation_std_px,
    };

    return featureVector;
  }

  async function verifyWithBackend(features, challengeId) {
    const payload = buildVerifyPayload(features);
    payload.challenge_id = challengeId;
    const res = await fetch(VERIFY_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Verify failed (${res.status}): ${text}`);
    }

    return res.json();
  }

  function render() {
    if (!root) return;
    root.innerHTML = '';

    const widget = document.createElement('section');
    widget.className = 'sc-widget';
    widget.setAttribute('role', 'group');
    widget.setAttribute('aria-label', 'SmartCAPTCHA slider');

    const label = document.createElement('div');
    label.className = 'sc-label';
    label.textContent = 'Slide to verify';

    const track = document.createElement('div');
    track.className = 'sc-track';
    track.setAttribute('role', 'presentation');

    const fill = document.createElement('div');
    fill.className = 'sc-fill';

    const handle = document.createElement('button');
    handle.type = 'button';
    handle.className = 'sc-handle';
    handle.setAttribute('aria-label', 'Drag slider');

    track.appendChild(fill);
    track.appendChild(handle);
    widget.appendChild(label);
    widget.appendChild(track);
    root.appendChild(widget);

    const baseTrackWidth = track.getBoundingClientRect().width;
    if (Number.isFinite(baseTrackWidth) && baseTrackWidth > 0) {
      const maxW = Math.min(baseTrackWidth, sessionConfig.trackWidthMaxPxCap);
      const minW = Math.min(maxW, sessionConfig.trackWidthMinPx);
      const targetWidth = minW + (sessionConfig.trackWidthU * (maxW - minW));
      track.style.width = `${Math.round(targetWidth)}px`;
    }

    const session = {
      widget_shown_at_ms: noisyNowMs(),
      interaction_started_at_ms: null,
      interaction_ended_at_ms: null,
      events: [],
    };

    window.__smartcaptcha_session = session;

    function toLocalPoint(evt) {
      const trackRect = track.getBoundingClientRect();
      const x = getClientX(evt) - trackRect.left;
      let y;
      if (evt.touches && evt.touches.length) y = evt.touches[0].clientY - trackRect.top;
      else if (evt.changedTouches && evt.changedTouches.length) y = evt.changedTouches[0].clientY - trackRect.top;
      else y = evt.clientY - trackRect.top;
      return {
        x,
        y,
      };
    }

    function recordEvent(evtType, evt) {
      const p = toLocalPoint(evt);
      session.events.push({
        type: evtType,
        t_ms: noisyNowMs(),
        x: p.x,
        y: p.y,
      });
    }

    const state = {
      dragging: false,
      verified: false,
      startX: 0,
      currentX: 0,
      maxX: 0,
      minX: 0,
      startOffsetPx: 0,
      interactionDelayMs: 0,
      pointerDown: false,
      beginTimerId: 0,
      pendingBeginEvt: null,
      rafId: 0,
      needsRender: false,
      challengeId: null,
    };

    fetch(CHALLENGE_ENDPOINT)
      .then(res => res.json())
      .then(data => {
        state.challengeId = data.challenge_id;
      })
      .catch(err => {
        console.error('Failed to fetch challenge ID:', err);
      });

    state.minX = state.startOffsetPx;
    state.currentX = state.minX;

    function measure() {
      const trackRect = track.getBoundingClientRect();
      const handleRect = handle.getBoundingClientRect();
      const baseMaxX = Math.max(0, trackRect.width - handleRect.width - 6);
      state.maxX = Math.max(state.minX, baseMaxX);
      state.currentX = clamp(state.currentX, state.minX, state.maxX);
      requestFrame();
    }

    function setPosition(x) {
      state.currentX = clamp(x, state.minX, state.maxX);
      requestFrame();
    }

    function requestFrame() {
      state.needsRender = true;
      if (state.rafId) return;
      state.rafId = window.requestAnimationFrame(renderFrame);
    }

    function renderFrame() {
      state.rafId = 0;
      if (!state.needsRender) return;
      state.needsRender = false;
      handle.style.transform = `translate(${state.currentX}px, 0px)`;
      fill.style.width = `${state.currentX + 26}px`;
    }

    function isComplete() {
      if (state.maxX <= 0) return false;
      const effectiveX = clamp(state.currentX - sessionConfig.startBiasPx, state.minX, state.maxX);
      return effectiveX >= state.maxX * sessionConfig.completionFactor;
    }

    function animateBack() {
      handle.classList.add('sc-handle--animate');
      fill.classList.add('sc-fill--animate');
      setPosition(state.minX);
      window.setTimeout(() => {
        handle.classList.remove('sc-handle--animate');
        fill.classList.remove('sc-fill--animate');
      }, 220);
    }

    function frontendLooksBotLike(features) {
      if (!features) return true;
      const fast = features.task_completion_time > 0 && features.task_completion_time < 0.25;
      const tooRegularTiming = features.timing_entropy < 0.04;
      const tooLowJitter = features.micro_jitter_variance < 0.15;
      const tooConstantSpeed = features.speed_cv < 0.02;
      const tooStraight = features.straightness_ratio > 1.02;
      const ySpan = Number.isFinite(features.y_span_px) ? features.y_span_px : 0;
      const yMicroRatio = Number.isFinite(features.y_micro_dev_ratio) ? features.y_micro_dev_ratio : 0;
      const tooFlat = ySpan <= sessionConfig.driftMinSpanPx && yMicroRatio <= sessionConfig.microDevRatioMin;
      const angleMean = Number.isFinite(features.angle_change_mean) ? features.angle_change_mean : 0;
      const lowEntropy = features.mouse_path_entropy >= 0 && features.mouse_path_entropy < sessionConfig.entropyMin;
      const flatDyRatio = Number.isFinite(features.flat_dy_ratio) ? features.flat_dy_ratio : 1;
      const dySignChanges = Number.isFinite(features.dy_sign_change_count) ? features.dy_sign_change_count : 0;

      const tooFlatDy = flatDyRatio >= sessionConfig.flatDyRatioMin;
      const tooFewTurns = dySignChanges <= sessionConfig.signChangeMax;

      const devMean = Number.isFinite(features.path_deviation_mean_px) ? features.path_deviation_mean_px : 0;
      const devStd = Number.isFinite(features.path_deviation_std_px) ? features.path_deviation_std_px : 0;
      const shapeMismatch = (sessionConfig.shapeMode !== 'straight') && (devMean > sessionConfig.shapeTolerancePx);
      const shapeTooPerfect = (sessionConfig.shapeMode !== 'straight') && (devStd < 0.65);

      let variantFlag = false;
      if (sessionConfig.patternVariant === 0) variantFlag = tooFlat;
      else if (sessionConfig.patternVariant === 1) variantFlag = tooFlat && angleMean <= sessionConfig.angleChangeMinRad;
      else if (sessionConfig.patternVariant === 2) variantFlag = tooFlat && lowEntropy;
      else if (sessionConfig.patternVariant === 3) variantFlag = tooFlatDy && tooFewTurns;
      else if (sessionConfig.patternVariant === 4) variantFlag = (tooFlatDy && tooFewTurns) && (angleMean <= sessionConfig.angleChangeMinRad);
      else variantFlag = (tooFlatDy && tooFewTurns) && lowEntropy;
      if ((tooRegularTiming && tooLowJitter && tooConstantSpeed) || (fast && tooRegularTiming && tooStraight)) {
        return true;
      }
      if (variantFlag && (tooRegularTiming || tooLowJitter) && (tooConstantSpeed || tooStraight)) {
        return true;
      }
      if (shapeMismatch && (tooRegularTiming || tooLowJitter) && (tooConstantSpeed || tooStraight)) {
        return true;
      }
      if (shapeTooPerfect && tooFlatDy && (tooRegularTiming || tooLowJitter) && (tooConstantSpeed || tooStraight)) {
        return true;
      }
      return false;
    }

    function beginDrag(evt) {
      if (state.verified) return;

      if (session.interaction_started_at_ms === null) {
        session.interaction_started_at_ms = noisyNowMs();
      }
      recordEvent('down', evt);

      state.dragging = true;
      handle.classList.add('sc-handle--active');
      track.classList.add('sc-track--active');

      const handleRect = handle.getBoundingClientRect();
      state.startX = getClientX(evt) - handleRect.left;
      setStatus('');
    }

    function scheduleBeginDrag(evt) {
      if (state.verified) return;
      if (state.dragging) return;
      if (state.beginTimerId) {
        window.clearTimeout(state.beginTimerId);
        state.beginTimerId = 0;
      }

      state.pointerDown = true;
      state.pendingBeginEvt = snapshotPointerEvent(evt);
      const delayMs = state.interactionDelayMs;
      if (delayMs <= 0) {
        beginDrag(state.pendingBeginEvt);
        return;
      }

      state.beginTimerId = window.setTimeout(() => {
        state.beginTimerId = 0;
        if (!state.pointerDown || state.verified) return;
        beginDrag(state.pendingBeginEvt);
      }, delayMs);
    }

    function moveDrag(evt) {
      if (!state.dragging || state.verified) return;
      recordEvent('move', evt);
      const trackRect = track.getBoundingClientRect();
      const x = getClientX(evt) - trackRect.left - state.startX;
      setPosition(x);
    }

    function endDrag(evt) {
      if (!state.dragging) return;

      session.interaction_ended_at_ms = noisyNowMs();
      if (evt) {
        recordEvent('up', evt);
      }

      state.dragging = false;
      handle.classList.remove('sc-handle--active');
      track.classList.remove('sc-track--active');

      if (isComplete()) {
        state.verified = true;
        handle.disabled = true;
        widget.classList.add('sc-widget--verified');
        setPosition(state.maxX);
        const features = computeFeatures(session);
        window.__smartcaptcha_features = features;
        if (!features) {
          setStatus('Slider completed, but not enough movement data to compute features.');
          return;
        }

        if (frontendLooksBotLike(features)) {
          setStatus('Verification failed. Try again.');
          window.setTimeout(() => {
            render();
            setStatus('Try again.');
          }, 250);
          return;
        }

        if (!state.challengeId) {
          setStatus('Verification error: Challenge ID not loaded yet. Try again.');
          window.setTimeout(() => {
            render();
          }, 1000);
          return;
        }

        setStatus('Verifying...');
        verifyWithBackend(features, state.challengeId)
          .then((result) => {
            const decision = (result && (result.prediction ?? result.decision ?? result.status)) || '';
            const confidence = (result && result.confidence !== undefined) ? (result.confidence * 100).toFixed(2) + '%' : 'N/A';
            if (decision.toLowerCase() === 'human') {
              setStatus(`Verified: Human (Confidence: ${confidence})`);
              return;
            }

            setStatus(`Verification failed. Bot detected (Confidence: ${confidence}). Try again.`);
            window.setTimeout(() => {
              render();
              setStatus('Try again.');
            }, 2000);
          })
          .catch((err) => {
            setStatus(`Verification error: ${err.message}`);
            window.setTimeout(() => {
              render();
            }, 250);
          });
      } else {
        animateBack();
        const features = computeFeatures(session);
        window.__smartcaptcha_features = features;
        setStatus('Try again.');
      }
    }

    function onMouseDown(evt) {
      evt.preventDefault();
      scheduleBeginDrag(evt);
      window.addEventListener('mousemove', onMouseMove, { passive: false });
      window.addEventListener('mouseup', onMouseUp, { passive: true });
    }

    function onMouseMove(evt) {
      evt.preventDefault();
      moveDrag(evt);
    }

    function onMouseUp(evt) {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      state.pointerDown = false;
      if (!state.dragging && state.beginTimerId) {
        window.clearTimeout(state.beginTimerId);
        state.beginTimerId = 0;
      }
      endDrag(evt);
    }

    function onTouchStart(evt) {
      scheduleBeginDrag(evt);
      window.addEventListener('touchmove', onTouchMove, { passive: false });
      window.addEventListener('touchend', onTouchEnd, { passive: true });
      window.addEventListener('touchcancel', onTouchEnd, { passive: true });
    }

    function onTouchMove(evt) {
      evt.preventDefault();
      moveDrag(evt);
    }

    function onTouchEnd(evt) {
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
      window.removeEventListener('touchcancel', onTouchEnd);
      state.pointerDown = false;
      if (!state.dragging && state.beginTimerId) {
        window.clearTimeout(state.beginTimerId);
        state.beginTimerId = 0;
      }
      endDrag(evt);
    }

    handle.addEventListener('mousedown', onMouseDown);
    handle.addEventListener('touchstart', onTouchStart, { passive: true });

    window.addEventListener('resize', measure);
    measure();
    setStatus('');
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      window.__smartcaptcha_session = undefined;
      window.__smartcaptcha_features = undefined;
      setStatus('');
      render();
    });
  }

  render();
})();
