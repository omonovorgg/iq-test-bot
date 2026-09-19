/* ============================================================
   IQ TEST — webapp/app.js
   Local-first test engine
   - No request per answer
   - Local autosave
   - Offline-safe
   - One final sync
   - Idempotent attempt_id
   - Compatible with the current index.html
   ============================================================ */

(() => {
  "use strict";

  const tg = window.Telegram?.WebApp || null;
  const API = "";

  const STORAGE_KEY = "iq_test_active_v3";
  const QUEUE_KEY = "iq_test_sync_queue_v3";
  const LANG_KEY = "iq_test_lang_v3";

  const QUESTION_COUNT = 16;
  const TOTAL_SECONDS = 8 * 60;

  const state = {
    lang: localStorage.getItem(LANG_KEY) || "uz",
    package: null,
    session: null,
    result: null,
    ranking: null,
    busy: false,
    finishing: false,
    clockTimer: null,
    saveTimer: null
  };

  const LETTERS = ["A", "B", "C", "D"];

  const T = {
    uz: {
      title: "IQ TEST",
      desc: "16 ta original mantiqiy puzzle orqali fikrlash qobiliyatingizni sinab ko‘ring.",
      start: "TESTNI BOSHLASH",
      ranking: "Reyting",
      profile: "Profil",
      free: "Birinchi test — bepul",
      why: "Natija va reytingingiz avtomatik saqlanadi.",
      question: "MANTIQIY PUZZLE",
      time: "Vaqt",
      correct: "To‘g‘ri",
      score: "IQ",
      rank: "Reyting",
      done: "TEST YAKUNLANDI",
      next: "DAVOM ETISH",
      finish: "NATIJANI KO‘RISH",
      loading: "Yuklanmoqda…",
      sending: "Natija tekshirilmoqda…",
      offline: "Internet yo‘q. Test baribir davom etadi.",
      synced: "Natija serverga saqlandi.",
      pending: "Natija internet tiklanganda yuboriladi.",
      error: "Xatolik yuz berdi.",
      retry: "QAYTA URINISH",
      back: "Orqaga",
      tests: "Testlar",
      best: "Eng yaxshi IQ",
      referrals: "Takliflar",
      retest: "QAYTA TEST",
      paid: "Keyingi test pullik.",
      quit: "Testdan chiqasizmi?",
      quitText: "Joriy natija saqlanadi va keyin davom ettirishingiz mumkin.",
      stay: "TESTDA QOLISH",
      leave: "CHIQISH",
      noData: "Ma’lumot topilmadi.",
      telegramOnly: "Bu ilovani Telegram ichidan oching.",
      share: "NATIJANI ULASHISH",
      certificate: "SERTIFIKAT",
      develop: "IQ’IMNI RIVOJLANTIRISH",
      cannotStart: "Testni boshlab bo‘lmadi.",
      cannotFinish: "Natijani yuborib bo‘lmadi.",
      sync: "Sinxronlashtirilmoqda…"
    },

    ru: {
      title: "IQ TEST",
      desc: "Проверьте логическое мышление с помощью 16 оригинальных задач.",
      start: "НАЧАТЬ ТЕСТ",
      ranking: "Рейтинг",
      profile: "Профиль",
      free: "Первая попытка — бесплатно",
      why: "Результат и рейтинг сохраняются автоматически.",
      question: "ЛОГИЧЕСКАЯ ЗАДАЧА",
      time: "Время",
      correct: "Верно",
      score: "IQ",
      rank: "Рейтинг",
      done: "ТЕСТ ЗАВЕРШЁН",
      next: "ПРОДОЛЖИТЬ",
      finish: "ПОКАЗАТЬ РЕЗУЛЬТАТ",
      loading: "Загрузка…",
      sending: "Результат проверяется…",
      offline: "Нет интернета. Тест продолжится.",
      synced: "Результат сохранён.",
      pending: "Результат будет отправлен после восстановления интернета.",
      error: "Произошла ошибка.",
      retry: "ПОВТОРИТЬ",
      back: "Назад",
      tests: "Тесты",
      best: "Лучший IQ",
      referrals: "Приглашения",
      retest: "ПОВТОРНЫЙ ТЕСТ",
      paid: "Следующая попытка платная.",
      quit: "Выйти из теста?",
      quitText: "Текущий прогресс будет сохранён.",
      stay: "ОСТАТЬСЯ",
      leave: "ВЫЙТИ",
      noData: "Данные не найдены.",
      telegramOnly: "Откройте приложение внутри Telegram.",
      share: "ПОДЕЛИТЬСЯ",
      certificate: "СЕРТИФИКАТ",
      develop: "РАЗВИВАТЬ IQ",
      cannotStart: "Не удалось начать тест.",
      cannotFinish: "Не удалось отправить результат.",
      sync: "Синхронизация…"
    },

    en: {
      title: "IQ TEST",
      desc: "Test your reasoning with 16 original logic puzzles.",
      start: "START TEST",
      ranking: "Ranking",
      profile: "Profile",
      free: "First attempt — free",
      why: "Your result and ranking are saved automatically.",
      question: "LOGIC PUZZLE",
      time: "Time",
      correct: "Correct",
      score: "IQ",
      rank: "Ranking",
      done: "TEST COMPLETE",
      next: "CONTINUE",
      finish: "VIEW RESULT",
      loading: "Loading…",
      sending: "Checking result…",
      offline: "No internet. The test will continue.",
      synced: "Result saved.",
      pending: "Result will be sent when internet returns.",
      error: "Something went wrong.",
      retry: "RETRY",
      back: "Back",
      tests: "Tests",
      best: "Best IQ",
      referrals: "Invites",
      retest: "RETAKE TEST",
      paid: "The next attempt is paid.",
      quit: "Leave the test?",
      quitText: "Your current progress will be saved.",
      stay: "STAY",
      leave: "LEAVE",
      noData: "No data found.",
      telegramOnly: "Open this app inside Telegram.",
      share: "SHARE RESULT",
      certificate: "CERTIFICATE",
      develop: "DEVELOP MY IQ",
      cannotStart: "Could not start the test.",
      cannotFinish: "Could not submit the result.",
      sync: "Synchronizing…"
    }
  };

  function t(key) {
    return T[state.lang]?.[key] || T.uz[key] || key;
  }

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function uuid() {
    if (crypto?.randomUUID) return crypto.randomUUID();

    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);

    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    const h = [...bytes].map(x => x.toString(16).padStart(2, "0"));

    return (
      h.slice(0, 4).join("") + "-" +
      h.slice(4, 6).join("") + "-" +
      h.slice(6, 8).join("") + "-" +
      h.slice(8, 10).join("") + "-" +
      h.slice(10, 16).join("")
    );
  }

  function initData() {
    return tg?.initData || "";
  }

  function telegramReady() {
    if (!tg) return;

    try {
      tg.ready();
      tg.expand();

      if (tg.setHeaderColor) {
        tg.setHeaderColor("#080b12");
      }

      if (tg.setBackgroundColor) {
        tg.setBackgroundColor("#080b12");
      }
    } catch (e) {
      console.warn("Telegram WebApp init:", e);
    }
  }

  function isOnline() {
    return navigator.onLine !== false;
  }

  function now() {
    return Date.now();
  }

  function safeJSONParse(value, fallback = null) {
    try {
      return JSON.parse(value);
    } catch {
      return fallback;
    }
  }

  function saveActiveSession() {
    if (!state.session) return;

    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          version: 3,
          savedAt: now(),
          ...state.session
        })
      );
    } catch (e) {
      console.warn("localStorage save failed:", e);
    }
  }

  function loadActiveSession() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;

      const data = safeJSONParse(raw);

      if (!data || data.version !== 3) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }

      if (
        !data.attemptId ||
        !Array.isArray(data.questions) ||
        !Array.isArray(data.answers)
      ) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }

      return data;
    } catch {
      return null;
    }
  }

  function clearActiveSession() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  }

  function queueResult(payload) {
    try {
      const queue = safeJSONParse(
        localStorage.getItem(QUEUE_KEY) || "[]",
        []
      );

      const exists = queue.some(
        x => x?.attempt_id === payload.attempt_id
      );

      if (!exists) {
        queue.push(payload);
      }

      localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
    } catch (e) {
      console.error("Queue error:", e);
    }
  }

  function getQueue() {
    return safeJSONParse(
      localStorage.getItem(QUEUE_KEY) || "[]",
      []
    );
  }

  function setQueue(queue) {
    try {
      localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
    } catch {}
  }

  async function syncQueue() {
    if (!isOnline()) return;

    const queue = getQueue();

    if (!queue.length) return;

    const remaining = [];

    for (const payload of queue) {
      try {
        await api("/api/session/finish", {
          method: "POST",
          body: JSON.stringify(payload)
        });
      } catch (e) {
        remaining.push(payload);
      }
    }

    setQueue(remaining);
  }

  async function api(path, options = {}) {
    const controller = new AbortController();

    const timeout = setTimeout(() => {
      controller.abort();
    }, 15000);

    const headers = {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData(),
      "Cache-Control": "no-cache",
      ...(options.headers || {})
    };

    try {
      const response = await fetch(API + path, {
        ...options,
        headers,
        cache: "no-store",
        signal: controller.signal
      });

      const text = await response.text();

      let data = {};

      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = { detail: text };
        }
      }

      if (!response.ok) {
        const error = new Error(
          data?.detail ||
          data?.error ||
          `HTTP_${response.status}`
        );

        error.status = response.status;
        error.code = data?.code || data?.error || data?.detail;

        throw error;
      }

      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  function showScreen(id) {
    document.querySelectorAll(".screen").forEach(screen => {
      screen.classList.remove("active");
    });

    const screen = document.getElementById(id);

    if (screen) {
      screen.classList.add("active");
    }

    window.scrollTo({
      top: 0,
      behavior: "instant"
    });
  }

  function setLoader(visible) {
    const loader = document.getElementById("globalLoader");

    if (!loader) return;

    loader.classList.toggle("hidden", !visible);
  }

  let toastTimer = null;

  function toast(message) {
    const el = document.getElementById("toast");
    const msg = document.getElementById("toastMessage");

    if (!el || !msg) return;

    msg.textContent = message;

    el.classList.add("visible");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
      el.classList.remove("visible");
    }, 2400);
  }

  function updateOfflineUI() {
    const banner = document.getElementById("offlineBanner");

    if (!banner) return;

    banner.classList.toggle("visible", !isOnline());
  }

  function formatTime(seconds) {
    seconds = Math.max(0, Math.floor(seconds));

    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;

    return (
      String(minutes).padStart(2, "0") +
      ":" +
      String(secs).padStart(2, "0")
    );
  }

  function elapsedSeconds() {
    if (!state.session) return 0;

    return Math.max(
      0,
      Math.floor(
        (now() - state.session.startedAt) / 1000
      )
    );
  }

  function remainingSeconds() {
    if (!state.session) return TOTAL_SECONDS;

    return Math.max(
      0,
      Math.ceil(
        (state.session.deadline - now()) / 1000
      )
    );
  }

  function updateTimer() {
    const timer = document.getElementById("timer");

    if (!timer || !state.session) return;

    const remaining = remainingSeconds();

    timer.textContent = formatTime(remaining);

    timer.classList.toggle(
      "warning",
      remaining <= 120 && remaining > 30
    );

    timer.classList.toggle(
      "danger",
      remaining <= 30
    );

    if (remaining <= 0 && !state.finishing) {
      finishTest("timeout");
    }
  }

  function startClock() {
    clearInterval(state.clockTimer);

    updateTimer();

    state.clockTimer = setInterval(() => {
      updateTimer();
    }, 500);
  }

  function stopClock() {
    clearInterval(state.clockTimer);
    state.clockTimer = null;
  }

  function getQuestionText(question) {
    if (!question) return "";

    if (typeof question.text === "string") {
      return question.text;
    }

    if (question.text) {
      return (
        question.text[state.lang] ||
        question.text.uz ||
        question.text.en ||
        Object.values(question.text)[0] ||
        ""
      );
    }

    return question.q || "";
  }

  function getQuestionOptions(question) {
    if (!question) return [];

    if (Array.isArray(question.options)) {
      return question.options;
    }

    if (Array.isArray(question.a)) {
      return question.a;
    }

    if (question.a && typeof question.a === "object") {
      return (
        question.a[state.lang] ||
        question.a.uz ||
        question.a.en ||
        Object.values(question.a)[0] ||
        []
      );
    }

    if (Array.isArray(question.opts)) {
      return question.opts;
    }

    if (question.opts && typeof question.opts === "object") {
      return (
        question.opts[state.lang] ||
        question.opts.uz ||
        question.opts.en ||
        Object.values(question.opts)[0] ||
        []
      );
    }

    return [];
  }

  function getVisual(question) {
    return (
      question?.visual ||
      question?.svg ||
      question?.image ||
      ""
    );
  }

  function renderHome() {
    stopClock();

    const startBtn = document.getElementById("startBtn");
    const rankingBtn = document.getElementById("rankingBtn");

    if (startBtn) {
      startBtn.textContent = t("start");
    }

    if (rankingBtn) {
      rankingBtn.textContent = t("ranking");
    }

    showScreen("homeScreen");

    const active = loadActiveSession();

    if (active) {
      toast(t("session"));
    }
  }

  async function startTest() {
    if (state.busy) return;

    const existing = loadActiveSession();

    if (existing) {
      state.session = existing;

      if (
        Array.isArray(existing.questions) &&
        existing.questions.length === QUESTION_COUNT &&
        existing.index < QUESTION_COUNT &&
        existing.deadline > now()
      ) {
        renderQuestion();
        return;
      }

      clearActiveSession();
    }

    state.busy = true;

    setLoader(true);

    try {
      /*
       * IMPORTANT:
       * Only one request is made to obtain the test package/start attempt.
       * Answers are NOT sent to the server individually.
       */
      const data = await api("/api/test/package", {
        method: "POST",
        body: JSON.stringify({
          language: state.lang
        })
      });

      const questions =
        data.questions ||
        data.items ||
        data.package?.questions;

      if (!Array.isArray(questions) || questions.length !== QUESTION_COUNT) {
        throw new Error("INVALID_QUESTION_PACKAGE");
      }

      const attemptId =
        data.attempt_id ||
        data.attemptId ||
        uuid();

      const serverSeconds = Number(
        data.time_limit ||
        data.timeLimit ||
        TOTAL_SECONDS
      );

      const duration =
        Number.isFinite(serverSeconds) &&
        serverSeconds > 0
          ? serverSeconds
          : TOTAL_SECONDS;

      state.package = data;

      state.session = {
        version: 3,
        attemptId,
        questions,
        index: 0,
        answers: Array(QUESTION_COUNT).fill(null),
        startedAt: now(),
        deadline: now() + duration * 1000,
        duration,
        language: state.lang,
        completed: false
      };

      saveActiveSession();

      renderQuestion();
    } catch (error) {
      /*
       * Compatibility fallback:
       * Some backend versions use /api/session/start instead of
       * /api/test/package.
       */
      if (
        error.status === 404 ||
        error.code === "NOT_FOUND"
      ) {
        try {
          const data = await api("/api/session/start", {
            method: "POST",
            body: JSON.stringify({
              language: state.lang
            })
          });

          const questions =
            data.questions ||
            data.items ||
            data.package?.questions;

          if (
            !Array.isArray(questions) ||
            questions.length !== QUESTION_COUNT
          ) {
            throw new Error("INVALID_QUESTION_PACKAGE");
          }

          const attemptId =
            data.attempt_id ||
            data.attemptId ||
            uuid();

          const duration =
            Number(
              data.time_limit ||
              data.timeLimit ||
              TOTAL_SECONDS
            ) || TOTAL_SECONDS;

          state.package = data;

          state.session = {
            version: 3,
            attemptId,
            questions,
            index: Number(data.index || 0),
            answers: Array.isArray(data.answers)
              ? data.answers.slice(0, QUESTION_COUNT)
              : Array(QUESTION_COUNT).fill(null),
            startedAt: now(),
            deadline: now() + duration * 1000,
            duration,
            language: state.lang,
            completed: false
          };

          while (
            state.session.answers.length <
            QUESTION_COUNT
          ) {
            state.session.answers.push(null);
          }

          saveActiveSession();
          renderQuestion();

          return;
        } catch (fallbackError) {
          handleStartError(fallbackError);
          return;
        }
      }

      handleStartError(error);
    } finally {
      state.busy = false;
      setLoader(false);
    }
  }

  function handleStartError(error) {
    console.error("START TEST:", error);

    if (
      error.status === 402 ||
      error.code === "PAID_RETEST"
    ) {
      openPaymentModal();
      return;
    }

    toast(t("cannotStart"));
  }

  function renderQuestion() {
    if (!state.session) {
      renderHome();
      return;
    }

    const s = state.session;

    if (s.index >= QUESTION_COUNT) {
      finishTest("completed");
      return;
    }

    const q = s.questions[s.index];

    if (!q) {
      toast(t("error"));
      return;
    }

    const number = s.index + 1;
    const text = getQuestionText(q);
    const options = getQuestionOptions(q);
    const visual = getVisual(q);

    const questionNumber =
      document.getElementById("questionNumber");

    const progressFill =
      document.getElementById("progressFill");

    const category =
      document.getElementById("questionCategory");

    const questionText =
      document.getElementById("questionText");

    const puzzle =
      document.getElementById("puzzle");

    const answers =
      document.getElementById("answers");

    const nextBtn =
      document.getElementById("nextBtn");

    if (questionNumber) {
      questionNumber.textContent =
        `${number} / ${QUESTION_COUNT}`;
    }

    if (progressFill) {
      progressFill.style.width =
        `${((number - 1) / QUESTION_COUNT) * 100}%`;
    }

    if (category) {
      category.textContent = t("question");
    }

    if (questionText) {
      questionText.innerHTML = esc(text).replace(
        /\n/g,
        "<br>"
      );
    }

    if (puzzle) {
      if (visual) {
        puzzle.innerHTML = visual;
        puzzle.classList.remove("hidden");
      } else {
        puzzle.innerHTML = "";
        puzzle.classList.add("hidden");
      }
    }

    if (answers) {
      answers.innerHTML = options
        .map((option, index) => {
          const selected =
            Number(s.answers[s.index]) === index;

          let content = option;

          if (
            typeof option === "object" &&
            option !== null
          ) {
            content =
              option.html ||
              option.svg ||
              option.text ||
              option.label ||
              "";
          }

          const safeContent =
            typeof content === "string" &&
            /<svg|<div|<span|<img|<path|<circle|<rect/i.test(
              content
            )
              ? content
              : esc(content);

          return `
            <button
              type="button"
              class="answer${selected ? " selected" : ""}"
              data-answer="${index}"
              aria-label="${esc(
                `${LETTERS[index]} ${String(
                  typeof content === "string"
                    ? content.replace(/<[^>]*>/g, "")
                    : ""
                )}`
              )}"
            >
              <span class="answer-visual">
                ${safeContent}
              </span>
            </button>
          `;
        })
        .join("");

      answers
        .querySelectorAll("[data-answer]")
        .forEach(button => {
          button.addEventListener(
            "click",
            () => chooseAnswer(
              Number(button.dataset.answer)
            ),
            { passive: true }
          );
        });
    }

    if (nextBtn) {
      nextBtn.textContent =
        number === QUESTION_COUNT
          ? t("finish")
          : t("next");

      nextBtn.disabled =
        !Number.isInteger(s.answers[s.index]);

      nextBtn.onclick = () => {
        if (!Number.isInteger(s.answers[s.index])) {
          return;
        }

        goNext();
      };
    }

    showScreen("testScreen");
    startClock();
    updateTimer();
  }

  function chooseAnswer(answerIndex) {
    if (
      state.busy ||
      !state.session ||
      state.finishing
    ) {
      return;
    }

    const index = state.session.index;

    if (
      index < 0 ||
      index >= QUESTION_COUNT
    ) {
      return;
    }

    if (
      !Number.isInteger(answerIndex) ||
      answerIndex < 0 ||
      answerIndex > 3
    ) {
      return;
    }

    state.session.answers[index] = answerIndex;

    saveActiveSession();

    const answers =
      document.querySelectorAll("[data-answer]");

    answers.forEach(button => {
      button.classList.toggle(
        "selected",
        Number(button.dataset.answer) === answerIndex
      );
    });

    const nextBtn =
      document.getElementById("nextBtn");

    if (nextBtn) {
      nextBtn.disabled = false;
    }
  }

  function goNext() {
    if (
      !state.session ||
      state.finishing
    ) {
      return;
    }

    const index = state.session.index;

    if (
      !Number.isInteger(state.session.answers[index])
    ) {
      return;
    }

    if (index >= QUESTION_COUNT - 1) {
      finishTest("completed");
      return;
    }

    state.session.index += 1;

    saveActiveSession();

    renderQuestion();
  }

  function buildFinishPayload() {
    if (!state.session) {
      throw new Error("NO_SESSION");
    }

    const answers = state.session.answers.map(
      (answer, index) => ({
        questionId:
          state.session.questions[index]?.id ??
          String(index + 1),

        answerIndex:
          Number.isInteger(answer)
            ? answer
            : null
      })
    );

    return {
      attempt_id: state.session.attemptId,

      answers,

      language: state.session.language,

      elapsed:
        Math.min(
          state.session.duration,
          elapsedSeconds()
        ),

      finished_at:
        new Date().toISOString()
    };
  }

  async function finishTest(reason = "completed") {
    if (
      state.finishing ||
      !state.session
    ) {
      return;
    }

    state.finishing = true;
    state.busy = true;

    stopClock();

    const payload = buildFinishPayload();

    /*
     * Never submit an incomplete test silently.
     * Timeout may finish it, but all answer positions remain explicit.
     */
    payload.finish_reason = reason;

    if (!isOnline()) {
      queueResult(payload);
      clearActiveSession();

      state.result = {
        iq: "—",
        correct: payload.answers.filter(
          x => Number.isInteger(x.answerIndex)
        ).length,
        elapsed: payload.elapsed,
        rank: "—",
        pending: true
      };

      state.finishing = false;
      state.busy = false;

      renderResult();
      return;
    }

    try {
      showSendingState();

      const result = await api(
        "/api/session/finish",
        {
          method: "POST",
          body: JSON.stringify(payload)
        }
      );

      /*
       * Server is authoritative.
       * Client never calculates the IQ score.
       */
      state.result = normalizeResult(result);

      clearActiveSession();

      renderResult();
    } catch (error) {
      console.error("FINISH TEST:", error);

      /*
       * Network errors are queued.
       * This prevents losing the completed test.
       */
      if (
        !isOnline() ||
        error.name === "AbortError" ||
        error instanceof TypeError
      ) {
        queueResult(payload);

        clearActiveSession();

        state.result = {
          iq: "—",
          correct: payload.answers.filter(
            x => Number.isInteger(x.answerIndex)
          ).length,
          elapsed: payload.elapsed,
          rank: "—",
          pending: true
        };

        renderResult();
      } else {
        toast(t("cannotFinish"));
      }
    } finally {
      state.finishing = false;
      state.busy = false;
    }
  }

  function showSendingState() {
    const status =
      document.getElementById("syncStatus");

    if (status) {
      status.textContent = t("sending");
      status.className =
        "sync-status pending";
    }
  }

  function normalizeResult(data) {
    const source =
      data?.result ||
      data?.data ||
      data ||
      {};

    return {
      iq:
        source.iq ??
        source.iq_score ??
        source.score ??
        "—",

      correct:
        source.correct ??
        source.correct_count ??
        0,

      elapsed:
        source.elapsed ??
        source.time ??
        0,

      rank:
        source.rank ??
        source.position ??
        null,

      synced: true
    };
  }

  function renderResult() {
    stopClock();

    const result = state.result || {};

    const score =
      document.getElementById("score");

    const correctCount =
      document.getElementById("correctCount");

    const resultTime =
      document.getElementById("resultTime");

    const rank =
      document.getElementById("rank");

    const syncStatus =
      document.getElementById("syncStatus");

    if (score) {
      score.textContent =
        result.iq ?? "—";
    }

    if (correctCount) {
      correctCount.textContent =
        `${result.correct ?? 0}/${QUESTION_COUNT}`;
    }

    if (resultTime) {
      resultTime.textContent =
        formatTime(result.elapsed ?? 0);
    }

    if (rank) {
      rank.textContent =
        result.rank
          ? `#${result.rank}`
          : "—";
    }

    if (syncStatus) {
      if (result.pending) {
        syncStatus.textContent = t("pending");
        syncStatus.className =
          "sync-status pending";
      } else {
        syncStatus.textContent = t("synced");
        syncStatus.className =
          "sync-status success";
      }
    }

    /*
     * Score ring:
     * This is visual only.
     * It does NOT calculate the actual score.
     */
    const scoreNumber =
      Number(result.iq);

    const screen =
      document.getElementById("resultScreen");

    if (
      screen &&
      Number.isFinite(scoreNumber)
    ) {
      const normalized =
        Math.max(
          0,
          Math.min(
            1,
            (scoreNumber - 70) / 108
          )
        );

      screen.style.setProperty(
        "--score-progress",
        `${normalized * 360}deg`
      );
    }

    showScreen("resultScreen");
  }

  async function openRanking() {
    showScreen("rankingScreen");

    const loading =
      document.getElementById("rankingLoading");

    const list =
      document.getElementById("rankingList");

    const empty =
      document.getElementById("rankingEmpty");

    const error =
      document.getElementById("rankingError");

    if (loading) loading.classList.remove("hidden");
    if (list) list.innerHTML = "";
    if (empty) empty.classList.add("hidden");
    if (error) error.classList.add("hidden");

    try {
      const data =
        await api("/api/ranking");

      const items =
        data.items ||
        data.ranking ||
        [];

      if (!Array.isArray(items) || !items.length) {
        if (empty) empty.classList.remove("hidden");
        return;
      }

      if (!list) return;

      list.innerHTML = items
        .map((item, index) => {
          const position =
            item.rank ??
            item.position ??
            index + 1;

          const name =
            item.first_name ||
            item.name ||
            item.username ||
            "User";

          const score =
            item.best_score ??
            item.iq ??
            item.score ??
            "—";

          return `
            <div class="ranking-item">
              <div class="ranking-position">
                ${esc(position)}
              </div>

              <div class="ranking-user">
                <div class="ranking-name">
                  ${esc(name)}
                </div>

                <div class="ranking-meta">
                  ${t("score")}
                </div>
              </div>

              <div class="ranking-score">
                ${esc(score)}
              </div>
            </div>
          `;
        })
        .join("");
    } catch (e) {
      console.error("RANKING:", e);

      if (error) {
        error.classList.remove("hidden");
      }
    } finally {
      if (loading) {
        loading.classList.add("hidden");
      }
    }
  }

  async function openProfile() {
    /*
     * The current index.html does not contain a dedicated profile
     * screen, so profile data is represented through a toast for now.
     * This deliberately avoids creating DOM elements that do not exist.
     */
    try {
      const data =
        await api("/api/profile");

      const score =
        data.best_score ??
        data.iq ??
        "—";

      const attempts =
        data.attempts ??
        0;

      toast(
        `${t("best")}: ${score} • ${t("tests")}: ${attempts}`
      );
    } catch (e) {
      toast(t("noData"));
    }
  }

  function openPaymentModal() {
    const modal =
      document.getElementById("paymentModal");

    if (!modal) {
      toast(t("paid"));
      return;
    }

    modal.classList.remove("hidden");

    loadPaymentInfo().catch(
      e => console.error("PAYMENT:", e)
    );
  }

  function closePaymentModal() {
    const modal =
      document.getElementById("paymentModal");

    modal?.classList.add("hidden");
  }

  async function loadPaymentInfo() {
    try {
      const data =
        await api("/api/payment/create", {
          method: "POST",
          body: JSON.stringify({})
        });

      const amount =
        data.amount ??
        data.price ??
        data.price_uzs;

      const amountEl =
        document.getElementById("paymentAmount");

      if (amountEl && amount != null) {
        amountEl.textContent =
          `${Number(amount).toLocaleString("uz-UZ")} so‘m`;
      }

      const cards =
        document.getElementById("paymentCards");

      if (cards && Array.isArray(data.cards)) {
        cards.innerHTML = data.cards
          .map(card => `
            <div class="payment-card">
              <div class="payment-card-title">
                ${esc(card.bank || "Karta")}
              </div>

              <div class="payment-card-number">
                ${esc(card.number || card.card_number || "")}
              </div>

              <div class="payment-card-title">
                ${esc(card.holder || "")}
              </div>
            </div>
          `)
          .join("");
      }

      if (data.payment_id) {
        const openBot =
          document.getElementById(
            "paymentOpenBotBtn"
          );

        if (openBot) {
          openBot.dataset.paymentId =
            String(data.payment_id);
        }
      }
    } catch (e) {
      /*
       * Payment creation is intentionally not retried
       * infinitely. payment.js can handle the provider-specific flow.
       */
      console.warn("Payment info unavailable:", e);
    }
  }

  function openBotPayment() {
    const button =
      document.getElementById(
        "paymentOpenBotBtn"
      );

    const paymentId =
      button?.dataset?.paymentId;

    if (!paymentId) {
      toast(t("error"));
      return;
    }

    const url =
      `https://t.me/${encodeURIComponent(
        window.IQ_BOT_USERNAME || "iq_test_bot"
      )}?start=pay_${encodeURIComponent(paymentId)}`;

    try {
      if (tg?.openTelegramLink) {
        tg.openTelegramLink(url);
      } else {
        window.location.href = url;
      }
    } catch {
      window.location.href = url;
    }
  }

  function shareResult() {
    const result = state.result;

    if (!result) return;

    const text =
      `🧠 IQ TEST\n` +
      `IQ: ${result.iq ?? "—"}\n` +
      `${result.correct ?? 0}/${QUESTION_COUNT}`;

    const url =
      `${location.origin}${location.pathname}`;

    const shareUrl =
      `https://t.me/share/url?url=${encodeURIComponent(
        url
      )}&text=${encodeURIComponent(text)}`;

    try {
      if (tg?.openTelegramLink) {
        tg.openTelegramLink(shareUrl);
      } else if (navigator.share) {
        navigator.share({
          title: "IQ TEST",
          text,
          url
        }).catch(() => {});
      } else if (navigator.clipboard) {
        navigator.clipboard
          .writeText(`${text}\n${url}`)
          .then(() => toast("Natija nusxalandi"))
          .catch(() => {});
      }
    } catch (e) {
      console.error("SHARE:", e);
    }
  }

  function showCertificate() {
    /*
     * Certificate endpoint belongs to the server.
     * Keep it separate from test scoring.
     */
    window.open(
      `${API}/api/certificate`,
      "_blank",
      "noopener,noreferrer"
    );
  }

  function openZako() {
    const url =
      "https://t.me/zako_tbot";

    try {
      if (tg?.openTelegramLink) {
        tg.openTelegramLink(url);
      } else {
        window.location.href = url;
      }
    } catch {
      window.location.href = url;
    }
  }

  function setupQuitModal() {
    const quitBtn =
      document.getElementById("quitBtn");

    const modal =
      document.getElementById("quitModal");

    const stay =
      document.getElementById("quitStayBtn");

    const confirm =
      document.getElementById("quitConfirmBtn");

    quitBtn?.addEventListener("click", () => {
      modal?.classList.remove("hidden");
    });

    stay?.addEventListener("click", () => {
      modal?.classList.add("hidden");
    });

    confirm?.addEventListener("click", () => {
      modal?.classList.add("hidden");

      saveActiveSession();
      stopClock();

      renderHome();
    });
  }

  function setupErrorModal() {
    const modal =
      document.getElementById("errorModal");

    const close =
      document.getElementById("errorCloseBtn");

    close?.addEventListener("click", () => {
      modal?.classList.add("hidden");
    });
  }

  function setupButtons() {
    document
      .getElementById("startBtn")
      ?.addEventListener(
        "click",
        startTest
      );

    document
      .getElementById("rankingBtn")
      ?.addEventListener(
        "click",
        openRanking
      );

    document
      .getElementById("retestBtn")
      ?.addEventListener(
        "click",
        openPaymentModal
      );

    document
      .getElementById("resultRankingBtn")
      ?.addEventListener(
        "click",
        openRanking
      );

    document
      .getElementById("homeBtn")
      ?.addEventListener(
        "click",
        renderHome
      );

    document
      .getElementById("shareBtn")
      ?.addEventListener(
        "click",
        shareResult
      );

    document
      .getElementById("certificateBtn")
      ?.addEventListener(
        "click",
        showCertificate
      );

    document
      .getElementById("zakoBtn")
      ?.addEventListener(
        "click",
        openZako
      );

    document
      .getElementById("paymentCloseBtn")
      ?.addEventListener(
        "click",
        closePaymentModal
      );

    document
      .getElementById("paymentOpenBotBtn")
      ?.addEventListener(
        "click",
        openBotPayment
      );

    document
      .getElementById("rankingRetryBtn")
      ?.addEventListener(
        "click",
        openRanking
      );
  }

  function setupOnlineSync() {
    window.addEventListener(
      "online",
      async () => {
        updateOfflineUI();

        await syncQueue();

        if (getQueue().length === 0) {
          const status =
            document.getElementById(
              "syncStatus"
            );

          if (
            status &&
            state.result?.pending
          ) {
            status.textContent = t("synced");
            status.className =
              "sync-status success";
          }
        }
      },
      { passive: true }
    );

    window.addEventListener(
      "offline",
      updateOfflineUI,
      { passive: true }
    );
  }

  function setupAutosave() {
    clearInterval(state.saveTimer);

    state.saveTimer = setInterval(() => {
      if (state.session) {
        saveActiveSession();
      }
    }, 2000);
  }

  function setupVisibilityProtection() {
    document.addEventListener(
      "visibilitychange",
      () => {
        if (document.visibilityState === "hidden") {
          saveActiveSession();
        }
      },
      { passive: true }
    );

    window.addEventListener(
      "pagehide",
      () => {
        saveActiveSession();
      },
      { passive: true }
    );
  }

  function setupBackButton() {
    if (!tg?.BackButton) return;

    tg.BackButton.onClick(() => {
      const active =
        document.querySelector(
          ".screen.active"
        );

      if (
        active?.id === "testScreen"
      ) {
        document
          .getElementById("quitModal")
          ?.classList.remove("hidden");

        return;
      }

      renderHome();
    });
  }

  function restoreSession() {
    const saved =
      loadActiveSession();

    if (!saved) return false;

    if (
      saved.deadline <= now()
    ) {
      /*
       * Expired session:
       * finish locally and queue it if necessary.
       */
      state.session = saved;

      finishTest("timeout");

      return true;
    }

    state.session = saved;

    return true;
  }

  
  function boot() {
  try {
    telegramReady();
    updateOfflineUI();

    setupButtons();
    setupQuitModal();
    setupErrorModal();
    setupOnlineSync();
    setupAutosave();
    setupVisibilityProtection();
    setupBackButton();

    const restored = restoreSession();

    if (restored) {
      if (
        state.session &&
        state.session.index < QUESTION_COUNT
      ) {
        renderQuestion();
      }

      setLoader(false);
      return;
    }

    showScreen("homeScreen");
    setLoader(false);

  } catch (error) {
    console.error("IQ TEST BOOT ERROR:", error);

    setLoader(false);
    showScreen("homeScreen");

    toast(t("error"));
  }
}

  /*
   * Sync previously completed offline attempts.
   * It is deliberately fire-and-forget so it never blocks startup.
   */
  syncQueue().catch(
    e => console.warn("Initial queue sync:", e)
  );

  boot();

  /*
   * Expose only a tiny controlled surface for payment.js
   * and debugging/integration.
   */
  window.IQTestApp = Object.freeze({
    startTest,
    finishTest,
    openPaymentModal,
    closePaymentModal,
    syncQueue,
    getState: () => ({
      index: state.session?.index ?? null,
      hasSession: Boolean(state.session),
      online: isOnline()
    })
  });

})();