(() => {
  "use strict";

  const tg = window.Telegram?.WebApp || null;
  if (tg) {
    try { tg.ready(); tg.expand(); } catch (_) {}
  }

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  const state = {
    user: null, prices: {}, questions: [],
    sessionId: null, testType: null, mode: "NORMAL",
    index: 0, answers: {}, selected: null, startedAt: 0,
    attemptId: null, paymentId: null, paymentAttemptId: null,
    battleId: null, battlePolling: null, paymentPolling: null, busy: false
  };

  const screens = ["loadingScreen","homeScreen","profileScreen","testScreen","loadingResult","paymentScreen","resultScreen","rankingScreen","certificateScreen","battleScreen"];

  function show(id) {
    screens.forEach((x) => document.getElementById(x)?.classList.toggle("hidden", x !== id));
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function toast(message) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(window.__toast);
    window.__toast = setTimeout(() => el.classList.remove("show"), 2800);
  }

  function initData() { return tg?.initData || ""; }

  async function api(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    const raw = initData();
    if (raw) headers.set("X-Telegram-Init-Data", raw);
    if (method !== "GET" && !(options.body instanceof FormData) && options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 18000);
    try {
      const res = await fetch(path, { ...options, method, headers, signal: controller.signal });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { ok: false, error: text || "Server javobi noto‘g‘ri" }; }
      if (!res.ok) throw new Error(data.error || data.detail || `HTTP ${res.status}`);
      return data;
    } catch (err) {
      if (err?.name === "AbortError") throw new Error("Server javobi juda uzoq davom etdi.");
      throw err;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function apiBlob(path) {
    const headers = new Headers();
    const raw = initData();
    if (raw) headers.set("X-Telegram-Init-Data", raw);
    const res = await fetch(path, { headers });
    if (!res.ok) {
      let message = `HTTP ${res.status}`;
      try { const d = await res.json(); message = d.error || d.detail || message; } catch (_) {}
      throw new Error(message);
    }
    return res.blob();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (m) => ({
      "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
    }[m]));
  }

  function saveProgress() {
    if (!state.sessionId || state.mode !== "NORMAL") return;
    try {
      localStorage.setItem("iq_test_progress", JSON.stringify({
        sessionId: state.sessionId, testType: state.testType,
        index: state.index, answers: state.answers, startedAt: state.startedAt
      }));
    } catch (_) {}
  }

  function clearProgress() {
    try { localStorage.removeItem("iq_test_progress"); } catch (_) {}
  }

  function difficulty(index) { return index < 6 ? "EASY" : index < 12 ? "MEDIUM" : "HARD"; }

  function svgFor(cell) {
    if (!cell || typeof cell !== "object") return null;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 44 44");
    svg.setAttribute("aria-hidden", "true");
    const add = (tag, attrs) => {
      const el = document.createElementNS(ns, tag);
      Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
      svg.appendChild(el);
      return el;
    };

    if (cell.type === "num") {
      const t = add("text", { x:"22", y:"28", "text-anchor":"middle", fill:"#f5f7ff", "font-size":"18", "font-weight":"800" });
      t.textContent = String(cell.val);
      return svg;
    }
    if (cell.type === "dot") {
      const n = Math.min(24, Math.max(1, Number(cell.count) || 1));
      const positions = [];
      for (let row = 0; row < 5; row++) {
        for (let col = 0; col < 5; col++) {
          if (positions.length >= 24) break;
          positions.push([8 + col * 7, 8 + row * 7]);
        }
      }
      positions.slice(0, n).forEach(([cx, cy]) => add("circle", { cx, cy, r:"2.2", fill:"#a78bfa" }));
      return svg;
    }
    if (cell.type === "grid") {
      const pos = Math.max(0, Math.min(8, Number(cell.pos) || 0));
      for (let i = 0; i < 9; i++) {
        add("rect", {
          x: 5 + (i % 3) * 11, y: 5 + Math.floor(i / 3) * 11,
          width:"8", height:"8", rx:"2",
          fill: i === pos ? "#a78bfa" : "#202a40",
          stroke: i === pos ? "#c9baff" : "none"
        });
      }
      return svg;
    }
    const drawShape = (name, cx, cy, size, fillMode) => {
      const fill = fillMode === "empty" ? "none" : fillMode === "half" ? "#a78bfa88" : "#a78bfa";
      const stroke = "#c9baff";
      if (name === "circle") add("circle", { cx, cy, r:size, fill, stroke, "stroke-width":"2" });
      else if (name === "square") add("rect", { x:cx-size, y:cy-size, width:size*2, height:size*2, rx:"2", fill, stroke, "stroke-width":"2" });
      else if (name === "triangle") add("polygon", { points:`${cx},${cy-size} ${cx+size},${cy+size} ${cx-size},${cy+size}`, fill, stroke, "stroke-width":"2" });
      else add("polygon", { points:`${cx},${cy-size} ${cx+size},${cy} ${cx},${cy+size} ${cx-size},${cy}`, fill, stroke, "stroke-width":"2" });
    };
    if (cell.type === "shape") { drawShape(cell.shape, 22, 22, 11, cell.fill); return svg; }
    if (cell.type === "combo") {
      const shapes = Array.isArray(cell.shapes) ? cell.shapes.slice(0, 4) : [];
      const spots = [[14,22],[30,22],[22,12],[22,32]];
      shapes.forEach((shape, i) => drawShape(shape, spots[i][0], spots[i][1], i ? 6 : 7, cell.fill));
      return svg;
    }
    return svg;
  }

  function renderCell(cell) {
    const div = document.createElement("div");
    div.className = "matrix-cell";
    if (cell?.type === "question") {
      div.classList.add("question");
      div.textContent = "?";
    } else {
      const svg = svgFor(cell);
      if (svg) div.appendChild(svg);
    }
    return div;
  }

  function renderOption(option, index) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "option";
    button.dataset.i = String(index);
    const letter = document.createElement("span");
    letter.className = "letter";
    letter.textContent = "ABCD"[index];
    button.appendChild(letter);

    if (typeof option === "string") {
      const text = document.createElement("span");
      text.className = "text-option";
      text.textContent = option;
      button.appendChild(text);
    } else {
      const svg = svgFor(option);
      if (svg) button.appendChild(svg);
    }

    button.addEventListener("click", () => {
      state.selected = index;
      $$(".option").forEach((x) => x.classList.remove("selected"));
      button.classList.add("selected");
      $("#nextQuestion").disabled = false;
    });
    return button;
  }

  function renderQuestion() {
    const q = state.questions[state.index];
    if (!q) return;
    state.selected = null;
    $("#nextQuestion").disabled = true;
    $("#questionLabel").textContent = `Q${state.index + 1}/${state.questions.length}`;
    $("#difficulty").textContent = state.mode === "BATTLE" ? "BATTLE" : state.testType === "IQ" ? difficulty(state.index) : state.testType;
    $("#progressBar").style.width = `${((state.index) / Math.max(1, state.questions.length)) * 100}%`;
    $("#questionText").textContent = state.testType === "IQ" ? "Qaysi variant matritsani to‘ldiradi?" : q.text || "Savol";

    const matrix = $("#matrix");
    matrix.innerHTML = "";
    matrix.classList.toggle("hidden", state.testType !== "IQ");
    if (state.testType === "IQ") (q.matrix || []).forEach((cell) => matrix.appendChild(renderCell(cell)));

    const options = $("#options");
    options.innerHTML = "";
    (q.options || []).forEach((option, i) => options.appendChild(renderOption(option, i)));
    $("#nextQuestion").textContent = state.index === state.questions.length - 1 ? "Natijani ko‘rish" : "Davom etish";
    $("#celebration")?.classList.toggle("hidden", !(state.testType === "IQ" && (state.index === 6 || state.index === 12)));
  }

  function startTimer() {
    clearInterval(window.__timer);
    const started = state.startedAt || Date.now();
    const end = started + 30 * 60 * 1000;
    const tick = () => {
      const sec = Math.max(0, Math.floor((end - Date.now()) / 1000));
      $("#timer").textContent = `${String(Math.floor(sec/60)).padStart(2,"0")}:${String(sec%60).padStart(2,"0")}`;
      if (sec <= 0) { clearInterval(window.__timer); finishTest(); }
    };
    tick();
    window.__timer = setInterval(tick, 500);
  }

  async function startTest(type, profileConfirmed = false) {
    if (state.busy) return;

    // Profile must be confirmed before every test. Existing values are prefilled.
    // profileConfirmed=true is used only after /api/profile/save succeeds, so
    // saving the profile does not reopen the profile screen in a loop.
    if (!profileConfirmed) {
      state.pendingType = type;
      $("#fullName").value = state.user?.full_name || "";
      $("#gender").value = state.user?.gender || "";
      $("#age").value = state.user?.age || "";
      $("#country").value = state.user?.country || "";
      show("profileScreen");
      return;
    }
    if (type === "EQ" && !state.user.hasIQ) { toast("Avval IQ testni yakunlang"); return; }
    if (type === "PQ" && !state.user.hasEQ) { toast("Avval EQ testni yakunlang"); return; }
    try {
      state.busy = true;
      const d = await api("/api/test/start", { method:"POST", body:JSON.stringify({ test_type:type }) });
      state.mode = "NORMAL";
      state.testType = type;
      state.questions = d.questions || [];
      state.sessionId = d.session_id;
      state.answers = d.resumed ? (d.answers || {}) : {};
      state.index = d.resumed ? Math.min(Object.keys(state.answers).length, Math.max(0, state.questions.length - 1)) : 0;
      state.startedAt = d.resumed && d.started_at ? Date.parse(d.started_at) : Date.now();
      saveProgress();
      show("testScreen");
      renderQuestion();
      startTimer();
    } catch (e) { toast(e.message); }
    finally { state.busy = false; }
  }

  async function finishTest() {
    if (state.busy || !state.questions.length) return;
    clearInterval(window.__timer);
    if (state.selected !== null) state.answers[String(state.index + 1)] = state.selected;
    saveProgress();
    show("loadingResult");
    try {
      state.busy = true;
      if (state.mode === "BATTLE") {
        const d = await api(`/api/battle/${state.battleId}/submit`, {
          method:"POST", body:JSON.stringify({ answers:state.answers })
        });
        state.busy = false;
        if (d.already_finished || d.status === "finished" || d.status === "waiting_opponent") {
          await waitBattleResult();
        }
        return;
      }
      const d = await api(`/api/test/${state.sessionId}/submit`, {
        method:"POST",
        body:JSON.stringify({ answers:state.answers, duration:Math.floor((Date.now()-state.startedAt)/1000) })
      });
      clearProgress();
      state.attemptId = d.attempt_id;
      state.paymentAttemptId = d.attempt_id;
      if (d.payment_required) {
        await renderPayment({ ...d, payment_id:d.payment_id });
        show("paymentScreen");
      } else {
        await showResult(d.attempt_id);
      }
    } catch (e) {
      show("testScreen");
      toast(e.message);
    } finally { state.busy = false; }
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    if (!total) return "—";
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  async function showResult(attemptId) {
    const d = await api(`/api/result/${attemptId}`);
    if (!d.visible) {
      state.attemptId = attemptId;
      const p = await api("/api/payment/mine");
      const mine = p.payments.find((x) => Number(x.attempt_id) === Number(attemptId));
      if (mine) {
        state.paymentId = mine.id;
        state.paymentAttemptId = attemptId;
        const card = await getPaymentCard(mine.id);
        await renderPayment({ amount:mine.amount, payment_id:mine.id, card, status:mine.status });
        show("paymentScreen");
      } else toast("Natija hali yopiq");
      return;
    }
    state.attemptId = attemptId;
    state.paymentAttemptId = attemptId;
    state.testType = d.test_type || state.testType || "IQ";
    const questionCount = Number(d.question_count || (state.testType === "IQ" ? 18 : 6));
    const correct = Number(d.correct_count || 0);
    const accuracy = Math.max(0, Math.min(100, Number(d.accuracy ?? (questionCount ? Math.round(correct / questionCount * 100) : 0))));
    const duration = Math.max(0, Number(d.duration || 0));
    const avg = Number(d.avg_time || (questionCount && duration ? duration / questionCount : 0));
    const score = Number(d.score || 0);

    $("#resultBadge").textContent = state.testType === "IQ" ? "IQ TEST YAKUNLANDI" : `${state.testType} TEST YAKUNLANDI`;
    $("#resultUnit").textContent = state.testType === "IQ" ? "IQ" : "%";
    $("#resultScore").textContent = score;
    $("#resultLevel").textContent = d.level || (state.testType === "IQ" ? "—" : "Natija");
    $("#resultQuestions").textContent = `${questionCount}/${questionCount}`;
    $("#resultCorrectStat").textContent = `${correct}/${questionCount}`;
    $("#resultDuration").textContent = formatDuration(duration);
    $("#resultAvgTime").textContent = avg ? `${avg.toFixed(1)} s` : "—";
    $("#resultAccuracy").textContent = `${accuracy}%`;
    $("#accuracyBar").style.width = `${accuracy}%`;

    const minScore = state.testType === "IQ" ? 70 : 0;
    const maxScore = state.testType === "IQ" ? 130 : 100;
    const ratio = Math.max(0, Math.min(1, (score - minScore) / Math.max(1, maxScore - minScore)));
    $("#scoreRing")?.style.setProperty("--score-angle", `${Math.round(35 + ratio * 325)}deg`);

    if (d.ranking_position) {
      const total = Number(d.ranking_total || 0);
      $("#resultRank").textContent = `#${d.ranking_position}`;
      $("#resultRankText").textContent = total > 1 ? `${total} ta natija ichida` : "Birinchi natijangiz";
    } else {
      $("#resultRank").textContent = "—";
      $("#resultRankText").textContent = "Reyting hali shakllanmagan";
    }

    $("#resultSummaryText").textContent = state.testType === "IQ"
      ? `${correct} ta savolga to‘g‘ri javob berdingiz. IQ ballingiz ${score} va test darajasi “${d.level || "—"}” sifatida hisoblandi.`
      : `Test natijangiz ${score}% ko‘rsatkich bilan yakunlandi.`;

    $("#startEqFromResult")?.classList.toggle("hidden", state.testType !== "IQ" || !state.user?.hasIQ);
    show("resultScreen");
  }

  async function getPaymentCard(paymentId) {
    try { const d = await api(`/api/payment/${paymentId}/card`); return d.card; } catch (_) { return null; }
  }

  function paymentActions() {
    let box = $("#paymentActions");
    if (!box) {
      box = document.createElement("div");
      box.id = "paymentActions";
      box.className = "payment-actions";
      $("#paymentStatus")?.insertAdjacentElement("afterend", box);
    }
    return box;
  }

  function clearPaymentActions() {
    const box = $("#paymentActions");
    if (box) box.innerHTML = "";
  }

  function renderApprovedPaymentAction() {
    const box = paymentActions();
    if (state.battleId) {
      box.innerHTML = `<button id="paymentNextBtn" class="primary">⚔️ Battle'ga o‘tish</button>`;
      $("#paymentNextBtn").onclick = async () => {
        show("battleScreen");
        await checkBattleReady(true);
        startBattlePolling();
      };
    } else if (state.paymentAttemptId) {
      box.innerHTML = `<button id="paymentNextBtn" class="primary">📊 Natijani ko‘rish</button>`;
      $("#paymentNextBtn").onclick = async () => {
        try { await showResult(state.paymentAttemptId); } catch (e) { toast(e.message); }
      };
    } else {
      box.innerHTML = `<button id="paymentNextBtn" class="primary">🏠 Bosh sahifaga qaytish</button>`;
      $("#paymentNextBtn").onclick = () => show("homeScreen");
    }
  }

  function renderRejectedPaymentAction() {
    const box = paymentActions();
    box.innerHTML = `<button id="paymentHomeBtn" class="secondary">🏠 Bosh sahifaga qaytish</button>
      <button id="paymentRetryBtn" class="primary" style="margin-top:8px">🔄 Receiptni qayta yuborish</button>`;
    $("#paymentHomeBtn").onclick = () => show("homeScreen");
    $("#paymentRetryBtn").onclick = () => {
      $("#paymentStatus").textContent = "Receiptni qayta yuboring.";
      $("#receiptFile").disabled = false;
      $("#sendReceipt").disabled = false;
      clearPaymentActions();
    };
  }

  async function renderPayment(d) {
    state.paymentId = d.payment_id ?? d.id ?? state.paymentId;
    state.paymentAttemptId = d.attempt_id ?? state.paymentAttemptId;
    if (d.battle_id !== undefined) state.battleId = d.battle_id || null;
    $("#paymentAmount").textContent = `${Number(d.amount || 0).toLocaleString("uz-UZ")} so‘m`;
    const card = d.card || (state.paymentId ? await getPaymentCard(state.paymentId) : null);
    $("#cardNumber").textContent = card?.card_number || "Faol karta topilmadi";
    $("#cardHolder").textContent = card?.holder || "";
    $("#cardBank").textContent = card?.bank || "";
    clearPaymentActions();
    $("#receiptFile").disabled = false;
    $("#sendReceipt").disabled = false;
    if (d.status === "approved") {
      $("#paymentStatus").textContent = "✅ To‘lov tasdiqlandi. Keyingi bosqich ochildi.";
      $("#receiptFile").disabled = true;
      $("#sendReceipt").disabled = true;
      renderApprovedPaymentAction();
    } else if (d.status === "rejected") {
      $("#paymentStatus").textContent = "❌ To‘lov tasdiqlanmadi. Admin receiptni rad etdi.";
      renderRejectedPaymentAction();
    } else if (d.receipt_file_id) {
      $("#paymentStatus").textContent = "✅ Receipt yuborilgan. Admin tasdig‘i kutilmoqda.";
    } else {
      $("#paymentStatus").textContent = card ? "Kartaga to‘lov qiling va receipt yuklang." : "Admin karta qo‘shishini kuting.";
    }
    $("#receiptInput").value = "";
    $("#receiptFile").value = "";
  }

  async function refreshPayment() {
    if (!state.paymentId) return;
    try {
      const p = await api("/api/payment/mine");
      const mine = p.payments.find((x) => Number(x.id) === Number(state.paymentId));
      if (!mine) return;
      if (mine.battle_id !== undefined) state.battleId = mine.battle_id || null;
      if (mine.attempt_id !== undefined) state.paymentAttemptId = mine.attempt_id;
      if (mine.status === "approved") {
        $("#paymentStatus").textContent = "✅ To‘lov tasdiqlandi. Keyingi bosqich ochildi.";
        $("#receiptFile").disabled = true;
        $("#sendReceipt").disabled = true;
        clearPaymentActions();
        renderApprovedPaymentAction();
      } else if (mine.status === "rejected") {
        $("#paymentStatus").textContent = "❌ To‘lov tasdiqlanmadi. Admin receiptni rad etdi.";
        $("#receiptFile").disabled = false;
        $("#sendReceipt").disabled = false;
        clearPaymentActions();
        renderRejectedPaymentAction();
      } else if (mine.receipt_file_id) {
        $("#paymentStatus").textContent = "✅ Receipt yuborilgan. Admin tasdig‘i kutilmoqda.";
      } else {
        $("#paymentStatus").textContent = "Receipt kutilmoqda.";
      }
    } catch (_) {}
  }

  async function sendReceipt() {
    if (!state.paymentId) { toast("Payment topilmadi"); return; }
    const file = $("#receiptFile")?.files?.[0];
    const legacy = $("#receiptInput")?.value.trim();
    if (!file && !legacy) { toast("Receipt rasmini tanlang"); return; }
    try {
      const fd = new FormData();
      if (file) fd.append("receipt", file, file.name);
      else fd.append("receipt_file_id", legacy);
      const d = await api(`/api/payment/${state.paymentId}/receipt`, { method:"POST", body:fd });
      clearPaymentActions();
      $("#paymentStatus").textContent = d.status === "approved" ? "✅ To‘lov tasdiqlandi. Keyingi bosqich ochildi." : "Receipt yuborildi. Admin tasdig‘i kutilmoqda.";
      toast(d.status === "approved" ? "To‘lov tasdiqlandi" : "Receipt yuborildi");
      if (d.status === "approved") renderApprovedPaymentAction();
      else if (state.battleId) startBattlePolling();
    } catch (e) { toast(e.message); }
  }

  async function loadHome() {
    const d = await api("/api/bootstrap");
    state.user = d.user;
    state.prices = d.prices || {};
    state.questions = d.questions || [];
    $("#userName").textContent = d.user.first_name || "Do‘st";
    $("#fullName").value = d.user.full_name || "";
    $("#gender").value = d.user.gender || "";
    $("#age").value = d.user.age || "";
    $("#country").value = d.user.country || "";
    updateHomeLocks();
    renderPersonalProfile();
    show("homeScreen");
    updateLive();
    clearInterval(window.__liveTimer);
    window.__liveTimer = setInterval(updateLive, 5000);

    // Payment state must survive closing/reopening the Mini App.
    // Bootstrap returns the latest pending payment, so the user is placed
    // straight back on the receipt screen instead of losing the flow.
    if (d.pending_payment) {
      const p = d.pending_payment;
      state.paymentId = p.id;
      state.paymentAttemptId = p.attempt_id;
      state.battleId = p.battle_id || null;
      await renderPayment({
        payment_id: p.id,
        attempt_id: p.attempt_id,
        battle_id: p.battle_id || null,
        amount: p.amount,
        status: p.status,
        receipt_file_id: p.receipt_file_id,
        card: p.card
      });
      show("paymentScreen");
    } else {
      await restoreProgress();
    }
  }

  function updateHomeLocks() {
    $("#eqState").textContent = state.user.hasIQ ? "Ochilgan" : "IQdan keyin ochiladi";
    $("#pqState").textContent = state.user.hasEQ ? "Ochilgan" : "EQdan keyin ochiladi";
    $(".test-card[data-test=EQ]")?.classList.toggle("locked", !state.user.hasIQ);
    $(".test-card[data-test=PQ]")?.classList.toggle("locked", !state.user.hasEQ);
  }

  async function restoreProgress() {
    let saved;
    try { saved = JSON.parse(localStorage.getItem("iq_test_progress") || "null"); } catch (_) { saved = null; }
    if (!saved?.sessionId) return;
    try {
      const d = await api(`/api/test/${saved.sessionId}/resume`);
      if (d.status === "completed" || d.status === "expired") { clearProgress(); return; }
      state.mode = "NORMAL";
      state.sessionId = saved.sessionId;
      state.testType = d.test_type;
      state.questions = d.questions || [];
      state.answers = saved.answers || d.answers || {};
      state.index = Math.max(0, Math.min(Number(saved.index) || 0, state.questions.length - 1));
      state.startedAt = Number(saved.startedAt) || Date.now();
      show("testScreen");
      renderQuestion();
      startTimer();
      toast("Testingiz saqlangan joyidan davom etdi.");
    } catch (_) { clearProgress(); }
  }

  async function updateLive() {
    try {
      const d = await api("/api/stats/live");
      animateNumber($("#liveTotal"), d.total);
      animateNumber($("#liveOnline"), d.online);
    } catch (_) {}
  }

  function animateNumber(el, n) { if (el) el.textContent = Number(n || 0).toLocaleString("uz-UZ"); }

  async function saveProfile() {
    const age = Number($("#age").value);
    const body = {
      full_name: $("#fullName").value.trim(), gender: $("#gender").value,
      age, country: $("#country").value
    };
    if (!body.full_name || !body.gender || !body.country || !Number.isInteger(age) || age < 10 || age > 120) {
      toast("Profil ma’lumotlarini to‘liq kiriting"); return;
    }
    try {
      state.busy = true;
      await api("/api/profile/save", { method:"POST", body:JSON.stringify(body) });
      state.user = { ...state.user, ...body };
      $("#userName").textContent = state.user.first_name || "Do‘st";
      renderPersonalProfile();
      toast("Profil saqlandi");
      const pending = state.pendingType;
      delete state.pendingType;
      if (pending) setTimeout(() => startTest(pending, true), 250);
      else show("homeScreen");
    } catch (e) { toast(e.message); }
    finally { state.busy = false; }
  }

  function renderPersonalProfile() {
    const box = $("#personalSummary");
    if (!box || !state.user) return;
    const ready = state.user.hasIQ && state.user.hasEQ && state.user.hasPQ;
    if (!ready) {
      box.innerHTML = `<div class="empty-state"><b>Shaxsiy profil</b><span>IQ + EQ + PQ testlarini yakunlaganingizdan keyin tahlil shu yerda ochiladi.</span></div>`;
      return;
    }
    box.innerHTML = `
      <div class="summary-grid">
        <div><small>IQ</small><b>Yakunlangan</b></div>
        <div><small>EQ</small><b>Yakunlangan</b></div>
        <div><small>PQ</small><b>Yakunlangan</b></div>
      </div>
      <div class="insight"><b>Kuchli tomonlar</b><p>Muammolarni tahlil qilish, hissiy vaziyatni anglash va vazifalarni rejalashtirish bo‘yicha test javoblaringiz mavjud.</p></div>
      <div class="insight"><b>Rivojlanish nuqtalari</b><p>Natijalarni muntazam qayta ko‘rib chiqish va real hayotdagi qarorlar bilan solishtirish foydali.</p></div>`;
  }

  async function loadRanking() {
    try {
      const d = await api("/api/ranking");
      const box = $("#rankingList");
      box.innerHTML = d.ranking?.length ? d.ranking.map((r) =>
        `<div class="rank-row"><span class="rank-pos">#${r.position}</span><span><b>${escapeHtml(r.name)}</b><small>${escapeHtml(r.level || "")}</small></span><strong>${r.score}</strong></div>`
      ).join("") : `<div class="form-card glass empty-state"><b>Hali natijalar yo‘q.</b></div>`;
      show("rankingScreen");
    } catch (e) { toast(e.message); }
  }

  async function loadCertificate() {
    try {
      const d = await api("/api/certificate/mine");
      const c = d.certificate;
      $("#certificateBox").innerHTML = c ? `
        <span class="pill">VERIFIED</span>
        <h2>${escapeHtml(c.full_name)}</h2>
        <div class="score-ring"><strong>${c.score}</strong><small>IQ</small></div>
        <p>${escapeHtml(c.level || "")}</p>
        <div class="cert-code">${escapeHtml(c.verification_code)}</div>
        <p>IQ TEST BOT</p>
        <button id="certDownload" class="primary">PNG ochish</button>` : `<div class="empty-state"><b>Sertifikat yo‘q</b><span>IQ testini yakunlang va natija ochilgach sertifikat yaratiladi.</span></div>`;
      $("#certDownload")?.addEventListener("click", async () => {
        try {
          const blob = await apiBlob(`/api/certificate/${encodeURIComponent(c.certificate_id)}/png`);
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank");
          setTimeout(() => URL.revokeObjectURL(url), 30000);
        } catch (e) { toast(e.message); }
      });
      show("certificateScreen");
    } catch (e) { toast(e.message); }
  }

  function setBattleInfo(html) { $("#battleInfo").innerHTML = html; }

  async function createBattle() {
    if (state.busy) return;
    try {
      state.busy = true;
      const d = await api("/api/battle/create", { method:"POST", body:"{}" });
      state.battleId = d.battle_id;
      state.paymentAttemptId = null;
      setBattleInfo(`<div class="cert-code battle-code">${escapeHtml(d.code)}</div><p>Do‘stingizga 4 belgili kodni yuboring. Ikkalangiz ham to‘lovni tasdiqlatgach battle ochiladi.</p><button id="battlePay" class="primary">To‘lovni boshlash · ${Number(d.price).toLocaleString("uz-UZ")} so‘m</button><div id="battleStatus" class="inline-status">Opponent kutilmoqda…</div>`);
      $("#battlePay").onclick = () => startBattlePayment();
      startBattlePolling();
    } catch (e) { toast(e.message); }
    finally { state.busy = false; }
  }

  async function joinBattle() {
    if (state.busy) return;
    const code = $("#battleCode").value.trim().toUpperCase();
    if (code.length !== 4) { toast("4 belgili kod kiriting"); return; }
    try {
      state.busy = true;
      const d = await api("/api/battle/join", { method:"POST", body:JSON.stringify({ code }) });
      state.battleId = d.battle_id;
      state.paymentAttemptId = null;
      setBattleInfo(`<div class="cert-code battle-code">${escapeHtml(code)}</div><p>Battle topildi. Endi o‘z to‘lovingizni yuboring.</p><button id="battlePay" class="primary">To‘lovni boshlash · ${Number(d.price).toLocaleString("uz-UZ")} so‘m</button><div id="battleStatus" class="inline-status">To‘lov kutilmoqda…</div>`);
      $("#battlePay").onclick = () => startBattlePayment();
      startBattlePolling();
    } catch (e) { toast(e.message); }
    finally { state.busy = false; }
  }

  async function startBattlePayment() {
    if (!state.battleId) return;
    state.paymentAttemptId = null;
    try {
      const d = await api(`/api/battle/${state.battleId}/payment`, { method:"POST", body:"{}" });
      await renderPayment({ ...d, payment_id:d.payment_id });
      state.paymentId = d.payment_id;
      show("paymentScreen");
      startBattlePolling();
    } catch (e) { toast(e.message); }
  }

  function startBattlePolling() {
    clearInterval(state.battlePolling);
    state.battlePolling = setInterval(() => checkBattleReady(false), 3000);
    checkBattleReady(false);
  }

  async function checkBattleReady(showToastOnReady) {
    if (!state.battleId) return false;
    try {
      const d = await api(`/api/battle/${state.battleId}/start`);
      const status = $("#battleStatus");
      if (status) status.textContent = d.ready ? "Battle tayyor. Test boshlanmoqda…" : `Holat: ${d.status || "kutilmoqda"}`;
      if (d.ready) {
        clearInterval(state.battlePolling);
        state.questions = d.questions || [];
        state.mode = "BATTLE";
        state.testType = "IQ";
        state.index = 0;
        state.answers = {};
        state.selected = null;
        state.startedAt = Date.now();
        show("testScreen");
        renderQuestion();
        startTimer();
        if (showToastOnReady) toast("Battle to‘lovi tasdiqlandi.");
        return true;
      }
    } catch (_) {}
    return false;
  }

  async function waitBattleResult() {
    show("loadingResult");
    clearInterval(window.__timer);
    for (let i = 0; i < 40; i++) {
      try {
        const d = await api(`/api/battle/${state.battleId}/result`);
        if (d.ready) {
          $("#resultBadge").textContent = "BATTLE RESULT";
          $("#resultUnit").textContent = "IQ";
          $("#resultScore").textContent = d.my_score;
          $("#resultLevel").textContent = d.outcome === "win" ? "G‘ALABA" : d.outcome === "loss" ? "MAG‘LUBIYAT" : "DURANG";
          $("#resultCorrect").textContent = `Opponent: ${d.opponent_score}`;
          show("resultScreen");
          return;
        }
      } catch (_) {}
      await new Promise((resolve) => setTimeout(resolve, 2500));
    }
    show("battleScreen");
    toast("Opponent natijasini kutish davom etmoqda.");
  }

  $("#nextQuestion")?.addEventListener("click", () => {
    if (state.selected === null || state.busy) return;
    state.answers[String(state.index + 1)] = state.selected;
    saveProgress();
    if (state.index < state.questions.length - 1) {
      state.index += 1;
      renderQuestion();
    } else finishTest();
  });
  $("#saveProfile")?.addEventListener("click", saveProfile);
  $("#copyCard")?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("#cardNumber").textContent); toast("Karta nusxalandi"); }
    catch (_) { toast("Nusxalash imkoni bo‘lmadi"); }
  });
  $("#sendReceipt")?.addEventListener("click", sendReceipt);
  $("#sharePayment")?.addEventListener("click", () => {
    const url = `https://t.me/${encodeURIComponent("iqtest_ubot")}`;
    if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.open(url, "_blank");
  });
  $("#certificateBtn")?.addEventListener("click", loadCertificate);
  $("#startEqFromResult")?.addEventListener("click", () => startTest("EQ"));
  $("#retryIqBtn")?.addEventListener("click", () => startTest("IQ"));
  $("#shareResultBtn")?.addEventListener("click", async () => {
    const score = $("#resultScore")?.textContent || "—";
    const level = $("#resultLevel")?.textContent || "";
    const text = `🧠 IQ TEST BOT\nNatijam: ${score} IQ · ${level}`;
    try {
      if (navigator.share) await navigator.share({ title: "IQ TEST BOT", text });
      else { await navigator.clipboard.writeText(text); toast("Natija nusxalandi"); }
    } catch (_) {}
  });
  $("#createBattle")?.addEventListener("click", createBattle);
  $("#joinBattle")?.addEventListener("click", joinBattle);
  $("#profileTopBtn")?.addEventListener("click", () => show("profileScreen"));
  $("#battleCard")?.addEventListener("click", () => show("battleScreen"));
  $("#profileCard")?.addEventListener("click", () => {
    renderPersonalProfile();
    show("profileScreen");
    $("#personalSummary")?.scrollIntoView({ behavior:"smooth", block:"center" });
  });
  $("#testBack")?.addEventListener("click", () => {
    clearInterval(window.__timer);
    if (state.mode === "NORMAL") saveProgress();
    show("homeScreen");
  });
  $("[data-back]") && $$('[data-back]').forEach((b) => b.addEventListener("click", () => show("homeScreen")));
  $$(".test-card[data-test]").forEach((b) => b.addEventListener("click", () => startTest(b.dataset.test)));
  $$('[data-nav]').forEach((b) => b.addEventListener("click", () => {
    const n = b.dataset.nav;
    if (n === "home") show("homeScreen");
    if (n === "ranking") loadRanking();
    if (n === "certificate") loadCertificate();
    if (n === "profile") { renderPersonalProfile(); show("profileScreen"); }
  }));

  setInterval(() => {
    if (state.paymentId && !$("#paymentScreen")?.classList.contains("hidden")) refreshPayment();
  }, 5000);

  (async () => {
    try {
      await loadHome();
    } catch (e) {
      show("homeScreen");
      toast(e.message || "Mini App yuklanmadi");
    }
  })();
})();
