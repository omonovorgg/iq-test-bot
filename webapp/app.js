/* ============================================================
   IQ TEST BOT — app.js (FINAL v1.0)
   ============================================================ */
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  try {
    tg.setHeaderColor?.("#0a0e1a");
    tg.setBackgroundColor?.("#0a0e1a");
  } catch {}
}

// initData ni olish (kechikish bilan)
let initData = tg?.initData || "";
setTimeout(() => {
  if (!initData && tg?.initData) {
    initData = tg.initData;
    console.log("[initData] delayed loaded, len =", initData.length);
  }
}, 500);


function haptic(type = "light") {
  try { tg?.HapticFeedback?.impactOccurred(type); } catch {}
}

async function api(path, body = null, method = "POST") {
  try {
    const currentInitData = tg?.initData || initData || "";
    const payload = body ? { ...body, initData: currentInitData } : null;
    const res = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: payload ? JSON.stringify(payload) : null,
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
  settings: {},
  test: {
    type: "iq",
    sessionId: null,
    attemptId: null,
    current: 0,
    answers: [],
    startedAt: null,
    duration: 0,
    timerInterval: null,
    resultData: null,
  },
  battle: {
    id: null,
    code: null,
    role: null,
    players: [],
    sessionId: null,
    current: 0,
    answers: [],
    startedAt: null,
    pollInterval: null,
  },
  payment: {
    id: null,
    product: null,
    amount: 0,
    cards: [],
    pollInterval: null,
    attemptId: null,
    battleId: null,
  },
  live: { interval: null },
  profile: {
    full_name: "",
    gender: null,
    age: null,
    country: null,
  },
};

const LS_KEY = "iqtestbot_state_v4";

function saveLocal() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      test: State.test,
      battle: State.battle,
      profile: State.profile,
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

// ==================== 18 IQ QUESTIONS ====================
const QUESTIONS = [
  { id: 1, difficulty: "easy", weight: 1,
    matrix: [
      { type: "dot", count: 1 }, { type: "dot", count: 2 }, { type: "dot", count: 3 },
      { type: "dot", count: 2 }, { type: "dot", count: 3 }, { type: "dot", count: 4 },
      { type: "dot", count: 3 }, { type: "dot", count: 4 }, { type: "question" },
    ],
    options: [
      { type: "dot", count: 3 }, { type: "dot", count: 4 },
      { type: "dot", count: 5 }, { type: "dot", count: 6 },
    ], correct: 2 },
  { id: 2, difficulty: "easy", weight: 1,
    matrix: [
      { type: "shape", shape: "circle", fill: "empty" }, { type: "shape", shape: "square", fill: "empty" }, { type: "shape", shape: "triangle", fill: "empty" },
      { type: "shape", shape: "square", fill: "empty" }, { type: "shape", shape: "triangle", fill: "empty" }, { type: "shape", shape: "circle", fill: "empty" },
      { type: "shape", shape: "triangle", fill: "empty" }, { type: "shape", shape: "circle", fill: "empty" }, { type: "question" },
    ],
    options: [
      { type: "shape", shape: "square", fill: "empty" }, { type: "shape", shape: "circle", fill: "empty" },
      { type: "shape", shape: "triangle", fill: "empty" }, { type: "shape", shape: "diamond", fill: "empty" },
    ], correct: 0 },
  { id: 3, difficulty: "easy", weight: 1,
    matrix: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 90 }, { type: "rotate", angle: 180 },
      { type: "rotate", angle: 90 }, { type: "rotate", angle: 180 }, { type: "rotate", angle: 270 },
      { type: "rotate", angle: 180 }, { type: "rotate", angle: 270 }, { type: "question" },
    ],
    options: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 90 },
      { type: "rotate", angle: 270 }, { type: "rotate", angle: 360 },
    ], correct: 3 },
  { id: 4, difficulty: "easy", weight: 1,
    matrix: [
      { type: "size", size: 12 }, { type: "size", size: 20 }, { type: "size", size: 28 },
      { type: "size", size: 20 }, { type: "size", size: 28 }, { type: "size", size: 36 },
      { type: "size", size: 28 }, { type: "size", size: 36 }, { type: "question" },
    ],
    options: [
      { type: "size", size: 28 }, { type: "size", size: 36 },
      { type: "size", size: 44 }, { type: "size", size: 52 },
    ], correct: 2 },
  { id: 5, difficulty: "easy", weight: 1,
    matrix: [
      { type: "grid", pos: 0 }, { type: "grid", pos: 1 }, { type: "grid", pos: 2 },
      { type: "grid", pos: 3 }, { type: "grid", pos: 4 }, { type: "grid", pos: 5 },
      { type: "grid", pos: 6 }, { type: "grid", pos: 7 }, { type: "question" },
    ],
    options: [
      { type: "grid", pos: 4 }, { type: "grid", pos: 6 },
      { type: "grid", pos: 7 }, { type: "grid", pos: 8 },
    ], correct: 3 },
  { id: 6, difficulty: "easy", weight: 1,
    matrix: [
      { type: "shape", shape: "circle", fill: "full" }, { type: "shape", shape: "square", fill: "full" }, { type: "shape", shape: "triangle", fill: "full" },
      { type: "shape", shape: "square", fill: "full" }, { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "circle", fill: "full" },
      { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "circle", fill: "full" }, { type: "question" },
    ],
    options: [
      { type: "shape", shape: "circle", fill: "full" }, { type: "shape", shape: "square", fill: "full" },
      { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "diamond", fill: "full" },
    ], correct: 1 },
  { id: 7, difficulty: "medium", weight: 2,
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
    ], correct: 1 },
  { id: 8, difficulty: "medium", weight: 2,
    matrix: [
      { type: "shape", shape: "circle", fill: "full" }, { type: "shape", shape: "circle", fill: "half" }, { type: "shape", shape: "circle", fill: "empty" },
      { type: "shape", shape: "square", fill: "full" }, { type: "shape", shape: "square", fill: "half" }, { type: "shape", shape: "square", fill: "empty" },
      { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "triangle", fill: "half" }, { type: "question" },
    ],
    options: [
      { type: "shape", shape: "triangle", fill: "full" }, { type: "shape", shape: "triangle", fill: "half" },
      { type: "shape", shape: "triangle", fill: "empty" }, { type: "shape", shape: "circle", fill: "empty" },
    ], correct: 2 },
  { id: 9, difficulty: "medium", weight: 2,
    matrix: [
      { type: "num", val: 2 }, { type: "num", val: 4 }, { type: "num", val: 6 },
      { type: "num", val: 3 }, { type: "num", val: 6 }, { type: "num", val: 9 },
      { type: "num", val: 4 }, { type: "num", val: 8 }, { type: "question" },
    ],
    options: [
      { type: "num", val: 10 }, { type: "num", val: 12 },
      { type: "num", val: 14 }, { type: "num", val: 16 },
    ], correct: 1 },
  { id: 10, difficulty: "medium", weight: 2,
    matrix: [
      { type: "rotate", angle: 45 }, { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 },
      { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 }, { type: "rotate", angle: 180 },
      { type: "rotate", angle: 135 }, { type: "rotate", angle: 180 }, { type: "question" },
    ],
    options: [
      { type: "rotate", angle: 180 }, { type: "rotate", angle: 225 },
      { type: "rotate", angle: 270 }, { type: "rotate", angle: 315 },
    ], correct: 1 },
  { id: 11, difficulty: "medium", weight: 2,
    matrix: [
      { type: "dot", count: 1 }, { type: "dot", count: 4 }, { type: "dot", count: 9 },
      { type: "dot", count: 4 }, { type: "dot", count: 9 }, { type: "dot", count: 16 },
      { type: "dot", count: 9 }, { type: "dot", count: 16 }, { type: "question" },
    ],
    options: [
      { type: "dot", count: 16 }, { type: "dot", count: 25 },
      { type: "dot", count: 36 }, { type: "dot", count: 49 },
    ], correct: 1 },
  { id: 12, difficulty: "medium", weight: 2,
    matrix: [
      { type: "grid", pos: 0 }, { type: "grid", pos: 2 }, { type: "grid", pos: 4 },
      { type: "grid", pos: 2 }, { type: "grid", pos: 4 }, { type: "grid", pos: 6 },
      { type: "grid", pos: 4 }, { type: "grid", pos: 6 }, { type: "question" },
    ],
    options: [
      { type: "grid", pos: 6 }, { type: "grid", pos: 7 },
      { type: "grid", pos: 8 }, { type: "grid", pos: 5 },
    ], correct: 2 },
  { id: 13, difficulty: "hard", weight: 3,
    matrix: [
      { type: "num", val: 1 }, { type: "num", val: 1 }, { type: "num", val: 2 },
      { type: "num", val: 3 }, { type: "num", val: 5 }, { type: "num", val: 8 },
      { type: "num", val: 13 }, { type: "num", val: 21 }, { type: "question" },
    ],
    options: [
      { type: "num", val: 30 }, { type: "num", val: 34 },
      { type: "num", val: 38 }, { type: "num", val: 42 },
    ], correct: 1 },
  { id: 14, difficulty: "hard", weight: 3,
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
    ], correct: 0 },
  { id: 15, difficulty: "hard", weight: 3,
    matrix: [
      { type: "rotate", angle: 0 }, { type: "rotate", angle: 45 }, { type: "rotate", angle: 90 },
      { type: "rotate", angle: 45 }, { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 },
      { type: "rotate", angle: 90 }, { type: "rotate", angle: 135 }, { type: "question" },
    ],
    options: [
      { type: "rotate", angle: 135 }, { type: "rotate", angle: 180 },
      { type: "rotate", angle: 225 }, { type: "rotate", angle: 270 },
    ], correct: 1 },
  { id: 16, difficulty: "hard", weight: 3,
    matrix: [
      { type: "num", val: 3 }, { type: "num", val: 9 }, { type: "num", val: 27 },
      { type: "num", val: 2 }, { type: "num", val: 4 }, { type: "num", val: 8 },
      { type: "num", val: 5 }, { type: "num", val: 25 }, { type: "question" },
    ],
    options: [
      { type: "num", val: 100 }, { type: "num", val: 125 },
      { type: "num", val: 150 }, { type: "num", val: 625 },
    ], correct: 1 },
  { id: 17, difficulty: "hard", weight: 3,
    matrix: [
      { type: "grid", pos: 0 }, { type: "grid", pos: 1 }, { type: "grid", pos: 3 },
      { type: "grid", pos: 1 }, { type: "grid", pos: 3 }, { type: "grid", pos: 5 },
      { type: "grid", pos: 3 }, { type: "grid", pos: 5 }, { type: "question" },
    ],
    options: [
      { type: "grid", pos: 5 }, { type: "grid", pos: 6 },
      { type: "grid", pos: 7 }, { type: "grid", pos: 8 },
    ], correct: 2 },
  { id: 18, difficulty: "hard", weight: 3,
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
    ], correct: 1 },
];

// ==================== EQ 6 ====================
const EQ_QUESTIONS = [
  { id: 1, text: "Ishingiz juda ko‘payib ketdi va boshliq yana yangi topshiriq berdi. Siz nima qilasiz?", options: ["Darhol ro‘yxat tuzaman va muhimini ajrataman", "Asabiylashaman, lekin baribir boshlayman", "Boshliqqa vaqt yetmasligini aytaman", "Kechqurun qolib ishlayman"], scores: [4, 2, 3, 1] },
  { id: 2, text: "Do‘stingiz yig‘layapti va nima bo‘lganini aytmayapti. Siz:", options: ["Yoniga o‘tiraman va jim kutaman", "Darhol savol bera boshlayman", "Hazil qilib kayfiyatini ko‘taraman", "Uydan ketsam bo‘ladi deb o‘ylayman"], scores: [4, 1, 2, 1] },
  { id: 3, text: "Siz xato qildingiz va buni birinchi bo‘lib kim payqadi?", options: ["O‘zim, darhol tan olaman", "Boshqalar aytganda tan olaman", "Inkor qilaman", "Bahona topaman"], scores: [4, 3, 1, 1] },
  { id: 4, text: "Hamkasbingiz sizning fikringizni ochiq tanqid qildi. Siz:", options: ["Xotirjam tinglab, sababini so‘rayman", "Darhol javob qaytaraman", "Indamay qolaman", "Boshqalardan yordam so‘rayman"], scores: [4, 2, 1, 2] },
  { id: 5, text: "Kutilmagan yomon xabar oldingiz. Birinchi harakatingiz:", options: ["Chuqur nafas olib, o‘zimni tutaman", "Darhol kimdirga aytaman", "Yolg‘iz qolaman", "Ishni tashlab ketaman"], scores: [4, 2, 3, 1] },
  { id: 6, text: "Suhbatdoshning ko‘zlari boshqa tomonga qarayapti. Bu nimani bildiradi?", options: ["U zerikkan yoki shoshilyapti", "U yolg‘on gapiryapti", "U sizni yoqtirmaydi", "Hech narsa, shunchaki shunday"], scores: [4, 2, 1, 2] },
];

// ==================== PQ 6 ====================
const PQ_QUESTIONS = [
  { id: 1, text: "Muhim loyiha bor, lekin siz uni doim keyinga surasiz. Sabab:", options: ["Qiyin bo‘lgani uchun", "Vaqt ko‘p deb o‘ylayman", "Nima qilishni bilmayman", "Kayfiyat yo‘q"], scores: [2, 1, 2, 1] },
  { id: 2, text: "Imtihonga 7 kun qoldi. Siz:", options: ["Har kuni oz-oz tayyorlanaman", "Oxirgi 2 kunda qattiq tayyorlanaman", "Oxirgi kechada tayyorlanaman", "Tayyorlanmayman, nima bo‘lsa bo‘lsin"], scores: [4, 2, 1, 0] },
  { id: 3, text: "Ishni boshlash uchun sizga nima kerak?", options: ["Aniq reja", "Kayfiyat", "Deadline", "Mukofot"], scores: [4, 1, 2, 2] },
  { id: 4, text: "Ishlayotganingizda telefonni tez-tez tekshirasizmi?", options: ["Yo‘q, telefon boshqa xonada", "Ba‘zan, lekin o‘zimni tutaman", "Ha, har 10 daqiqada", "Doim qo‘limda"], scores: [4, 3, 1, 0] },
  { id: 5, text: "Deadline yaqinlashganda siz:", options: ["Avvaldan tayyor bo‘laman", "Oxirgi paytda tezlashaman", "Kechikaman", "Umuman bajarmayman"], scores: [4, 2, 1, 0] },
  { id: 6, text: "Rejangizni qanchalik bajarasiz?", options: ["Doim bajaraman", "Ko‘pincha bajaraman", "Ba‘zan bajaraman", "Deyarli hech qachon"], scores: [4, 3, 1, 0] },
];

// ==================== RENDER HELPERS ====================
function renderCell(cell) {
  if (!cell) return "";
  if (cell.type === "question") return "";
  if (cell.type === "dot") {
    let html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:2px;width:44px;height:44px;align-items:center;justify-items:center;">';
    for (let i = 0; i < Math.min(cell.count, 16); i++) {
      html += '<div style="width:6px;height:6px;border-radius:50%;background:#a78bfa;box-shadow:0 0 6px #a78bfa;"></div>';
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
    if (cell.shape === "circle") return `<svg width="44" height="44" viewBox="0 0 44 44"><circle cx="22" cy="22" r="14" fill="${fill}" stroke="#a78bfa" stroke-width="2"/></svg>`;
    if (cell.shape === "square") return `<svg width="44" height="44" viewBox="0 0 44 44"><rect x="7" y="7" width="30" height="30" rx="4" fill="${fill}" stroke="#a78bfa" stroke-width="2"/></svg>`;
    if (cell.shape === "triangle") return `<svg width="44" height="44" viewBox="0 0 44 44"><polygon points="22,7 37,37 7,37" fill="${fill}" stroke="#a78bfa" stroke-width="2" stroke-linejoin="round"/></svg>`;
    if (cell.shape === "diamond") return `<svg width="44" height="44" viewBox="0 0 44 44"><polygon points="22,6 38,22 22,38 6,22" fill="${fill}" stroke="#a78bfa" stroke-width="2" stroke-linejoin="round"/></svg>`;
  }
  if (cell.type === "rotate") {
    return `<svg width="44" height="44" viewBox="0 0 44 44"><g transform="rotate(${cell.angle} 22 22)"><path d="M12 22 L32 22 M27 17 L32 22 L27 27" stroke="#a78bfa" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g></svg>`;
  }
  if (cell.type === "combo") {
    const colors = { full: "#a78bfa", half: "rgba(167,139,250,.5)", empty: "transparent" };
    const fill = colors[cell.fill] || "transparent";
    let svg = '<svg width="44" height="44" viewBox="0 0 44 44">';
    if (cell.shapes.includes("triangle")) svg += `<polygon points="22,8 36,36 8,36" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linejoin="round"/>`;
    if (cell.shapes.includes("square")) svg += `<rect x="9" y="9" width="26" height="26" rx="3" fill="none" stroke="#60a5fa" stroke-width="2"/>`;
    if (cell.shapes.includes("circle")) svg += `<circle cx="22" cy="22" r="13" fill="${fill}" stroke="#a78bfa" stroke-width="2"/>`;
    svg += "</svg>";
    return svg;
  }
  if (cell.type === "size") {
    const s = Math.min(cell.size, 36);
    return `<svg width="44" height="44" viewBox="0 0 44 44"><circle cx="22" cy="22" r="${s/2}" fill="none" stroke="#a78bfa" stroke-width="2"/></svg>`;
  }
  if (cell.type === "grid") {
    const pos = cell.pos;
    const row = Math.floor(pos / 3);
    const col = pos % 3;
    return `<svg width="44" height="44" viewBox="0 0 44 44">
      <rect x="3" y="3" width="38" height="38" rx="4" fill="none" stroke="rgba(167,139,250,.3)" stroke-width="1.5"/>
      <circle cx="${10 + col * 12}" cy="${10 + row * 12}" r="5" fill="#a78bfa"/>
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
    this.startLiveLoop();

    const local = loadLocal();
    if (local && local.profile) {
      State.profile = local.profile;
    }

    if (initData) {
      const me = await api("/api/me", { initData });
      if (me.ok) {
        State.user = me.user;
        State.completed = me.completed || {};
        if (me.user.full_name) {
          State.profile.full_name = me.user.full_name;
          State.profile.gender = me.user.gender;
          State.profile.age = me.user.age;
          State.profile.country = me.user.country;
        }
        this.applyUnlocks();
        if (me.active_battles && me.active_battles.length > 0) {
          State.battle.id = me.active_battles[0].id;
          State.battle.code = me.active_battles[0].battle_code;
          setTimeout(() => {
            if (confirm("Battle davom etmoqda. Ochishni xohlaysizmi?")) {
              App.openBattleDetail();
            }
          }, 600);
        }
      }
    }

    if (local && local.test && local.test.sessionId && local.test.current > 0 && local.test.current < 18 && local.test.type === "iq") {
      setTimeout(() => {
        if (confirm("Test davom etmoqda. Davom ettirishni xohlaysizmi?")) {
          State.test = Object.assign({}, State.test, local.test);
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
      this.animateNumber("live-total", res.total);
      this.animateNumber("live-online", res.online);
    }
  },

  startLiveLoop() {
    if (State.live.interval) clearInterval(State.live.interval);
    State.live.interval = setInterval(() => this.refreshLive(), 5000);
  },

  animateNumber(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    let cur = parseInt(el.textContent.replace(/\D/g, "")) || 0;
    if (cur === target) return;
    const diff = target - cur;
    const step = diff > 0 ? Math.max(1, Math.floor(diff / 10)) : Math.min(-1, Math.ceil(diff / 10));
    const timer = setInterval(() => {
      cur += step;
      if ((step > 0 && cur >= target) || (step < 0 && cur <= target)) { cur = target; clearInterval(timer); }
      el.textContent = cur.toLocaleString();
    }, 40);
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
    const c = State.completed || {};
    console.log("[applyUnlocks]", c);
    // IQ → EQ unlock (bir marta)
    if (c.iq) {
        const el = document.getElementById("card-eq");
        if (el) {
            el.classList.remove("locked"); el.classList.add("unlocked");
            const s = el.querySelector(".card-state"); if (s) s.textContent = "🔓";
            const h = el.querySelector(".card-hint"); if (h) h.textContent = "";
        }
    }
    // EQ → PQ unlock
    if (c.eq) {
        const el = document.getElementById("card-pq");
        if (el) {
            el.classList.remove("locked"); el.classList.add("unlocked");
            const s = el.querySelector(".card-state"); if (s) s.textContent = "🔓";
            const h = el.querySelector(".card-hint"); if (h) h.textContent = "";
        }
    }
    // IQ+EQ+PQ → Profile unlock
    if (c.iq && c.eq && c.pq) {
        const el = document.getElementById("card-profile");
        if (el) {
            el.classList.remove("locked"); el.classList.add("unlocked");
            const s = el.querySelector(".card-state"); if (s) s.textContent = "🔓";
        }
    }
},

  async saveProfile() {
    const fullName = document.getElementById("profile-fullname")?.value.trim() || State.profile.full_name;
    const gender = State.profile.gender;
    const age = parseInt(document.getElementById("profile-age")?.value) || State.profile.age;
    const country = State.profile.country;
    if (!fullName || fullName.length < 3) { alert("Ism-familiyani to‘liq kiriting."); return; }
    if (!gender) { alert("Jinsni tanlang."); return; }
    if (!age || age < 8 || age > 100) { alert("Yoshni to‘g‘ri kiriting (8-100)."); return; }
    if (!country) { alert("Davlatni tanlang."); return; }
    State.profile.full_name = fullName; State.profile.age = age;
    saveLocal();
    if (initData) {
      const res = await api("/api/profile/save", { initData, full_name: fullName, gender, age, country });
      if (!res.ok) { alert("Saqlashda xatolik."); return; }
    }
    haptic("medium");
    this.go("iq-intro");
  },

  selectGender(g) {
    State.profile.gender = g;
    document.querySelectorAll("#gender-selector .option").forEach(el => el.classList.remove("selected"));
    document.querySelector(`#gender-selector [data-gender="${g}"]`)?.classList.add("selected");
    haptic("light");
  },

  selectCountry(c) {
    State.profile.country = c;
    document.querySelectorAll("#country-selector .option").forEach(el => el.classList.remove("selected"));
    document.querySelector(`#country-selector [data-country="${c}"]`)?.classList.add("selected");
    haptic("light");
  },

  async startIQ() {
    if (!State.profile.full_name || !State.profile.gender || !State.profile.age || !State.profile.country) {
      this.go("profile-name");
      return;
    }
    this.go("iq-intro");
  },

  async startIQTest() {
    if (initData) {
      const res = await api("/api/session/start", { initData, test_type: "iq" });
      if (res.ok) { State.test.sessionId = res.session_id; State.test.attemptId = res.attempt_id; }
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
    const nextBtn = document.getElementById("sample-next");
    if (nextBtn) nextBtn.disabled = true;
    renderOptions(document.getElementById("sample-options"), sample.options, (idx) => {
      if (nextBtn) nextBtn.disabled = false;
      document.querySelectorAll("#sample-options .option").forEach((o, i) => {
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
    document.getElementById("progress-fill").style.width = ((State.test.current / 18) * 100) + "%";
    const diff = document.getElementById("difficulty-bar");
    let dh = "";
    for (let i = 0; i < 18; i++) {
      let cls = i >= 12 ? "hard" : (i >= 6 ? "medium" : "easy");
      dh += (i <= State.test.current) ? `<span class="${cls}"></span>` : `<span></span>`;
    }
    if (diff) diff.innerHTML = dh;
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
    if (cur === 5) { this.go("q6"); return; }
    if (cur === 11) { this.go("q12"); return; }
    if (cur === 17) { this.finish(); return; }
    State.test.current++;
    saveLocal();
    this.renderQuestion();
  },

  continueAfterQ6() { State.test.current = 6; saveLocal(); this.go("test"); this.renderQuestion(); },
  continueAfterQ12() { State.test.current = 12; saveLocal(); this.go("test"); this.renderQuestion(); },

  async finish() {
    clearInterval(State.test.timerInterval);
    this.go("iq-loading");
    await new Promise(r => setTimeout(r, 3500));

    let score = 0, correct = 0, level = "—", resultVisible = true, paymentRequired = false, attemptId = null;
    if (initData && State.test.sessionId) {
      const res = await api("/api/test/submit", {
        initData,
        session_id: State.test.sessionId,
        answers: State.test.answers,
        duration: State.test.duration,
      });
      if (res.ok) {
        score = res.score; correct = res.correct; level = res.level;
        resultVisible = res.result_visible;
        paymentRequired = res.payment_required;
        attemptId = res.attempt_id;
        State.completed.iq = score;
      }
    } else {
      let w = 0, mw = 0;
      QUESTIONS.forEach((q, i) => { mw += q.weight; if (State.test.answers[i] === q.correct) w += q.weight; });
      correct = State.test.answers.filter((a, i) => a === QUESTIONS[i].correct).length;
      score = Math.round(70 + (w / mw) * 60);
      level = score >= 115 ? "YUQORI DARAJA" : score >= 100 ? "O‘RTA DARAJA" : "RIVOJLANTIRISH";
      State.completed.iq = score;
    }
    State.test.resultData = { score, correct, level, attemptId };

    if (paymentRequired) {
      const iqPrice = parseInt(State.settings.iq_price || "10000");
      document.getElementById("payreq-price").textContent = iqPrice.toLocaleString() + " so‘m";
      this.go("payment-required");
    } else {
      this.renderResult(score, correct, level);
      this.go("result");
    }
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
      const d = dirs[i]; el.dataset.label = d.label;
      const f = el.querySelector(".dir-fill"); const sp = el.querySelector("span");
      setTimeout(() => { if (f) f.style.width = d.val + "%"; }, 100 + i * 150);
      if (sp) sp.textContent = Math.round(d.val) + "%";
    });
    const strongest = dirs.reduce((a, b) => a.val > b.val ? a : b);
    document.getElementById("res-strongest").textContent = strongest.label;
  },

  // ============ CERTIFICATE — BRAUZERDA ============
  async getCertificate() {
    if (!initData) { alert("Sertifikat uchun Telegram kerak."); return; }
    haptic("medium");
    try {
      const res = await fetch("/api/certificate/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData }),
      });
      if (!res.ok) {
        alert("Sertifikat topilmadi. Avval IQ testni yakunlang.");
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "IQ-TEST-BOT-Sertifikat.png";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert("Sertifikat yuklashda xatolik.");
    }
  },

  shareResult() {
    const score = document.getElementById("res-score")?.textContent || "0";
    const text = `🧠 IQ TEST BOT\n\nMen IQ-style testda ${score} ball oldim!\nSiz ham sinab ko‘ring 👇`;
    const url = `https://t.me/${window.__BOT_USERNAME__ || "iqtest_ubot"}`;
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`);
    } else {
      navigator.clipboard?.writeText(text + " " + url);
      alert("Nusxa olindi!");
    }
  },

  retry() {
    clearLocal();
    State.test = { type: "iq", sessionId: null, attemptId: null, current: 0, answers: [], startedAt: null, duration: 0, timerInterval: null, resultData: null };
    this.go("iq-intro");
  },

  // ============ PAYMENT ============
  async startIQPayment() {
    await this.createPayment("iq", State.test.resultData?.attemptId);
  },

  async startBattlePayment() {
    await this.createPayment("battle", null, State.battle.id);
  },

  async createPayment(product, attemptId = null, battleId = null) {
    if (!initData) { alert("To‘lov faqat Telegram orqali."); return; }
    haptic("medium");
    const res = await api("/api/payment/create", {
      initData, product,
      attempt_id: attemptId,
      battle_id: battleId,
    });
    if (res.ok) {
      if (res.free) {
        if (product === "iq") {
          const rd = State.test.resultData;
          this.renderResult(rd.score, rd.correct, rd.level);
          this.go("result");
        } else if (product === "battle") {
          this.checkBattle();
        }
        return;
      }
      State.payment.id = res.payment_id;
      State.payment.product = product;
      State.payment.amount = res.amount;
      State.payment.cards = res.cards;
      State.payment.attemptId = attemptId;
      State.payment.battleId = battleId;
      document.getElementById("pay-amount").textContent = res.amount.toLocaleString() + " so‘m";
      const cardsEl = document.getElementById("pay-cards");
      if (cardsEl) {
        cardsEl.innerHTML = res.cards.map(c =>
          `<div class="pay-card"><div class="pay-card-num">${c.card_number}</div><div class="pay-card-holder">${c.holder}</div><div class="pay-card-bank">${c.bank || ""}</div></div>`
        ).join("") || "<div>Karta mavjud emas. Admin bilan bog‘laning.</div>";
      }
      this.go("payment");
      this.startPaymentPoll();
    } else {
      alert("To‘lov yaratishda xatolik.");
    }
  },

  startPaymentPoll() {
    if (State.payment.pollInterval) clearInterval(State.payment.pollInterval);
    State.payment.pollInterval = setInterval(async () => {
      if (!State.payment.id) return;
      const res = await api(`/api/payment/${State.payment.id}`, { initData });
      if (res.ok && res.payment && res.payment.status === "approved") {
        clearInterval(State.payment.pollInterval);
        State.payment.pollInterval = null;
        alert("✅ To‘lov tasdiqlandi!");
        if (State.payment.product === "iq") {
          const rd = State.test.resultData;
          this.renderResult(rd.score, rd.correct, rd.level);
          this.go("result");
        } else if (State.payment.product === "battle") {
          this.checkBattle();
        }
      }
    }, 5000);
  },

  async sendReceipt() {
    alert("Chek rasmini Telegram botga yuboring:\n\nBot → chek rasmini yuboring.");
  },

  // ============ EQ ============
  async startEQ() {
    if (State.completed.eq) {
      const rp = parseInt(State.settings.eq_retry_price || "0");
      if (rp > 0 && !confirm(`EQ qayta ishlash ${rp} so‘m. To‘lashni xohlaysizmi?`)) return;
    }
    haptic("medium");
    if (initData) {
      const res = await api("/api/session/start", { initData, test_type: "eq" });
      if (res.ok) { State.test.sessionId = res.session_id; State.test.attemptId = res.attempt_id; }
    }
    State.test.type = "eq";
    State.test.current = 0;
    State.test.answers = new Array(EQ_QUESTIONS.length).fill(null);
    State.test.startedAt = Date.now();
    this.go("eq-intro");
  },

  goEQTest() { this.go("eq-test"); this.renderEQQuestion(); },

  renderEQQuestion() {
    const q = EQ_QUESTIONS[State.test.current];
    if (!q) return;
    document.getElementById("eq-progress-text").textContent = `Q${State.test.current + 1} / ${EQ_QUESTIONS.length}`;
    document.getElementById("eq-progress-fill").style.width = ((State.test.current / EQ_QUESTIONS.length) * 100) + "%";
    document.getElementById("eq-question-text").textContent = q.text;
    const nextBtn = document.getElementById("eq-next");
    if (nextBtn) { nextBtn.disabled = true; nextBtn.textContent = State.test.current === EQ_QUESTIONS.length - 1 ? "YAKUNLASH →" : "KEYINGISI →"; }
    renderTextOptions(document.getElementById("eq-options"), q.options, (idx) => {
      State.test.answers[State.test.current] = idx;
      if (nextBtn) nextBtn.disabled = false;
    });
    if (State.test.answers[State.test.current] !== null && State.test.answers[State.test.current] !== undefined) {
      const prev = State.test.answers[State.test.current];
      document.querySelectorAll("#eq-options .option")[prev]?.classList.add("selected");
      if (nextBtn) nextBtn.disabled = false;
    }
  },

  nextEQQuestion() {
    haptic("light");
    if (State.test.current === EQ_QUESTIONS.length - 1) { this.finishEQ(); return; }
    State.test.current++;
    this.renderEQQuestion();
  },

  async finishEQ() {
    this.go("iq-loading");
    await new Promise(r => setTimeout(r, 2500));
    let score = 0;
    EQ_QUESTIONS.forEach((q, i) => {
      const a = State.test.answers[i];
      if (a !== null && a !== undefined) score += q.scores[a];
    });
    const maxS = EQ_QUESTIONS.length * 4;
    const percent = Math.round((score / maxS) * 100);
    State.completed.eq = percent;
    if (initData && State.test.sessionId) {
      await api("/api/test/submit", {
        initData, session_id: State.test.sessionId, answers: State.test.answers,
        duration: Math.floor((Date.now() - State.test.startedAt) / 1000),
      });
    }
    document.getElementById("eq-res-score").textContent = percent + "%";
    document.getElementById("eq-res-level").textContent =
      percent >= 80 ? "JUDA YUQORI" : percent >= 60 ? "YUQORI" : percent >= 40 ? "O‘RTA" : "RIVOJLANTIRISH";
    this.go("eq-result");
    this.applyUnlocks();
  },

  // ============ PQ ============
  async startPQ() {
    if (State.completed.pq) {
      const rp = parseInt(State.settings.pq_retry_price || "0");
      if (rp > 0 && !confirm(`PQ qayta ishlash ${rp} so‘m. To‘lashni xohlaysizmi?`)) return;
    }
    haptic("medium");
    if (initData) {
      const res = await api("/api/session/start", { initData, test_type: "pq" });
      if (res.ok) { State.test.sessionId = res.session_id; State.test.attemptId = res.attempt_id; }
    }
    State.test.type = "pq";
    State.test.current = 0;
    State.test.answers = new Array(PQ_QUESTIONS.length).fill(null);
    State.test.startedAt = Date.now();
    this.go("pq-intro");
  },

  goPQTest() { this.go("pq-test"); this.renderPQQuestion(); },

  renderPQQuestion() {
    const q = PQ_QUESTIONS[State.test.current];
    if (!q) return;
    document.getElementById("pq-progress-text").textContent = `Q${State.test.current + 1} / ${PQ_QUESTIONS.length}`;
    document.getElementById("pq-progress-fill").style.width = ((State.test.current / PQ_QUESTIONS.length) * 100) + "%";
    document.getElementById("pq-question-text").textContent = q.text;
    const nextBtn = document.getElementById("pq-next");
    if (nextBtn) { nextBtn.disabled = true; nextBtn.textContent = State.test.current === PQ_QUESTIONS.length - 1 ? "YAKUNLASH →" : "KEYINGISI →"; }
    renderTextOptions(document.getElementById("pq-options"), q.options, (idx) => {
      State.test.answers[State.test.current] = idx;
      if (nextBtn) nextBtn.disabled = false;
    });
    if (State.test.answers[State.test.current] !== null && State.test.answers[State.test.current] !== undefined) {
      const prev = State.test.answers[State.test.current];
      document.querySelectorAll("#pq-options .option")[prev]?.classList.add("selected");
      if (nextBtn) nextBtn.disabled = false;
    }
  },

  nextPQQuestion() {
    haptic("light");
    if (State.test.current === PQ_QUESTIONS.length - 1) { this.finishPQ(); return; }
    State.test.current++;
    this.renderPQQuestion();
  },

  async finishPQ() {
    this.go("iq-loading");
    await new Promise(r => setTimeout(r, 2500));
    let score = 0;
    PQ_QUESTIONS.forEach((q, i) => {
      const a = State.test.answers[i];
      if (a !== null && a !== undefined) score += q.scores[a];
    });
    const maxS = PQ_QUESTIONS.length * 4;
    const percent = Math.round((score / maxS) * 100);
    State.completed.pq = percent;
    if (initData && State.test.sessionId) {
      await api("/api/test/submit", {
        initData, session_id: State.test.sessionId, answers: State.test.answers,
        duration: Math.floor((Date.now() - State.test.startedAt) / 1000),
      });
    }
    document.getElementById("pq-res-score").textContent = percent + "%";
    document.getElementById("pq-res-level").textContent =
      percent >= 80 ? "JUDA YAXSHI" : percent >= 60 ? "YAXSHI" : percent >= 40 ? "O‘RTA" : "RIVOJLANTIRISH KERAK";
    this.go("pq-result");
    this.applyUnlocks();
  },

  // ============ PROFILE ============
  openProfile() {
    if (!(State.completed.iq && State.completed.eq && State.completed.pq)) {
      alert("Avval IQ, EQ va PQ testlarini tugatishingiz kerak.");
      return;
    }
    const iq = State.completed.iq, eq = State.completed.eq, pq = State.completed.pq;
    document.getElementById("prof-iq").textContent = iq;
    document.getElementById("prof-eq").textContent = eq + "%";
    document.getElementById("prof-pq").textContent = pq + "%";
    const strengths = [], weaknesses = [];
    if (iq >= 115) strengths.push("Kuchli mantiqiy fikrlash"); else weaknesses.push("Mantiqiy fikrlashni rivojlantirish");
    if (eq >= 70) strengths.push("Yaxshi hissiy intellekt"); else weaknesses.push("Emotsiyalarni boshqarish");
    if (pq >= 70) strengths.push("Ishni o‘z vaqtida bajarish"); else weaknesses.push("Prokrastinatsiyani kamaytirish");
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

  // ============ BATTLE ============
  openBattle() {
    console.log("[Battle] initData:", initData ? initData.substring(0, 50) : "EMPTY");
    this.go("battle-home");
},

  async createBattle() {
    haptic("medium");
    const res = await api("/api/battle/create", { initData });
    if (res.ok) {
      State.battle.id = res.battle_id;
      State.battle.code = res.code;
      State.battle.role = "creator";
      document.getElementById("battle-code-display").textContent = res.code;
      document.getElementById("battle-price-display").textContent = res.price.toLocaleString() + " so‘m";
      this.go("battle-wait");
      this.startBattlePoll();
    } else if (res.error === "ACTIVE_BATTLE_EXISTS") {
      State.battle.id = res.battle_id;
      State.battle.code = res.code;
      this.go("battle-wait");
      this.startBattlePoll();
    } else {
      alert("Battle yaratishda xatolik.");
    }
  },

  async joinBattle() {
    const code = document.getElementById("battle-join-code").value.trim().toUpperCase();
    if (!/^[A-Z0-9]{4}$/.test(code)) { alert("4 xonali kod kiriting."); return; }
    haptic("medium");
    const res = await api("/api/battle/join", { initData, code });
    if (res.ok) {
      State.battle.id = res.battle_id;
      State.battle.code = code;
      State.battle.role = "opponent";
      this.go("battle-wait");
      this.startBattlePoll();
    } else {
      const errs = {
        NOT_FOUND: "Kod topilmadi.",
        OWN_BATTLE: "O‘z battlingizga qo‘shila olmaysiz.",
        BATTLE_NOT_OPEN: "Battle allaqachon boshlangan.",
        BATTLE_FULL: "Battle to‘lgan.",
        ACTIVE_BATTLE_EXISTS: "Sizda faol battle bor.",
      };
      alert(errs[res.error] || "Xatolik.");
    }
  },

  startBattlePoll() {
    if (State.battle.pollInterval) clearInterval(State.battle.pollInterval);
    State.battle.pollInterval = setInterval(() => this.checkBattle(), 5000);
  },

  async checkBattle() {
    if (!State.battle.id) return;
    const res = await api(`/api/battle/${State.battle.id}`, { initData });
    if (!res.ok) return;
    State.battle.players = res.players || [];
    const statusEl = document.getElementById("battle-wait-status");
    const myPlayer = res.players.find(p => p.is_me);
    if (statusEl) {
      if (res.battle.status === "waiting_for_player") statusEl.innerHTML = "⏳ Do‘stingiz kodni kiritishini kuting...";
      else if (res.battle.status === "waiting_for_payment") statusEl.innerHTML = "💳 To‘lovni amalga oshiring";
      else if (res.battle.status === "ready") statusEl.innerHTML = "🎉 Ikkalangiz tayyorsiz! Testni boshlashingiz mumkin.";
      else if (res.battle.status === "in_progress") statusEl.innerHTML = "🧠 Test davom etmoqda";
      else if (res.battle.status === "completed" || res.battle.status === "draw") { this.openBattleResult(res); return; }
    }
    const playersEl = document.getElementById("battle-players-list");
    if (playersEl) {
      playersEl.innerHTML = res.players.map(p => `
        <div class="battle-player-row ${p.is_me ? 'me' : ''}">
          <span class="bp-name">${p.is_me ? "👤 SIZ" : "👤 " + p.name}</span>
          <span class="bp-progress">${p.current_question}/18</span>
          <span class="bp-status">${p.test_status === 'completed' ? '✅' : p.test_status === 'in_progress' ? '⏳' : '—'}</span>
        </div>
      `).join("");
    }
    if (res.battle.status === "ready" && myPlayer && myPlayer.test_status === "not_started") {
      const sb = document.getElementById("battle-start-btn"); if (sb) sb.style.display = "block";
    }
    if (myPlayer && myPlayer.test_status === "in_progress") {
      const cb = document.getElementById("battle-continue-btn"); if (cb) cb.style.display = "block";
    }
  },

  async startBattleTest() {
    const res = await api(`/api/battle/${State.battle.id}/start`, { initData });
    if (res.ok) {
      State.battle.sessionId = res.session_id;
      State.battle.current = 0;
      State.battle.answers = new Array(18).fill(null);
      State.battle.startedAt = Date.now();
      this.go("battle-test");
      this.renderBattleQuestion();
    } else {
      alert(res.error || "Boshlanmadi");
    }
  },

  async continueBattle() {
    if (!State.battle.id) return;
    const res = await api(`/api/battle/${State.battle.id}`, { initData });
    if (res.ok) {
      const mp = res.players.find(p => p.is_me);
      if (mp && mp.test_status === "in_progress") {
        State.battle.current = mp.current_question || 0;
        State.battle.answers = new Array(18).fill(null);
        State.battle.startedAt = Date.now();
        this.go("battle-test");
        this.renderBattleQuestion();
      } else if (mp && mp.test_status === "not_started") {
        this.startBattleTest();
      }
    }
  },

  renderBattleQuestion() {
    const q = QUESTIONS[State.battle.current];
    if (!q) return;
    document.getElementById("battle-progress-text").textContent = `Q${State.battle.current + 1} / 18`;
    document.getElementById("battle-progress-fill").style.width = ((State.battle.current / 18) * 100) + "%";
    renderMatrix(document.getElementById("battle-matrix"), q.matrix);
    const nextBtn = document.getElementById("battle-next");
    if (nextBtn) { nextBtn.disabled = true; nextBtn.textContent = State.battle.current === 17 ? "YAKUNLASH →" : "KEYINGISI →"; }
    renderOptions(document.getElementById("battle-options"), q.options, (idx) => {
      State.battle.answers[State.battle.current] = idx;
      if (nextBtn) nextBtn.disabled = false;
      this.syncBattle();
    });
    if (State.battle.answers[State.battle.current] !== null && State.battle.answers[State.battle.current] !== undefined) {
      const prev = State.battle.answers[State.battle.current];
      document.querySelectorAll("#battle-options .option")[prev]?.classList.add("selected");
      if (nextBtn) nextBtn.disabled = false;
    }
  },

  async syncBattle() {
    if (!State.battle.id) return;
    try {
      await api(`/api/battle/${State.battle.id}/sync`, {
        initData,
        current_question: State.battle.current + 1,
        answers: State.battle.answers,
      });
    } catch {}
  },

  nextBattleQuestion() {
    haptic("light");
    if (State.battle.current === 17) { this.finishBattle(); return; }
    State.battle.current++;
    this.syncBattle();
    this.renderBattleQuestion();
  },

  async finishBattle() {
    this.go("iq-loading");
    await new Promise(r => setTimeout(r, 3000));
    const res = await api(`/api/battle/${State.battle.id}/finish`, {
      initData,
      answers: State.battle.answers,
      duration: Math.floor((Date.now() - State.battle.startedAt) / 1000),
    });
    if (res.ok) {
      if (State.battle.pollInterval) { clearInterval(State.battle.pollInterval); State.battle.pollInterval = null; }
      this.go("battle-result");
      document.getElementById("battle-my-score").textContent = res.score;
      if (res.opponent_score !== null && res.opponent_score !== undefined) {
        document.getElementById("battle-opp-score").textContent = res.opponent_score;
        if (res.score > res.opponent_score) {
          document.getElementById("battle-winner").textContent = "🏆 SIZ G‘OLIB";
          document.getElementById("battle-winner").className = "battle-winner win";
        } else if (res.score < res.opponent_score) {
          document.getElementById("battle-winner").textContent = "😔 DO‘STINGIZ G‘OLIB";
          document.getElementById("battle-winner").className = "battle-winner lose";
        } else {
          document.getElementById("battle-winner").textContent = "🤝 DURANG";
          document.getElementById("battle-winner").className = "battle-winner draw";
        }
      } else {
        document.getElementById("battle-opp-score").textContent = "⏳";
        document.getElementById("battle-winner").textContent = "Kutilmoqda";
      }
    } else {
      alert("Yakunlashda xatolik.");
      this.go("battle-home");
    }
  },

  openBattleResult(data) {
    if (State.battle.pollInterval) { clearInterval(State.battle.pollInterval); State.battle.pollInterval = null; }
    const mp = data.players.find(p => p.is_me);
    const op = data.players.find(p => !p.is_me);
    document.getElementById("battle-my-score").textContent = mp?.score ?? "—";
    document.getElementById("battle-opp-score").textContent = op?.score ?? "—";
    const wEl = document.getElementById("battle-winner");
    if (data.battle.status === "draw") {
      wEl.textContent = "🤝 DURANG"; wEl.className = "battle-winner draw";
    } else if (data.battle.winner_id === State.user?.user_id) {
      wEl.textContent = "🏆 SIZ G‘OLIB"; wEl.className = "battle-winner win";
    } else {
      wEl.textContent = "😔 DO‘STINGIZ G‘OLIB"; wEl.className = "battle-winner lose";
    }
    this.go("battle-result");
  },

  async openBattleDetail() {
    if (!State.battle.id) return;
    await this.checkBattle();
    this.go("battle-wait");
    this.startBattlePoll();
  },
};

// ==================== EVENT BINDINGS ====================
document.addEventListener("DOMContentLoaded", () => {
  App.init();

  document.querySelector('[data-test="iq"]')?.addEventListener("click", () => { haptic("medium"); App.startIQ(); });
  document.getElementById("card-eq")?.addEventListener("click", () => {
    const el = document.getElementById("card-eq");
    if (el?.classList.contains("locked")) { haptic("rigid"); return; }
    App.startEQ();
  });
  document.getElementById("card-pq")?.addEventListener("click", () => {
    const el = document.getElementById("card-pq");
    if (el?.classList.contains("locked")) { haptic("rigid"); return; }
    App.startPQ();
  });
  document.getElementById("card-profile")?.addEventListener("click", () => {
    const el = document.getElementById("card-profile");
    if (el?.classList.contains("locked")) { haptic("rigid"); return; }
    App.openProfile();
  });
  document.getElementById("battle-card")?.addEventListener("click", () => App.openBattle());

  document.querySelectorAll("#gender-selector [data-gender]").forEach(el => {
    el.addEventListener("click", () => App.selectGender(el.dataset.gender));
  });
  document.querySelectorAll("#country-selector [data-country]").forEach(el => {
    el.addEventListener("click", () => App.selectCountry(el.dataset.country));
  });
});