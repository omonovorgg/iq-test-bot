(() => {
  "use strict";

  const tg = window.Telegram?.WebApp || null;

  if (tg) {
    try {
      tg.ready();
      tg.expand();
      tg.enableClosingConfirmation?.();
    } catch (_) {}
  }

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const state = {
    user: null,
    prices: {},
    questions: [],

    sessionId: null,
    testType: null,
    mode: "NORMAL",

    index: 0,
    answers: {},
    selected: null,
    startedAt: 0,

    attemptId: null,
    paymentId: null,
    paymentAttemptId: null,

    battleId: null,
    battlePolling: null,

    pendingType: null,
    busy: false
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
    screens.forEach((screenId) => {
      document
        .getElementById(screenId)
        ?.classList.toggle("hidden", screenId !== id);
    });

    window.scrollTo({
      top: 0,
      behavior: "instant"
    });
  }

  function toast(message) {
    const element = $("#toast");

    if (!element) return;

    element.textContent = String(message || "");
    element.classList.add("show");

    clearTimeout(window.__toastTimer);

    window.__toastTimer = setTimeout(() => {
      element.classList.remove("show");
    }, 2800);
  }

  function initData() {
    return tg?.initData || "";
  }

  async function api(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();

    const headers = new Headers(options.headers || {});
    const rawInitData = initData();

    if (rawInitData) {
      headers.set("X-Telegram-Init-Data", rawInitData);
    }

    if (
      method !== "GET" &&
      !(options.body instanceof FormData) &&
      options.body !== undefined
    ) {
      headers.set("Content-Type", "application/json");
    }

    const controller = new AbortController();

    const timeout = setTimeout(() => {
      controller.abort();
    }, 18000);

    try {
      const response = await fetch(path, {
        ...options,
        method,
        headers,
        signal: controller.signal
      });

      const text = await response.text();

      let data = {};

      try {
        data = text ? JSON.parse(text) : {};
      } catch (_) {
        data = {
          ok: false,
          error: text || "Server javobi noto‘g‘ri."
        };
      }

      if (!response.ok) {
        throw new Error(
          data.error ||
          data.detail ||
          `HTTP ${response.status}`
        );
      }

      return data;
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new Error("Server javobi juda uzoq davom etdi.");
      }

      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function apiBlob(path) {
    const headers = new Headers();
    const rawInitData = initData();

    if (rawInitData) {
      headers.set(
        "X-Telegram-Init-Data",
        rawInitData
      );
    }

    const response = await fetch(path, {
      headers
    });

    if (!response.ok) {
      let message = `HTTP ${response.status}`;

      try {
        const data = await response.json();

        message =
          data.error ||
          data.detail ||
          message;
      } catch (_) {}

      throw new Error(message);
    }

    return response.blob();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(
      /[&<>"']/g,
      (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }[character])
    );
  }

  function saveProgress() {
    if (
      !state.sessionId ||
      state.mode !== "NORMAL"
    ) {
      return;
    }

    try {
      localStorage.setItem(
        "iq_test_progress",
        JSON.stringify({
          sessionId: state.sessionId,
          testType: state.testType,
          index: state.index,
          answers: state.answers,
          startedAt: state.startedAt
        })
      );
    } catch (_) {}
  }

  function clearProgress() {
    try {
      localStorage.removeItem(
        "iq_test_progress"
      );
    } catch (_) {}
  }

  function difficulty(index) {
    if (index < 6) return "EASY";
    if (index < 12) return "MEDIUM";
    return "HARD";
  }

  function svgFor(cell) {
    if (!cell || typeof cell !== "object") {
      return null;
    }

    const namespace =
      "http://www.w3.org/2000/svg";

    const svg =
      document.createElementNS(
        namespace,
        "svg"
      );

    svg.setAttribute(
      "viewBox",
      "0 0 44 44"
    );

    svg.setAttribute(
      "aria-hidden",
      "true"
    );

    const add = (tag, attributes) => {
      const element =
        document.createElementNS(
          namespace,
          tag
        );

      Object.entries(attributes).forEach(
        ([key, value]) => {
          element.setAttribute(
            key,
            value
          );
        }
      );

      svg.appendChild(element);

      return element;
    };

    if (cell.type === "num") {
      const text = add(
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

      text.textContent =
        String(cell.val ?? "");

      return svg;
    }

    if (cell.type === "dot") {
      const count = Math.min(
        9,
        Math.max(
          1,
          Number(cell.count) || 1
        )
      );

      const positions = [
        [10, 10],
        [22, 10],
        [34, 10],
        [10, 22],
        [22, 22],
        [34, 22],
        [10, 34],
        [22, 34],
        [34, 34]
      ];

      positions
        .slice(0, count)
        .forEach(([cx, cy]) => {
          add(
            "circle",
            {
              cx,
              cy,
              r: "3",
              fill: "#a78bfa"
            }
          );
        });

      return svg;
    }

    if (cell.type === "grid") {
      const position = Math.max(
        0,
        Math.min(
          8,
          Number(cell.pos) || 0
        )
      );

      for (let index = 0; index < 9; index += 1) {
        add(
          "rect",
          {
            x:
              5 +
              (index % 3) * 11,
            y:
              5 +
              Math.floor(index / 3) * 11,
            width: "8",
            height: "8",
            rx: "2",
            fill:
              index === position
                ? "#a78bfa"
                : "#202a40",
            stroke:
              index === position
                ? "#c9baff"
                : "none"
          }
        );
      }

      return svg;
    }

    const drawShape = (
      name,
      cx,
      cy,
      size,
      fillMode
    ) => {
      const fill =
        fillMode === "empty"
          ? "none"
          : fillMode === "half"
            ? "#a78bfa88"
            : "#a78bfa";

      const stroke = "#c9baff";

      if (name === "circle") {
        add(
          "circle",
          {
            cx,
            cy,
            r: size,
            fill,
            stroke,
            "stroke-width": "2"
          }
        );
      } else if (name === "square") {
        add(
          "rect",
          {
            x: cx - size,
            y: cy - size,
            width: size * 2,
            height: size * 2,
            rx: "2",
            fill,
            stroke,
            "stroke-width": "2"
          }
        );
      } else if (name === "triangle") {
        add(
          "polygon",
          {
            points:
              `${cx},${cy - size} ` +
              `${cx + size},${cy + size} ` +
              `${cx - size},${cy + size}`,
            fill,
            stroke,
            "stroke-width": "2"
          }
        );
      } else {
        add(
          "polygon",
          {
            points:
              `${cx},${cy - size} ` +
              `${cx + size},${cy} ` +
              `${cx},${cy + size} ` +
              `${cx - size},${cy}`,
            fill,
            stroke,
            "stroke-width": "2"
          }
        );
      }
    };

    if (cell.type === "shape") {
      drawShape(
        cell.shape,
        22,
        22,
        11,
        cell.fill
      );

      return svg;
    }

    if (cell.type === "combo") {
      const shapes =
        Array.isArray(cell.shapes)
          ? cell.shapes.slice(0, 4)
          : [];

      const spots = [
        [14, 22],
        [30, 22],
        [22, 12],
        [22, 32]
      ];

      shapes.forEach((shape, index) => {
        drawShape(
          shape,
          spots[index][0],
          spots[index][1],
          index ? 6 : 7,
          cell.fill
        );
      });

      return svg;
    }

    return svg;
  }

  function renderCell(cell) {
    const element =
      document.createElement("div");

    element.className =
      "matrix-cell";

    if (cell?.type === "question") {
      element.classList.add("question");
      element.textContent = "?";
    } else {
      const svg = svgFor(cell);

      if (svg) {
        element.appendChild(svg);
      }
    }

    return element;
  }

  function renderOption(
    option,
    index
  ) {
    const button =
      document.createElement("button");

    button.type = "button";
    button.className = "option";
    button.dataset.i =
      String(index);

    const letter =
      document.createElement("span");

    letter.className = "letter";
    letter.textContent =
      "ABCD"[index];

    button.appendChild(letter);

    if (typeof option === "string") {
      const text =
        document.createElement("span");

      text.className =
        "text-option";

      text.textContent =
        option;

      button.appendChild(text);
    } else {
      const svg = svgFor(option);

      if (svg) {
        button.appendChild(svg);
      }
    }

    button.addEventListener(
      "click",
      () => {
        if (state.busy) return;

        state.selected = index;

        $$(".option").forEach(
          (element) => {
            element.classList.remove(
              "selected"
            );
          }
        );

        button.classList.add(
          "selected"
        );

        const nextButton =
          $("#nextQuestion");

        if (nextButton) {
          nextButton.disabled =
            false;
        }
      }
    );

    return button;
  }

  function renderQuestion() {
    const question =
      state.questions[state.index];

    if (!question) return;

    state.selected = null;

    const nextButton =
      $("#nextQuestion");

    if (nextButton) {
      nextButton.disabled = true;
    }

    $("#questionLabel").textContent =
      `Q${state.index + 1}/${state.questions.length}`;

    $("#difficulty").textContent =
      state.mode === "BATTLE"
        ? "BATTLE"
        : state.testType === "IQ"
          ? difficulty(state.index)
          : state.testType;

    $("#progressBar").style.width =
      `${
        ((state.index) /
          Math.max(
            1,
            state.questions.length
          )) *
        100
      }%`;

    $("#questionText").textContent =
      state.testType === "IQ"
        ? "Qaysi variant matritsani to‘ldiradi?"
        : question.text ||
          "Savol";

    const matrix = $("#matrix");

    matrix.innerHTML = "";

    matrix.classList.toggle(
      "hidden",
      state.testType !== "IQ"
    );

    if (state.testType === "IQ") {
      (question.matrix || [])
        .forEach((cell) => {
          matrix.appendChild(
            renderCell(cell)
          );
        });
    }

    const options =
      $("#options");

    options.innerHTML = "";

    (question.options || [])
      .forEach(
        (option, index) => {
          options.appendChild(
            renderOption(
              option,
              index
            )
          );
        }
      );

    if (nextButton) {
      nextButton.textContent =
        state.index ===
        state.questions.length - 1
          ? "Natijani ko‘rish"
          : "Davom etish";
    }

    $("#celebration")
      ?.classList.toggle(
        "hidden",
        !(
          state.testType === "IQ" &&
          (
            state.index === 6 ||
            state.index === 12
          )
        )
      );
  }

  function startTimer() {
    clearInterval(
      window.__testTimer
    );

    const started =
      state.startedAt ||
      Date.now();

    const end =
      started +
      30 * 60 * 1000;

    const tick = () => {
      const seconds =
        Math.max(
          0,
          Math.floor(
            (end - Date.now()) /
              1000
          )
        );

      const timer =
        $("#timer");

      if (timer) {
        timer.textContent =
          `${String(
            Math.floor(
              seconds / 60
            )
          ).padStart(2, "0")}:${String(
            seconds % 60
          ).padStart(2, "0")}`;
      }

      if (seconds <= 0) {
        clearInterval(
          window.__testTimer
        );

        finishTest();
      }
    };

    tick();

    window.__testTimer =
      setInterval(
        tick,
        500
      );
  }

  async function startTest(type) {
    if (state.busy) return;

    const profile =
      state.user || {};

    if (
      !profile.full_name ||
      !profile.gender ||
      !profile.age ||
      !profile.country
    ) {
      state.pendingType = type;

      show("profileScreen");

      toast(
        "Avval profilingizni to‘ldiring."
      );

      return;
    }

    if (
      type === "EQ" &&
      !state.user.hasIQ
    ) {
      toast(
        "Avval IQ testini yakunlang."
      );

      return;
    }

    if (
      type === "PQ" &&
      !state.user.hasEQ
    ) {
      toast(
        "Avval EQ testini yakunlang."
      );

      return;
    }

    try {
      state.busy = true;

      const data =
        await api(
          "/api/test/start",
          {
            method: "POST",
            body: JSON.stringify({
              test_type: type
            })
          }
        );

      state.mode = "NORMAL";
      state.testType = type;
      state.questions =
        data.questions || [];

      state.sessionId =
        data.session_id;

      state.answers =
        data.resumed
          ? (data.answers || {})
          : {};

      state.index =
        data.resumed
          ? Math.min(
              Object.keys(
                state.answers
              ).length,
              Math.max(
                0,
                state.questions.length -
                  1
              )
            )
          : 0;

      state.startedAt =
        data.resumed &&
        data.started_at
          ? Date.parse(
              data.started_at
            )
          : Date.now();

      saveProgress();

      show("testScreen");

      renderQuestion();

      startTimer();
    } catch (error) {
      toast(
        error.message ||
        "Testni boshlashda xato."
      );
    } finally {
      state.busy = false;
    }
  }

  async function finishTest() {
    if (
      state.busy ||
      !state.questions.length
    ) {
      return;
    }

    clearInterval(
      window.__testTimer
    );

    if (
      state.selected !== null
    ) {
      state.answers[
        String(
          state.index + 1
        )
      ] = state.selected;
    }

    saveProgress();

    show("loadingResult");

    try {
      state.busy = true;

      if (
        state.mode === "BATTLE"
      ) {
        const data =
          await api(
            `/api/battle/${encodeURIComponent(
              state.battleId
            )}/submit`,
            {
              method: "POST",
              body: JSON.stringify({
                answers:
                  state.answers
              })
            }
          );

        if (
          data.already_finished ||
          data.status === "finished" ||
          data.status ===
            "waiting_opponent"
        ) {
          await waitBattleResult();
        }

        return;
      }

      const data =
        await api(
          `/api/test/${encodeURIComponent(
            state.sessionId
          )}/submit`,
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

      clearProgress();

      state.attemptId =
        data.attempt_id;

      state.paymentAttemptId =
        data.attempt_id;

      if (
        data.payment_required
      ) {
        await renderPayment({
          ...data,
          payment_id:
            data.payment_id
        });

        show("paymentScreen");
      } else {
        await showResult(
          data.attempt_id
        );
      }
    } catch (error) {
      show("testScreen");

      toast(
        error.message ||
        "Natijani yuborishda xato."
      );
    } finally {
      state.busy = false;
    }
  }

  async function showResult(
    attemptId
  ) {
    const data =
      await api(
        `/api/result/${encodeURIComponent(
          attemptId
        )}`
      );

    if (!data.visible) {
      state.attemptId =
        attemptId;

      const payments =
        await api(
          "/api/payment/mine"
        );

      const mine =
        (payments.payments || [])
          .find(
            (payment) =>
              Number(
                payment.attempt_id
              ) ===
              Number(attemptId)
          );

      if (mine) {
        state.paymentId =
          mine.id;

        state.paymentAttemptId =
          attemptId;

        const card =
          await getPaymentCard(
            mine.id
          );

        await renderPayment({
          amount: mine.amount,
          payment_id: mine.id,
          card,
          status: mine.status
        });

        show("paymentScreen");
      } else {
        toast(
          "Natija hali yopiq."
        );
      }

      return;
    }

    state.testType =
      data.test_type ||
      state.testType ||
      "IQ";

    $("#resultBadge").textContent =
      `${state.testType} RESULT`;

    $("#resultUnit").textContent =
      state.testType === "IQ"
        ? "IQ"
        : "%";

    $("#resultScore").textContent =
      data.score ?? "—";

    $("#resultLevel").textContent =
      data.level ||
      (
        state.testType === "IQ"
          ? "—"
          : "Natija"
      );

    $("#resultCorrect").textContent =
      `${data.correct_count ?? 0}/${state.questions.length} to‘g‘ri`;

    show("resultScreen");
  }

  async function getPaymentCard(
    paymentId
  ) {
    try {
      const data =
        await api(
          `/api/payment/${encodeURIComponent(
            paymentId
          )}/card`
        );

      return data.card || null;
    } catch (_) {
      return null;
    }
  }

  async function renderPayment(
    data
  ) {
    state.paymentId =
      data.payment_id ||
      state.paymentId;

    state.paymentAttemptId =
      data.attempt_id ||
      state.paymentAttemptId;

    $("#paymentAmount").textContent =
      `${Number(
        data.amount || 0
      ).toLocaleString(
        "uz-UZ"
      )} so‘m`;

    const card =
      data.card ||
      (
        state.paymentId
          ? await getPaymentCard(
              state.paymentId
            )
          : null
      );

    $("#cardNumber").textContent =
      card?.card_number ||
      "Faol karta topilmadi";

    $("#cardHolder").textContent =
      card?.holder || "";

    $("#cardBank").textContent =
      card?.bank || "";

    $("#paymentStatus").textContent =
      data.status === "approved"
        ? "To‘lov tasdiqlangan."
        : card
          ? "Kartaga to‘lov qiling va receipt yuklang."
          : "Admin karta qo‘shishini kuting.";

    if ($("#receiptInput")) {
      $("#receiptInput").value = "";
    }

    if ($("#receiptFile")) {
      $("#receiptFile").value = "";
    }
  }

  async function refreshPayment() {
    if (!state.paymentId) {
      return;
    }

    try {
      const data =
        await api(
          "/api/payment/mine"
        );

      const mine =
        (data.payments || [])
          .find(
            (payment) =>
              Number(payment.id) ===
              Number(state.paymentId)
          );

      if (!mine) {
        return;
      }

      $("#paymentStatus").textContent =
        `Status: ${mine.status}`;

      if (
        mine.status === "approved"
      ) {
        if (state.battleId) {
          await checkBattleReady(
            true
          );
        } else if (
          state.paymentAttemptId
        ) {
          await showResult(
            state.paymentAttemptId
          );
        }
      }
    } catch (_) {}
  }

  async function sendReceipt() {
    if (!state.paymentId) {
      toast("Payment topilmadi.");
      return;
    }

    const file =
      $("#receiptFile")
        ?.files?.[0];

    const legacy =
      $("#receiptInput")
        ?.value
        .trim();

    if (!file && !legacy) {
      toast(
        "Receipt rasmini tanlang."
      );

      return;
    }

    try {
      state.busy = true;

      const formData =
        new FormData();

      if (file) {
        formData.append(
          "receipt",
          file,
          file.name
        );
      } else {
        formData.append(
          "receipt_file_id",
          legacy
        );
      }

      const data =
        await api(
          `/api/payment/${encodeURIComponent(
            state.paymentId
          )}/receipt`,
          {
            method: "POST",
            body: formData
          }
        );

      $("#paymentStatus").textContent =
        "Receipt yuborildi. Admin tasdig‘i kutilmoqda.";

      toast(
        "Receipt yuborildi."
      );

      if (state.battleId) {
        startBattlePolling();
      } else if (
        data.status === "approved" &&
        state.paymentAttemptId
      ) {
        await showResult(
          state.paymentAttemptId
        );
      }
    } catch (error) {
      toast(
        error.message ||
        "Receipt yuborilmadi."
      );
    } finally {
      state.busy = false;
    }
  }

  async function loadHome() {
    const data =
      await api(
        "/api/bootstrap"
      );

    state.user =
      data.user || {};

    state.prices =
      data.prices || {};

    state.questions =
      data.questions || [];

    $("#userName").textContent =
      data.user?.first_name ||
      "Do‘st";

    $("#fullName").value =
      data.user?.full_name ||
      "";

    $("#gender").value =
      data.user?.gender ||
      "";

    $("#age").value =
      data.user?.age ||
      "";

    $("#country").value =
      data.user?.country ||
      "";

    updateHomeLocks();

    renderPersonalProfile();

    show("homeScreen");

    updateLive();

    clearInterval(
      window.__liveTimer
    );

    window.__liveTimer =
      setInterval(
        updateLive,
        5000
      );

    await restoreProgress();
  }

  function updateHomeLocks() {
    const hasIQ =
      Boolean(state.user?.hasIQ);

    const hasEQ =
      Boolean(state.user?.hasEQ);

    $("#eqState").textContent =
      hasIQ
        ? "Ochilgan"
        : "IQdan keyin ochiladi";

    $("#pqState").textContent =
      hasEQ
        ? "Ochilgan"
        : "EQdan keyin ochiladi";

    $(
      ".test-card[data-test='EQ']"
    )?.classList.toggle(
      "locked",
      !hasIQ
    );

    $(
      ".test-card[data-test='PQ']"
    )?.classList.toggle(
      "locked",
      !hasEQ
    );

    $("#profileCard")
      ?.classList.toggle(
        "locked",
        !(
          hasIQ &&
          hasEQ &&
          Boolean(state.user?.hasPQ)
        )
      );
  }

  async function restoreProgress() {
    let saved = null;

    try {
      saved =
        JSON.parse(
          localStorage.getItem(
            "iq_test_progress"
          ) || "null"
        );
    } catch (_) {
      saved = null;
    }

    if (!saved?.sessionId) {
      return;
    }

    try {
      const data =
        await api(
          `/api/test/${encodeURIComponent(
            saved.sessionId
          )}/resume`
        );

      if (
        data.status === "completed" ||
        data.status === "expired"
      ) {
        clearProgress();
        return;
      }

      state.mode = "NORMAL";

      state.sessionId =
        saved.sessionId;

      state.testType =
        data.test_type;

      state.questions =
        data.questions || [];

      state.answers =
        saved.answers ||
        data.answers ||
        {};

      state.index =
        Math.max(
          0,
          Math.min(
            Number(saved.index) || 0,
            Math.max(
              0,
              state.questions.length - 1
            )
          )
        );

      state.startedAt =
        Number(saved.startedAt) ||
        Date.now();

      show("testScreen");

      renderQuestion();

      startTimer();

      toast(
        "Testingiz saqlangan joyidan davom etdi."
      );
    } catch (_) {
      clearProgress();
    }
  }

  async function updateLive() {
    try {
      const data =
        await api(
          "/api/stats/live"
        );

      animateNumber(
        $("#liveTotal"),
        data.total
      );

      animateNumber(
        $("#liveOnline"),
        data.online
      );
    } catch (_) {}
  }

  function animateNumber(
    element,
    number
  ) {
    if (!element) return;

    element.textContent =
      Number(number || 0)
        .toLocaleString(
          "uz-UZ"
        );
  }

  async function saveProfile() {
    const age =
      Number(
        $("#age").value
      );

    const body = {
      full_name:
        $("#fullName")
          .value
          .trim(),

      gender:
        $("#gender").value,

      age,

      country:
        $("#country").value
    };

    if (
      !body.full_name ||
      !body.gender ||
      !body.country ||
      !Number.isInteger(age) ||
      age < 10 ||
      age > 120
    ) {
      toast(
        "Profil ma’lumotlarini to‘liq kiriting."
      );

      return;
    }

    try {
      state.busy = true;

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

      $("#userName").textContent =
        state.user.first_name ||
        "Do‘st";

      renderPersonalProfile();

      updateHomeLocks();

      toast(
        "Profil saqlandi."
      );

      const pending =
        state.pendingType;

      delete state.pendingType;

      if (pending) {
        setTimeout(
          () => startTest(pending),
          250
        );
      } else {
        show("homeScreen");
      }
    } catch (error) {
      toast(
        error.message ||
        "Profilni saqlab bo‘lmadi."
      );
    } finally {
      state.busy = false;
    }
  }

  function renderPersonalProfile() {
    const box =
      $("#personalSummary");

    if (
      !box ||
      !state.user
    ) {
      return;
    }

    const ready =
      Boolean(state.user.hasIQ) &&
      Boolean(state.user.hasEQ) &&
      Boolean(state.user.hasPQ);

    if (!ready) {
      box.innerHTML = `
        <div class="empty-state">
          <b>Shaxsiy profil</b>
          <span>
            IQ + EQ + PQ testlarini
            yakunlaganingizdan keyin
            tahlil shu yerda ochiladi.
          </span>
        </div>
      `;

      return;
    }

    box.innerHTML = `
      <div class="summary-grid">
        <div>
          <small>IQ</small>
          <b>Yakunlangan</b>
        </div>

        <div>
          <small>EQ</small>
          <b>Yakunlangan</b>
        </div>

        <div>
          <small>PQ</small>
          <b>Yakunlangan</b>
        </div>
      </div>

      <div class="insight">
        <b>Kuchli tomonlar</b>
        <p>
          Muammolarni tahlil qilish,
          hissiy vaziyatni anglash va
          vazifalarni rejalashtirish
          bo‘yicha test javoblaringiz
          mavjud.
        </p>
      </div>

      <div class="insight">
        <b>Rivojlanish nuqtalari</b>
        <p>
          Natijalarni muntazam qayta
          ko‘rib chiqish va real
          hayotdagi qarorlar bilan
          solishtirish foydali.
        </p>
      </div>
    `;
  }

  async function loadRanking() {
    try {
      const data =
        await api(
          "/api/ranking"
        );

      const box =
        $("#rankingList");

      const ranking =
        Array.isArray(
          data.ranking
        )
          ? data.ranking
          : [];

      if (!ranking.length) {
        box.innerHTML = `
          <div class="form-card glass empty-state">
            <b>Hali natijalar yo‘q.</b>
          </div>
        `;
      } else {
        box.innerHTML =
          ranking
            .map(
              (item) => `
                <div class="rank-row">
                  <span class="rank-pos">
                    #${escapeHtml(
                      item.position
                    )}
                  </span>

                  <span>
                    <b>
                      ${escapeHtml(
                        item.name
                      )}
                    </b>

                    <small>
                      ${escapeHtml(
                        item.level || ""
                      )}
                    </small>
                  </span>

                  <strong>
                    ${escapeHtml(
                      item.score
                    )}
                  </strong>
                </div>
              `
            )
            .join("");
      }

      show("rankingScreen");
    } catch (error) {
      toast(
        error.message ||
        "Reytingni yuklab bo‘lmadi."
      );
    }
  }

  async function loadCertificate() {
    try {
      const data =
        await api(
          "/api/certificate/mine"
        );

      const certificate =
        data.certificate;

      const box =
        $("#certificateBox");

      if (!certificate) {
        box.innerHTML = `
          <div class="empty-state">
            <b>Sertifikat yo‘q</b>

            <span>
              IQ testini yakunlang va
              natija ochilgach sertifikat
              yaratiladi.
            </span>
          </div>
        `;

        show(
          "certificateScreen"
        );

        return;
      }

      box.innerHTML = `
        <span class="pill">
          VERIFIED
        </span>

        <h2>
          ${escapeHtml(
            certificate.full_name
          )}
        </h2>

        <div class="score-ring">
          <strong>
            ${escapeHtml(
              certificate.score
            )}
          </strong>

          <small>IQ</small>
        </div>

        <p>
          ${escapeHtml(
            certificate.level || ""
          )}
        </p>

        <div class="cert-code">
          ${escapeHtml(
            certificate.verification_code
          )}
        </div>

        <p>IQ TEST BOT</p>

        <button
          id="certDownload"
          class="primary"
          type="button"
        >
          PNG ochish
        </button>
      `;

      $("#certDownload")
        ?.addEventListener(
          "click",
          async () => {
            try {
              const blob =
                await apiBlob(
                  `/api/certificate/${encodeURIComponent(
                    certificate.certificate_id
                  )}/png`
                );

              const url =
                URL.createObjectURL(
                  blob
                );

              if (
                tg?.openLink
              ) {
                tg.openLink(url);
              } else {
                window.open(
                  url,
                  "_blank"
                );
              }

              setTimeout(
                () =>
                  URL.revokeObjectURL(
                    url
                  ),
                30000
              );
            } catch (error) {
              toast(
                error.message ||
                "Sertifikatni ochib bo‘lmadi."
              );
            }
          }
        );

      show(
        "certificateScreen"
      );
    } catch (error) {
      toast(
        error.message ||
        "Sertifikatni yuklab bo‘lmadi."
      );
    }
  }

  function setBattleInfo(html) {
    const element =
      $("#battleInfo");

    if (element) {
      element.innerHTML =
        html;
    }
  }

  async function createBattle() {
    if (state.busy) return;

    try {
      state.busy = true;

      const data =
        await api(
          "/api/battle/create",
          {
            method: "POST",
            body: "{}"
          }
        );

      state.battleId =
        data.battle_id;

      state.paymentAttemptId =
        null;

      setBattleInfo(`
        <div class="cert-code battle-code">
          ${escapeHtml(
            data.code
          )}
        </div>

        <p>
          Do‘stingizga 4 belgili
          kodni yuboring.
          Ikkalangiz ham to‘lovni
          tasdiqlatgach battle ochiladi.
        </p>

        <button
          id="battlePay"
          class="primary"
          type="button"
        >
          To‘lovni boshlash ·
          ${Number(
            data.price || 0
          ).toLocaleString(
            "uz-UZ"
          )}
          so‘m
        </button>

        <div
          id="battleStatus"
          class="inline-status"
        >
          Opponent kutilmoqda…
        </div>
      `);

      $("#battlePay").onclick =
        () => startBattlePayment();

      startBattlePolling();
    } catch (error) {
      toast(
        error.message ||
        "Battle yaratilmadi."
      );
    } finally {
      state.busy = false;
    }
  }

  async function joinBattle() {
    if (state.busy) return;

    const code =
      $("#battleCode")
        .value
        .trim()
        .toUpperCase();

    if (code.length !== 4) {
      toast(
        "4 belgili kod kiriting."
      );

      return;
    }

    try {
      state.busy = true;

      const data =
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
        data.battle_id;

      state.paymentAttemptId =
        null;

      setBattleInfo(`
        <div class="cert-code battle-code">
          ${escapeHtml(code)}
        </div>

        <p>
          Battle topildi.
          Endi o‘z to‘lovingizni yuboring.
        </p>

        <button
          id="battlePay"
          class="primary"
          type="button"
        >
          To‘lovni boshlash ·
          ${Number(
            data.price || 0
          ).toLocaleString(
            "uz-UZ"
          )}
          so‘m
        </button>

        <div
          id="battleStatus"
          class="inline-status"
        >
          To‘lov kutilmoqda…
        </div>
      `);

      $("#battlePay").onclick =
        () => startBattlePayment();

      startBattlePolling();
    } catch (error) {
      toast(
        error.message ||
        "Battle'ga kirib bo‘lmadi."
      );
    } finally {
      state.busy = false;
    }
  }

  async function startBattlePayment() {
    if (!state.battleId) {
      return;
    }

    state.paymentAttemptId =
      null;

    try {
      state.busy = true;

      const data =
        await api(
          `/api/battle/${encodeURIComponent(
            state.battleId
          )}/payment`,
          {
            method: "POST",
            body: "{}"
          }
        );

      await renderPayment({
        ...data,
        payment_id:
          data.payment_id
      });

      state.paymentId =
        data.payment_id;

      show("paymentScreen");

      startBattlePolling();
    } catch (error) {
      toast(
        error.message ||
        "Battle to‘lovi yaratilmadi."
      );
    } finally {
      state.busy = false;
    }
  }

  function startBattlePolling() {
    clearInterval(
      state.battlePolling
    );

    state.battlePolling =
      setInterval(
        () => {
          checkBattleReady(false);
        },
        3000
      );

    checkBattleReady(false);
  }

  async function checkBattleReady(
    showToastOnReady
  ) {
    if (!state.battleId) {
      return false;
    }

    try {
      const data =
        await api(
          `/api/battle/${encodeURIComponent(
            state.battleId
          )}/start`
        );

      const status =
        $("#battleStatus");

      if (status) {
        status.textContent =
          data.ready
            ? "Battle tayyor. Test boshlanmoqda…"
            : `Holat: ${
                data.status ||
                "kutilmoqda"
              }`;
      }

      if (data.ready) {
        clearInterval(
          state.battlePolling
        );

        state.questions =
          data.questions || [];

        state.mode =
          "BATTLE";

        state.testType =
          "IQ";

        state.index = 0;
        state.answers = {};
        state.selected = null;
        state.startedAt =
          Date.now();

        show("testScreen");

        renderQuestion();

        startTimer();

        if (showToastOnReady) {
          toast(
            "Battle to‘lovi tasdiqlandi."
          );
        }

        return true;
      }
    } catch (_) {}

    return false;
  }

  async function waitBattleResult() {
    show("loadingResult");

    clearInterval(
      window.__testTimer
    );

    for (
      let attempt = 0;
      attempt < 40;
      attempt += 1
    ) {
      try {
        const data =
          await api(
            `/api/battle/${encodeURIComponent(
              state.battleId
            )}/result`
          );

        if (data.ready) {
          $("#resultBadge").textContent =
            "BATTLE RESULT";

          $("#resultUnit").textContent =
            "IQ";

          $("#resultScore").textContent =
            data.my_score ?? "—";

          $("#resultLevel").textContent =
            data.outcome === "win"
              ? "G‘ALABA"
              : data.outcome === "loss"
                ? "MAG‘LUBIYAT"
                : "DURANG";

          $("#resultCorrect").textContent =
            `Opponent: ${
              data.opponent_score ?? "—"
            }`;

          show("resultScreen");

          return;
        }
      } catch (_) {}

      await new Promise(
        (resolve) =>
          setTimeout(
            resolve,
            2500
          )
      );
    }

    show("battleScreen");

    toast(
      "Opponent natijasini kutish davom etmoqda."
    );
  }

  $("#nextQuestion")
    ?.addEventListener(
      "click",
      () => {
        if (
          state.selected === null ||
          state.busy
        ) {
          return;
        }

        state.answers[
          String(
            state.index + 1
          )
        ] = state.selected;

        saveProgress();

        if (
          state.index <
          state.questions.length - 1
        ) {
          state.index += 1;

          renderQuestion();
        } else {
          finishTest();
        }
      }
    );

  $("#saveProfile")
    ?.addEventListener(
      "click",
      saveProfile
    );

  $("#copyCard")
    ?.addEventListener(
      "click",
      async () => {
        try {
          const number =
            $("#cardNumber")
              ?.textContent
              ?.trim();

          if (!number) {
            throw new Error();
          }

          await navigator.clipboard.writeText(
            number
          );

          toast(
            "Karta nusxalandi."
          );
        } catch (_) {
          toast(
            "Nusxalash imkoni bo‘lmadi."
          );
        }
      }
    );

  $("#sendReceipt")
    ?.addEventListener(
      "click",
      sendReceipt
    );

  $("#sharePayment")
    ?.addEventListener(
      "click",
      () => {
        const username =
          "iqtest_ubot";

        const url =
          `https://t.me/${username}`;

        if (
          tg?.openTelegramLink
        ) {
          tg.openTelegramLink(
            url
          );
        } else {
          window.open(
            url,
            "_blank",
            "noopener,noreferrer"
          );
        }
      }
    );

  $("#certificateBtn")
    ?.addEventListener(
      "click",
      loadCertificate
    );

  $("#createBattle")
    ?.addEventListener(
      "click",
      createBattle
    );

  $("#joinBattle")
    ?.addEventListener(
      "click",
      joinBattle
    );

  $("#profileTopBtn")
    ?.addEventListener(
      "click",
      () => {
        show("profileScreen");
      }
    );

  $("#battleCard")
    ?.addEventListener(
      "click",
      () => {
        show("battleScreen");
      }
    );

  $("#profileCard")
    ?.addEventListener(
      "click",
      () => {
        renderPersonalProfile();

        show("profileScreen");

        $("#personalSummary")
          ?.scrollIntoView({
            behavior: "smooth",
            block: "center"
          });
      }
    );

  $("#testBack")
    ?.addEventListener(
      "click",
      () => {
        clearInterval(
          window.__testTimer
        );

        if (
          state.mode === "NORMAL"
        ) {
          saveProgress();
        }

        show("homeScreen");
      }
    );

  $$("[data-back]")
    .forEach(
      (button) => {
        button.addEventListener(
          "click",
          () => {
            show("homeScreen");
          }
        );
      }
    );

  $$(".test-card[data-test]")
    .forEach(
      (button) => {
        button.addEventListener(
          "click",
          () => {
            startTest(
              button.dataset.test
            );
          }
        );
      }
    );

  $$("[data-nav]")
    .forEach(
      (button) => {
        button.addEventListener(
          "click",
          () => {
            const navigation =
              button.dataset.nav;

            if (
              navigation === "home"
            ) {
              show("homeScreen");
            }

            if (
              navigation === "ranking"
            ) {
              loadRanking();
            }

            if (
              navigation === "certificate"
            ) {
              loadCertificate();
            }

            if (
              navigation === "profile"
            ) {
              renderPersonalProfile();
              show("profileScreen");
            }

            $$(".bottom-nav button")
              .forEach(
                (item) => {
                  item.classList.toggle(
                    "active",
                    item === button
                  );
                }
              );
          }
        );
      }
    );

  if ($("#battleCode")) {
    $("#battleCode")
      .addEventListener(
        "input",
        (event) => {
          event.target.value =
            event.target.value
              .replace(
                /[^A-Z0-9]/gi,
                ""
              )
              .toUpperCase()
              .slice(0, 4);
        }
      );
  }

  const paymentRefreshTimer =
    setInterval(
      () => {
        if (
          state.paymentId &&
          !$("#paymentScreen")
            ?.classList.contains(
              "hidden"
            )
        ) {
          refreshPayment();
        }
      },
      5000
    );

  window.addEventListener(
    "beforeunload",
    () => {
      clearInterval(
        paymentRefreshTimer
      );

      clearInterval(
        window.__liveTimer
      );

      clearInterval(
        window.__testTimer
      );

      clearInterval(
        state.battlePolling
      );

      if (
        state.mode === "NORMAL" &&
        state.sessionId
      ) {
        saveProgress();
      }
    }
  );

  (async () => {
    show("loadingScreen");

    try {
      await loadHome();
    } catch (error) {
      show("homeScreen");

      toast(
        error.message ||
        "Mini App yuklanmadi."
      );
    }
  })();
})();