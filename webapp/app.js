// ==================== TELEGRAM ====================
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor?.("#0a0e1a");
  tg.setBackgroundColor?.("#0a0e1a");
}
const initData = tg?.initData || "";

// ==================== HAPTIC ====================
function haptic(type = "light") {
  try { tg?.HapticFeedback?.impactOccurred(type); } catch {}
}

// ==================== API ====================
async function api(path, body = null, method = "POST") {
  try {
    const res = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : null,
    });
    return await res.json();
  } catch (e) {
    console.error("API error:", e);
    return { ok: false, error: "NETWORK" };
  }
}

// ==================== STATE ====================
const State = {
  currentScreen: "home",
  user: null,
  completed: {},
  test: {
    type: "iq",
    sessionId: null,
    attemptId: null,
    current: 0,
    answers: [],
    startedAt: null,
    duration: 0,
  },
  settings: {},
  totalUsers: 0,
  onlineUsers: 0,
  sampleAnswered: false,
};

// ==================== LOCAL STORAGE (OFFLINE-FIRST) ====================
const LS_KEY = "iqtestbot_session";

function saveLocal() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      type: State.test.type,
      sessionId: State.test.sessionId,
      attemptId: State.test.attemptId,
      current: State.test.current,
      answers: State.test.answers,
      startedAt: State.test.startedAt,
      duration: State.test.duration,
    }));
  } catch {}
}

function loadLocal() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch { return null; }
}

function clearLocal() {
  try { localStorage.removeItem(LS_KEY); } catch {}
}

// ==================== QUESTIONS ====================
// NOTE: Keyingi bosqichda 18 ta to‘liq savol yoziladi.
// Hozircha 6 ta namuna (har difficulty dan 2 ta).
const QUESTIONS = [
  // EASY (weight 1)
  {
    id: 1, difficulty: "easy", weight: 1,
    category: "Pattern",
    matrix: [
      { type: "dot", count: 1 }, { type: "dot", count: 2 }, { type: "dot", count: 3 },
      { type: "dot", count: 2 }, { type: "dot", count: 3 }, { type: "dot", count: 4 },
      { type: "dot", count: 3 }, { type: "dot", count: 4 }, { type: "question" },
    ],
    options: [
      { type: "dot", count: 4 }, { type: "dot", count: 5 },
      { type: "dot", count: 3 }, { type: "dot", count: 6 },
    ],
    correct: 1, // 5 dots
  },
  {
    id: 2, difficulty: "easy", weight: 1,
    category: "Mantiq",
    matrix: [
      { type: "shape", shape: "circle", fill: "empty" }, { type: "shape", shape: "square", fill: "empty" }, { type: "shape", shape: "triangle", fill: "empty" },
      { type: "shape", shape: "square", fill: "empty" }, { type: "shape", shape: "triangle", fill: "empty" }, { type: "shape", shape: "circle", fill: "empty" },
      { type: "shape", shape: "triangle", fill: "empty" }, { type: "shape", shape: "circle", fill: "empty" }, { type: "question" },
    ],
    options: [
      { type: "shape", shape: "square", fill: "empty" },
      { type: "shape", shape: "circle", fill: "empty" },
      { type: "shape", shape: "triangle", fill: "empty" },
      { type: "shape", shape: "diamond", fill: "empty" },
    ],
    correct: 0, // square
  },
  // MEDIUM (weight 2)
  {
    id: 3, difficulty: "medium", weight: 2,
    category: "Pattern",
    matrix: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 90 }, { type: "rotate", angle: 180 },
      { type: "rotate", angle: 90 }, { type: "rotate", angle: 180 }, { type: "rotate", angle: 270 },
      { type: "rotate", angle: 180 }, { type: "rotate", angle: 270 }, { type: "question" },
    ],
    options: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 90 },
      { type: "rotate", angle: 180 }, { type: "rotate", angle: 360 },
    ],
    correct: 3, // 360 = 0
  },
  {
    id: 4, difficulty: "medium", weight: 2,
    category: "Fazoviy fikr",
    matrix: [
      { type: "shape", shape: "circle", fill: "full" }, { type: "shape", shape: "circle", fill: "half" }, { type: "shape", shape: "circle", fill: "empty" },
      { type: "shape", shape: "square", fill: "full" }, { type: "shape", shape: "square", fill: "half" }, { type: "shape", shape: "square", fill: "empty" },
      { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "triangle", fill: "half" }, { type: "question" },
    ],
    options: [
      { type: "shape", shape: "triangle", fill: "full" },
      { type: "shape", shape: "triangle", fill: "half" },
      { type: "shape", shape: "triangle", fill: "empty" },
      { type: "shape", shape: "circle", fill: "empty" },
    ],
    correct: 2, // empty
  },
  // HARD (weight 3)
  {
    id: 5, difficulty: "hard", weight: 3,
    category: "Mantiq",
    matrix: [
      { type: "combo", shapes: ["circle"], fill: "full" },
      { type: "combo", shapes: ["circle","square"], fill: "full" },
      { type: "combo", shapes: ["circle","square","triangle"], fill: "full" },
      { type: "combo", shapes: ["square"], fill: "empty" },
      { type: "combo", shapes: ["square","triangle"], fill: "empty" },
      { type: "combo", shapes: ["square","triangle","circle"], fill: "empty" },
      { type: "combo", shapes: ["triangle"], fill: "half" },
      { type: "combo", shapes: ["triangle","circle"], fill: "half" },
      { type: "question" },
    ],
    options: [
      { type: "combo", shapes: ["triangle","circle","square"], fill: "half" },
      { type: "combo", shapes: ["triangle"], fill: "half" },
      { type: "combo", shapes: ["circle","square"], fill: "half" },
      { type: "combo", shapes: ["triangle","square"], fill: "half" },
    ],
    correct: 0,
  },
  {
    id: 6, difficulty: "hard", weight: 3,
    category: "Raqamlar",
    matrix: [
      { type: "num", val: 2 }, { type: "num", val: 4 }, { type: "num", val: 6 },
      { type: "num", val: 3 }, { type: "num", val: 6 }, { type: "num", val: 9 },
      { type: "num", val: 4 }, { type: "num", val: 8 }, { type: "question" },
    ],
    options: [
      { type: "num", val: 10 }, { type: "num", val: 12 },
      { type: "num", val: 14 }, { type: "num", val: 16 },
    ],
    correct: 1, // 12
  },
];

// ==================== RENDER HELPERS ====================
function renderCell(cell) {
  if (!cell) return "";
  if (cell.type === "question") return "";
  if (cell.type === "dot") {
    let html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:3px;width:40px;height:40px;align-items:center;justify-items:center;">';
    for (let i = 0; i < cell.count; i++) {
      html += '<div style="width:8px;height:8px;border-radius:50%;background:#a78bfa;box-shadow:0 0 6px #a78bfa;"></div>';
    }
    html += "</div>";
    return html;
  }
  if (cell.type === "num") {
    return `<span style="font-size:24px;font-weight:800;color:#a78bfa;">${cell.val}</span>`;
  }
  if (cell.type === "shape") {
    const colors = { full: "#a78bfa", half: "rgba(167,139,250,.5)", empty: "transparent" };
    const stroke = "#a78bfa";
    const fill = colors[cell.fill] || "transparent";
    if (cell.shape === "circle") return `<svg width="40" height="40"><circle cx="20" cy="20" r="16" fill="${fill}" stroke="${stroke}" stroke-width="2"/></svg>`;
    if (cell.shape === "square") return `<svg width="40" height="40"><rect x="5" y="5" width="30" height="30" rx="4" fill="${fill}" stroke="${stroke}" stroke-width="2"/></svg>`;
    if (cell.shape === "triangle") return `<svg width="40" height="40"><polygon points="20,5 35,35 5,35" fill="${fill}" stroke="${stroke}" stroke-width="2"/></svg>`;
    if (cell.shape === "diamond") return `<svg width="40" height="40"><polygon points="20,4 36,20 20,36 4,20" fill="${fill}" stroke="${stroke}" stroke-width="2"/></svg>`;
  }
  if (cell.type === "rotate") {
    return `<svg width="40" height="40" style="transform:rotate(${cell.angle}deg)"><path d="M10 20 L30 20 M25 15 L30 20 L25 25" stroke="#a78bfa" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>`;
  }
  if (cell.type === "combo") {
    const colors = { full: "#a78bfa", half: "rgba(167,139,250,.5)", empty: "transparent" };
    const fill = colors[cell.fill] || "transparent";
    let svg = '<svg width="44" height="44">';
    if (cell.shapes.includes("circle")) svg += `<circle cx="22" cy="22" r="16" fill="${fill}" stroke="#a78bfa" stroke-width="2"/>`;
    if (cell.shapes.includes("square")) svg += `<rect x="8" y="8" width="28" height="28" rx="3" fill="none" stroke="#60a5fa" stroke-width="2"/>`;
    if (cell.shapes.includes("triangle")) svg += `<polygon points="22,6 38,38 6,38" fill="none" stroke="#f59e0b" stroke-width="2"/>`;
    svg += "</svg>";
    return svg;
  }
  return "";
}

function renderMatrix(el, cells) {
  el.innerHTML = cells.map(c => `<div class="cell ${c.type==='question'?'question':''}">${renderCell(c)}</div>`).join("");
}

function renderOptions(el, options, onSelect) {
  el.innerHTML = options.map((o, i) => `<div class="option" data-idx="${i}">${renderCell(o)}</div>`).join("");
  el.querySelectorAll(".option").forEach(opt => {
    opt.addEventListener("click", () => {
      haptic("light");
      el.querySelectorAll(".option").forEach(x => x.classList.remove("selected"));
      opt.classList.add("selected");
      onSelect(parseInt(opt.dataset.idx));
    });
  });
}

// ==================== APP ====================
const App = {
  async init() {
    // Load config
    const cfg = await api("/api/config", null, "GET");
    if (cfg.ok) State.settings = cfg.settings;

    // Load live stats
    await this.refreshLive();

    // Load user
    if (initData) {
      const me = await api("/api/me", { initData });
      if (me.ok) {
        State.user = me.user;
        State.completed = me.completed || {};
        this.applyUnlocks();
      }
    }

    // Check local session
    const local = loadLocal();
    if (local && local.sessionId && local.current > 0 && local.current < 18) {
      // Resume prompt
      setTimeout(() => {
        if (confirm("Test davom etmoqda. Davom ettirishni xohlaysizmi?")) {
          State.test = { ...State.test, ...local };
          this.go("test");
          this.renderQuestion();
        } else {
          clearLocal();
        }
      }, 600);
    }
  },

  async refreshLive() {
    const res = await api("/api/stats/live", null, "GET");
    if (res.ok) {
      State.totalUsers = res.total;
      State.onlineUsers = res.online;
      this.animateNumber("live-total", res.total);
      document.getElementById("live-online").textContent = res.online;
    }
  },

  animateNumber(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    let cur = 0;
    const step = Math.max(1, Math.floor(target / 40));
    const timer = setInterval(() => {
      cur += step;
      if (cur >= target) { cur = target; clearInterval(timer); }
      el.textContent = cur.toLocaleString();
    }, 25);
  },

  go(screen) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    document.getElementById("screen-" + screen)?.classList.add("active");
    State.currentScreen = screen;
    haptic("light");
    window.scrollTo(0, 0);
  },

  applyUnlocks() {
    const c = State.completed;
    if (c.iq) {
      document.getElementById("card-eq")?.classList.remove("locked");
      document.getElementById("card-eq")?.classList.add("unlocked");
      document.getElementById("card-eq").querySelector(".card-state").textContent = "🔓";
    }
    if (c.eq) {
      document.getElementById("card-pq")?.classList.remove("locked");
      document.getElementById("card-pq")?.classList.add("unlocked");
      document.getElementById("card-pq").querySelector(".card-state").textContent = "🔓";
    }
    if (c.iq && c.eq && c.pq) {
      document.getElementById("card-profile")?.classList.remove("locked");
      document.getElementById("card-profile")?.classList.add("unlocked");
      document.getElementById("card-profile").querySelector(".card-state").textContent = "🔓";
    }
  },

  // ---------- IQ FLOW ----------
  async startIQ() {
    haptic("medium");
    // Create server session
    if (initData) {
      const res = await api("/api/session/start", { initData, test_type: "iq" });
      if (res.ok) {
        State.test.sessionId = res.session_id;
        State.test.attemptId = res.attempt_id;
      }
    }
    State.test.type = "iq";
    State.test.current = 0;
    State.test.answers = [];
    State.test.startedAt = Date.now();
    State.test.duration = 0;
    saveLocal();
    this.go("sample");
    this.renderSample();
  },

  renderSample() {
    // Sample question (separate from real test)
    const sample = {
      matrix: [
        { type: "dot", count: 1 }, { type: "dot", count: 2 }, { type: "dot", count: 3 },
        { type: "dot", count: 2 }, { type: "dot", count: 3 }, { type: "dot", count: 4 },
        { type: "dot", count: 3 }, { type: "dot", count: 4 }, { type: "question" },
      ],
      options: [
        { type: "dot", count: 4 }, { type: "dot", count: 5 },
        { type: "dot", count: 3 }, { type: "dot", count: 6 },
      ],
      correct: 1,
    };
    renderMatrix(document.getElementById("sample-matrix"), sample.matrix);
    State.sampleAnswered = false;
    document.getElementById("sample-next").disabled = true;
    renderOptions(document.getElementById("sample-options"), sample.options, (idx) => {
      State.sampleAnswered = true;
      document.getElementById("sample-next").disabled = false;
      const opts = document.querySelectorAll("#sample-options .option");
      opts.forEach((o, i) => {
        if (i === sample.correct) o.classList.add("correct");
        else if (i === idx) o.classList.add("wrong");
      });
    });
  },

  goTest() {
    this.go("test");
    this.renderQuestion();
    this.startTimer();
  },

  startTimer() {
    if (State.test.timerInterval) clearInterval(State.test.timerInterval);
    State.test.timerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - State.test.startedAt) / 1000);
      State.test.duration = elapsed;
      const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
      const s = String(elapsed % 60).padStart(2, "0");
      const el = document.getElementById("test-timer");
      if (el) el.textContent = `${m}:${s}`;
      saveLocal();
    }, 1000);
  },

  renderQuestion() {
    const q = QUESTIONS[State.test.current];
    if (!q) return;
    document.getElementById("test-progress-text").textContent = `Q${State.test.current + 1} / 18`;
    const pct = ((State.test.current) / 18) * 100;
    document.getElementById("progress-fill").style.width = pct + "%";

    // Difficulty bar
    const diff = document.getElementById("difficulty-bar");
    let diffHtml = "";
    for (let i = 0; i < 18; i++) {
      let cls = "easy";
      if (i >= 12) cls = "hard";
      else if (i >= 6) cls = "medium";
      if (i <= State.test.current) diffHtml += `<span class="${cls}"></span>`;
      else diffHtml += `<span></span>`;
    }
    diff.innerHTML = diffHtml;

    renderMatrix(document.getElementById("test-matrix"), q.matrix);
    const nextBtn = document.getElementById("test-next");
    nextBtn.disabled = true;
    nextBtn.textContent = State.test.current === 17 ? "YAKUNLASH →" : "KEYINGISI →";

    renderOptions(document.getElementById("test-options"), q.options, (idx) => {
      State.test.answers[State.test.current] = idx;
      nextBtn.disabled = false;
      saveLocal();
    });

    // Restore previous answer
    if (State.test.answers[State.test.current] !== undefined) {
      const prev = State.test.answers[State.test.current];
      document.querySelectorAll("#test-options .option")[prev]?.classList.add("selected");
      nextBtn.disabled = false;
    }
  },

  nextQuestion() {
    haptic("light");
    if (State.test.current === 4) {
      // Q5 done
      this.go("q5");
      return;
    }
    if (State.test.current === 17) {
      this.finish();
      return;
    }
    State.test.current++;
    saveLocal();
    this.renderQuestion();
  },

  continueAfterQ5() {
    State.test.current = 5;
    saveLocal();
    this.go("test");
    this.renderQuestion();
  },

  async finish() {
    clearInterval(State.test.timerInterval);
    this.go("loading");

    // Fake analysis delay (real feel)
    await new Promise(r => setTimeout(r, 2200));

    // Submit to server
    let score = 0, correct = 0, level = "—";
    if (initData && State.test.sessionId) {
      const res = await api("/api/test/submit", {
        initData,
        session_id: State.test.sessionId,
        answers: State.test.answers,
        answer_key: QUESTIONS.map(q => q.correct),
        duration: State.test.duration,
      });
      if (res.ok) {
        score = res.score;
        correct = res.correct;
        level = res.level;
        State.completed.iq = score;
      }
    } else {
      // Offline fallback
      correct = State.test.answers.filter((a, i) => a === QUESTIONS[i]?.correct).length;
      score = Math.round(70 + (correct / QUESTIONS.length) * 60);
      level = score >= 115 ? "YUQORI DARAJA" : score >= 100 ? "O‘RTA DARAJA" : "RIVOJLANTIRISH";
    }

    this.renderResult(score, correct, level);
    this.go("result");
    clearLocal();
  },

  renderResult(score, correct, level) {
    document.getElementById("res-score").textContent = score;
    document.getElementById("res-level").textContent = level;
    document.getElementById("res-correct").textContent = `${correct} / 18`;
    const m = String(Math.floor(State.test.duration / 60)).padStart(2, "0");
    const s = String(State.test.duration % 60).padStart(2, "0");
    document.getElementById("res-time").textContent = `${m}:${s}`;

    // Directions (approximate from answers)
    const dirs = [
      { label: "Mantiq", val: Math.min(100, 50 + correct * 3) },
      { label: "Pattern", val: Math.min(100, 55 + correct * 2.5) },
      { label: "Raqamlar", val: Math.min(100, 45 + correct * 3.2) },
      { label: "Fazoviy fikr", val: Math.min(100, 40 + correct * 3.5) },
    ];
    document.querySelectorAll(".dir").forEach((el, i) => {
      const d = dirs[i];
      el.dataset.label = d.label;
      const fill = el.querySelector(".dir-fill");
      const span = el.querySelector("span");
      setTimeout(() => { fill.style.width = d.val + "%"; }, 100 + i * 150);
      span.textContent = Math.round(d.val) + "%";
    });
    const strongest = dirs.reduce((a, b) => a.val > b.val ? a : b);
    document.getElementById("res-strongest").textContent = strongest.label;
  },

  async getCertificate() {
    if (!initData) {
      alert("Sertifikat Telegram orqali yuboriladi. Botga o‘ting.");
      return;
    }
    haptic("medium");
    alert("Sertifikat Telegram bot orqali yuboriladi. /start → 📜 Sertifikatim");
  },

  shareResult() {
    const score = document.getElementById("res-score").textContent;
    const text = `🧠 IQ TEST BOT\n\nMen IQ-style testda ${score} ball oldim!\nSiz ham sinab ko‘ring 👇`;
    const url = `https://t.me/${window.__BOT_USERNAME__ || "IQTestBot"}`;
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`);
    } else {
      alert(text + "\n" + url);
    }
  },

  retry() {
    clearLocal();
    State.test = { type: "iq", sessionId: null, attemptId: null, current: 0, answers: [], startedAt: null, duration: 0 };
    this.go("intro");
  },

  async loadUser() {
    if (!initData) return;
    const me = await api("/api/me", { initData });
    if (me.ok) {
      State.user = me.user;
      State.completed = me.completed || {};
      this.applyUnlocks();
    }
  },
};

// ==================== EVENT BINDINGS ====================
document.addEventListener("DOMContentLoaded", () => {
  App.init();

  // IQ card
  document.querySelector('[data-test="iq"]')?.addEventListener("click", () => {
    haptic("medium");
    App.go("intro");
  });

  // EQ / PQ / Profile (locked or not)
  document.querySelectorAll('[data-test="eq"], [data-test="pq"], [data-test="profile"]').forEach(card => {
    card.addEventListener("click", () => {
      if (card.classList.contains("locked")) {
        haptic("rigid");
        return;
      }
      haptic("medium");
      // Keyingi bosqichda EQ/PQ/Profile render
      alert("Bu test keyingi bosqichda qo‘shiladi.");
    });
  });

  // Battle
  document.getElementById("battle-card")?.addEventListener("click", () => {
    haptic("medium");
    alert("Battle keyingi bosqichda qo‘shiladi.");
  });
});