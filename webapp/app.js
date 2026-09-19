/* ============================================================
   IQ TEST BOT — webapp/app.js
   Local-first reasoning test

   ARCHITECTURE
   ------------------------------------------------------------
   START:
     1 request -> server creates authenticated attempt

   DURING TEST:
     0 requests
     answers live only in localStorage

   FINISH:
     1 request -> server verifies/scorers result

   OFFLINE:
     completed payload is queued locally
     and retried automatically when internet returns
   ============================================================ */

(() => {
  "use strict";

  const tg = window.Telegram?.WebApp || null;
  const API = "";

  const STORAGE_KEY = "iq_test_active_v4";
  const QUEUE_KEY = "iq_test_finish_queue_v4";
  const LANG_KEY = "iq_test_lang_v4";

  const QUESTION_COUNT = 16;
  const TOTAL_SECONDS = 8 * 60;

  const state = {
    lang: localStorage.getItem(LANG_KEY) || "uz",
    session: null,
    result: null,
    busy: false,
    finishing: false,
    clock: null,
    autosave: null
  };

  const LETTERS = ["A", "B", "C", "D"];

  /* ==========================================================
     TEXT
     ========================================================== */

  const T = {
    uz: {
      title: "IQ TEST",
      desc: "16 ta qisqa reasoning topshirig‘i orqali fikrlashingizni sinang.",
      start: "TESTNI BOSHLASH",
      ranking: "Reyting",
      profile: "Profil",
      free: "Birinchi test — bepul",
      why: "Test davomida javoblar serverga yuborilmaydi.",
      puzzle: "REASONING",
      time: "Vaqt",
      correct: "To‘g‘ri",
      score: "IQ",
      rank: "Reyting",
      done: "TEST YAKUNLANDI",
      next: "DAVOM ETISH",
      finish: "NATIJANI KO‘RISH",
      loading: "Yuklanmoqda…",
      checking: "Natija tekshirilmoqda…",
      offline: "Internet yo‘q. Test davom etadi.",
      synced: "Natija serverga saqlandi.",
      pending: "Natija internet tiklanganda yuboriladi.",
      error: "Xatolik yuz berdi.",
      retry: "QAYTA URINISH",
      share: "NATIJANI ULASHISH",
      certificate: "SERTIFIKAT",
      develop: "IQ’IMNI RIVOJLANTIRISH",
      quit: "Testdan chiqasizmi?",
      quitText: "Joriy progress qurilmangizda saqlanadi.",
      stay: "TESTDA QOLISH",
      leave: "CHIQISH",
      noData: "Ma’lumot topilmadi.",
      paid: "Keyingi test pullik.",
      cannotStart: "Testni boshlab bo‘lmadi.",
      cannotFinish: "Natijani yuborib bo‘lmadi.",
      session: "Test davom ettirilmoqda."
    },

    ru: {
      title: "IQ ТЕСТ",
      desc: "16 коротких заданий на логику и reasoning.",
      start: "НАЧАТЬ ТЕСТ",
      ranking: "Рейтинг",
      profile: "Профиль",
      free: "Первая попытка — бесплатно",
      why: "Во время теста ответы не отправляются на сервер.",
      puzzle: "REASONING",
      time: "Время",
      correct: "Верно",
      score: "IQ",
      rank: "Рейтинг",
      done: "ТЕСТ ЗАВЕРШЁН",
      next: "ПРОДОЛЖИТЬ",
      finish: "ПОКАЗАТЬ РЕЗУЛЬТАТ",
      loading: "Загрузка…",
      checking: "Проверка результата…",
      offline: "Нет интернета. Тест продолжается.",
      synced: "Результат сохранён.",
      pending: "Результат отправится после восстановления интернета.",
      error: "Произошла ошибка.",
      retry: "ПОВТОРИТЬ",
      share: "ПОДЕЛИТЬСЯ",
      certificate: "СЕРТИФИКАТ",
      develop: "РАЗВИВАТЬ IQ",
      quit: "Выйти из теста?",
      quitText: "Прогресс сохранится на устройстве.",
      stay: "ОСТАТЬСЯ",
      leave: "ВЫЙТИ",
      noData: "Данные не найдены.",
      paid: "Следующая попытка платная.",
      cannotStart: "Не удалось начать тест.",
      cannotFinish: "Не удалось отправить результат.",
      session: "Тест продолжается."
    },

    en: {
      title: "IQ TEST",
      desc: "16 short reasoning tasks designed for quick mobile play.",
      start: "START TEST",
      ranking: "Ranking",
      profile: "Profile",
      free: "First attempt — free",
      why: "Answers are not sent to the server during the test.",
      puzzle: "REASONING",
      time: "Time",
      correct: "Correct",
      score: "IQ",
      rank: "Ranking",
      done: "TEST COMPLETE",
      next: "CONTINUE",
      finish: "VIEW RESULT",
      loading: "Loading…",
      checking: "Checking result…",
      offline: "No internet. The test continues.",
      synced: "Result saved.",
      pending: "Result will be sent when internet returns.",
      error: "Something went wrong.",
      retry: "RETRY",
      share: "SHARE RESULT",
      certificate: "CERTIFICATE",
      develop: "DEVELOP MY IQ",
      quit: "Leave the test?",
      quitText: "Your progress will be saved locally.",
      stay: "STAY",
      leave: "LEAVE",
      noData: "No data found.",
      paid: "The next attempt is paid.",
      cannotStart: "Could not start the test.",
      cannotFinish: "Could not submit the result.",
      session: "Test in progress."
    }
  };

  function t(key) {
    return T[state.lang]?.[key] || T.uz[key] || key;
  }

  /* ==========================================================
     QUESTION BANK
     ----------------------------------------------------------
     IMPORTANT:
     - 16 questions
     - 4 options each
     - correct is used ONLY locally for UI-free operation.
     - Server will have the same answer key and remains
       authoritative at final submission.
     ========================================================== */

  const QUESTIONS = [
    {
      id: "Q01",
      type: "pattern",
      text: {
        uz: "Ketma-ketlikni davom ettiring.",
        ru: "Продолжите последовательность.",
        en: "Continue the sequence."
      },
      visual: `
        <div class="sequence-big">
          <span>2</span>
          <span>4</span>
          <span>8</span>
          <span>16</span>
          <b>?</b>
        </div>
      `,
      options: ["24", "30", "32", "36"],
      correct: 2
    },

    {
      id: "Q02",
      type: "number",
      text: {
        uz: "Qaysi son yetishmayapti?",
        ru: "Какого числа не хватает?",
        en: "Which number is missing?"
      },
      visual: `
        <div class="sequence-big">
          <span>3</span>
          <span>6</span>
          <span>11</span>
          <span>18</span>
          <b>?</b>
        </div>
      `,
      options: ["25", "27", "29", "31"],
      correct: 1
    },

    {
      id: "Q03",
      type: "pattern",
      text: {
        uz: "Qaysi belgi keyingi bo‘ladi?",
        ru: "Какой символ будет следующим?",
        en: "Which symbol comes next?"
      },
      visual: `
        <div class="shape-sequence">
          <span>●</span>
          <span>▲</span>
          <span>●</span>
          <span>▲</span>
          <b>?</b>
        </div>
      `,
      options: ["●", "▲", "■", "◆"],
      correct: 0
    },

    {
      id: "Q04",
      type: "number",
      text: {
        uz: "Qoidani toping.",
        ru: "Найдите правило.",
        en: "Find the rule."
      },
      visual: `
        <div class="math-sequence">
          <span>5 → 11</span>
          <span>7 → 15</span>
          <span>9 → 19</span>
          <span>12 → ?</span>
        </div>
      `,
      options: ["23", "24", "25", "27"],
      correct: 2
    },

    {
      id: "Q05",
      type: "number",
      text: {
        uz: "Ketma-ketlikni davom ettiring.",
        ru: "Продолжите последовательность.",
        en: "Continue the sequence."
      },
      visual: `
        <div class="sequence-big">
          <span>1</span>
          <span>4</span>
          <span>9</span>
          <span>16</span>
          <b>?</b>
        </div>
      `,
      options: ["20", "24", "25", "27"],
      correct: 2
    },

    {
      id: "Q06",
      type: "logic",
      text: {
        uz: "Barcha A — B. Qaysi xulosa aniq?",
        ru: "Все A — это B. Какой вывод точен?",
        en: "All A are B. Which conclusion is certain?"
      },
      visual: `
        <div class="logic-box">
          <span>A</span>
          <i>→</i>
          <span>B</span>
        </div>
      `,
      options: [
        "Barcha B — A",
        "Hech bir A — B emas",
        "A bo‘lsa, B ham bo‘ladi",
        "Ba’zi B — A emas"
      ],
      correct: 2
    },

    {
      id: "Q07",
      type: "number",
      text: {
        uz: "Keyingi sonni toping.",
        ru: "Найдите следующее число.",
        en: "Find the next number."
      },
      visual: `
        <div class="sequence-big">
          <span>2</span>
          <span>6</span>
          <span>12</span>
          <span>20</span>
          <b>?</b>
        </div>
      `,
      options: ["28", "30", "32", "36"],
      correct: 1
    },

    {
      id: "Q08",
      type: "pattern",
      text: {
        uz: "Qaysi shakl naqshni to‘ldiradi?",
        ru: "Какая фигура завершает узор?",
        en: "Which shape completes the pattern?"
      },
      visual: `
        <svg viewBox="0 0 320 150" class="question-svg">
          <rect x="15" y="30" width="60" height="60" rx="8"/>
          <circle cx="45" cy="60" r="15"/>

          <rect x="95" y="30" width="60" height="60" rx="8"/>
          <path d="M125 43 L140 75 L110 75 Z"/>

          <rect x="175" y="30" width="60" height="60" rx="8"/>
          <circle cx="205" cy="60" r="15"/>

          <rect x="255" y="30" width="50" height="60" rx="8"/>
          <text x="272" y="70" font-size="28">?</text>
        </svg>
      `,
      options: ["●", "▲", "■", "◆"],
      correct: 1
    },

    {
      id: "Q09",
      type: "number",
      text: {
        uz: "Qaysi son yetishmayapti?",
        ru: "Какого числа не хватает?",
        en: "Which number is missing?"
      },
      visual: `
        <div class="sequence-big">
          <span>4</span>
          <span>9</span>
          <span>19</span>
          <span>39</span>
          <b>?</b>
        </div>
      `,
      options: ["69", "79", "89", "99"],
      correct: 1
    },

    {
      id: "Q10",
      type: "letters",
      text: {
        uz: "Harflar qatorini davom ettiring.",
        ru: "Продолжите ряд букв.",
        en: "Continue the letter sequence."
      },
      visual: `
        <div class="sequence-big">
          <span>A</span>
          <span>C</span>
          <span>F</span>
          <span>J</span>
          <b>?</b>
        </div>
      `,
      options: ["M", "N", "O", "P"],
      correct: 2
    },

    {
      id: "Q11",
      type: "logic",
      text: {
        uz: "Qaysi tartib barcha shartlarga mos?",
        ru: "Какой порядок соответствует всем условиям?",
        en: "Which order satisfies all conditions?"
      },
      visual: `
        <div class="logic-lines">
          <div>A &lt; B</div>
          <div>B &lt; C</div>
          <div>D &lt; A</div>
        </div>
      `,
      options: [
        "A B C D",
        "D A B C",
        "B D A C",
        "C B A D"
      ],
      correct: 1
    },

    {
      id: "Q12",
      type: "number",
      text: {
        uz: "Keyingi sonni toping.",
        ru: "Найдите следующее число.",
        en: "Find the next number."
      },
      visual: `
        <div class="sequence-big">
          <span>2</span>
          <span>5</span>
          <span>11</span>
          <span>23</span>
          <b>?</b>
        </div>
      `,
      options: ["35", "41", "47", "49"],
      correct: 2
    },

    {
      id: "Q13",
      type: "logic",
      text: {
        uz: "Faqat bitta gap rost. Qaysi quti?",
        ru: "Только одно утверждение истинно. Какая коробка?",
        en: "Only one statement is true. Which box?"
      },
      visual: `
        <div class="boxes">
          <div>A</div>
          <div>B</div>
          <div>C</div>
        </div>
      `,
      options: [
        "A qutida",
        "B qutida",
        "C qutida",
        "Aniqlab bo‘lmaydi"
      ],
      correct: 1
    },

    {
      id: "Q14",
      type: "number",
      text: {
        uz: "Qaysi son qoidaga mos?",
        ru: "Какое число соответствует правилу?",
        en: "Which number follows the rule?"
      },
      visual: `
        <div class="math-sequence">
          <span>2 × 3 + 2 = 8</span>
          <span>3 × 4 + 3 = 15</span>
          <span>4 × 5 + 4 = 24</span>
        </div>
      `,
      options: ["30", "32", "35", "36"],
      correct: 2
    },

    {
      id: "Q15",
      type: "pattern",
      text: {
        uz: "Naqshni davom ettiring.",
        ru: "Продолжите узор.",
        en: "Continue the pattern."
      },
      visual: `
        <div class="shape-sequence">
          <span>○↑</span>
          <span>●→</span>
          <span>○↓</span>
          <span>●←</span>
          <b>?</b>
        </div>
      `,
      options: ["○↑", "●↑", "○→", "●↓"],
      correct: 0
    },

    {
      id: "Q16",
      type: "logic",
      text: {
        uz: "Qaysi xulosa majburiy?",
        ru: "Какой вывод обязателен?",
        en: "Which conclusion must be true?"
      },
      visual: `
        <div class="logic-lines">
          <div>Ba'zi A → B</div>
          <div>B → C</div>
        </div>
      `,
      options: [
        "Barcha A — C",
        "Ba'zi A — C",
        "Barcha C — A",
        "A va C bog‘liq emas"
      ],
      correct: 1
    }
  ];

  /* ==========================================================
     BASIC HELPERS
     ========================================================== */

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function initData() {
    return tg?.initData || "";
  }

  function online() {
    return navigator.onLine !== false;
  }

  function now() {
    return Date.now();
  }

  function uuid() {
    if (crypto?.randomUUID) {
      return crypto.randomUUID();
    }

    const a = new Uint8Array(16);
    crypto.getRandomValues(a);

    a[6] = (a[6] & 15) | 64;
    a[8] = (a[8] & 63) | 128;

    const h = [...a].map(x =>
      x.toString(16).padStart(2, "0")
    );

    return [
      h.slice(0, 4).join(""),
      h.slice(4, 6).join(""),
      h.slice(6, 8).join(""),
      h.slice(8, 10).join(""),
      h.slice(10, 16).join("")
    ].join("-");
  }

  function formatTime(seconds) {
    seconds = Math.max(0, Math.floor(seconds));

    const m = Math.floor(seconds / 60);
    const s = seconds % 60;

    return (
      String(m).padStart(2, "0") +
      ":" +
      String(s).padStart(2, "0")
    );
  }

  function parseJSON(value, fallback) {
    try {
      return JSON.parse(value);
    } catch {
      return fallback;
    }
  }

  /* ==========================================================
     TELEGRAM
     ========================================================== */

  function telegramReady() {
    if (!tg) return;

    try {
      tg.ready();
      tg.expand();

      tg.setHeaderColor?.("#090b12");
      tg.setBackgroundColor?.("#090b12");

      if (tg.enableClosingConfirmation) {
        tg.enableClosingConfirmation();
      }
    } catch (e) {
      console.warn("Telegram:", e);
    }
  }

  /* ==========================================================
     LOCAL STORAGE
     ========================================================== */

  function saveSession() {
    if (!state.session) return;

    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          version: 4,
          savedAt: now(),
          ...state.session
        })
      );
    } catch (e) {
      console.warn("Session save:", e);
    }
  }

  function loadSession() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);

      if (!raw) return null;

      const data = parseJSON(raw, null);

      if (!data || data.version !== 4) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }

      if (
        !data.attemptId ||
        !Array.isArray(data.answers) ||
        data.answers.length !== QUESTION_COUNT
      ) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }

      return data;
    } catch {
      return null;
    }
  }

  function clearSession() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  }

  function queueResult(payload) {
    try {
      const queue = parseJSON(
        localStorage.getItem(QUEUE_KEY) || "[]",
        []
      );

      if (
        !queue.some(
          x => x?.attempt_id === payload.attempt_id
        )
      ) {
        queue.push(payload);
      }

      localStorage.setItem(
        QUEUE_KEY,
        JSON.stringify(queue)
      );
    } catch (e) {
      console.error("Queue:", e);
    }
  }

  function getQueue() {
    return parseJSON(
      localStorage.getItem(QUEUE_KEY) || "[]",
      []
    );
  }

  function setQueue(queue) {
    try {
      localStorage.setItem(
        QUEUE_KEY,
        JSON.stringify(queue)
      );
    } catch {}
  }

  /* ==========================================================
     API
     ========================================================== */

  async function api(path, options = {}) {
    const controller = new AbortController();

    const timer = setTimeout(() => {
      controller.abort();
    }, 15000);

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData(),
        ...(options.headers || {})
      };

      const response = await fetch(
        API + path,
        {
          ...options,
          headers,
          cache: "no-store",
          signal: controller.signal
        }
      );

      const text = await response.text();

      let data = {};

      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = {
            detail: text
          };
        }
      }

      if (!response.ok) {
        const error = new Error(
          data?.detail ||
          data?.error ||
          `HTTP_${response.status}`
        );

        error.status = response.status;
        error.code =
          data?.code ||
          data?.error ||
          data?.detail;

        throw error;
      }

      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  /* ==========================================================
     UI
     ========================================================== */

  function showScreen(id) {
    document
      .querySelectorAll(".screen")
      .forEach(el =>
        el.classList.remove("active")
      );

    const screen =
      document.getElementById(id);

    if (screen) {
      screen.classList.add("active");
    }

    window.scrollTo({
      top: 0,
      behavior: "instant"
    });
  }

  function loader(show) {
    const el =
      document.getElementById("globalLoader");

    if (!el) return;

    el.classList.toggle(
      "hidden",
      !show
    );
  }

  let toastTimer = null;

  function toast(message) {
    const el =
      document.getElementById("toast");

    const text =
      document.getElementById("toastMessage");

    if (!el || !text) return;

    text.textContent = message;

    el.classList.add("visible");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
      el.classList.remove("visible");
    }, 2400);
  }

  function offlineUI() {
    const banner =
      document.getElementById("offlineBanner");

    if (!banner) return;

    banner.classList.toggle(
      "visible",
      !online()
    );
  }

  /* ==========================================================
     HOME
     ========================================================== */

  function renderHome() {
    stopClock();

    const start =
      document.getElementById("startBtn");

    const ranking =
      document.getElementById("rankingBtn");

    if (start) {
      start.textContent = t("start");
    }

    if (ranking) {
      ranking.textContent = t("ranking");
    }

    showScreen("homeScreen");

    if (loadSession()) {
      toast(t("session"));
    }
  }

  /* ==========================================================
     START
     ----------------------------------------------------------
     Only ONE server request here.
     The server creates an attempt_id.
     ========================================================== */

  async function startTest() {
    if (state.busy) return;

    const saved = loadSession();

    if (saved) {
      if (
        saved.deadline > now() &&
        saved.index >= 0 &&
        saved.index < QUESTION_COUNT
      ) {
        state.session = saved;
        renderQuestion();
        return;
      }

      clearSession();
    }

    if (!online()) {
      toast(t("cannotStart"));
      return;
    }

    state.busy = true;
    loader(true);

    try {
      const data = await api(
        "/api/session/start",
        {
          method: "POST",
          body: JSON.stringify({
            language: state.lang
          })
        }
      );

      const attemptId =
        data.attempt_id ||
        data.attemptId ||
        uuid();

      state.session = {
        version: 4,

        attemptId,

        index: 0,

        answers:
          Array(QUESTION_COUNT).fill(null),

        startedAt: now(),

        deadline:
          now() +
          TOTAL_SECONDS * 1000,

        duration: TOTAL_SECONDS,

        language: state.lang,

        completed: false
      };

      saveSession();

      renderQuestion();

    } catch (error) {
      console.error("START:", error);

      if (
        error.status === 402 ||
        error.code === "PAID_RETEST"
      ) {
        openPayment();
      } else {
        toast(t("cannotStart"));
      }
    } finally {
      state.busy = false;
      loader(false);
    }
  }

  /* ==========================================================
     QUESTION
     ========================================================== */

  function questionText(q) {
    if (!q) return "";

    if (typeof q.text === "string") {
      return q.text;
    }

    return (
      q.text?.[state.lang] ||
      q.text?.uz ||
      q.text?.en ||
      ""
    );
  }

  function questionOptions(q) {
    if (!q) return [];

    return (
      q.options?.[state.lang] ||
      q.options?.uz ||
      q.options ||
      []
    );
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

    const q =
      QUESTIONS[s.index];

    if (!q) {
      toast(t("error"));
      return;
    }

    const number =
      s.index + 1;

    const qText =
      questionText(q);

    const options =
      questionOptions(q);

    const numberEl =
      document.getElementById(
        "questionNumber"
      );

    const progress =
      document.getElementById(
        "progressFill"
      );

    const category =
      document.getElementById(
        "questionCategory"
      );

    const text =
      document.getElementById(
        "questionText"
      );

    const puzzle =
      document.getElementById(
        "puzzle"
      );

    const answers =
      document.getElementById(
        "answers"
      );

    const next =
      document.getElementById(
        "nextBtn"
      );

    if (numberEl) {
      numberEl.textContent =
        `${String(number).padStart(2, "0")} / ${QUESTION_COUNT}`;
    }

    if (progress) {
      progress.style.width =
        `${(number / QUESTION_COUNT) * 100}%`;
    }

    if (category) {
      category.textContent =
        t("puzzle");
    }

    if (text) {
      text.innerHTML =
        esc(qText).replace(
          /\n/g,
          "<br>"
        );
    }

    if (puzzle) {
      if (q.visual) {
        puzzle.innerHTML =
          q.visual;

        puzzle.classList.remove(
          "hidden"
        );
      } else {
        puzzle.innerHTML = "";
        puzzle.classList.add(
          "hidden"
        );
      }
    }

    if (answers) {
      answers.innerHTML =
        options
          .map(
            (option, index) => {

              const selected =
                s.answers[s.index] === index;

              return `
                <button
                  type="button"
                  class="answer${selected ? " selected" : ""}"
                  data-answer="${index}"
                  aria-label="${LETTERS[index]}"
                >
                  <span class="answer-letter">
                    ${LETTERS[index]}
                  </span>

                  <span class="answer-text">
                    ${esc(option)}
                  </span>
                </button>
              `;
            }
          )
          .join("");

      answers
        .querySelectorAll(
          "[data-answer]"
        )
        .forEach(button => {

          button.addEventListener(
            "click",
            () => {
              chooseAnswer(
                Number(
                  button.dataset.answer
                )
              );
            }
          );

        });
    }

    if (next) {
      next.textContent =
        number === QUESTION_COUNT
          ? t("finish")
          : t("next");

      next.disabled =
        !Number.isInteger(
          s.answers[s.index]
        );

      next.onclick = () => {

        if (
          !Number.isInteger(
            s.answers[s.index]
          )
        ) {
          return;
        }

        goNext();
      };
    }

    showScreen("testScreen");

    startClock();
    updateTimer();
  }

  /* ==========================================================
     ANSWER
     ----------------------------------------------------------
     ZERO NETWORK REQUESTS.
     ========================================================== */

  function chooseAnswer(index) {
    if (
      !state.session ||
      state.finishing
    ) {
      return;
    }

    if (
      !Number.isInteger(index) ||
      index < 0 ||
      index > 3
    ) {
      return;
    }

    const qIndex =
      state.session.index;

    state.session.answers[qIndex] =
      index;

    saveSession();

    document
      .querySelectorAll(
        "[data-answer]"
      )
      .forEach(button => {

        button.classList.toggle(
          "selected",
          Number(
            button.dataset.answer
          ) === index
        );

      });

    const next =
      document.getElementById(
        "nextBtn"
      );

    if (next) {
      next.disabled = false;
    }
  }

  function goNext() {
    if (
      !state.session ||
      state.finishing
    ) {
      return;
    }

    const index =
      state.session.index;

    if (
      !Number.isInteger(
        state.session.answers[index]
      )
    ) {
      return;
    }

    if (
      index ===
      QUESTION_COUNT - 1
    ) {
      finishTest("completed");
      return;
    }

    state.session.index++;

    saveSession();

    renderQuestion();
  }

  /* ==========================================================
     TIMER
     ========================================================== */

  function remainingSeconds() {
    if (!state.session) {
      return TOTAL_SECONDS;
    }

    return Math.max(
      0,
      Math.ceil(
        (
          state.session.deadline -
          now()
        ) / 1000
      )
    );
  }

  function elapsedSeconds() {
    if (!state.session) return 0;

    return Math.max(
      0,
      Math.floor(
        (
          now() -
          state.session.startedAt
        ) / 1000
      )
    );
  }

  function updateTimer() {
    const el =
      document.getElementById(
        "timer"
      );

    if (!el || !state.session) {
      return;
    }

    const remaining =
      remainingSeconds();

    el.textContent =
      formatTime(remaining);

    el.classList.toggle(
      "warning",
      remaining <= 120 &&
      remaining > 30
    );

    el.classList.toggle(
      "danger",
      remaining <= 30
    );

    if (
      remaining <= 0 &&
      !state.finishing
    ) {
      finishTest("timeout");
    }
  }

  function startClock() {
    stopClock();

    updateTimer();

    state.clock =
      setInterval(
        updateTimer,
        500
      );
  }

  function stopClock() {
    if (state.clock) {
      clearInterval(
        state.clock
      );

      state.clock = null;
    }
  }

  /* ==========================================================
     FINAL PAYLOAD
     ========================================================== */

  function buildPayload(reason) {
    if (!state.session) {
      throw new Error(
        "NO_SESSION"
      );
    }

    return {
      attempt_id:
        state.session.attemptId,

      answers:
        state.session.answers.map(
          (answer, index) => ({
            question_id:
              QUESTIONS[index].id,

            answer_index:
              Number.isInteger(answer)
                ? answer
                : null
          })
        ),

      language:
        state.session.language,

      elapsed:
        Math.min(
          state.session.duration,
          elapsedSeconds()
        ),

      finish_reason:
        reason,

      finished_at:
        new Date().toISOString()
    };
  }

  /* ==========================================================
     FINISH
     ----------------------------------------------------------
     ONE network request.
     ========================================================== */

  async function finishTest(
    reason = "completed"
  ) {
    if (
      state.finishing ||
      !state.session
    ) {
      return;
    }

    state.finishing = true;
    state.busy = true;

    stopClock();

    const payload =
      buildPayload(reason);

    /* Offline = don't even try network. */
    if (!online()) {
      queueResult(payload);

      clearSession();

      state.result = {
        iq: "—",
        correct:
          payload.answers.filter(
            x =>
              Number.isInteger(
                x.answer_index
              )
          ).length,
        elapsed:
          payload.elapsed,
        rank: null,
        pending: true
      };

      state.finishing = false;
      state.busy = false;

      renderResult();

      return;
    }

    showChecking();

    try {

      /*
       * THE ONLY RESULT REQUEST.
       */
      const data =
        await api(
          "/api/session/finish",
          {
            method: "POST",
            body:
              JSON.stringify(
                payload
              )
          }
        );

      state.result =
        normalizeResult(data);

      clearSession();

      renderResult();

    } catch (error) {

      console.error(
        "FINISH:",
        error
      );

      /*
       * Network failure:
       * never lose completed test.
       */
      if (
        error.name ===
          "AbortError" ||
        error instanceof TypeError ||
        !online()
      ) {

        queueResult(payload);

        clearSession();

        state.result = {
          iq: "—",
          correct:
            payload.answers.filter(
              x =>
                Number.isInteger(
                  x.answer_index
                )
            ).length,
          elapsed:
            payload.elapsed,
          rank: null,
          pending: true
        };

        renderResult();

      } else {

        /*
         * Server deliberately rejected
         * the payload. Don't pretend it succeeded.
         */
        toast(
          t("cannotFinish")
        );

        state.finishing =
          false;

        state.busy =
          false;

        return;
      }

    } finally {
      state.finishing =
        false;

      state.busy =
        false;
    }
  }

  function showChecking() {
    const el =
      document.getElementById(
        "syncStatus"
      );

    if (!el) return;

    el.textContent =
      t("checking");

    el.className =
      "sync-status pending";
  }

  function normalizeResult(data) {
    const r =
      data?.result ||
      data ||
      {};

    return {
      iq:
        r.iq ??
        r.iq_score ??
        "—",

      correct:
        r.correct ??
        r.correct_count ??
        0,

      elapsed:
        r.elapsed ??
        0,

      rank:
        r.rank ??
        null,

      pending: false
    };
  }

  /* ==========================================================
     RESULT
     ========================================================== */

  function renderResult() {
    stopClock();

    const result =
      state.result || {};

    const score =
      document.getElementById(
        "score"
      );

    const correct =
      document.getElementById(
        "correctCount"
      );

    const time =
      document.getElementById(
        "resultTime"
      );

    const rank =
      document.getElementById(
        "rank"
      );

    const sync =
      document.getElementById(
        "syncStatus"
      );

    if (score) {
      score.textContent =
        result.iq ?? "—";
    }

    if (correct) {
      correct.textContent =
        `${result.correct ?? 0}/${QUESTION_COUNT}`;
    }

    if (time) {
      time.textContent =
        formatTime(
          result.elapsed ?? 0
        );
    }

    if (rank) {
      rank.textContent =
        result.rank
          ? `#${result.rank}`
          : "—";
    }

    if (sync) {
      if (result.pending) {

        sync.textContent =
          t("pending");

        sync.className =
          "sync-status pending";

      } else {

        sync.textContent =
          t("synced");

        sync.className =
          "sync-status success";
      }
    }

    /* Visual score ring only. */
    const scoreNumber =
      Number(result.iq);

    const screen =
      document.getElementById(
        "resultScreen"
      );

    if (
      screen &&
      Number.isFinite(
        scoreNumber
      )
    ) {

      const progress =
        Math.max(
          0,
          Math.min(
            1,
            (
              scoreNumber - 70
            ) / 108
          )
        );

      screen.style.setProperty(
        "--score-progress",
        `${progress * 360}deg`
      );
    }

    showScreen(
      "resultScreen"
    );
  }

  /* ==========================================================
     OFFLINE QUEUE SYNC
     ========================================================== */

  async function syncQueue() {
    if (!online()) return;

    const queue =
      getQueue();

    if (!queue.length) {
      return;
    }

    const remaining = [];

    for (
      const payload of queue
    ) {

      try {

        await api(
          "/api/session/finish",
          {
            method: "POST",
            body:
              JSON.stringify(
                payload
              )
          }
        );

      } catch (error) {

        /*
         * Keep only failed payloads.
         * Successful ones are removed.
         */
        remaining.push(
          payload
        );
      }
    }

    setQueue(
      remaining
    );
  }

  /* ==========================================================
     RANKING
     ========================================================== */

  async function openRanking() {
    showScreen(
      "rankingScreen"
    );

    const loading =
      document.getElementById(
        "rankingLoading"
      );

    const list =
      document.getElementById(
        "rankingList"
      );

    const empty =
      document.getElementById(
        "rankingEmpty"
      );

    const error =
      document.getElementById(
        "rankingError"
      );

    loading?.classList.remove(
      "hidden"
    );

    if (list) {
      list.innerHTML = "";
    }

    empty?.classList.add(
      "hidden"
    );

    error?.classList.add(
      "hidden"
    );

    try {

      const data =
        await api(
          "/api/ranking"
        );

      const items =
        data.items ||
        [];

      if (!items.length) {

        empty?.classList.remove(
          "hidden"
        );

        return;
      }

      if (!list) return;

      list.innerHTML =
        items.map(
          (item, index) => {

            const position =
              item.rank ??
              item.position ??
              index + 1;

            const name =
              item.first_name ||
              item.username ||
              "User";

            const score =
              item.best_score ??
              item.iq ??
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
                    IQ
                  </div>
                </div>

                <div class="ranking-score">
                  ${esc(score)}
                </div>

              </div>
            `;
          }
        ).join("");

    } catch (errorObject) {

      console.error(
        "RANKING:",
        errorObject
      );

      error?.classList.remove(
        "hidden"
      );

    } finally {

      loading?.classList.add(
        "hidden"
      );
    }
  }

  /* ==========================================================
     PROFILE
     ========================================================== */

  async function openProfile() {
    try {

      const data =
        await api(
          "/api/profile"
        );

      toast(
        `${t("score")}: ${
          data.best_score ?? "—"
        } • ${
          t("correct")
        }: ${
          data.attempts ?? 0
        }`
      );

    } catch {

      toast(
        t("noData")
      );
    }
  }

  /* ==========================================================
     PAYMENT
     ----------------------------------------------------------
     payment.js owns actual payment UI.
     ========================================================== */

  function openPayment() {

    if (
      window.IQPayment?.open
    ) {

      window.IQPayment.open();

      return;
    }

    const modal =
      document.getElementById(
        "paymentModal"
      );

    modal?.classList.remove(
      "hidden"
    );
  }

  /* ==========================================================
     SHARE
     ========================================================== */

  function shareResult() {
    if (!state.result) {
      return;
    }

    const text =
      `🧠 IQ TEST\n` +
      `IQ: ${
        state.result.iq ?? "—"
      }\n` +
      `${
        state.result.correct ?? 0
      }/${QUESTION_COUNT}`;

    const url =
      `${location.origin}${location.pathname}`;

    const shareUrl =
      `https://t.me/share/url?url=${
        encodeURIComponent(url)
      }&text=${
        encodeURIComponent(text)
      }`;

    try {

      if (
        tg?.openTelegramLink
      ) {

        tg.openTelegramLink(
          shareUrl
        );

      } else if (
        navigator.share
      ) {

        navigator.share({
          title: "IQ TEST",
          text,
          url
        }).catch(
          () => {}
        );

      } else if (
        navigator.clipboard
      ) {

        navigator.clipboard
          .writeText(
            `${text}\n${url}`
          )
          .then(
            () =>
              toast(
                "Natija nusxalandi"
              )
          )
          .catch(
            () => {}
          );
      }

    } catch (e) {
      console.error(
        "SHARE:",
        e
      );
    }
  }

  /* ==========================================================
     CERTIFICATE
     ========================================================== */

  function showCertificate() {

    fetch(
      "/api/certificate",
      {
        headers: {
          "X-Telegram-Init-Data":
            initData()
        }
      }
    )
      .then(async response => {

        if (!response.ok) {

          const data =
            await response
              .json()
              .catch(
                () => ({})
              );

          toast(
            data.detail ||
            "Certificate error"
          );

          return;
        }

        const blob =
          await response.blob();

        const url =
          URL.createObjectURL(
            blob
          );

        window.open(
          url,
          "_blank"
        );
      })
      .catch(
        () =>
          toast(
            t("error")
          )
      );
  }

  /* ==========================================================
     ZAKO
     ========================================================== */

  function openZako() {

    const url =
      "https://t.me/zako_tbot";

    try {

      if (
        tg?.openTelegramLink
      ) {
        tg.openTelegramLink(
          url
        );
      } else {
        location.href =
          url;
      }

    } catch {
      location.href =
        url;
    }
  }

  /* ==========================================================
     QUIT
     ========================================================== */

  function setupQuit() {

    const quit =
      document.getElementById(
        "quitBtn"
      );

    const modal =
      document.getElementById(
        "quitModal"
      );

    const stay =
      document.getElementById(
        "quitStayBtn"
      );

    const leave =
      document.getElementById(
        "quitConfirmBtn"
      );

    quit?.addEventListener(
      "click",
      () => {
        modal?.classList.remove(
          "hidden"
        );
      }
    );

    stay?.addEventListener(
      "click",
      () => {
        modal?.classList.add(
          "hidden"
        );
      }
    );

    leave?.addEventListener(
      "click",
      () => {

        modal?.classList.add(
          "hidden"
        );

        saveSession();

        stopClock();

        renderHome();
      }
    );
  }

  /* ==========================================================
     BUTTONS
     ========================================================== */

  function setupButtons() {

    document
      .getElementById(
        "startBtn"
      )
      ?.addEventListener(
        "click",
        startTest
      );

    document
      .getElementById(
        "rankingBtn"
      )
      ?.addEventListener(
        "click",
        openRanking
      );

    document
      .getElementById(
        "retestBtn"
      )
      ?.addEventListener(
        "click",
        openPayment
      );

    document
      .getElementById(
        "resultRankingBtn"
      )
      ?.addEventListener(
        "click",
        openRanking
      );

    document
      .getElementById(
        "homeBtn"
      )
      ?.addEventListener(
        "click",
        renderHome
      );

    document
      .getElementById(
        "shareBtn"
      )
      ?.addEventListener(
        "click",
        shareResult
      );

    document
      .getElementById(
        "certificateBtn"
      )
      ?.addEventListener(
        "click",
        showCertificate
      );

    document
      .getElementById(
        "zakoBtn"
      )
      ?.addEventListener(
        "click",
        openZako
      );

    document
      .getElementById(
        "paymentCloseBtn"
      )
      ?.addEventListener(
        "click",
        () =>
          window.IQPayment?.close?.()
      );

    document
      .getElementById(
        "rankingRetryBtn"
      )
      ?.addEventListener(
        "click",
        openRanking
      );
  }

  /* ==========================================================
     ONLINE / OFFLINE
     ========================================================== */

  function setupNetwork() {

    window.addEventListener(
      "online",
      async () => {

        offlineUI();

        await syncQueue();

        /*
         * If there was a pending result,
         * reload ranking/result only after
         * successful queue synchronization.
         */
      }
    );

    window.addEventListener(
      "offline",
      offlineUI
    );
  }

  /* ==========================================================
     AUTOSAVE
     ========================================================== */

  function setupAutosave() {

    clearInterval(
      state.autosave
    );

    state.autosave =
      setInterval(
        () => {

          if (
            state.session
          ) {
            saveSession();
          }

        },
        1500
      );
  }

  function setupVisibility() {

    document.addEventListener(
      "visibilitychange",
      () => {

        if (
          document.visibilityState ===
          "hidden"
        ) {
          saveSession();
        }

      }
    );

    window.addEventListener(
      "pagehide",
      saveSession
    );
  }

  /* ==========================================================
     TELEGRAM BACK BUTTON
     ========================================================== */

  function setupBackButton() {

    if (!tg?.BackButton) {
      return;
    }

    tg.BackButton.onClick(
      () => {

        const active =
          document.querySelector(
            ".screen.active"
          );

        if (
          active?.id ===
          "testScreen"
        ) {

          document
            .getElementById(
              "quitModal"
            )
            ?.classList.remove(
              "hidden"
            );

          return;
        }

        renderHome();
      }
    );
  }

  /* ==========================================================
     RESTORE
     ========================================================== */

  function restore() {

    const saved =
      loadSession();

    if (!saved) {
      return false;
    }

    if (
      saved.deadline <= now()
    ) {

      state.session =
        saved;

      finishTest(
        "timeout"
      );

      return true;
    }

    state.session =
      saved;

    return true;
  }

  /* ==========================================================
     BOOT
     ========================================================== */

  function boot() {

    telegramReady();

    offlineUI();

    setupButtons();

    setupQuit();

    setupNetwork();

    setupAutosave();

    setupVisibility();

    setupBackButton();

    const restored =
      restore();

    if (restored) {

      if (
        state.session &&
        state.session.index <
          QUESTION_COUNT
      ) {
        renderQuestion();
      }

      return;
    }

    showScreen(
      "homeScreen"
    );
  }

  /*
   * Previous offline results are synchronized
   * in the background.
   */
  syncQueue().catch(
    error =>
      console.warn(
        "Initial sync:",
        error
      )
  );

  boot();

  /* ==========================================================
     PUBLIC API
     ========================================================== */

  window.IQTestApp =
    Object.freeze({
      startTest,
      finishTest,
      openPayment,
      syncQueue,

      getState: () => ({
        index:
          state.session?.index ??
          null,

        hasSession:
          Boolean(
            state.session
          ),

        online:
          online(),

        queued:
          getQueue().length
      })
    });

})();