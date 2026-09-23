/* =============================================================================
   IQ TEST BOT — app.js
   Part A: WebApp init, API wrapper, Home, Profile, IQ test engine, offline
   ============================================================================= */
(function () {
"use strict";

/* ---------- Telegram WebApp ---------- */
const TG = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
const INIT_DATA = TG && TG.initData ? TG.initData : "";

if (TG) {
  try {
    TG.ready();
    TG.expand();
    if (TG.setHeaderColor) TG.setHeaderColor("#0a0e1a");
    if (TG.setBackgroundColor) TG.setBackgroundColor("#0a0e1a");
  } catch (e) { /* noop */ }
}

/* ---------- DOM helpers ---------- */
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};
const show = (e) => { if (e) e.classList.remove("hidden"); };
const hide = (e) => { if (e) e.classList.add("hidden"); };
const qsAll = (sel, root) => Array.from((root || document).querySelectorAll(sel));

/* ---------- State ---------- */
const State = {
  screen: "home",
  history: [],
  user: null,
  unlocked: { iq: true, eq: false, pq: false, personal: false },
  currentTest: null,
  currentQuestionIndex: 0,
  answers: {},
  testStartTime: 0,
  sessionId: null,
  sessionType: null,
  submitting: false,
  liveTimer: null,
};

/* ---------- Toast ---------- */
function toast(msg, type, ms) {
  const root = $("toast-root");
  if (!root) return;
  const t = el("div", "toast " + (type || "info"), msg);
  root.appendChild(t);
  setTimeout(() => {
    t.style.opacity = "0";
    t.style.transform = "translateY(20px)";
    setTimeout(() => t.remove(), 250);
  }, ms || 2600);
}

/* ---------- Modal ---------- */
let modalResolve = null;
function modal(title, body, okText, cancelText) {
  return new Promise((resolve) => {
    modalResolve = resolve;
    $("modal-title").textContent = title || "";
    $("modal-body").textContent = body || "";
    $("modal-ok").textContent = okText || "OK";
    $("modal-cancel").textContent = cancelText || "Bekor";
    $("modal-cancel").style.display = cancelText === false ? "none" : "block";
    show($("modal-root"));
  });
}
document.addEventListener("click", (ev) => {
  const t = ev.target;
  if (t && t.dataset && t.dataset.closeModal) {
    hide($("modal-root"));
    if (modalResolve) { modalResolve(false); modalResolve = null; }
  }
});
$("modal-ok").addEventListener("click", () => {
  hide($("modal-root"));
  if (modalResolve) { modalResolve(true); modalResolve = null; }
});

/* ---------- Global loading ---------- */
let loadingCount = 0;
function loadingOn() {
  loadingCount++;
  show($("global-loading"));
}
function loadingOff() {
  loadingCount = Math.max(0, loadingCount - 1);
  if (loadingCount === 0) hide($("global-loading"));
}

/* ---------- API wrapper ---------- */
async function api(path, options) {
  const opts = Object.assign({}, options || {});
  opts.headers = Object.assign({}, opts.headers || {});
  if (INIT_DATA) {
    opts.headers["Authorization"] = "tma " + INIT_DATA;
  }
  if (opts.json !== undefined) {
    opts.method = opts.method || "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.json);
    delete opts.json;
  }
  const method = (opts.method || "GET").toUpperCase();
  opts.method = method;
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    const err = new Error("network");
    err.status = 0;
    throw err;
  }
  let data = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try { data = await res.json(); } catch (e) { data = null; }
  }
  if (!res.ok) {
    const err = new Error((data && (data.detail || data.message)) || ("HTTP " + res.status));
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data || {};
}

/* ---------- Screen navigation ---------- */
function showScreen(name, addHistory) {
  const prev = State.screen;
  qsAll(".screen").forEach((s) => s.classList.remove("active"));
  const target = $("screen-" + name);
  if (target) target.classList.add("active");
  State.screen = name;
  if (addHistory !== false && prev && prev !== name) {
    State.history.push(prev);
  }
  updateBackButton();
  if (name !== "test") stopLiveTimer();
}

function goBack() {
  const prev = State.history.pop();
  if (prev) {
    showScreen(prev, false);
  } else {
    showScreen("home", false);
  }
}
function updateBackButton() {
  const b = $("btn-back");
  if (!b) return;
  if (State.screen === "home") hide(b);
  else show(b);
}

/* ---------- Error screen ---------- */
function showErrorScreen(title, sub) {
  $("error-title").textContent = title || "Xatolik";
  $("error-sub").textContent = sub || "Qaytadan urinib ko'ring";
  showScreen("error");
}
$("error-retry").addEventListener("click", () => {
  showScreen("home", false);
});

/* ---------- Screens: HOME ---------- */
async function loadHome() {
  try {
    const me = await api("/api/profile/me", { method: "GET" });
    State.user = me.user || null;
    State.unlocked = Object.assign({ iq: true, eq: false, pq: false, personal: false }, me.unlocked || {});
    applyUnlocks();
  } catch (e) {
    // Even without auth, home is visible; unlocks stay default
  }
  startLiveTimer();
}

function applyUnlocks() {
  const map = {
    iq: $("card-iq"),
    eq: $("card-eq"),
    pq: $("card-pq"),
    personal: $("card-personal"),
  };
  const reasons = {
    eq: "🔒 IQ dan keyin ochiladi",
    pq: "🔒 EQ dan keyin ochiladi",
    personal: "🔒 IQ + EQ + PQ dan keyin",
  };
  Object.keys(map).forEach((key) => {
    const node = map[key];
    if (!node) return;
    const unlocked = !!State.unlocked[key];
    node.classList.toggle("locked", !unlocked);
    const lock = node.querySelector(".card-lock");
    if (!unlocked) {
      if (!lock) {
        const span = el("div", "card-lock", reasons[key] || "🔒");
        node.querySelector(".card-body").appendChild(span);
      }
    } else if (lock) {
      lock.remove();
    }
  });
}

/* Card click handlers */
qsAll(".cards-grid .card").forEach((card) => {
  card.addEventListener("click", async () => {
    const target = card.dataset.target;
    if (!target) return;
    if (card.classList.contains("locked")) {
      toast("Bu test hali ochilmagan", "info");
      return;
    }
    if (target === "iq" || target === "eq" || target === "pq") {
      await startTestFlow(target);
    } else if (target === "personal") {
      await openPersonal();
    } else if (target === "battle") {
      await openBattle();
    }
  });
});

/* ---------- PROFILE (before test) ---------- */
let pendingTestType = null;

async function startTestFlow(type) {
  // If user already completed this test -> straight result
  try {
    const r = await api("/api/result/me?type=" + encodeURIComponent(type), { method: "GET" });
    if (r && r.has_result && r.result_visible) {
      renderResult(r);
      showScreen("result");
      return;
    }
    if (r && r.has_result && !r.result_visible) {
      // pending payment
      await openPaymentForAttempt(r.attempt_id, type);
      return;
    }
  } catch (e) { /* continue */ }

  pendingTestType = type;
  // Prefill from saved profile
  if (State.user) {
    $("prof-fullname").value = State.user.full_name || "";
    if (State.user.gender) $("prof-gender").value = State.user.gender;
    if (State.user.age) $("prof-age").value = State.user.age;
    if (State.user.country) $("prof-country").value = State.user.country;
  }
  hide($("prof-error"));
  showScreen("profile");
}

$("prof-submit").addEventListener("click", async () => {
  const fullname = $("prof-fullname").value.trim();
  const gender = $("prof-gender").value;
  const age = parseInt($("prof-age").value, 10);
  const country = $("prof-country").value;

  const err = $("prof-error");
  const errors = [];
  if (fullname.length < 2) errors.push("Ism-familiyani kiriting");
  if (!gender) errors.push("Jinsni tanlang");
  if (!age || age < 5 || age > 120) errors.push("Yoshni to'g'ri kiriting");
  if (!country) errors.push("Davlatni tanlang");
  if (errors.length) {
    err.textContent = errors[0];
    show(err);
    return;
  }
  hide(err);

  const btn = $("prof-submit");
  btn.disabled = true;
  loadingOn();
  try {
    await api("/api/profile/save", {
      method: "POST",
      json: { full_name: fullname, gender, age, country },
    });
    State.user = Object.assign({}, State.user || {}, {
      full_name: fullname, gender, age, country,
    });
    await beginTest(pendingTestType);
  } catch (e) {
    toast("Saqlashda xatolik: " + (e.message || "network"), "error");
  } finally {
    loadingOff();
    btn.disabled = false;
  }
});

/* ---------- TEST START ---------- */
async function beginTest(type) {
  loadingOn();
  try {
    const r = await api("/api/test/start", { method: "POST", json: { type } });
    State.sessionId = r.session_id;
    State.sessionType = type;
    State.answers = {};
    State.currentQuestionIndex = 0;
    State.testStartTime = Date.now();

    // Restore progress if same session in localStorage
    const saved = loadProgress(r.session_id);
    if (saved && saved.type === type) {
      State.answers = saved.answers || {};
      State.currentQuestionIndex = Math.min(saved.index || 0, (r.questions || []).length - 1);
      if (saved.startedAt) State.testStartTime = saved.startedAt;
    }

    State.currentTest = {
      type,
      questions: r.questions || [],
      attempt_no: r.attempt_no || 1,
      price: r.price || 0,
    };

    if (State.currentTest.questions.length === 0) {
      toast("Savollar yuklanmadi", "error");
      showScreen("home");
      return;
    }

    if (type === "iq" && (!saved || State.currentQuestionIndex === 0)) {
      // Show sample first for IQ
      renderSample();
      showScreen("sample");
    } else {
      renderQuestion();
      showScreen("test");
    }
  } catch (e) {
    if (e.status === 403) {
      toast("Avval oldingi testni yakunlang", "error");
    } else {
      toast("Testni boshlashda xatolik: " + (e.message || ""), "error");
    }
    showScreen("home", false);
  } finally {
    loadingOff();
  }
}

/* ---------- SAMPLE ---------- */
const SAMPLE = {
  matrix: [
    ["circle", "triangle", "square"],
    ["square", "circle", "triangle"],
    ["triangle", "square", "?"],
  ],
  options: [
    { key: "A", shape: "circle" },
    { key: "B", shape: "triangle" },
    { key: "C", shape: "square" },
    { key: "D", shape: "pentagon" },
  ],
  correct: "A",
};

function renderSample() {
  const wrap = $("sample-matrix");
  wrap.innerHTML = "";
  SAMPLE.matrix.forEach((row) => row.forEach((cell) => {
    const c = el("div", "matrix-cell");
    if (cell === "?") {
      c.classList.add("missing");
      c.textContent = "?";
    } else {
      c.appendChild(shapeSVG(cell));
    }
    wrap.appendChild(c);
  }));

  const opts = $("sample-options");
  opts.innerHTML = "";
  SAMPLE.options.forEach((o) => {
    const b = el("button", "option-btn");
    b.type = "button";
    b.dataset.key = o.key;
    b.appendChild(el("div", "opt-key", o.key));
    const svgWrap = el("div", "opt-svg");
    svgWrap.appendChild(shapeSVG(o.shape));
    b.appendChild(svgWrap);
    b.addEventListener("click", () => {
      qsAll(".option-btn", opts).forEach((x) => x.classList.remove("selected"));
      b.classList.add("selected");
      if (o.key === SAMPLE.correct) {
        toast("To'g'ri! Endi testni boshlaymiz", "success");
        setTimeout(() => {
          renderQuestion();
          showScreen("test");
        }, 650);
      } else {
        toast("Bu namuna edi. To'g'ri javob: A", "info");
        setTimeout(() => {
          renderQuestion();
          showScreen("test");
        }, 900);
      }
    });
    opts.appendChild(b);
  });
}

$("sample-start").addEventListener("click", () => {
  renderQuestion();
  showScreen("test");
});

/* ---------- SHAPES (SVG) ---------- */
function shapeSVG(name) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  const stroke = "#e8eaf6";
  const strokeViolet = "#a78bfa";
  const strokeBlue = "#60a5fa";

  const add = (tag, attrs) => {
    const n = document.createElementNS(ns, tag);
    Object.keys(attrs).forEach((k) => n.setAttribute(k, String(attrs[k])));
    svg.appendChild(n);
    return n;
  };

  const s = String(name || "").toLowerCase();

  if (s === "circle") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "triangle") {
    add("polygon", { points: "50,20 82,78 18,78", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "square") {
    add("rect", { x: 22, y: 22, width: 56, height: 56, fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "pentagon") {
    add("polygon", { points: "50,18 82,42 70,80 30,80 18,42", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "hexagon") {
    add("polygon", { points: "50,18 80,35 80,65 50,82 20,65 20,35", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "heptagon") {
    add("polygon", { points: "50,16 78,32 82,62 62,84 38,84 18,62 22,32", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "octagon") {
    add("polygon", { points: "32,18 68,18 82,32 82,68 68,82 32,82 18,68 18,32", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "1dot" || s === "2dot" || s === "3dot" || s === "4dot" || s === "5dot" || s === "6dot") {
    const n = parseInt(s[0], 10);
    const positions = dotPositions(n);
    positions.forEach((p) => add("circle", { cx: p[0], cy: p[1], r: 7, fill: strokeViolet }));
  } else if (s === "dark") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#4c1d95" });
  } else if (s === "mid") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#a78bfa" });
  } else if (s === "light") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#e8eaf6" });
  } else if (s === "extra_light") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#f8fafc" });
  } else if (s === "arrow_up") {
    add("polygon", { points: "50,20 76,60 60,60 60,82 40,82 40,60 24,60", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "arrow_down") {
    add("polygon", { points: "50,82 76,42 60,42 60,20 40,20 40,42 24,42", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "arrow_left") {
    add("polygon", { points: "20,50 60,24 60,40 82,40 82,60 60,60 60,76", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "arrow_right") {
    add("polygon", { points: "80,50 40,24 40,40 18,40 18,60 40,60 40,76", fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "half") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "none", stroke, "stroke-width": 4 });
    add("path", { d: "M50,22 A28,28 0 0,1 50,78 Z", fill: strokeViolet });
  } else if (s === "full") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: strokeViolet });
  } else if (s === "empty") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "none", stroke, "stroke-width": 4 });
  } else if (s === "double_full") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: strokeViolet });
    add("circle", { cx: 50, cy: 50, r: 16, fill: strokeBlue });
  } else if (s.startsWith("circle+")) {
    const n = parseInt(s.split("+")[1], 10) || 1;
    for (let i = 0; i < n; i++) {
      add("circle", { cx: 50, cy: 50, r: 8 + i * 5, fill: "none", stroke: i % 2 ? strokeBlue : strokeViolet, "stroke-width": 3 });
    }
  } else if (s === "red") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#ef4444" });
  } else if (s === "blue") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#60a5fa" });
  } else if (s === "green") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#22c55e" });
  } else if (s === "yellow") {
    add("circle", { cx: 50, cy: 50, r: 28, fill: "#facc15" });
  } else if (s.startsWith("triangle_")) {
    const variant = s.substring("triangle_".length);
    if (variant === "out") {
      add("polygon", { points: "50,20 82,78 18,78", fill: "none", stroke, "stroke-width": 4 });
    } else if (variant === "in") {
      add("polygon", { points: "50,30 72,70 28,70", fill: strokeViolet });
    } else if (variant === "double") {
      add("polygon", { points: "50,20 82,78 18,78", fill: "none", stroke, "stroke-width": 4 });
      add("polygon", { points: "50,38 68,68 32,68", fill: "none", stroke: strokeBlue, "stroke-width": 3 });
    } else {
      add("polygon", { points: "50,20 82,78 18,78", fill: "none", stroke, "stroke-width": 4 });
    }
  } else if (s.endsWith("line")) {
    const n = parseInt(s[0], 10) || 1;
    for (let i = 0; i < n; i++) {
      const y = 30 + i * (40 / Math.max(1, n - 1 || 1));
      add("line", { x1: 25, y1: y, x2: 75, y2: y, stroke: i % 2 ? strokeBlue : strokeViolet, "stroke-width": 4 });
    }
  } else if (s.startsWith("star")) {
    const n = parseInt(s.replace("star", ""), 10) || 5;
    add("polygon", { points: starPoints(50, 50, 28, 14, n), fill: "none", stroke, "stroke-width": 3 });
  } else if (s === "rot0" || s === "rot90" || s === "rot180" || s === "rot270" || s === "rot360") {
    const deg = parseInt(s.replace("rot", ""), 10) || 0;
    const g = document.createElementNS(ns, "g");
    g.setAttribute("transform", "rotate(" + deg + " 50 50)");
    const r = document.createElementNS(ns, "rect");
    r.setAttribute("x", 30); r.setAttribute("y", 40);
    r.setAttribute("width", 40); r.setAttribute("height", 20);
    r.setAttribute("fill", "none"); r.setAttribute("stroke", stroke); r.setAttribute("stroke-width", 4);
    g.appendChild(r);
    svg.appendChild(g);
  } else if (s.startsWith("sq+") && s.endsWith("tri")) {
    const n = parseInt(s.replace("sq+", "").replace("tri", ""), 10) || 1;
    add("rect", { x: 30, y: 30, width: 40, height: 40, fill: "none", stroke, "stroke-width": 3 });
    for (let i = 0; i < n; i++) {
      const ang = (i / n) * Math.PI * 2;
      const cx = 50 + Math.cos(ang) * 40;
      const cy = 50 + Math.sin(ang) * 40;
      add("circle", { cx, cy, r: 3, fill: strokeViolet });
    }
  } else if (s === "A1" || s === "B2" || s === "C3" || s === "D4" || s === "E5" || s === "F6" || s === "G7") {
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", "50"); t.setAttribute("y", "62");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("fill", stroke);
    t.setAttribute("font-size", "42");
    t.setAttribute("font-family", "sans-serif");
    t.setAttribute("font-weight", "700");
    t.textContent = s;
    svg.appendChild(t);
  } else if (s.startsWith("full+") || s.startsWith("half+") || s.startsWith("empty+")) {
    const [base, dotsStr] = s.split("+");
    const n = parseInt((dotsStr || "").replace("dot", ""), 10) || 1;
    if (base === "full") add("circle", { cx: 50, cy: 50, r: 28, fill: strokeViolet });
    else if (base === "half") {
      add("circle", { cx: 50, cy: 50, r: 28, fill: "none", stroke, "stroke-width": 3 });
      add("path", { d: "M50,22 A28,28 0 0,1 50,78 Z", fill: strokeViolet });
    } else add("circle", { cx: 50, cy: 50, r: 28, fill: "none", stroke, "stroke-width": 3 });
    for (let i = 0; i < n; i++) {
      const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
      add("circle", { cx: 50 + Math.cos(ang) * 38, cy: 50 + Math.sin(ang) * 38, r: 3, fill: strokeBlue });
    }
  } else if (s === "outer_red" || s === "mid_blue" || s === "inner_green" || s === "center_gold") {
    if (s === "outer_red") {
      add("circle", { cx: 50, cy: 50, r: 32, fill: "#ef4444" });
      add("circle", { cx: 50, cy: 50, r: 18, fill: "none", stroke: "#fff", "stroke-width": 2 });
    } else if (s === "mid_blue") {
      add("circle", { cx: 50, cy: 50, r: 32, fill: "none", stroke: "#60a5fa", "stroke-width": 6 });
      add("circle", { cx: 50, cy: 50, r: 16, fill: "#60a5fa" });
    } else if (s === "inner_green") {
      add("circle", { cx: 50, cy: 50, r: 32, fill: "none", stroke, "stroke-width": 2 });
      add("circle", { cx: 50, cy: 50, r: 12, fill: "#22c55e" });
    } else {
      add("circle", { cx: 50, cy: 50, r: 12, fill: "#facc15" });
    }
  } else if (s.includes("+")) {
    const parts = s.split("+");
    if (parts.length === 2) {
      const [a, b] = parts;
      if (a === "tri" || a === "sq" || a === "pent" || a === "hex" || a === "hep" || a === "oct" || a === "non" || a === "dec") {
        addPolygonByName(add, a, stroke, 0);
      }
      if (b === "tri" || b === "sq" || b === "pent" || b === "hex" || b === "hep" || b === "oct" || b === "non" || b === "dec") {
        addPolygonByName(add, b, strokeBlue, 8);
      }
    }
  } else if (s.endsWith("c")) {
    const n = parseInt(s.replace("c", ""), 10) || 1;
    for (let i = 0; i < Math.min(n, 20); i++) {
      const x = 20 + (i % 5) * 15;
      const y = 25 + Math.floor(i / 5) * 15;
      add("circle", { cx: x, cy: y, r: 4, fill: strokeViolet });
    }
  } else {
    add("circle", { cx: 50, cy: 50, r: 26, fill: "none", stroke, "stroke-width": 3 });
  }

  return svg;
}

function addPolygonByName(add, name, stroke, offset) {
  const o = offset || 0;
  const base = { tri: "50,20 82,78 18,78", sq: "22,22 78,22 78,78 22,78",
    pent: "50,18 82,42 70,80 30,80 18,42",
    hex: "50,18 80,35 80,65 50,82 20,65 20,35",
    hep: "50,16 78,32 82,62 62,84 38,84 18,62 22,32",
    oct: "32,18 68,18 82,32 82,68 68,82 32,82 18,68 18,32",
    non: "50,14 78,28 86,58 68,84 32,84 14,58 22,28",
    dec: "50,12 76,24 86,50 76,76 50,88 24,76 14,50 24,24" };
  const pts = base[name];
  if (!pts) return;
  const scaled = pts.split(" ").map((p) => {
    const [x, y] = p.split(",").map(Number);
    return (x * 0.7 + 50 * 0.3 + o) + "," + (y * 0.7 + 50 * 0.3 + o);
  }).join(" ");
  add("polygon", { points: scaled, fill: "none", stroke, "stroke-width": 3 });
}

function dotPositions(n) {
  if (n <= 1) return [[50, 50]];
  if (n === 2) return [[38, 50], [62, 50]];
  if (n === 3) return [[50, 30], [32, 65], [68, 65]];
  if (n === 4) return [[35, 35], [65, 35], [35, 65], [65, 65]];
  if (n === 5) return [[50, 28], [30, 50], [70, 50], [38, 72], [62, 72]];
  return [[35, 30], [65, 30], [28, 52], [72, 52], [38, 74], [62, 74]];
}

function starPoints(cx, cy, outer, inner, n) {
  const pts = [];
  for (let i = 0; i < n * 2; i++) {
    const r = i % 2 === 0 ? outer : inner;
    const a = (i / (n * 2)) * Math.PI * 2 - Math.PI / 2;
    pts.push((cx + Math.cos(a) * r).toFixed(1) + "," + (cy + Math.sin(a) * r).toFixed(1));
  }
  return pts.join(" ");
}

/* ---------- RENDER QUESTION ---------- */
function renderQuestion() {
  const t = State.currentTest;
  if (!t) return;
  const q = t.questions[State.currentQuestionIndex];
  if (!q) { finishTest(); return; }

  const total = t.questions.length;
  const idx = State.currentQuestionIndex;

  // progress
  $("test-progress").style.width = Math.round((idx / total) * 100) + "%";
  $("test-counter").textContent = (idx + 1) + " / " + total;

  const diff = q.difficulty || "easy";
  const badge = $("test-diff");
  badge.textContent = diff.toUpperCase();
  badge.className = "badge badge-" + diff;

  // question text
  let qtext = "";
  if (t.type === "iq") {
    qtext = "Matritsa mantiqini toping";
  } else {
    qtext = q.question || "Savol";
  }
  $("test-question").textContent = qtext;

  const mw = $("test-matrix");
  mw.innerHTML = "";
  if (t.type === "iq" && Array.isArray(q.matrix)) {
    q.matrix.forEach((row) => row.forEach((cell) => {
      const c = el("div", "matrix-cell");
      if (cell === "?") {
        c.classList.add("missing");
        c.textContent = "?";
      } else {
        c.appendChild(shapeSVG(cell));
      }
      mw.appendChild(c);
    }));
    mw.style.display = "";
  } else {
    mw.style.display = "none";
  }

  const opts = $("test-options");
  opts.innerHTML = "";
  const options = q.options || [];
  options.forEach((o) => {
    const b = el("button", "option-btn");
    b.type = "button";
    b.dataset.key = o.key;
    b.appendChild(el("div", "opt-key", o.key));
    if (t.type === "iq") {
      const svgWrap = el("div", "opt-svg");
      svgWrap.appendChild(shapeSVG(o.shape));
      b.appendChild(svgWrap);
    } else {
      const t2 = el("div", "opt-text", o.text || "");
      b.appendChild(t2);
    }
    if (State.answers[String(q.id)] === o.key) {
      b.classList.add("selected");
    }
    b.addEventListener("click", () => onAnswer(q, o.key));
    opts.appendChild(b);
  });
}

function onAnswer(q, key) {
  State.answers[String(q.id)] = key;
  const opts = $("test-options");
  qsAll(".option-btn", opts).forEach((b) => {
    b.classList.toggle("selected", b.dataset.key === key);
  });

  saveProgress();

  // Celebration checkpoints for IQ
  const t = State.currentTest;
  const idx = State.currentQuestionIndex;
  if (t.type === "iq" && (idx === 5 || idx === 11)) {
    showCelebration(() => advance());
    return;
  }
  setTimeout(advance, 220);
}

function advance() {
  State.currentQuestionIndex++;
  saveProgress();
  const t = State.currentTest;
  if (!t) return;
  if (State.currentQuestionIndex >= t.questions.length) {
    finishTest();
  } else {
    renderQuestion();
  }
}

function showCelebration(cb) {
  const c = $("test-celebration");
  show(c);
  setTimeout(() => {
    hide(c);
    if (cb) cb();
  }, 1400);
}

/* ---------- PROGRESS PERSISTENCE ---------- */
function progressKey(sessionId) { return "iqbot_prog_" + sessionId; }
function saveProgress() {
  if (!State.sessionId) return;
  try {
    localStorage.setItem(progressKey(State.sessionId), JSON.stringify({
      type: State.sessionType,
      index: State.currentQuestionIndex,
      answers: State.answers,
      startedAt: State.testStartTime,
    }));
  } catch (e) { /* noop */ }
}
function loadProgress(sessionId) {
  try {
    const raw = localStorage.getItem(progressKey(sessionId));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) { return null; }
}
function clearProgress(sessionId) {
  try { localStorage.removeItem(progressKey(sessionId)); } catch (e) { /* noop */ }
}

/* ---------- FINISH TEST ---------- */
async function finishTest() {
  if (State.submitting) return;
  State.submitting = true;
  showScreen("loading");

  // animate loading checklist
  const steps = qsAll("#loading-checklist li");
  steps.forEach((s) => s.classList.remove("done"));
  let i = 0;
  const stepTimer = setInterval(() => {
    if (i < steps.length) {
      steps[i].classList.add("done");
      i++;
      $("loading-progress").style.width = Math.round((i / steps.length) * 90) + "%";
    }
  }, 320);

  const duration = Math.max(1, Math.round((Date.now() - State.testStartTime) / 1000));

  try {
    const r = await api("/api/test/submit", {
      method: "POST",
      json: {
        session_id: State.sessionId,
        answers: State.answers,
        duration,
      },
    });

    clearInterval(stepTimer);
    steps.forEach((s) => s.classList.add("done"));
    $("loading-progress").style.width = "100%";
    await new Promise((res) => setTimeout(res, 500));

    clearProgress(State.sessionId);

    if (r && r.result_visible === false && r.payment_required) {
      await openPaymentForAttempt(r.attempt_id, State.sessionType);
      return;
    }

    // Try to get full result
    try {
      const full = await api("/api/result/me?type=" + encodeURIComponent(State.sessionType), { method: "GET" });
      renderResult(full);
    } catch (e) {
      renderResult(r);
    }
    showScreen("result");
    // refresh unlocks
    loadHome().catch(() => {});
  } catch (e) {
    clearInterval(stepTimer);
    if (e.status === 0) {
      toast("Internet aloqasi yo'q. Qaytadan urinib ko'ring.", "error", 4000);
    } else {
      toast("Natijani yuborishda xatolik: " + (e.message || ""), "error", 4000);
    }
    showScreen("test", false);
  } finally {
    State.submitting = false;
  }
}

/* ---------- RESULT RENDER ---------- */
function renderResult(r) {
  const type = (r.type || State.sessionType || "iq").toLowerCase();
  const badge = $("result-badge");
  const titleMap = { iq: "IQ Natijangiz", eq: "EQ Natijangiz", pq: "PQ Natijangiz" };
  const emojiMap = { iq: "🧠", eq: "🎭", pq: "⏳" };
  badge.textContent = emojiMap[type] || "🧠";
  $("result-title").textContent = titleMap[type] || "Natijangiz";

  const scoreEl = $("result-score");
  scoreEl.textContent = r.score != null ? String(r.score) : "—";
  $("result-level").textContent = r.level || "";

  // stats
  const stats = $("result-stats");
  stats.innerHTML = "";
  const add = (lbl, val) => {
    const c = el("div", "result-stat");
    c.appendChild(el("div", "lbl", lbl));
    c.appendChild(el("div", "val", String(val == null ? "—" : val)));
    stats.appendChild(c);
  };
  if (type === "iq") {
    add("To'g'ri javob", (r.correct_count != null ? r.correct_count : "—") + " / 18");
    add("Urinish", "#" + (r.attempt_no || 1));
  } else {
    add("Foiz", (r.score != null ? r.score : "—") + "%");
    add("Urinish", "#" + (r.attempt_no || 1));
  }
  if (r.certificate && r.certificate.verification_code) {
    add("Sertifikat", r.certificate.verification_code);
  }

  // certificate preview
  if (r.certificate) {
    $("cert-name").textContent = (State.user && State.user.full_name) || "Foydalanuvchi";
    $("cert-score").textContent = (r.certificate.score != null ? r.certificate.score : r.score || "—") + "";
    $("cert-level").textContent = r.certificate.level || r.level || "";
    $("cert-code").textContent = "Kod: " + r.certificate.verification_code;
  } else {
    $("cert-name").textContent = (State.user && State.user.full_name) || "Foydalanuvchi";
    $("cert-score").textContent = (r.score != null ? r.score : "—") + "";
    $("cert-level").textContent = r.level || "";
    $("cert-code").textContent = "Kod: —";
  }
}

$("result-cert").addEventListener("click", () => {
  showScreen("certificate");
});
$("result-home").addEventListener("click", () => {
  showScreen("home", false);
});
$("cert-open-bot").addEventListener("click", () => {
  const url = "https://t.me/iqtest_ubot";
  if (TG && TG.openTelegramLink) {
    TG.openTelegramLink(url);
  } else {
    window.open(url, "_blank");
  }
});

/* ---------- LIVE COUNTER ---------- */
function startLiveTimer() {
  stopLiveTimer();
  updateLive();
  State.liveTimer = setInterval(updateLive, 5000);
}
function stopLiveTimer() {
  if (State.liveTimer) {
    clearInterval(State.liveTimer);
    State.liveTimer = null;
  }
}
async function updateLive() {
  try {
    const r = await api("/api/stats/live", { method: "GET" });
    if (!r || !r.ok) return;
    setLive($("live-total"), r.total);
    setLive($("live-online"), r.online);
  } catch (e) { /* noop */ }
}
function setLive(node, val) {
  if (!node) return;
  const v = Number(val) || 0;
  const txt = v.toLocaleString("en-US").replace(/,/g, " ");
  if (node.textContent !== txt) {
    node.textContent = txt;
    node.classList.add("tick");
    setTimeout(() => node.classList.remove("tick"), 300);
  }
}

/* =============================================================================
   PART 6/6 — app.js B qism
   EQ / PQ handling, Personal, Battle, Payment, Certificate, Ranking, Referral
   ============================================================================= */

/* ---------- PERSONAL PROFILE ---------- */
async function openPersonal() {
  showScreen("personal");
  const wrap = $("personal-content");
  wrap.innerHTML = '<div class="center" style="padding:40px 0"><div class="loader-ring"></div></div>';
  try {
    const r = await api("/api/profile/personal", { method: "GET" });
    wrap.innerHTML = "";
    const bars = el("div", "personal-card");
    bars.appendChild(el("h3", null, "Umumiy ko'rsatkichlar"));
    const barWrap = el("div", "personal-bars");

    const addBar = (label, val, max) => {
      const row = el("div", "personal-bar");
      row.appendChild(el("div", "lbl", label));
      const track = el("div", "track");
      const fill = el("div", "fill");
      const pct = Math.max(0, Math.min(100, Math.round((Number(val) / max) * 100)));
      fill.style.width = pct + "%";
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el("div", "val", String(val)));
      barWrap.appendChild(row);
    };
    addBar("IQ", r.iq, 130);
    addBar("EQ", r.eq, 100);
    addBar("PQ", r.pq, 100);
    bars.appendChild(barWrap);
    wrap.appendChild(bars);

    if (Array.isArray(r.strengths) && r.strengths.length) {
      const c = el("div", "personal-card");
      c.appendChild(el("h3", null, "Kuchli tomonlaringiz"));
      const ul = el("ul", "personal-list strengths");
      r.strengths.forEach((s) => ul.appendChild(el("li", null, s)));
      c.appendChild(ul);
      wrap.appendChild(c);
    }
    if (Array.isArray(r.growth) && r.growth.length) {
      const c = el("div", "personal-card");
      c.appendChild(el("h3", null, "Rivojlantirish kerak"));
      const ul = el("ul", "personal-list growth");
      r.growth.forEach((s) => ul.appendChild(el("li", null, s)));
      c.appendChild(ul);
      wrap.appendChild(c);
    }

    const profile = el("div", "personal-card");
    profile.appendChild(el("h3", null, "Umumiy profil"));
    const ptext = el("p", null, "");
    let summary = "";
    if (r.iq >= 115) summary += "Siz yuqori intellektga egasiz. ";
    else if (r.iq >= 95) summary += "Sizning IQ darajangiz o'rtacha-yuqori. ";
    else summary += "IQ darajangizni mashqlar bilan oshirishingiz mumkin. ";
    if (r.eq >= 75) summary += "Emotsiyalarni yaxshi boshqarasiz. ";
    else summary += "Emotsional intellektni rivojlantirish foydali. ";
    if (r.pq >= 75) summary += "Maqsadlarga erishishda samaralisiz.";
    else summary += "Vaqtni boshqarish odatlarini yaxshilash kerak.";
    ptext.textContent = summary;
    profile.appendChild(ptext);
    wrap.appendChild(profile);

    const back = el("button", "btn btn-ghost btn-lg", "🏠 Bosh sahifa");
    back.addEventListener("click", () => showScreen("home", false));
    wrap.appendChild(back);
  } catch (e) {
    if (e.status === 403) {
      wrap.innerHTML = '<div class="empty"><div class="empty-emoji">🔒</div><div class="empty-title">Hali ochilmagan</div><div class="empty-sub">IQ + EQ + PQ testlarini yakunlang</div></div>';
    } else {
      wrap.innerHTML = '<div class="empty"><div class="empty-emoji">⚠️</div><div class="empty-title">Xatolik</div><div class="empty-sub">' + (e.message || "") + '</div></div>';
    }
  }
}

/* ---------- BATTLE ---------- */
let battleTimer = null;
let currentBattleId = null;

async function openBattle() {
  showScreen("battle");
  stopBattleTimer();
  renderBattleIdle();
}

function stopBattleTimer() {
  if (battleTimer) { clearInterval(battleTimer); battleTimer = null; }
}

function renderBattleIdle() {
  const wrap = $("battle-content");
  wrap.innerHTML = "";

  const menu = el("div", "battle-card");
  const title = el("h3", null, "Do'stingiz bilan duel");
  title.style.margin = "0 0 4px";
  menu.appendChild(title);
  menu.appendChild(el("div", "battle-status", "4 belgili kod yarating yoki mavjud kodni kiriting"));

  const createBtn = el("button", "btn btn-primary btn-lg", "➕ Battle yaratish");
  createBtn.addEventListener("click", createBattle);
  menu.appendChild(createBtn);

  const joinWrap = el("div");
  joinWrap.style.marginTop = "8px";
  const input = el("input", "battle-code-input");
  input.maxLength = 4;
  input.placeholder = "KOD";
  input.id = "battle-join-input";
  const joinBtn = el("button", "btn btn-ghost btn-lg", "🔗 Kod bilan qo'shilish");
  joinBtn.style.marginTop = "10px";
  joinBtn.addEventListener("click", () => joinBattle(input.value));
  joinWrap.appendChild(input);
  joinWrap.appendChild(joinBtn);
  menu.appendChild(joinWrap);

  // Resume existing battleapi
  const resumeBtn = el("button", "btn btn-/bghost btn-lg", "🔄 Joriy batattlelni tekshirish");
  resumeBtn/.style.marginTop = "10pxjoin",";
  resumeBtn.addEventListener("click", resumeBattle);
  menu.appendChild(resumeBtn);

  wrap.appendChild(menu);
  resumeBattle();
}

async function createBattle() {
  loadingOn();
  try {
    const r = await api("/api/battle/create", { method: "POST", json: {} });
    currentBattleId = r.battle_id;
    toast("Battle yaratildi", "success");
    await showBattlePayment(r.battle_id, r.code, r.price);
  } catch (e) {
    toast("Battle yaratishda xatolik: " + (e.message || ""), "error");
  } finally { loadingOff(); }
}

async function joinBattle(code) {
  code = String(code || "").trim().toUpperCase();
  if (code.length !== 4) { toast("Kod 4 belgi bo'lishi kerak", "error"); return; }
  loadingOn();
  try {
    const r = await api("/ { method: "POST", json: { code } });
    currentBattleId = r.battle_id;
    toast("Batlega qo'shildingiz", "success");
    await showBattlePayment(r.battle_id, code, r.price);
  } catch (e) {
    if (e.status === 400) toast("O'z batlingizga qo'shila olmaysiz", "error");
    else if (e.status === 404) toast("Battle topilmadi", "error");
    else if (e.status === 409) toast("Battle to'la", "error");
    else toast("Xatolik: " + (e.message || ""), "error");
  } finally { loadingOff(); }
}

async function resumeBattle() {
  try {
    const r = await api("/api/battle/me", { method: "GET" });
    if (!r || !r.has_battle) return;
    const b = r.battle;
    currentBattleId = b.battle_id;
    await routeBattleState(b);
  } catch (e) { /* noop */ }
}

async function routeBattleState(b) {
  stopBattleTimer();
  const you = b.you || (State.user && State.user.user_id) || 0;
  const youPlayer = (b.players || []).find((p) => Number(p.user_id) === Number(you));
  const oppPlayer = (b.players || []).find((p) => Number(p.user_id) !== Number(you));

  const wrap = $("battle-content");
  wrap.innerHTML = "";

  const card = el("div", "battle-card");
  card.appendChild(el("div", "battle-code", b.code || "----"));

  const vs = el("div", "battle-vs");
  vs.appendChild(el("div", "name", "Siz"));
  vs.appendChild(el("div", "vs", "VS"));
  vs.appendChild(el("div", "name", oppPlayer ? "Raqib" : "Kutilmoqda…"));
  card.appendChild(vs);

  const youPaid = youPlayer && youPlayer.payment_ok;
  const oppPaid = oppPlayer && oppPlayer.payment_ok;

  const status = el("div", "battle-status");
  if (b.status === "waiting") {
    status.textContent = "⏳ Raqib kutilmoqda. Kodni ulashing.";
  } else if (b.status === "payment") {
    status.textContent = "💳 Ikkala tomon to'lovi kutilmoqda";
    status.classList.add("warn");
  } else if (b.status === "ready" || b.status === "active") {
    status.textContent = "✅ Battle tayyor!";
    status.classList.add("ok");
  } else if (b.status === "finished") {
    status.textContent = "🏁 Battle tugadi";
    status.classList.add("ok");
  }
  card.appendChild(status);

  if (b.status !== "finished") {
    const payInfo = el("div");
    payInfo.style.display = "grid";
    payInfo.style.gap = "6px";
    const youRow = el("div", "pay-row");
    youRow.appendChild(el("span", null, "Sizning to'lov"));
    youRow.appendChild(el("b", null, youPaid ? "✅ To'langan" : "❌ Kutilmoqda"));
    const oppRow = el("div", "pay-row");
    oppRow.appendChild(el("span", null, "Raqib to'lovi"));
    oppRow.appendChild(el("b", null, oppPaid ? "✅ To'langan" : "❌ Kutilmoqda"));
    payInfo.appendChild(youRow);
    payInfo.appendChild(oppRow);
    card.appendChild(payInfo);

    if (!youPaid) {
      const payBtn = el("button", "btn btn-primary btn-lg", "💳 To'lash");
      payBtn.addEventListener("click", () => openBattlePayment(b));
      card.appendChild(payBtn);
    }
  }

  if (b.status === "ready" || b.status === "active") {
    const startBtn = el("button", "btn btn-primary btn-lg", "🧠 Testni boshlash");
    startBtn.addEventListener("click", () => startBattleTest(b.battle_id));
    card.appendChild(startBtn);
  }

  if (b.status === "finished") {
    const winner = Number(b.winner_id) === Number(you);
    const draw = !b.winner_id;
    const res = el("div");
    res.style.fontSize = "18px";
    res.style.fontWeight = "800";
    if (draw) { res.textContent = "🤝 Durang!"; }
    else if (winner) { res.textContent = "🏆 Siz yutdingiz!"; res.style.color = "var(--gold-light)"; }
    else { res.textContent = "😔 Raqib yutdi"; res.style.color = "var(--text-dim)"; }
    card.appendChild(res);

    const scores = el("div");
    scores.style.fontSize = "14px";
    scores.style.color = "var(--text-dim)";
    scores.textContent = "Siz: " + (Number(b.creator_id) === Number(you) ? b.creator_score : b.opponent_score) +
      " • Raqib: " + (Number(b.creator_id) === Number(you) ? b.opponent_score : b.creator_score);
    card.appendChild(scores);

    const back = el("button", "btn btn-ghost btn-lg", "🏠 Bosh sahifa");
    back.style.marginTop = "10px";
    back.addEventListener("click", () => showScreen("home", false));
    card.appendChild(back);
  } else {
    // Poll every 4s while not finished
    battleTimer = setInterval(async () => {
      try {
        const st = await api("/api/battle/" + encodeURIComponent(b.battle_id) + "/state", { method: "GET" });
        if (st && (st.status === "finished" || st.you_finished)) {
          stopBattleTimer();
          await resumeBattle();
        } else if (st && st.status !== b.status) {
          stopBattleTimer();
          await resumeBattle();
        }
      } catch (e) { /* noop */ }
    }, 4000);
  }

  wrap.appendChild(card);
}

async function openBattlePayment(b) {
  // Load active cards and show pay screen
  loadingOn();
  try {
    const cards = await api("/api/payment/cards", { method: "GET" });
    loadingOff();
    if (!cards || !cards.cards || !cards.cards.length) {
      toast("Admin hali karta qo'shmagan", "error");
      return;
    }
    const card = cards.cards[0];
    const price = await getBattlePrice();
    await modal(
      "Battle to'lovi",
      "Karta: " + card.card_number + "\nEgasi: " + card.holder +
      (card.bank ? "\nBank: " + card.bank : "") +
      "\n\nSumma: " + price + " so'm\n\nTo'lovni amalga oshirib, chekni botga yuboring.",
      "To'ladim",
      "Bekor"
    );
    // Create payment record
    const p = await api("/api/payment/create", {
      method: "POST",
      json: {
        purpose: "battle",
        amount: price,
        battle_id: b.battle_id,
        card_id: card.card_id,
      },
    });
    toast("To'lov yaratildi. Chekni botga yuboring.", "info", 4000);
    // show payment screen for details
    openPaymentScreenForBattle(p.payment_id, card, price, b.battle_id);
  } catch (e) {
    loadingOff();
    toast("Xatolik: " + (e.message || ""), "error");
  }
}

async function showBattlePayment(battleId, code, price) {
  // Render a small payment prompt inside battle card
  const wrap = $("battle-content");
  wrap.innerHTML = "";
  const card = el("div", "battle-card");
  card.appendChild(el("div", "battle-code", code));
  card.appendChild(el("div", "battle-status", "Kodni do'stingizga yuboring va to'lovni amalga oshiring"));
  card.appendChild(el("div", "pay-amount", (price || 0) + " so'm"));

  const payBtn = el("button", "btn btn-primary btn-lg", "💳 To'lovni ko'rish");
  payBtn.addEventListener("click", () => {
    resumeBattle();
  });
  card.appendChild(payBtn);

  const refreshBtn = el("button", "btn btn-ghost btn-lg", "🔄 Holatni yangilash");
  refreshBtn.style.marginTop = "8px";
  refreshBtn.addEventListener("click", resumeBattle);
  card.appendChild(refreshBtn);

  wrap.appendChild(card);
  // Auto poll
  setTimeout(resumeBattle, 1500);
}

async function getBattlePrice() {
  try {
    const live = await api("/api/stats/live", { method: "GET" });
    // fallback price, from settings via create response is preferable
  } catch (e) { /* noop */ }
  return 7500;
}

async function startBattleTest(battleId) {
  loadingOn();
  try {
    // Fetch IQ questions once and start a "battle session"
    const r = await api("/api/test/questions?type=iq", { method: "GET" });
    State.currentTest = {
      type: "iq",
      questions: r.questions || [],
      attempt_no: 1,
      price: 0,
      battleId: battleId,
    };
    State.answers = {};
    State.currentQuestionIndex = 0;
    State.testStartTime = Date.now();
    State.sessionId = "battle_" + battleId;
    State.sessionType = "iq";

    if (!State.currentTest.questions.length) {
      toast("Savollar yuklanmadi", "error");
      return;
    }
    renderQuestion();
    showScreen("test");
    // The submit path handles battle
  } catch (e) {
    toast("Xatolik: " + (e.message || ""), "error");
  } finally { loadingOff(); }
}

/* ---------- PAYMENT SCREEN ---------- */
let currentPaymentId = null;

async function openPaymentForAttempt(attemptId, type) {
  loadingOn();
  try {
    const cards = await api("/api/payment/cards", { method: "GET" });
    if (!cards || !cards.cards || !cards.cards.length) {
      toast("Admin hali karta qo'shmagan", "error");
      showScreen("home", false);
      return;
    }
    const card = cards.cards[0];
    // price from attempt result
    let price = 5000;
    try {
      const rr = await api("/api/result/me?type=" + encodeURIComponent(type), { method: "GET" });
      // fallback; price came from /api/test/submit response previously. We'll create payment anyway.
    } catch (e) { /* noop */ }

    await modal(
      "To'lov",
      "Natijani ko'rish uchun to'lovni amalga oshiring.\n\n" +
      "Karta: " + card.card_number + "\n" +
      "Egasi: " + card.holder + (card.bank ? "\nBank: " + card.bank : ""),
      "Davom",
      "Bekor"
    );

    const p = await api("/api/payment/create", {
      method: "POST",
      json: {
        purpose: type + (attemptId ? "" : "_retry"),
        amount: price,
        attempt_id: attemptId,
        card_id: card.card_id,
      },
    });
    currentPaymentId = p.payment_id;
    renderPaymentScreen(card, price, attemptId);
  } catch (e) {
    toast("Xatolik: " + (e.message || ""), "error");
    showScreen("home", false);
  } finally { loadingOff(); }
}

function openPaymentScreenForBattle(paymentId, card, price, battleId) {
  currentPaymentId = paymentId;
  renderPaymentScreen(card, price, null, battleId);
}

function renderPaymentScreen(card, price, attemptId, battleId) {
  $("payment-sub").textContent = "To'lovni amalga oshirib, holatni tekshiring";
  $("pay-amount").textContent = (price || 0).toLocaleString("en-US").replace(/,/g, " ") + " so'm";
  $("pay-number").textContent = card.card_number || "—";
  $("pay-holder").textContent = card.holder || "—";
  $("pay-bank").textContent = card.bank || "—";

  $("pay-status").textContent = "";
  $("pay-status").className = "pay-status";

  showScreen("payment");

  const copyBtn = $("pay-copy");
  copyBtn.onclick = async () => {
    try {
      await navigator.clipboard.writeText(card.card_number || "");
      toast("Karta nusxalandi", "success");
    } catch (e) {
      toast("Nusxalash imkonsiz", "error");
    }
  };

  const receiptBtn = $("pay-receipt");
  receiptBtn.onclick = async () => {
    if (!currentPaymentId) return;
    try {
      await api("/api/payment/receipt", {
        method: "POST",
        json: { payment_id: currentPaymentId },
      });
      toast("Chek yuborildi. Admin tasdiqlashini kuting.", "success", 4000);
    } catch (e) {
      toast("Xatolik: " + (e.message || ""), "error");
    }
  };

  const checkBtn = $("pay-check");
  checkBtn.onclick = () => checkPaymentStatus(attemptId, battleId);
}

async function checkPaymentStatus(attemptId, battleId) {
  if (!currentPaymentId) return;
  loadingOn();
  try {
    const r = await api("/api/payment/status?payment_id=" + encodeURIComponent(currentPaymentId), { method: "GET" });
    const st = $("pay-status");
    st.className = "pay-status " + (r.status || "");
    if (r.status === "pending") {
      st.textContent = "⏳ To'lov kutilmoqda. Admin tasdiqlagach natija ochiladi.";
    } else if (r.status === "approved") {
      st.textContent = "✅ To'lov tasdiqlandi!";
      if (battleId) {
        setTimeout(() => resumeBattle(), 800);
      } else if (attemptId) {
        const full = await api("/api/result/me?type=" + encodeURIComponent(State.sessionType || "iq"), { method: "GET" });
        renderResult(full);
        showScreen("result");
      } else {
        setTimeout(() => showScreen("home", false), 800);
      }
    } else {
      st.textContent = "❌ To'lov rad etildi.";
    }
  } catch (e) {
    toast("Xatolik: " + (e.message || ""), "error");
  } finally { loadingOff(); }
}

/* ---------- CERTIFICATE (open in app) ---------- */
async function openCertificate(type) {
  showScreen("certificate");
  try {
    const r = await api("/api/certificate/me?type=" + encodeURIComponent(type || "IQ"), { method: "GET" });
    if (!r.has_certificate) {
      toast("Sertifikat topilmadi", "info");
      return;
    }
    $("cert-name").textContent = r.full_name || "Foydalanuvchi";
    $("cert-score").textContent = r.score != null ? String(r.score) : "—";
    $("cert-level").textContent = r.level || "";
    $("cert-code").textContent = "Kod: " + (r.verification_code || "—");
  } catch (e) {
    toast("Xatolik: " + (e.message || ""), "error");
  }
}

/* ---------- RANKING ---------- */
async function openRanking(type) {
  showScreen("ranking");
  await loadRanking(type || "iq");
}

async function loadRanking(type) {
  const list = $("rank-list");
  const me = $("rank-me");
  list.innerHTML = '<div class="center" style="padding:20px 0"><div class="loader-ring"></div></div>';
  me.textContent = "";
  qsAll("#rank-tabs .tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.type === type);
  });
  try {
    const r = await api("/api/ranking?type=" + encodeURIComponent(type), { method: "GET" });
    list.innerHTML = "";
    if (!r.list || !r.list.length) {
      list.innerHTML = '<div class="empty"><div class="empty-emoji">📊</div><div class="empty-title">Hozircha natijalar yo\'q</div></div>';
      return;
    }
    r.list.forEach((it) => {
      const row = el("div", "rank-item");
      if (it.rank === 1) row.classList.add("top1");
      if (it.rank === 2) row.classList.add("top2");
      if (it.rank === 3) row.classList.add("top3");
      const isMe = State.user && Number(State.user.user_id) === Number(it.user_id);
      if (isMe) row.classList.add("me");
      row.appendChild(el("div", "rank-pos", String(it.rank)));
      row.appendChild(el("div", "rank-name", it.name || "User"));
      row.appendChild(el("div", "rank-score", String(it.best != null ? it.best : "—")));
      list.appendChild(row);
    });
    if (r.me) {
      me.textContent = "Sizning o'rningiz: #" + r.me.position + " — " + (r.me.best != null ? r.me.best : "—");
    }
  } catch (e) {
    list.innerHTML = '<div class="empty"><div class="empty-emoji">⚠️</div><div class="empty-title">Xatolik</div><div class="empty-sub">' + (e.message || "") + '</div></div>';
  }
}

qsAll("#rank-tabs .tab").forEach((tab) => {
  tab.addEventListener("click", () => loadRanking(tab.dataset.type));
});

/* ---------- REFERRAL ---------- */
async function openReferral() {
  showScreen("referral");
  try {
    const r = await api("/api/referral/me", { method: "GET" });
    $("ref-count").textContent = String(r.count || 0);
    $("ref-link").textContent = r.link || "—";
    $("ref-copy").onclick = async () => {
      try {
        await navigator.clipboard.writeText(r.link || "");
        toast("Havola nusxalandi", "success");
      } catch (e) {
        toast("Nusxalash imkonsiz", "error");
      }
    };
  } catch (e) {
    toast("Xatolik: " + (e.message || ""), "error");
  }
}

/* ---------- HOOK MENU / BOT-INITIATED ACTIONS ---------- */
// Header right button (referral quick access) — optional
(function attachHeaderActions() {
  const hr = $("header-right");
  if (!hr) return;
  // nothing by default; reserved
})();

/* ---------- OVERRIDE STUBS (ensure real versions used) ---------- */
// These assignments ensure the real implementations replace any stubs.
window.openPersonal = openPersonal;
window.openBattle = openBattle;
window.openPaymentForAttempt = openPaymentForAttempt;

/* ---------- RESULTS: hook certificate button to open certificate screen ---------- */
(function hookResultCert() {
  const btn = $("result-cert");
  if (!btn) return;
  // Replace listener by cloning
  const clone = btn.cloneNode(true);
  btn.parentNode.replaceChild(clone, btn);
  clone.addEventListener("click", () => {
    const t = (State.sessionType || "iq").toUpperCase();
    openCertificate(t);
  });
})();

/* ---------- HOME card event - ensure Personal/Battle/Ranking/Referral links ---------- */
// Extra: expose ranking/referral via toast on header, but not required

/* ---------- BOOT SAFETY (idempotent) ---------- */
// The main boot happens in PART 5/6.

/* ---------- NAV ---------- */
$("btn-back").addEventListener("click", goBack);

/* ---------- REFERRAL deep-link exposure ---------- */
window.__IQBOT__ = {
  State,
  api,
  toast,
  showScreen,
  renderResult,
  renderQuestion,
  SAMPLE,
  shapeSVG,
};

/* ---------- BOOT ---------- */
window.addEventListener("load", () => {
  showScreen("home", false);
  loadHome();
});

})();
