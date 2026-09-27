(() => {
"use strict";

const tg = window.Telegram?.WebApp;

if (tg) {
  try {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#0a0e1a");
    tg.setBackgroundColor("#0a0e1a");
  } catch (e) {}
}

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const state = {
  user: null,
  prices: {},
  questions: [],
  sessionId: null,
  testType: null,
  index: 0,
  answers: {},
  selected: null,
  startedAt: 0,
  attemptId: null,
  paymentId: null,
  battleId: null,
  localKey: null,
  battlePoll: null,
  battleReady: false
};

const screens = [
  "loadingScreen",
  "homeScreen",
  "profileScreen",
  "testScreen",
  "loadingResult",
  "paymentScreen",
  "resultScreen",
  "rankingScreen",
  "certificateScreen",
  "battleScreen"
];

function show(id) {
  screens.forEach((x) => {
    const el = document.getElementById(x);
    if (el) {
      el.classList.toggle("hidden", x !== id);
    }
  });

  window.scrollTo({
    top: 0,
    behavior: "instant"
  });
}

function toast(msg) {
  const el = $("#toast");

  if (!el) return;

  el.textContent = msg;
  el.classList.add("show");

  clearTimeout(window.__toast);

  window.__toast = setTimeout(() => {
    el.classList.remove("show");
  }, 2600);
}

function initData() {
  return tg?.initData || "";
}

async function api(path, options = {}) {
  const method =
    (options.method || "GET").toUpperCase();

  const headers =
    new Headers(options.headers || {});

  const raw = initData();

  if (raw) {
    headers.set(
      "X-Telegram-Init-Data",
      raw
    );
  }

  if (
    method === "POST" &&
    !(options.body instanceof FormData) &&
    options.body !== undefined
  ) {
    headers.set(
      "Content-Type",
      "application/json"
    );
  }

  const controller =
    new AbortController();

  const timeout =
    setTimeout(
      () => controller.abort(),
      15000
    );

  try {
    const res = await fetch(
      path,
      {
        ...options,
        method,
        headers,
        signal: controller.signal
      }
    );

    const text = await res.text();

    let data = {};

    try {
      data = text
        ? JSON.parse(text)
        : {};
    } catch {
      data = {
        ok: false,
        error:
          text ||
          "Server javobi noto‘g‘ri"
      };
    }

    if (!res.ok) {
      throw new Error(
        data.error ||
        data.detail ||
        `HTTP ${res.status}`
      );
    }

    return data;

  } finally {
    clearTimeout(timeout);
  }
}


/* =========================
   LOCAL PROGRESS
========================= */

function saveProgress() {
  if (!state.sessionId) return;

  try {
    localStorage.setItem(
      "iq_progress",
      JSON.stringify({
        sessionId: state.sessionId,
        testType: state.testType,
        index: state.index,
        answers: state.answers,
        startedAt: state.startedAt
      })
    );
  } catch (e) {}
}

function clearProgress() {
  try {
    localStorage.removeItem(
      "iq_progress"
    );
  } catch (e) {}
}


/* =========================
   SVG QUESTION RENDERER
========================= */

function svgFor(cell) {
  const ns =
    "http://www.w3.org/2000/svg";

  const svg =
    document.createElementNS(
      ns,
      "svg"
    );

  svg.setAttribute(
    "viewBox",
    "0 0 44 44"
  );

  const add = (
    tag,
    attrs
  ) => {
    const e =
      document.createElementNS(
        ns,
        tag
      );

    Object.entries(attrs)
      .forEach(([k, v]) => {
        e.setAttribute(k, v);
      });

    svg.appendChild(e);

    return e;
  };

  if (!cell) {
    return svg;
  }

  if (cell.type === "num") {
    const t = add(
      "text",
      {
        x: "22",
        y: "28",
        "text-anchor": "middle",
        fill: "#f5f7ff",
        "font-size": "18",
        "font-weight": "800"
      }
    );

    t.textContent =
      String(cell.val ?? "");

    return svg;
  }

  if (cell.type === "dot") {
    const n =
      Math.min(
        9,
        Math.max(
          1,
          Number(cell.count || 1)
        )
      );

    for (let i = 0; i < n; i++) {
      let x =
        10 + (i % 3) * 12;

      let y =
        10 +
        Math.floor(i / 3) * 12;

      if (n === 4) {
        x =
          [10, 34, 10, 34][i];

        y =
          [10, 10, 34, 34][i];
      }

      add(
        "circle",
        {
          cx: x,
          cy: y,
          r: "3",
          fill: "#a78bfa"
        }
      );
    }

    return svg;
  }

  const shape = (
    name,
    cx,
    cy,
    size,
    fill
  ) => {
    let e;

    const f =
      fill === "empty"
        ? "none"
        : "#a78bfa";

    if (name === "circle") {
      e = add(
        "circle",
        {
          cx,
          cy,
          r: size,
          fill: f,
          stroke: "#c9baff",
          "stroke-width": "2"
        }
      );

    } else if (
      name === "square"
    ) {
      e = add(
        "rect",
        {
          x: cx - size,
          y: cy - size,
          width: size * 2,
          height: size * 2,
          rx: "2",
          fill: f,
          stroke: "#c9baff",
          "stroke-width": "2"
        }
      );

    } else if (
      name === "triangle"
    ) {
      e = add(
        "polygon",
        {
          points:
            `${cx},${cy - size} ` +
            `${cx + size},${cy + size} ` +
            `${cx - size},${cy + size}`,
          fill: f,
          stroke: "#c9baff",
          "stroke-width": "2"
        }
      );

    } else {
      e = add(
        "polygon",
        {
          points:
            `${cx},${cy - size} ` +
            `${cx + size},${cy} ` +
            `${cx},${cy + size} ` +
            `${cx - size},${cy}`,
          fill: f,
          stroke: "#c9baff",
          "stroke-width": "2"
        }
      );
    }

    if (fill === "half") {
      e.setAttribute(
        "fill",
        "#a78bfa55"
      );
    }

    return e;
  };


  if (cell.type === "grid") {
    for (let i = 0; i < 9; i++) {
      add(
        "rect",
        {
          x:
            5 +
            (i % 3) * 11,

          y:
            5 +
            Math.floor(i / 3) * 11,

          width: "8",
          height: "8",
          rx: "2",

          fill:
            i === Number(cell.pos)
              ? "#a78bfa"
              : "#202a40",

          stroke:
            i === Number(cell.pos)
              ? "#c9baff"
              : "none"
        }
      );
    }

    return svg;
  }


  if (cell.type === "shape") {
    shape(
      cell.shape,
      22,
      22,
      11,
      cell.fill
    );

    return svg;
  }


  if (cell.type === "combo") {
    const names =
      Array.isArray(cell.shapes)
        ? cell.shapes
        : [];

    const spots = [
      [14, 22],
      [30, 22],
      [22, 12],
      [22, 32]
    ];

    names
      .slice(0, 4)
      .forEach((s, i) => {
        shape(
          s,
          spots[i][0],
          spots[i][1],
          i ? 6 : 7,
          cell.fill
        );
      });

    return svg;
  }

  if (cell.type === "rotate") {
    const angle =
      Number(cell.angle || 0);

    const e =
      shape(
        "diamond",
        22,
        22,
        11,
        cell.fill
      );

    e.setAttribute(
      "transform",
      `rotate(${angle} 22 22)`
    );

    return svg;
  }

  if (cell.type === "size") {
    const sizes = {
      small: 6,
      medium: 10,
      large: 15
    };

    add(
      "circle",
      {
        cx: "22",
        cy: "22",
        r:
          sizes[cell.size] || 10,
        fill: "#a78bfa",
        stroke: "#c9baff",
        "stroke-width": "2"
      }
    );

    return svg;
  }

  return svg;
}


function renderCell(cell) {
  const div =
    document.createElement("div");

  div.className =
    "matrix-cell";

  if (
    cell &&
    cell.type === "question"
  ) {
    div.classList.add("question");
    div.textContent = "?";
  } else {
    div.appendChild(
      svgFor(cell)
    );
  }

  return div;
}


function renderOption(opt, i) {
  const b =
    document.createElement("button");

  b.className =
    "option";

  b.dataset.i = i;

  b.innerHTML =
    `<span class="letter">
      ${"ABCD"[i]}
    </span>`;

  b.appendChild(
    svgFor(opt)
  );

  b.onclick = () => {
    state.selected = i;

    $$(".option")
      .forEach((x) => {
        x.classList.remove(
          "selected"
        );
      });

    b.classList.add(
      "selected"
    );

    $("#nextQuestion").disabled =
      false;
  };

  return b;
}


function difficulty(i) {
  return i < 6
    ? "EASY"
    : i < 12
      ? "MEDIUM"
      : "HARD";
}


/* =========================
   QUESTION
========================= */

function renderQuestion() {
  const q =
    state.questions[state.index];

  if (!q) return;

  state.selected =
    state.answers[
      String(state.index + 1)
    ] ?? null;

  $("#nextQuestion").disabled =
    state.selected === null;

  $("#questionLabel").textContent =
    `Q${state.index + 1}/${state.questions.length}`;

  $("#difficulty").textContent =
    difficulty(state.index);

  $("#progressBar").style.width =
    `${((state.index + 1) /
      state.questions.length) * 100}%`;

  $("#questionText").textContent =
    state.testType === "IQ" ||
    state.testType === "BATTLE"
      ? "Qaysi variant matritsani to‘ldiradi?"
      : q.text;

  const matrix =
    $("#matrix");

  matrix.innerHTML = "";

  if (
    state.testType === "IQ" ||
    state.testType === "BATTLE"
  ) {
    matrix.classList.remove(
      "hidden"
    );

    if (
      Array.isArray(q.matrix)
    ) {
      q.matrix.forEach((c) => {
        matrix.appendChild(
          renderCell(c)
        );
      });
    }
  } else {
    matrix.classList.add(
      "hidden"
    );
  }

  const opts =
    $("#options");

  opts.innerHTML = "";

  if (
    Array.isArray(q.options)
  ) {
    q.options.forEach(
      (o, i) => {
        opts.appendChild(
          renderOption(o, i)
        );
      }
    );
  }

  if (
    state.selected !== null
  ) {
    const selected =
      opts.children[
        state.selected
      ];

    selected?.classList.add(
      "selected"
    );

    $("#nextQuestion").disabled =
      false;
  }

  $("#nextQuestion").textContent =
    state.index ===
    state.questions.length - 1
      ? "Natijani ko‘rish"
      : "Davom etish";

  if (
    state.index === 6 ||
    state.index === 12
  ) {
    $("#celebration")
      .classList.remove(
        "hidden"
      );

    setTimeout(() => {
      $("#celebration")
        ?.classList.add(
          "hidden"
        );
    }, 1800);

  } else {
    $("#celebration")
      ?.classList.add(
        "hidden"
      );
  }
}


/* =========================
   NORMAL TEST
========================= */

async function startTest(type) {
  const profile =
    state.user;

  if (
    !profile.full_name ||
    !profile.gender ||
    !profile.age ||
    !profile.country
  ) {
    state.pendingType =
      type;

    show(
      "profileScreen"
    );

    toast(
      "Avval profilingizni to‘ldiring"
    );

    return;
  }

  if (
    type === "EQ" &&
    !state.user.hasIQ
  ) {
    toast(
      "Avval IQ testni yakunlang"
    );

    return;
  }

  if (
    type === "PQ" &&
    !state.user.hasEQ
  ) {
    toast(
      "Avval EQ testni yakunlang"
    );

    return;
  }

  try {
    const d =
      await api(
        "/api/test/start",
        {
          method: "POST",
          body: JSON.stringify({
            test_type: type
          })
        }
      );

    state.testType =
      type;

    state.questions =
      d.questions || [];

    state.sessionId =
      d.session_id;

    state.index = 0;
    state.answers = {};
    state.selected = null;
    state.startedAt =
      Date.now();

    state.localKey =
      "iq_progress";

    saveProgress();

    show("testScreen");

    renderQuestion();

    startTimer();

  } catch (e) {
    toast(
      e.message ||
      "Testni boshlashda xatolik"
    );
  }
}


/* =========================
   TIMER
========================= */

let timerHandle = null;

function startTimer() {
  clearInterval(
    timerHandle
  );

  const end =
    Date.now() +
    30 * 60 * 1000;

  timerHandle =
    setInterval(() => {

      const sec =
        Math.max(
          0,
          Math.floor(
            (end - Date.now()) /
            1000
          )
        );

      $("#timer").textContent =
        `${String(
          Math.floor(sec / 60)
        ).padStart(2, "0")}:${String(
          sec % 60
        ).padStart(2, "0")}`;

      if (sec <= 0) {
        clearInterval(
          timerHandle
        );

        finishTest();
      }

    }, 500);
}


/* =========================
   NORMAL TEST SUBMIT
========================= */

async function finishTest() {
  clearInterval(
    timerHandle
  );

  if (
    state.selected !== null
  ) {
    state.answers[
      String(state.index + 1)
    ] =
      state.selected;
  }

  saveProgress();

  show(
    "loadingResult"
  );

  try {

    const d =
      await api(
        `/api/test/${state.sessionId}/submit`,
        {
          method: "POST",
          body: JSON.stringify({
            answers:
              state.answers,

            duration:
              Math.floor(
                (
                  Date.now() -
                  state.startedAt
                ) / 1000
              )
          })
        }
      );

    state.attemptId =
      d.attempt_id;

    clearProgress();

    if (
      d.payment_required
    ) {
      state.paymentData =
        d;

      await renderPayment(
        d
      );

      show(
        "paymentScreen"
      );

    } else {
      await showResult(
        d.attempt_id
      );
    }

  } catch (e) {

    show(
      "testScreen"
    );

    toast(
      e.message ||
      "Natijani yuborishda xatolik"
    );
  }
}


/* =========================
   RESULT
========================= */

async function showResult(
  attemptId
) {
  const d =
    await api(
      `/api/result/${attemptId}`
    );

  if (!d.visible) {

    state.attemptId =
      attemptId;

    const p =
      await api(
        "/api/payment/mine"
      );

    const mine =
      p.payments.find(
        (x) =>
          x.attempt_id ===
          attemptId
      );

    if (mine) {
      state.paymentId =
        mine.id;

      await renderPayment({
        amount:
          mine.amount,
        payment_id:
          mine.id,
        card: null
      });

      show(
        "paymentScreen"
      );

    } else {
      toast(
        "Natija hali yopiq"
      );
    }

    return;
  }

  $("#resultScore")
    .textContent =
    d.score;

  $("#resultLevel")
    .textContent =
    d.level || "—";

  $("#resultCorrect")
    .textContent =
    `${d.correct_count || 0}/${state.questions.length} to‘g‘ri`;

  show(
    "resultScreen"
  );
}


/* =========================
   PAYMENT
========================= */

async function renderPayment(d) {
  $("#paymentAmount")
    .textContent =
    `${Number(
      d.amount || 0
    ).toLocaleString(
      "uz-UZ"
    )} so‘m`;

  state.paymentId =
    d.payment_id ||
    state.paymentId;

  const card =
    d.card;

  $("#cardNumber")
    .textContent =
    card?.card_number ||
    "Faol karta topilmadi";

  $("#cardHolder")
    .textContent =
    card?.holder || "";

  $("#cardBank")
    .textContent =
    card?.bank || "";

  $("#paymentStatus")
    .textContent =
    card
      ? "Kartaga to‘lov qiling."
      : "Admin karta qo‘shishini kuting.";
}


async function refreshPayment() {
  if (!state.paymentId)
    return;

  try {

    const p =
      await api(
        "/api/payment/mine"
      );

    const mine =
      p.payments.find(
        (x) =>
          x.id ===
          state.paymentId
      );

    if (!mine)
      return;

    $("#paymentStatus")
      .textContent =
      `Status: ${mine.status}`;

    if (
      mine.status ===
      "approved"
    ) {

      if (
        state.testType ===
        "BATTLE"
      ) {
        await checkBattle();
      } else {
        await showResult(
          state.attemptId
        );
      }
    }

  } catch (e) {}
}


/* =========================
   HOME
========================= */

async function loadHome() {
  const d =
    await api(
      "/api/bootstrap"
    );

  state.user =
    d.user;

  state.prices =
    d.prices;

  state.questions =
    d.questions || [];

  $("#userName")
    .textContent =
    d.user.first_name ||
    "Do‘st";

  $("#fullName")
    .value =
    d.user.full_name ||
    "";

  $("#gender")
    .value =
    d.user.gender ||
    "";

  $("#age")
    .value =
    d.user.age ||
    "";

  $("#country")
    .value =
    d.user.country ||
    "";

  $("#eqState")
    .textContent =
    state.user.hasIQ
      ? "Ochilgan"
      : "IQdan keyin ochiladi";

  $("#pqState")
    .textContent =
    state.user.hasEQ
      ? "Ochilgan"
      : "EQdan keyin ochiladi";

  $(".test-card[data-test=EQ]")
    ?.classList.toggle(
      "locked",
      !state.user.hasIQ
    );

  $(".test-card[data-test=PQ]")
    ?.classList.toggle(
      "locked",
      !state.user.hasEQ
    );

  show(
    "homeScreen"
  );

  updateLive();

  setInterval(
    updateLive,
    5000
  );
}


async function updateLive() {
  try {

    const d =
      await api(
        "/api/stats/live"
      );

    animateNumber(
      $("#liveTotal"),
      d.total
    );

    animateNumber(
      $("#liveOnline"),
      d.online
    );

  } catch (e) {}
}


function animateNumber(
  el,
  n
) {
  if (!el) return;

  el.textContent =
    Number(
      n || 0
    ).toLocaleString(
      "uz-UZ"
    );
}


/* =========================
   PROFILE
========================= */

async function saveProfile() {
  const body = {
    full_name:
      $("#fullName")
        .value
        .trim(),

    gender:
      $("#gender")
        .value,

    age:
      Number(
        $("#age")
          .value
      ),

    country:
      $("#country")
        .value
  };

  try {

    await api(
      "/api/profile/save",
      {
        method: "POST",
        body:
          JSON.stringify(body)
      }
    );

    state.user = {
      ...state.user,
      ...body
    };

    toast(
      "Profil saqlandi"
    );

    const pending =
      state.pendingType;

    if (pending) {

      delete state.pendingType;

      setTimeout(
        () => startTest(
          pending
        ),
        300
      );

    } else {
      show(
        "homeScreen"
      );
    }

  } catch (e) {

    toast(
      e.message ||
      "Profil saqlanmadi"
    );
  }
}


/* =========================
   RANKING
========================= */

async function loadRanking() {
  try {

    const d =
      await api(
        "/api/ranking"
      );

    const box =
      $("#rankingList");

    box.innerHTML =
      d.ranking.length

        ? d.ranking
            .map(
              (r) => `
                <div class="rank-row">

                  <span class="rank-pos">
                    #${r.position}
                  </span>

                  <span>
                    <b>
                      ${escapeHtml(
                        r.name
                      )}
                    </b>

                    <small>
                      ${escapeHtml(
                        r.level || ""
                      )}
                    </small>
                  </span>

                  <strong>
                    ${r.score}
                  </strong>

                </div>
              `
            )
            .join("")

        : `
          <div class="form-card glass">
            Hali natijalar yo‘q.
          </div>
        `;

    show(
      "rankingScreen"
    );

  } catch (e) {

    toast(
      e.message ||
      "Reyting yuklanmadi"
    );
  }
}


/* =========================
   CERTIFICATE
========================= */

async function loadCertificate() {
  try {

    const d =
      await api(
        "/api/certificate/mine"
      );

    const c =
      d.certificate;

    $("#certificateBox")
      .innerHTML =

      c

        ? `
          <span class="pill">
            VERIFIED
          </span>

          <h2>
            ${escapeHtml(
              c.full_name
            )}
          </h2>

          <div class="score-ring">

            <strong>
              ${c.score}
            </strong>

            <small>
              IQ
            </small>

          </div>

          <p>
            ${escapeHtml(
              c.level || ""
            )}
          </p>

          <div class="cert-code">
            ${escapeHtml(
              c.verification_code
            )}
          </div>

          <p>
            IQ TEST BOT
          </p>

          <button
            id="certDownload"
            class="primary"
          >
            PNG ochish
          </button>
        `

        : `
          <p>
            Hali sertifikatingiz yo‘q.
          </p>
        `;

    $("#certDownload")
      ?.addEventListener(
        "click",
        () => {
          window.open(
            `/api/certificate/${encodeURIComponent(
              c.certificate_id
            )}/png`,
            "_blank"
          );
        }
      );

    show(
      "certificateScreen"
    );

  } catch (e) {

    toast(
      e.message ||
      "Sertifikat yuklanmadi"
    );
  }
}


/* =========================
   BATTLE
========================= */

async function createBattle() {
  try {

    const d =
      await api(
        "/api/battle/create",
        {
          method: "POST",
          body: "{}"
        }
      );

    state.battleId =
      d.battle_id;

    state.battleReady =
      false;

    $("#battleInfo")
      .innerHTML = `
        <div class="cert-code">
          ${escapeHtml(d.code)}
        </div>

        <p>
          Do‘stingizga shu kodni yuboring.
        </p>

        <button
          id="battlePay"
          class="primary"
        >
          To‘lovni boshlash
        </button>

        <p id="battleStatus">
          Raqib kutilmoqda...
        </p>
      `;

    $("#battlePay")
      ?.addEventListener(
        "click",
        async () => {

          try {

            const p =
              await api(
                `/api/battle/${state.battleId}/payment`,
                {
                  method: "POST",
                  body: "{}"
                }
              );

            await renderPayment(
              p
            );

            show(
              "paymentScreen"
            );

          } catch (e) {

            toast(
              e.message ||
              "Battle to‘lovi ochilmadi"
            );
          }
        }
      );

    startBattlePolling();

  } catch (e) {

    toast(
      e.message ||
      "Battle yaratilmadi"
    );
  }
}


async function joinBattle() {
  const code =
    $("#battleCode")
      .value
      .trim()
      .toUpperCase();

  if (
    !/^[A-Z0-9]{4}$/.test(
      code
    )
  ) {
    toast(
      "4 belgili battle kodini kiriting"
    );

    return;
  }

  try {

    const d =
      await api(
        "/api/battle/join",
        {
          method: "POST",
          body:
            JSON.stringify({
              code
            })
        }
      );

    state.battleId =
      d.battle_id;

    state.battleReady =
      false;

    const p =
      await api(
        `/api/battle/${state.battleId}/payment`,
        {
          method: "POST",
          body: "{}"
        }
      );

    await renderPayment(
      p
    );

    show(
      "paymentScreen"
    );

    startBattlePolling();

  } catch (e) {

    toast(
      e.message ||
      "Battlega qo‘shilib bo‘lmadi"
    );
  }
}


function startBattlePolling() {
  clearInterval(
    state.battlePoll
  );

  if (!state.battleId)
    return;

  state.battlePoll =
    setInterval(
      checkBattle,
      5000
    );

  checkBattle();
}


async function checkBattle() {
  if (!state.battleId)
    return;

  try {

    const d =
      await api(
        `/api/battle/${state.battleId}`
      );

    const battle =
      d.battle;

    if (!battle)
      return;

    const status =
      battle.status;

    const statusEl =
      $("#battleStatus");

    if (statusEl) {

      if (status === "waiting") {
        statusEl.textContent =
          "Raqib kutilmoqda...";
      }

      else if (
        status === "payments"
      ) {
        statusEl.textContent =
          "Ikkinchi ishtirokchi to‘lovi kutilmoqda...";
      }

      else if (
        status === "ready"
      ) {
        statusEl.textContent =
          "✅ Battle tayyor.";
      }

      else if (
        status === "finished"
      ) {
        statusEl.textContent =
          "Battle yakunlangan.";
      }
    }

    if (
      status === "ready" &&
      !state.battleReady
    ) {

      state.battleReady =
        true;

      clearInterval(
        state.battlePoll
      );

      renderBattleReady();
    }

    if (
      status === "finished"
    ) {
      clearInterval(
        state.battlePoll
      );
    }

  } catch (e) {}
}


function renderBattleReady() {
  const info =
    $("#battleInfo");

  if (!info)
    return;

  info.innerHTML += `
    <button
      id="startBattleTest"
      class="primary"
      style="margin-top:12px"
    >
      ⚔️ Battle testini boshlash
    </button>
  `;

  $("#startBattleTest")
    ?.addEventListener(
      "click",
      startBattleTest
    );

  toast(
    "Battle tayyor. Testni boshlashingiz mumkin."
  );
}


async function startBattleTest() {
  if (!state.battleId) {
    toast(
      "Battle topilmadi"
    );

    return;
  }

  try {

    const d =
      await api(
        `/api/battle/${state.battleId}`
      );

    if (
      d.battle?.status !==
      "ready"
    ) {
      toast(
        "Hali battle tayyor emas"
      );

      return;
    }

    if (
      !state.questions.length
    ) {
      const boot =
        await api(
          "/api/bootstrap"
        );

      state.questions =
        boot.questions || [];
    }

    if (
      !state.questions.length
    ) {
      toast(
        "Battle savollari topilmadi"
      );

      return;
    }

    state.testType =
      "BATTLE";

    state.index = 0;
    state.answers = {};
    state.selected = null;
    state.startedAt =
      Date.now();

    show(
      "testScreen"
    );

    renderQuestion();

    startTimer();

  } catch (e) {

    toast(
      e.message ||
      "Battle boshlanmadi"
    );
  }
}


async function finishBattle() {
  clearInterval(
    timerHandle
  );

  if (
    state.selected !== null
  ) {
    state.answers[
      String(state.index + 1)
    ] =
      state.selected;
  }

  show(
    "loadingResult"
  );

  try {

    const d =
      await api(
        `/api/battle/${state.battleId}/submit`,
        {
          method: "POST",
          body:
            JSON.stringify({
              answers:
                state.answers
            })
        }
      );

    $("#resultScore")
      .textContent =
      d.score ??
      "—";

    $("#resultLevel")
      .textContent =
      d.status === "finished"
        ? "Battle yakunlandi"
        : "Javoblaringiz qabul qilindi";

    $("#resultCorrect")
      .textContent =
      "Raqib natijasi ikkalangiz ham tugatgandan keyin ochiladi.";

    show(
      "resultScreen"
    );

    startBattleResultPolling();

  } catch (e) {

    show(
      "testScreen"
    );

    toast(
      e.message ||
      "Battle natijasini yuborib bo‘lmadi"
    );
  }
}


function startBattleResultPolling() {
  clearInterval(
    state.battlePoll
  );

  state.battlePoll =
    setInterval(
      async () => {

        try {

          const d =
            await api(
              `/api/battle/${state.battleId}/result`
            );

          if (!d.ready)
            return;

          clearInterval(
            state.battlePoll
          );

          $("#resultLevel")
            .textContent =
            d.outcome === "win"
              ? "🏆 G‘alaba"
              : d.outcome === "loss"
                ? "Battle yakunlandi"
                : "🤝 Durrang";

          $("#resultCorrect")
            .textContent =
            `Siz: ${d.my_score} · Raqib: ${d.opponent_score}`;

        } catch (e) {}

      },
      5000
    );
}


/* =========================
   HELPERS
========================= */

function escapeHtml(s) {
  return String(
    s ?? ""
  ).replace(
    /[&<>"']/g,
    (m) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }[m])
  );
}


/* =========================
   EVENTS
========================= */

$$(".test-card")
  .forEach((b) => {

    b.addEventListener(
      "click",
      () => {
        startTest(
          b.dataset.test
        );
      }
    );

  });


$("#nextQuestion")
  .onclick = () => {

    if (
      state.selected === null
    ) {
      return;
    }

    state.answers[
      String(state.index + 1)
    ] =
      state.selected;

    saveProgress();

    if (
      state.index <
      state.questions.length - 1
    ) {

      state.index++;

      renderQuestion();

    } else {

      if (
        state.testType ===
        "BATTLE"
      ) {
        finishBattle();
      } else {
        finishTest();
      }
    }
  };


$("#saveProfile")
  .onclick =
  saveProfile;


$("#copyCard")
  .onclick =
  async () => {

    try {

      await navigator.clipboard
        .writeText(
          $("#cardNumber")
            .textContent
        );

      toast(
        "Karta nusxalandi"
      );

    } catch {

      toast(
        "Nusxalash imkoni bo‘lmadi"
      );
    }
  };


$("#sendReceipt")
  .onclick =
  async () => {

    try {

      if (!state.paymentId) {
        toast(
          "Payment topilmadi"
        );

        return;
      }

      const receipt =
        $("#receiptInput")
          .value
          .trim();

      if (!receipt) {
        toast(
          "Receipt file_id kiriting"
        );

        return;
      }

      const fd =
        new FormData();

      fd.append(
        "receipt_file_id",
        receipt
      );

      await api(
        `/api/payment/${state.paymentId}/receipt`,
        {
          method: "POST",
          body: fd
        }
      );

      $("#paymentStatus")
        .textContent =
        "Receipt yuborildi. Admin tasdig‘i kutilmoqda.";

      toast(
        "Receipt yuborildi"
      );

    } catch (e) {

      toast(
        e.message ||
        "Receipt yuborilmadi"
      );
    }
  };


$("#sharePayment")
  .onclick =
  () => {

    toast(
      "To‘lov kartasi ma’lumotlari yuqorida ko‘rsatilgan"
    );
  };


$("#certificateBtn")
  .onclick =
  loadCertificate;


$("#createBattle")
  .onclick =
  createBattle;


$("#joinBattle")
  .onclick =
  joinBattle;


$$("[data-nav]")
  .forEach((b) => {

    b.addEventListener(
      "click",
      () => {

        const n =
          b.dataset.nav;

        if (
          n === "home"
        ) {
          show(
            "homeScreen"
          );
        }

        if (
          n === "ranking"
        ) {
          loadRanking();
        }

        if (
          n === "certificate"
        ) {
          loadCertificate();
        }

        if (
          n === "profile"
        ) {
          show(
            "profileScreen"
          );
        }
      }
    );

  });


$$("[data-back]")
  .forEach((b) => {

    b.addEventListener(
      "click",
      () => {
        show(
          "homeScreen"
        );
      }
    );

  });


$("#testBack")
  .onclick =
  () => {

    clearInterval(
      timerHandle
    );

    if (
      state.testType ===
      "BATTLE"
    ) {
      show(
        "battleScreen"
      );
    } else {
      show(
        "homeScreen"
      );
    }
  };


$("#profileTopBtn")
  .onclick =
  () => {
    show(
      "profileScreen"
    );
  };


$("#battleCard")
  .onclick =
  () => {

    show(
      "battleScreen"
    );

    if (
      state.battleId
    ) {
      startBattlePolling();
    }
  };


$("#profileCard")
  .onclick =
  () => {

    if (
      state.user?.hasIQ &&
      state.user?.hasEQ &&
      state.user?.hasPQ
    ) {
      show(
        "profileScreen"
      );
    } else {
      toast(
        "IQ + EQ + PQ natijalari kerak"
      );
    }
  };


$("#battleCode")
  ?.addEventListener(
    "input",
    (e) => {

      e.target.value =
        e.target.value
          .toUpperCase()
          .replace(
            /[^A-Z0-9]/g,
            ""
          )
          .slice(0, 4);
    }
  );


setInterval(
  () => {

    if (
      state.paymentId &&
      !$("#paymentScreen")
        .classList
        .contains("hidden")
    ) {
      refreshPayment();
    }

  },
  5000
);


/* =========================
   START
========================= */

(async () => {

  try {

    show(
      "loadingScreen"
    );

    await loadHome();

  } catch (e) {

    show(
      "homeScreen"
    );

    toast(
      e.message ||
      "Mini App yuklanmadi"
    );
  }

})();

})();