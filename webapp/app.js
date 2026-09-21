/* ============================================================
   IQ TEST BOT — app.js (FINAL)
   IQ + EQ + PQ + Profile + Battle + Payment
   ============================================================ */

// ==================== TELEGRAM ====================
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  try {
    tg.setHeaderColor?.("#0a0e1a");
    tg.setBackgroundColor?.("#0a0e1a");
  } catch {}
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
    timerInterval: null,
  },
  settings: {},
  totalUsers: 0,
  onlineUsers: 0,
  sampleAnswered: false,
  battle: { id: null, code: null, role: null, players: [] },
  payment: { id: null, product: null, amount: 0, cards: [] },
};

// ==================== LOCAL STORAGE ====================
const LS_KEY = "iqtestbot_session_v2";

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
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function clearLocal() {
  try { localStorage.removeItem(LS_KEY); } catch {}
}

// ==================== 18 TA IQ SAVOLI ====================
const QUESTIONS = [
  // ===== EASY (Q1-Q6) weight 1 =====
  {
    id: 1, difficulty: "easy", weight: 1, category: "Raqamlar",
    matrix: [
      { type: "dot", count: 1 }, { type: "dot", count: 2 }, { type: "dot", count: 3 },
      { type: "dot", count: 2 }, { type: "dot", count: 3 }, { type: "dot", count: 4 },
      { type: "dot", count: 3 }, { type: "dot", count: 4 }, { type: "question" },
    ],
    options: [
      { type: "dot", count: 3 }, { type: "dot", count: 4 },
      { type: "dot", count: 5 }, { type: "dot", count: 6 },
    ],
    correct: 2,
  },
  {
    id: 2, difficulty: "easy", weight: 1, category: "Pattern",
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
    correct: 0,
  },
  {
    id: 3, difficulty: "easy", weight: 1, category: "Fazoviy fikr",
    matrix: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 90 }, { type: "rotate", angle: 180 },
      { type: "rotate", angle: 90 }, { type: "rotate", angle: 180 }, { type: "rotate", angle: 270 },
      { type: "rotate", angle: 180 }, { type: "rotate", angle: 270 }, { type: "question" },
    ],
    options: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 90 },
      { type: "rotate", angle: 270 }, { type: "rotate", angle: 360 },
    ],
    correct: 3,
  },
  {
    id: 4, difficulty: "easy", weight: 1, category: "Pattern",
    matrix: [
      { type: "size", size: 10 }, { type: "size", size: 20 }, { type: "size", size: 30 },
      { type: "size", size: 20 }, { type: "size", size: 30 }, { type: "size", size: 40 },
      { type: "size", size: 30 }, { type: "size", size: 40 }, { type: "question" },
    ],
    options: [
      { type: "size", size: 30 }, { type: "size", size: 40 },
      { type: "size", size: 50 }, { type: "size", size: 60 },
    ],
    correct: 2,
  },
  {
    id: 5, difficulty: "easy", weight: 1, category: "Mantiq",
    matrix: [
      { type: "grid", pos: 0 }, { type: "grid", pos: 1 }, { type: "grid", pos: 2 },
      { type: "grid", pos: 3 }, { type: "grid", pos: 4 }, { type: "grid", pos: 5 },
      { type: "grid", pos: 6 }, { type: "grid", pos: 7 }, { type: "question" },
    ],
    options: [
      { type: "grid", pos: 4 }, { type: "grid", pos: 6 },
      { type: "grid", pos: 7 }, { type: "grid", pos: 8 },
    ],
    correct: 3,
  },
  {
    id: 6, difficulty: "easy", weight: 1, category: "Pattern",
    matrix: [
      { type: "shape", shape: "circle", fill: "full" }, { type: "shape", shape: "square", fill: "full" }, { type: "shape", shape: "triangle", fill: "full" },
      { type: "shape", shape: "square", fill: "full" }, { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "circle", fill: "full" },
      { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "circle", fill: "full" }, { type: "question" },
    ],
    options: [
      { type: "shape", shape: "circle", fill: "full" },
      { type: "shape", shape: "square", fill: "full" },
      { type: "shape", shape: "triangle", fill: "full" },
      { type: "shape", shape: "diamond", fill: "full" },
    ],
    correct: 1,
  },
  // ===== MEDIUM (Q7-Q12) weight 2 =====
  {
    id: 7, difficulty: "medium", weight: 2, category: "Pattern",
    matrix: [
      { type: "combo", shapes: ["circle"], fill: "full" },
      { type: "combo", shapes: ["circle", "square"], fill: "full" },
      { type: "combo", shapes: ["circle", "square", "triangle"], fill: "full" },
      { type: "combo", shapes: ["square"], fill: "empty" },
      { type: "combo", shapes: ["square", "triangle"], fill: "empty" },
      { type: "combo", shapes: ["square", "triangle", "circle"], fill: "empty" },
      { type: "combo", shapes: ["triangle"], fill: "half" },
      { type: "combo", shapes: ["triangle", "circle"], fill: "half" },
      { type: "question" },
    ],
    options: [
      { type: "combo", shapes: ["triangle"], fill: "half" },
      { type: "combo", shapes: ["triangle", "circle", "square"], fill: "half" },
      { type: "combo", shapes: ["circle", "square"], fill: "half" },
      { type: "combo", shapes: ["triangle", "square"], fill: "half" },
    ],
    correct: 1,
  },
  {
    id: 8, difficulty: "medium", weight: 2, category: "Fazoviy fikr",
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
    correct: 2,
  },
  {
    id: 9, difficulty: "medium", weight: 2, category: "Raqamlar",
    matrix: [
      { type: "num", val: 2 }, { type: "num", val: 4 }, { type: "num", val: 6 },
      { type: "num", val: 3 }, { type: "num", val: 6 }, { type: "num", val: 9 },
      { type: "num", val: 4 }, { type: "num", val: 8 }, { type: "question" },
    ],
    options: [
      { type: "num", val: 10 }, { type: "num", val: 12 },
      { type: "num", val: 14 }, { type: "num", val: 16 },
    ],
    correct: 1,
  },
  {
    id: 10, difficulty: "medium", weight: 2, category: "Mantiq",
    matrix: [
      { type: "rotate", angle: 45 }, { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 },
      { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 }, { type: "rotate", angle: 180 },
      { type: "rotate", angle: 135 }, { type: "rotate", angle: 180 }, { type: "question" },
    ],
    options: [
      { type: "rotate", angle: 180 }, { type: "rotate", angle: 225 },
      { type: "rotate", angle: 270 }, { type: "rotate", angle: 315 },
    ],
    correct: 1,
  },
  {
    id: 11, difficulty: "medium", weight: 2, category: "Pattern",
    matrix: [
      { type: "dot", count: 1 }, { type: "dot", count: 4 }, { type: "dot", count: 9 },
      { type: "dot", count: 4 }, { type: "dot", count: 9 }, { type: "dot", count: 16 },
      { type: "dot", count: 9 }, { type: "dot", count: 16 }, { type: "question" },
    ],
    options: [
      { type: "dot", count: 20 }, { type: "dot", count: 25 },
      { type: "dot", count: 30 }, { type: "dot", count: 36 },
    ],
    correct: 1,
  },
  {
    id: 12, difficulty: "medium", weight: 2, category: "Fazoviy fikr",
    matrix: [
      { type: "grid", pos: 0 }, { type: "grid", pos: 2 }, { type: "grid", pos: 4 },
      { type: "grid", pos: 2 }, { type: "grid", pos: 4 }, { type: "grid", pos: 6 },
      { type: "grid", pos: 4 }, { type: "grid", pos: 6 }, { type: "question" },
    ],
    options: [
      { type: "grid", pos: 6 }, { type: "grid", pos: 7 },
      { type: "grid", pos: 8 }, { type: "grid", pos: 5 },
    ],
    correct: 2,
  },
  // ===== HARD (Q13-Q18) weight 3 =====
  {
    id: 13, difficulty: "hard", weight: 3, category: "Raqamlar",
    matrix: [
      { type: "num", val: 1 }, { type: "num", val: 1 }, { type: "num", val: 2 },
      { type: "num", val: 3 }, { type: "num", val: 5 }, { type: "num", val: 8 },
      { type: "num", val: 13 }, { type: "num", val: 21 }, { type: "question" },
    ],
    options: [
      { type: "num", val: 30 }, { type: "num", val: 34 },
      { type: "num", val: 38 }, { type: "num", val: 42 },
    ],
    correct: 1,
  },
  {
    id: 14, difficulty: "hard", weight: 3, category: "Pattern",
    matrix: [
      { type: "combo", shapes: ["circle"], fill: "full" },
      { type: "combo", shapes: ["circle", "square"], fill: "half" },
      { type: "combo", shapes: ["circle", "square", "triangle"], fill: "empty" },
      { type: "combo", shapes: ["square"], fill: "half" },
      { type: "combo", shapes: ["square", "triangle"], fill: "empty" },
      { type: "combo", shapes: ["square", "triangle", "circle"], fill: "full" },
      { type: "combo", shapes: ["triangle"], fill: "empty" },
      { type: "combo", shapes: ["triangle", "circle"], fill: "full" },
      { type: "question" },
    ],
    options: [
      { type: "combo", shapes: ["triangle", "circle", "square"], fill: "half" },
      { type: "combo", shapes: ["triangle"], fill: "full" },
      { type: "combo", shapes: ["circle", "square"], fill: "half" },
      { type: "combo", shapes: ["triangle", "square"], fill: "empty" },
    ],
    correct: 0,
  },
  {
    id: 15, difficulty: "hard", weight: 3, category: "Fazoviy fikr",
    matrix: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 45 }, { type: "rotate", angle: 90 },
      { type: "rotate", angle: 45 }, { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 },
      { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 }, { type: "question" },
    ],
    options: [
      { type: "rotate", angle: 135 }, { type: "rotate", angle: 180 },
      { type: "rotate", angle: 225 }, { type: "rotate", angle: 270 },
    ],
    correct: 1,
  },
  {
    id: 16, difficulty: "hard", weight: 3, category: "Raqamlar",
    matrix: [
      { type: "num", val: 3 }, { type: "num", val: 9 }, { type: "num", val: 27 },
      { type: "num", val: 2 }, { type: "num", val: 4 }, { type: "num", val: 8 },
      { type: "num", val: 5 }, { type: "num", val: 25 }, { type: "question" },
    ],
    options: [
      { type: "num", val: 100 }, { type: "num", val: 125 },
      { type: "num", val: 150 }, { type: "num", val: 625 },
    ],
    correct: 1,
  },
  {
    id: 17, difficulty: "hard", weight: 3, category: "Mantiq",
    matrix: [
      { type: "grid", pos: 0 }, { type: "grid", pos: 1 }, { type: "grid", pos: 3 },
      { type: "grid", pos: 1 }, { type: "grid", pos: 3 }, { type: "grid", pos: 5 },
      { type: "grid", pos: 3 }, { type: "grid", pos: 5 }, { type: "question" },
    ],
    options: [
      { type: "grid", pos: 5 }, { type: "grid", pos: 6 },
      { type: "grid", pos: 7 }, { type: "grid", pos: 8 },
    ],
    correct: 2,
  },
  {
    id: 18, difficulty: "hard", weight: 3, category: "Pattern",
    matrix: [
      { type: "combo", shapes: ["circle", "square"], fill: "full" },
      { type: "combo", shapes: ["square", "triangle"], fill: "half" },
      { type: "combo", shapes: ["triangle", "circle"], fill: "empty" },
      { type: "combo", shapes: ["square", "triangle"], fill: "half" },
      { type: "combo", shapes: ["triangle", "circle"], fill: "empty" },
      { type: "combo", shapes: ["circle", "square"], fill: "full" },
      { type: "combo", shapes: ["triangle", "circle"], fill: "empty" },
      { type: "combo", shapes: ["circle", "square"], fill: "full" },
      { type: "question" },
    ],
    options: [
      { type: "combo", shapes: ["circle", "square"], fill: "full" },
      { type: "combo", shapes: ["square", "triangle"], fill: "half" },
      { type: "combo", shapes: ["triangle", "circle"], fill: "empty" },
      { type: "combo", shapes: ["circle", "triangle"], fill: "half" },
    ],
    correct: 1,
  },
];

// ==================== EQ SAVOLLARI (6 ta) ====================
const EQ_QUESTIONS = [
  {
    id: 1, category: "stress",
    text: "Ishingiz juda ko‘payib ketdi va boshliq yana yangi topshiriq berdi. Siz nima qilasiz?",
    options: [
      "Darhol ro‘yxat tuzaman va muhimini ajrataman",
      "Asabiylashaman, lekin baribir boshlayman",
      "Boshliqqa vaqt yetmasligini aytaman",
      "Kechqurun qolib ishlayman",
    ],
    scores: [4, 2, 3, 1],
  },
  {
    id: 2, category: "empathy",
    text: "Do‘stingiz yig‘layapti va nima bo‘lganini aytmayapti. Siz:",
    options: [
      "Yoniga o‘tiraman va jim kutaman",
      "Darhol savol bera boshlayman",
      "Hazil qilib kayfiyatini ko‘taraman",
      "Uydan ketsam bo‘ladi deb o‘ylayman",
    ],
    scores: [4, 1, 2, 1],
  },
  {
    id: 3, category: "self-awareness",
    text: "Siz xato qildingiz va buni birinchi bo‘lib kim payqadi?",
    options: [
      "O‘zim, darhol tan olaman",
      "Boshqalar aytganda tan olaman",
      "Inkor qilaman",
      "Bahona topaman",
    ],
    scores: [4, 3, 1, 1],
  },
  {
    id: 4, category: "conflict",
    text: "Hamkasbingiz sizning fikringizni ochiq tanqid qildi. Siz:",
    options: [
      "Xotirjam tinglab, sababini so‘rayman",
      "Darhol javob qaytaraman",
      "Indamay qolaman",
      "Boshqalardan yordam so‘rayman",
    ],
    scores: [4, 2, 1, 2],
  },
  {
    id: 5, category: "emotion regulation",
    text: "Kutilmagan yomon xabar oldingiz. Birinchi harakatingiz:",
    options: [
      "Chuqur nafas olib, o‘zimni tutaman",
      "Darhol kimdirga aytaman",
      "Yolg‘iz qolaman",
      "Ishni tashlab ketaman",
    ],
    scores: [4, 2, 3, 1],
  },
  {
    id: 6, category: "social perception",
    text: "Suhbatdoshning ko‘zlari boshqa tomonga qarayapti. Bu nimani bildiradi?",
    options: [
      "U zerikkan yoki shoshilyapti",
      "U yolg‘on gapiryapti",
      "U sizni yoqtirmaydi",
      "Hech narsa, shunchaki shunday",
    ],
    scores: [4, 2, 1, 2],
  },
];

// ==================== PQ SAVOLLARI (6 ta) ====================
const PQ_QUESTIONS = [
  {
    id: 1, category: "task avoidance",
    text: "Muhim loyiha bor, lekin siz uni doim keyinga surasiz. Sabab:",
    options: [
      "Qiyin bo‘lgani uchun",
      "Vaqt ko‘p deb o‘ylayman",
      "Nima qilishni bilmayman",
      "Kayfiyat yo‘q",
    ],
    scores: [2, 1, 2, 1],
  },
  {
    id: 2, category: "delay",
    text: "Imtihonga 7 kun qoldi. Siz:",
    options: [
      "Har kuni oz-oz tayyorlanaman",
      "Oxirgi 2 kunda qattiq tayyorlanaman",
      "Oxirgi kechada tayyorlanaman",
      "Tayyorlanmayman, nima bo‘lsa bo‘lsin",
    ],
    scores: [4, 2, 1, 0],
  },
  {
    id: 3, category: "motivation",
    text: "Ishni boshlash uchun sizga nima kerak?",
    options: [
      "Aniq reja",
      "Kayfiyat",
      "Deadline",
      "Mukofot",
    ],
    scores: [4, 1, 2, 2],
  },
  {
    id: 4, category: "distraction",
    text: "Ishlayotganingizda telefonni tez-tez tekshirasizmi?",
    options: [
      "Yo‘q, telefon boshqa xonada",
      "Ba‘zan, lekin o‘zimni tutaman",
      "Ha, har 10 daqiqada",
      "Doim qo‘limda",
    ],
    scores: [4, 3, 1, 0],
  },
  {
    id: 5, category: "deadline",
    text: "Deadline yaqinlashganda siz:",
    options: [
      "Avvaldan tayyor bo‘laman",
      "Oxirgi paytda tezlashaman",
      "Kechikaman",
      "Umuman bajarmayman",
    ],
    scores: [4, 2, 1, 0],
  },
  {
    id: 6, category: "self-control",
    text: "Rejangizni qanchalik bajarasiz?",
    options: [
      "Doim bajaraman",
      "Ko‘pincha bajaraman",
      "Ba‘zan bajaraman",
      "Deyarli hech qachon",
    ],
    scores: [4, 3, 1, 0],
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
    return `<span style="font-size:22px;font-weight:800;color:#a78bfa;">${cell.val}</span>`;
  }

  if (cell.type === "shape") {
    const colors = { full: "#a78bfa", half: "rgba(167,139,250,.5)", empty: "transparent" };
    const fill = colors[cell.fill] || "transparent";
    if (cell.shape === "circle") return `<svg width="40" height="40"><circle cx="20" cy="20" r="16" fill="${fill}" stroke="#a78bfa" stroke-width="2"/></svg>`;
    if (cell.shape === "square") return `<svg width="40" height="40"><rect x="5" y="5" width="30" height="30" rx="4" fill="${fill}" stroke="#a78bfa" stroke-width="2"/></svg>`;
    if (cell.shape === "triangle") return `<svg width="40" height="40"><polygon points="20,5 35,35 5,35" fill="${fill}" stroke="#a78bfa" stroke-width="2"/></svg>`;
    if (cell.shape === "diamond") return `<svg width="40" height="40"><polygon points="20,4 36,20 20,36 4,20" fill="${fill}" stroke="#a78bfa" stroke-width="2"/></svg>`;
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

  if (cell.type === "size") {
    const s = cell.size;
    return `<svg width="40" height="40"><circle cx="20" cy="20" r="${s / 2}" fill="none" stroke="#a78bfa" stroke-width="2"/></svg>`;
  }

  if (cell.type === "grid") {
    const pos = cell.pos;
    const row = Math.floor(pos / 3);
    const col = pos % 3;
    return `<svg width="40" height="40">
      <rect x="2" y="2" width="36" height="36" rx="3" fill="none" stroke="rgba(167,139,250,.3)" stroke-width="1.5"/>
      <circle cx="${8 + col * 12}" cy="${8 + row * 12}" r="5" fill="#a78bfa"/>
    </svg>`;
  }

  return "";
}

function renderMatrix(el, cells) {
  if (!el) return;
  el.innerHTML = cells.map(c => `<div class="cell ${c.type === 'question' ? 'question' : ''}">${renderCell(c)}</div>`).join("");
}

function renderOptions(el, options, onSelect) {
  if (!el) return;
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

function renderTextOptions(el, options, onSelect) {
  if (!el) return;
  el.innerHTML = options.map((o, i) => `<div class="option text-option" data-idx="${i}"><span class="opt-letter">${String.fromCharCode(65 + i)}</span><span class="opt-text">${o}</span></div>`).join("");
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
    const cfg = await api("/api/config", null, "GET");
    if (cfg.ok) State.settings = cfg.settings;

    await this.refreshLive();

    if (initData) {
      const me = await api("/api/me", { initData });
      if (me.ok) {
        State.user = me.user;
        State.completed = me.completed || {};
        this.applyUnlocks();
      }
    }

    const local = loadLocal();
    if (local && local.sessionId && local.current > 0 && local.current < 18 && local.type === "iq") {
      setTimeout(() => {
        if (confirm("Test davom etmoqda. Davom ettirishni xohlaysizmi?")) {
          State.test = Object.assign({}, State.test, local);
          if (!Array.isArray(State.test.answers) || State.test.answers.length !== 18) {
            State.test.answers = new Array(18).fill(null);
          }
          this.go("test");
          this.renderQuestion();
          this.startTimer();
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
      const onlineEl = document.getElementById("live-online");
      if (onlineEl) onlineEl.textContent = res.online;
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
    const el = document.getElementById("screen-" + screen);
    if (el) el.classList.add("active");
    State.currentScreen = screen;
    haptic("light");
    window.scrollTo(0, 0);
  },

  applyUnlocks() {
    const c = State.completed;
    if (c.iq) {
      const el = document.getElementById("card-eq");
      if (el) {
        el.classList.remove("locked");
        el.classList.add("unlocked");
        const s = el.querySelector(".card-state");
        if (s) s.textContent = "🔓";
      }
    }
    if (c.eq) {
      const el = document.getElementById("card-pq");
      if (el) {
        el.classList.remove("locked");
        el.classList.add("unlocked");
        const s = el.querySelector(".card-state");
        if (s) s.textContent = "🔓";
      }
    }
    if (c.iq && c.eq && c.pq) {
      const el = document.getElementById("card-profile");
      if (el) {
        el.classList.remove("locked");
        el.classList.add("unlocked");
        const s = el.querySelector(".card-state");
        if (s) s.textContent = "🔓";
      }
    }
  },

  // ==================== IQ ====================
  async startIQ() {
    haptic("medium");
    if (initData) {
      const res = await api("/api/session/start", { initData, test_type: "iq" });
      if (res.ok) {
        State.test.sessionId = res.session_id;
        State.test.attemptId = res.attempt_id;
      }
    }
    State.test.type = "iq";
    State.test.current = 0;
    State.test.answers = new Array(18).fill(null);
    State.test.startedAt = Date.now();
    State.test.duration = 0;
    saveLocal();
    this.go("sample");
    this.renderSample();
  },

  renderSample() {
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
    const nextBtn = document.getElementById("sample-next");
    if (nextBtn) nextBtn.disabled = true;
    renderOptions(document.getElementById("sample-options"), sample.options, (idx) => {
      State.sampleAnswered = true;
      if (nextBtn) nextBtn.disabled = false;
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
    const pct = (State.test.current / 18) * 100;
    document.getElementById("progress-fill").style.width = pct + "%";

    const diff = document.getElementById("difficulty-bar");
    let diffHtml = "";
    for (let i = 0; i < 18; i++) {
      let cls = "easy";
      if (i >= 12) cls = "hard";
      else if (i >= 6) cls = "medium";
      if (i <= State.test.current) diffHtml += `<span class="${cls}"></span>`;
      else diffHtml += `<span></span>`;
    }
    if (diff) diff.innerHTML = diffHtml;

    renderMatrix(document.getElementById("test-matrix"), q.matrix);
    const nextBtn = document.getElementById("test-next");
    if (nextBtn) {
      nextBtn.disabled = true;
      nextBtn.textContent = State.test.current === 17 ? "YAKUNLASH →" : "KEYINGISI →";
    }

    renderOptions(document.getElementById("test-options"), q.options, (idx) => {
      State.test.answers[State.test.current] = idx;
      if (nextBtn) nextBtn.disabled = false;
      saveLocal();
    });

    if (State.test.answers[State.test.current] !== null && State.test.answers[State.test.current] !== undefined) {
      const prev = State.test.answers[State.test.current];
      const optEl = document.querySelectorAll("#test-options .option")[prev];
      if (optEl) optEl.classList.add("selected");
      if (nextBtn) nextBtn.disabled = false;
    }
  },

  nextQuestion() {
    haptic("light");
    const cur = State.test.current;
    // Celebration 1 (Q6 dan keyin)
    if (cur === 5) { this.go("q6"); return; }
    // Celebration 2 (Q12 dan keyin)
    if (cur === 11) { this.go("q12"); return; }
    // Test tugadi
    if (cur === 17) { this.finish(); return; }
    State.test.current++;
    saveLocal();
    this.renderQuestion();
  },

  continueAfterQ6() {
    State.test.current = 6;
    saveLocal();
    this.go("test");
    this.renderQuestion();
  },

  continueAfterQ12() {
    State.test.current = 12;
    saveLocal();
    this.go("test");
    this.renderQuestion();
  },

  async finish() {
    clearInterval(State.test.timerInterval);
    this.go("loading");
    await new Promise(r => setTimeout(r, 2200));

    let score = 0, correct = 0, level = "—";
    if (initData && State.test.sessionId) {
      const res = await api("/api/test/submit", {
        initData,
        session_id: State.test.sessionId,
        answers: State.test.answers,
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
      let weighted = 0, maxW = 0;
      QUESTIONS.forEach((q, i) => {
        maxW += q.weight;
        if (State.test.answers[i] === q.correct) weighted += q.weight;
      });
      correct = State.test.answers.filter((a, i) => a === QUESTIONS[i].correct).length;
      score = Math.round(70 + (weighted / maxW) * 60);
      level = score >= 115 ? "YUQORI DARAJA" : score >= 100 ? "O‘RTA DARAJA" : "RIVOJLANTIRISH";
    }

    this.renderResult(score, correct, level);
    this.go("result");
    clearLocal();
    this.applyUnlocks();
  },

  renderResult(score, correct, level) {
    document.getElementById("res-score").textContent = score;
    document.getElementById("res-level").textContent = level;
    document.getElementById("res-correct").textContent = `${correct} / 18`;
    const m = String(Math.floor(State.test.duration / 60)).padStart(2, "0");
    const s = String(State.test.duration % 60).padStart(2, "0");
    document.getElementById("res-time").textContent = `${m}:${s}`;

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
      setTimeout(() => { if (fill) fill.style.width = d.val + "%"; }, 100 + i * 150);
      if (span) span.textContent = Math.round(d.val) + "%";
    });
    const strongest = dirs.reduce((a, b) => a.val > b.val ? a : b);
    const stEl = document.getElementById("res-strongest");
    if (stEl) stEl.textContent = strongest.label;
  },

  async getCertificate() {
    if (!initData) { alert("Sertifikat Telegram orqali yuboriladi."); return; }
    haptic("medium");
    alert("Sertifikat Telegram bot orqali yuboriladi.\n\n/start → 📜 Sertifikatim");
  },

  shareResult() {
    const score = document.getElementById("res-score")?.textContent || "0";
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
    State.test = { type: "iq", sessionId: null, attemptId: null, current: 0, answers: [], startedAt: null, duration: 0, timerInterval: null };
    this.go("intro");
  },

  // ==================== EQ ====================
  async startEQ() {
    haptic("medium");
    if (initData) {
      const res = await api("/api/session/start", { initData, test_type: "eq" });
      if (res.ok) {
        State.test.sessionId = res.session_id;
        State.test.attemptId = res.attempt_id;
      }
    }
    State.test.type = "eq";
    State.test.current = 0;
    State.test.answers = new Array(EQ_QUESTIONS.length).fill(null);
    State.test.startedAt = Date.now();
    this.go("eq-intro");
  },

  goEQTest() {
    this.go("eq-test");
    this.renderEQQuestion();
  },

  renderEQQuestion() {
    const q = EQ_QUESTIONS[State.test.current];
    if (!q) return;
    document.getElementById("eq-progress-text").textContent = `Q${State.test.current + 1} / ${EQ_QUESTIONS.length}`;
    const pct = (State.test.current / EQ_QUESTIONS.length) * 100;
    const pf = document.getElementById("eq-progress-fill");
    if (pf) pf.style.width = pct + "%";
    const qt = document.getElementById("eq-question-text");
    if (qt) qt.textContent = q.text;
    const nextBtn = document.getElementById("eq-next");
    if (nextBtn) {
      nextBtn.disabled = true;
      nextBtn.textContent = State.test.current === EQ_QUESTIONS.length - 1 ? "YAKUNLASH →" : "KEYINGISI →";
    }
    renderTextOptions(document.getElementById("eq-options"), q.options, (idx) => {
      State.test.answers[State.test.current] = idx;
      if (nextBtn) nextBtn.disabled = false;
    });
    if (State.test.answers[State.test.current] !== null && State.test.answers[State.test.current] !== undefined) {
      const prev = State.test.answers[State.test.current];
      const el = document.querySelectorAll("#eq-options .option")[prev];
      if (el) el.classList.add("selected");
      if (nextBtn) nextBtn.disabled = false;
    }
  },

  nextEQQuestion() {
    haptic("light");
    if (State.test.current === EQ_QUESTIONS.length - 1) {
      this.finishEQ();
      return;
    }
    State.test.current++;
    this.renderEQQuestion();
  },

  async finishEQ() {
    this.go("loading");
    await new Promise(r => setTimeout(r, 2000));

    let score = 0;
    EQ_QUESTIONS.forEach((q, i) => {
      const ans = State.test.answers[i];
      if (ans !== null && ans !== undefined) score += q.scores[ans];
    });
    const maxScore = EQ_QUESTIONS.length * 4;
    const percent = Math.round((score / maxScore) * 100);
    State.completed.eq = percent;

    document.getElementById("eq-res-score").textContent = percent;
    document.getElementById("eq-res-level").textContent =
      percent >= 80 ? "JUDA YUQORI" : percent >= 60 ? "YUQORI" : percent >= 40 ? "O‘RTA" : "RIVOJLANTIRISH";
    this.go("eq-result");
    this.applyUnlocks();
  },

  // ==================== PQ ====================
  async startPQ() {
    haptic("medium");
    if (initData) {
      const res = await api("/api/session/start", { initData, test_type: "pq" });
      if (res.ok) {
        State.test.sessionId = res.session_id;
        State.test.attemptId = res.attempt_id;
      }
    }
    State.test.type = "pq";
    State.test.current = 0;
    State.test.answers = new Array(PQ_QUESTIONS.length).fill(null);
    this.go("pq-intro");
  },

  goPQTest() {
    this.go("pq-test");
    this.renderPQQuestion();
  },

  renderPQQuestion() {
    const q = PQ_QUESTIONS[State.test.current];
    if (!q) return;
    document.getElementById("pq-progress-text").textContent = `Q${State.test.current + 1} / ${PQ_QUESTIONS.length}`;
    const pct = (State.test.current / PQ_QUESTIONS.length) * 100;
    const pf = document.getElementById("pq-progress-fill");
    if (pf) pf.style.width = pct + "%";
    const qt = document.getElementById("pq-question-text");
    if (qt) qt.textContent = q.text;
    const nextBtn = document.getElementById("pq-next");
    if (nextBtn) {
      nextBtn.disabled = true;
      nextBtn.textContent = State.test.current === PQ_QUESTIONS.length - 1 ? "YAKUNLASH →" : "KEYINGISI →";
    }
    renderTextOptions(document.getElementById("pq-options"), q.options, (idx) => {
      State.test.answers[State.test.current] = idx;
      if (nextBtn) nextBtn.disabled = false;
    });
    if (State.test.answers[State.test.current] !== null && State.test.answers[State.test.current] !== undefined) {
      const prev = State.test.answers[State.test.current];
      const el = document.querySelectorAll("#pq-options .option")[prev];
      if (el) el.classList.add("selected");
      if (nextBtn) nextBtn.disabled = false;
    }
  },

  nextPQQuestion() {
    haptic("light");
    if (State.test.current === PQ_QUESTIONS.length - 1) {
      this.finishPQ();
      return;
    }
    State.test.current++;
    this.renderPQQuestion();
  },

  async finishPQ() {
    this.go("loading");
    await new Promise(r => setTimeout(r, 2000));

    let score = 0;
    PQ_QUESTIONS.forEach((q, i) => {
      const ans = State.test.answers[i];
      if (ans !== null && ans !== undefined) score += q.scores[ans];
    });
    const maxScore = PQ_QUESTIONS.length * 4;
    const percent = Math.round((score / maxScore) * 100);
    State.completed.pq = percent;

    document.getElementById("pq-res-score").textContent = percent;
    document.getElementById("pq-res-level").textContent =
      percent >= 80 ? "JUDA YAXSHI" : percent >= 60 ? "YAXSHI" : percent >= 40 ? "O‘RTA" : "RIVOJLANTIRISH KERAK";
    this.go("pq-result");
    this.applyUnlocks();
  },

  // ==================== PROFILE ====================
  openProfile() {
    if (!(State.completed.iq && State.completed.eq && State.completed.pq)) {
      alert("Avval IQ, EQ va PQ testlarini tugatishingiz kerak.");
      return;
    }
    const iq = State.completed.iq;
    const eq = State.completed.eq;
    const pq = State.completed.pq;

    document.getElementById("prof-iq").textContent = iq;
    document.getElementById("prof-eq").textContent = eq + "%";
    document.getElementById("prof-pq").textContent = pq + "%";

    const strengths = [];
    const weaknesses = [];
    if (iq >= 115) strengths.push("Kuchli mantiqiy fikrlash");
    else weaknesses.push("Mantiqiy fikrlashni rivojlantirish");
    if (eq >= 70) strengths.push("Yaxshi hissiy intellekt");
    else weaknesses.push("Emotsiyalarni boshqarish");
    if (pq >= 70) strengths.push("Ishni o‘z vaqtida bajarish");
    else weaknesses.push("Prokrastinatsiyani kamaytirish");

    document.getElementById("prof-strengths").innerHTML = strengths.map(s => `<li>✅ ${s}</li>`).join("") || "<li>—</li>";
    document.getElementById("prof-weaknesses").innerHTML = weaknesses.map(s => `<li>⚠️ ${s}</li>`).join("") || "<li>—</li>";

    const overall = Math.round(((iq - 70) / 60 * 100) * 0.5 + eq * 0.25 + pq * 0.25);
    document.getElementById("prof-overall").textContent = overall;
    document.getElementById("prof-summary").textContent =
      overall >= 75 ? "Siz analitik va hissiy jihatdan kuchli insonsiz." :
      overall >= 55 ? "Sizning profilingiz o‘rtacha, rivojlanish uchun joy bor." :
      "Sizga bir nechta yo‘nalishda rivojlanish kerak.";

    this.go("profile");
  },

  // ==================== BATTLE ====================
  openBattle() {
    this.go("battle-home");
  },

  async createBattle() {
    if (!initData) { alert("Battle faqat Telegram orqali."); return; }
    haptic("medium");
    const res = await api("/api/battle/create", { initData });
    if (res.ok) {
      State.battle.id = res.battle_id;
      State.battle.code = res.code;
      State.battle.role = "creator";
      document.getElementById("battle-code-display").textContent = res.code;
      this.go("battle-wait");
    } else {
      alert("Battle yaratishda xatolik.");
    }
  },

  async joinBattle() {
    if (!initData) { alert("Battle faqat Telegram orqali."); return; }
    const code = document.getElementById("battle-join-code").value.trim();
    if (!/^\d{4}$/.test(code)) { alert("4 xonali kod kiriting."); return; }
    haptic("medium");
    const res = await api("/api/battle/join", { initData, code });
    if (res.ok) {
      State.battle.id = res.battle_id;
      State.battle.code = code;
      State.battle.role = "opponent";
      this.go("battle-wait");
    } else {
      alert("Kod topilmadi yoki xatolik.");
    }
  },

  async checkBattle() {
    if (!State.battle.id) return;
    const res = await api(`/api/battle/${State.battle.id}`, { initData });
    if (res.ok) {
      State.battle.players = res.players || [];
      const bothJoined = State.battle.players.length >= 2;
      const bothPaid = State.battle.players.every(p => p.payment_status === "approved");
      const statusEl = document.getElementById("battle-wait-status");
      if (bothJoined && bothPaid) {
        this.startBattleTest();
      } else if (bothJoined) {
        if (statusEl) statusEl.textContent = "To‘lovni kuting...";
      }
    }
  },

  startBattleTest() {
    this.go("battle-test");
    State.test.type = "battle";
    State.test.current = 0;
    State.test.answers = new Array(18).fill(null);
    State.test.startedAt = Date.now();
    this.renderBattleQuestion();
  },

  renderBattleQuestion() {
    const q = QUESTIONS[State.test.current];
    if (!q) return;
    document.getElementById("battle-progress-text").textContent = `Q${State.test.current + 1} / 18`;
    renderMatrix(document.getElementById("battle-matrix"), q.matrix);
    const nextBtn = document.getElementById("battle-next");
    if (nextBtn) {
      nextBtn.disabled = true;
      nextBtn.textContent = State.test.current === 17 ? "YAKUNLASH →" : "KEYINGISI →";
    }
    renderOptions(document.getElementById("battle-options"), q.options, (idx) => {
      State.test.answers[State.test.current] = idx;
      if (nextBtn) nextBtn.disabled = false;
    });
  },

  nextBattleQuestion() {
    haptic("light");
    if (State.test.current === 17) { this.finishBattle(); return; }
    State.test.current++;
    this.renderBattleQuestion();
  },

  async finishBattle() {
    const correct = State.test.answers.filter((a, i) => a === QUESTIONS[i].correct).length;
    const score = Math.round(70 + (correct / 18) * 60);
    const res = await api(`/api/battle/${State.battle.id}/finish`, {
      initData, score, answers: State.test.answers
    });
    this.go("battle-result");
    document.getElementById("battle-my-score").textContent = score;
    if (res.ok && res.opponent_score) {
      document.getElementById("battle-opp-score").textContent = res.opponent_score;
      if (score > res.opponent_score) document.getElementById("battle-winner").textContent = "🏆 SIZ";
      else if (score < res.opponent_score) document.getElementById("battle-winner").textContent = "😔 DO‘STINGIZ";
      else document.getElementById("battle-winner").textContent = "🤝 DURANG";
    } else {
      document.getElementById("battle-opp-score").textContent = "Kutilyapti...";
      document.getElementById("battle-winner").textContent = "⏳";
    }
  },

  // ==================== PAYMENT ====================
  async createPayment(product) {
    if (!initData) { alert("To‘lov faqat Telegram orqali."); return; }
    haptic("medium");
    const res = await api("/api/payment/create", { initData, product });
    if (res.ok) {
      State.payment.id = res.payment_id;
      State.payment.product = product;
      State.payment.amount = res.amount;
      State.payment.cards = res.cards;
      document.getElementById("pay-amount").textContent = res.amount.toLocaleString() + " so‘m";
      const cardsEl = document.getElementById("pay-cards");
      if (cardsEl) {
        cardsEl.innerHTML = res.cards.map(c =>
          `<div class="pay-card"><div class="pay-card-num">${c.card_number}</div><div class="pay-card-holder">${c.holder}</div><div class="pay-card-bank">${c.bank || ""}</div></div>`
        ).join("") || "<div>Karta mavjud emas. Admin bilan bog‘laning.</div>";
      }
      this.go("payment");
    } else {
      alert("To‘lov yaratishda xatolik.");
    }
  },

  async sendReceipt() {
    alert("Chekni Telegram botga yuboring:\n\n/start → to‘lov bo‘limi → chek rasmini yuboring");
  },
};

// ==================== EVENT BINDINGS ====================
document.addEventListener("DOMContentLoaded", () => {
  App.init();

  document.querySelector('[data-test="iq"]')?.addEventListener("click", () => {
    haptic("medium");
    App.go("intro");
  });

  document.getElementById("card-eq")?.addEventListener("click", () => {
    const el = document.getElementById("card-eq");
    if (el?.classList.contains("locked")) { haptic("rigid"); return; }
    haptic("medium");
    App.startEQ();
  });

  document.getElementById("card-pq")?.addEventListener("click", () => {
    const el = document.getElementById("card-pq");
    if (el?.classList.contains("locked")) { haptic("rigid"); return; }
    haptic("medium");
    App.startPQ();
  });

  document.getElementById("card-profile")?.addEventListener("click", () => {
    const el = document.getElementById("card-profile");
    if (el?.classList.contains("locked")) { haptic("rigid"); return; }
    haptic("medium");
    App.openProfile();
  });

  document.getElementById("battle-card")?.addEventListener("click", () => {
    haptic("medium");
    App.openBattle();
  });
});