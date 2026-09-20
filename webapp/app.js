"use strict";

(() => {
  const tg = window.Telegram?.WebApp || null;
  const COUNT = 18;
  const LETTERS = ["A", "B", "C", "D"];

  const state = {
    lang: localStorage.getItem("iq_lang") || "uz",
    session: null,
    result: null,
    busy: false,
    finishing: false,
    startedAt: 0,
    timer: null
  };

  /*
   * =========================================================
   * IQ TEST — 18 QUESTIONS
   * =========================================================
   */

  const QUESTIONS = [
    [
      "Ketma-ketlik: 4, 7, 13, 25, 49, ?",
      ["73", "97", "98", "101"],
      1
    ],
    [
      "Ketma-ketlik: 2, 5, 11, 23, 47, ?",
      ["91", "93", "95", "97"],
      2
    ],
    [
      "Ketma-ketlik: 3, 8, 15, 24, 35, ?",
      ["48", "49", "50", "51"],
      0
    ],
    [
      "Ketma-ketlik: 2, 6, 12, 20, 30, ?",
      ["38", "40", "42", "44"],
      2
    ],
    [
      "Ketma-ketlik: 1, 2, 6, 24, 120, ?",
      ["480", "600", "720", "840"],
      2
    ],
    [
      "Harflar ketma-ketligi: A, C, F, J, O, ?",
      ["T", "U", "V", "W"],
      1
    ],
    [
      "Barcha K lar L. Ba’zi L lar M. Qaysi gap albatta to‘g‘ri?",
      [
        "Barcha K lar L",
        "Ba’zi K lar M",
        "Hech bir K M emas",
        "Barcha M lar K"
      ],
      0
    ],
    [
      "A, B, C, D, E bir qatorda turadi. A — B dan oldin. C — D dan darhol keyin. E birinchi emas. Qaysi tartib mumkin?",
      [
        "D-C-A-E-B",
        "A-C-D-E-B",
        "B-A-D-E-C",
        "E-D-C-B-A"
      ],
      0
    ],
    [
      "Har bir qatorda 3-son = 1-son + 2-son: 2,5,7 / 4,9,13 / 6,13, ?",
      ["17", "18", "19", "20"],
      2
    ],
    [
      "Ketma-ketlik: 1, 4, 10, 22, 46, ?",
      ["90", "92", "94", "96"],
      2
    ],
    [
      "Ketma-ketlik: 2, 3, 6, 11, 18, 27, ?",
      ["36", "38", "40", "42"],
      1
    ],
    [
      "Soat 3:40 ni ko‘rsatmoqda. Soat va minut strelkalari orasidagi kichik burchak necha daraja?",
      ["110°", "120°", "130°", "140°"],
      2
    ],
    [
      "Ba’zi rassomlar muhandis. Barcha muhandislar kitobxon. Qaysi xulosa albatta to‘g‘ri?",
      [
        "Barcha rassomlar kitobxon",
        "Ba’zi rassomlar kitobxon",
        "Hech bir rassom kitobxon emas",
        "Barcha kitobxonlar muhandis"
      ],
      1
    ],
    [
      "Ketma-ketlik: 2, 9, 28, 65, 126, ?",
      ["181", "205", "217", "225"],
      2
    ],
    [
      "Kubning qarama-qarshi tomonlari A-D, B-E va C-F. Qaysi tomon A bilan bitta qirrani bo‘lisha olmaydi?",
      ["B", "C", "E", "D"],
      3
    ],
    [
      "A: “B yolg‘on gapiryapti.” B: “C yolg‘on gapiryapti.” C: “A va B bir xil turdagi odamlar.” Faqat bittasi rost gapirsa, kim?",
      ["A", "B", "C", "Hech biri"],
      1
    ],
    [
      "4 xonali koddagi barcha raqamlar turlicha. Birinchi raqam 0 bo‘lishi mumkin emas. Nechta kod mavjud?",
      ["4032", "4320", "4536", "5040"],
      2
    ],
    [
      "Ketma-ketlik: 1, 2, 6, 15, 31, 56, ?",
      ["84", "88", "92", "96"],
      2
    ]
  ];

  const TEXT = {
    uz: {
      start: "TESTNI BOSHLASH",
      free: "Birinchi test — bepul",
      ranking: "🏆 Reyting",
      profile: "👤 Profil",
      back: "‹ Orqaga",
      next: "DAVOM ETISH",
      correct: "To‘g‘ri",
      time: "Vaqt",
      result: "TEST YAKUNLANDI",
      certificate: "SERTIFIKAT OLISH",
      share: "NATIJANI ULASHISH",
      home: "Bosh sahifa",
      description:
        "18 ta mantiqiy puzzle orqali fikrlash qobiliyatingizni sinang.",
      loading: "Yuklanmoqda…",
      error: "Xatolik yuz berdi. Qayta urinib ko‘ring.",
      offline: "Internet yo‘q. Javoblaringiz saqlandi.",
      paid: "Keyingi test pullik.",
      noData: "Ma’lumot topilmadi."
    },

    ru: {
      start: "НАЧАТЬ ТЕСТ",
      free: "Первая попытка — бесплатно",
      ranking: "🏆 Рейтинг",
      profile: "👤 Профиль",
      back: "‹ Назад",
      next: "ПРОДОЛЖИТЬ",
      correct: "Верно",
      time: "Время",
      result: "ТЕСТ ЗАВЕРШЁН",
      certificate: "ПОЛУЧИТЬ СЕРТИФИКАТ",
      share: "ПОДЕЛИТЬСЯ",
      home: "Главная",
      description:
        "Проверьте мышление с помощью 18 логических задач.",
      loading: "Загрузка…",
      error: "Произошла ошибка. Попробуйте ещё раз.",
      offline: "Нет интернета. Ответы сохранены.",
      paid: "Следующая попытка платная.",
      noData: "Данные не найдены."
    },

    en: {
      start: "START TEST",
      free: "First attempt — free",
      ranking: "🏆 Ranking",
      profile: "👤 Profile",
      back: "‹ Back",
      next: "CONTINUE",
      correct: "Correct",
      time: "Time",
      result: "TEST COMPLETE",
      certificate: "GET CERTIFICATE",
      share: "SHARE RESULT",
      home: "Home",
      description:
        "Test your thinking with 18 logic puzzles.",
      loading: "Loading…",
      error: "Something went wrong.",
      offline: "No internet. Your answers were saved.",
      paid: "The next attempt is paid.",
      noData: "No data found."
    }
  };

  const t = key => {
    return (TEXT[state.lang] || TEXT.uz)[key] || key;
  };

  const $ = id => document.getElementById(id);

  function escapeHTML(value) {
    return String(value ?? "").replace(
      /[&<>"']/g,
      char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]
    );
  }

  function getInitData() {
    return tg?.initData || "";
  }

  function localKey() {
    const id =
      tg?.initDataUnsafe?.user?.id ||
      "guest";

    return `iqtestpro_session_${id}`;
  }

  function saveSession() {
    if (!state.session) return;

    try {
      localStorage.setItem(
        localKey(),
        JSON.stringify({
          index: state.session.index,
          answers: state.session.answers,
          elapsed: getElapsed(),
          startedAt: state.startedAt,
          language: state.lang,
          savedAt: Date.now()
        })
      );
    } catch {}
  }

  function loadSession() {
    try {
      const raw = localStorage.getItem(localKey());

      if (!raw) return null;

      const data = JSON.parse(raw);

      if (!data || !Array.isArray(data.answers)) {
        return null;
      }

      if (data.answers.length > COUNT) {
        return null;
      }

      return data;
    } catch {
      return null;
    }
  }

  function clearSession() {
    try {
      localStorage.removeItem(localKey());
    } catch {}
  }

  function getElapsed() {
    if (!state.session) {
      return 0;
    }

    const base =
      Number(state.session.elapsed) || 0;

    if (!state.startedAt) {
      return base;
    }

    return Math.max(
      base,
      Math.floor(
        (Date.now() - state.startedAt) / 1000
      )
    );
  }

  function formatTime(seconds) {
    const value = Math.max(
      0,
      Math.floor(Number(seconds) || 0)
    );

    const minutes =
      String(Math.floor(value / 60)).padStart(2, "0");

    const secondsPart =
      String(value % 60).padStart(2, "0");

    return `${minutes}:${secondsPart}`;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": getInitData(),
        ...(options.headers || {})
      }
    });

    let data = {};

    try {
      data = await response.json();
    } catch {}

    if (!response.ok) {
      const error = new Error(
        data?.detail ||
        `HTTP_${response.status}`
      );

      error.status = response.status;
      error.code =
        data?.detail ||
        "REQUEST_FAILED";

      throw error;
    }

    return data;
  }

  function telegramReady() {
    try {
      tg?.ready();
      tg?.expand();

      tg?.setHeaderColor?.("#070914");
      tg?.setBackgroundColor?.("#070914");
    } catch {}
  }

  /*
   * =========================================================
   * UI
   * =========================================================
   */

  function buildUI() {
    const root = $("app");

    if (!root) {
      throw new Error("APP_ROOT_NOT_FOUND");
    }

    root.innerHTML = `
      <main class="page">

        <div class="brand-row">
          <div class="brand">
            <div class="brand-mark">IQ</div>
            <div>
              <b>IQTestPro</b>
              <small>LOGIC • INTELLIGENCE</small>
            </div>
          </div>

          <button
            id="languageButton"
            class="lang-mini"
            type="button"
          >
            ${state.lang.toUpperCase()}
          </button>
        </div>


        <!-- HOME -->

        <section
          id="homeScreen"
          class="screen"
        >

          <div class="hero">

            <div class="brain-glow">
              🧠
            </div>

            <div class="eyebrow">
              18 TA MANTIQIY PUZZLE
            </div>

            <h1>
              IQ darajangizni
              <span>sinab ko‘ring</span>
            </h1>

            <p>
              ${t("description")}
            </p>

          </div>


          <div class="cards">

            <button
              id="startButton"
              class="test-card"
              type="button"
            >

              <div class="card-icon">
                🧠
              </div>

              <div>
                <b>${t("start")}</b>
                <small>${t("free")}</small>
              </div>

              <span class="arrow">
                ›
              </span>

            </button>

          </div>


          <button
            id="rankingButton"
            class="ghost"
            type="button"
          >
            ${t("ranking")}
          </button>


          <button
            id="profileButton"
            class="ghost"
            type="button"
          >
            ${t("profile")}
          </button>

        </section>


        <!-- TEST -->

        <section
          id="testScreen"
          class="screen test"
          style="display:none"
        >

          <button
            id="backButton"
            class="back"
            type="button"
          >
            ${t("back")}
          </button>


          <div class="test-top">

            <div>
              <b>IQ TEST</b>
              <small id="timer">
                00:00
              </small>
            </div>

            <div
              id="questionNumber"
              class="progress-num"
            >
              01 / 18
            </div>

          </div>


          <div class="progress">
            <i
              id="progressBar"
              style="width:5.55%"
            ></i>
          </div>


          <div class="question-number">
            MANTIQIY PUZZLE
          </div>


          <h2 id="questionText"></h2>


          <div
            id="puzzle"
            class="visual-puzzle"
            style="display:none"
          ></div>


          <div
            id="answers"
            class="options"
          ></div>


          <button
            id="nextButton"
            class="primary"
            type="button"
            disabled
          >
            ${t("next")}
            <span>›</span>
          </button>

        </section>


        <!-- RESULT -->

        <section
          id="resultScreen"
          class="screen result"
          style="display:none"
        >

          <div class="result-icon">
            🧠
          </div>

          <div class="eyebrow">
            ${t("result")}
          </div>


          <div
            id="iqScore"
            class="score"
          >
            —
          </div>

          <div class="score-label">
            IQ SCORE
          </div>


          <div class="result-card">

            <span>
              ${t("correct")}
            </span>

            <strong id="correctCount">
              — / 18
            </strong>

          </div>


          <div class="metrics">

            <div>
              <span>⏱</span>
              <b id="resultTime">00:00</b>
              <small>${t("time")}</small>
            </div>

            <div>
              <span>🏆</span>
              <b id="resultRank">—</b>
              <small>Reyting</small>
            </div>

            <div>
              <span>🧠</span>
              <b id="resultRaw">—</b>
              <small>Score</small>
            </div>

          </div>


          <button
            id="certificateButton"
            class="primary"
            type="button"
          >
            ${t("certificate")}
          </button>


          <button
            id="shareButton"
            class="secondary"
            type="button"
          >
            ${t("share")}
          </button>


          <button
            id="homeButton"
            class="ghost"
            type="button"
          >
            ${t("home")}
          </button>

        </section>


        <!-- RANKING -->

        <section
          id="rankingScreen"
          class="screen full"
          style="display:none"
        >

          <button
            id="rankingBack"
            class="back"
            type="button"
          >
            ${t("back")}
          </button>

          <h1>
            ${t("ranking")}
          </h1>

          <p>
            Eng yaxshi natijalar
          </p>

          <div id="rankingList"></div>

        </section>


        <!-- PROFILE -->

        <section
          id="profileScreen"
          class="screen profile"
          style="display:none"
        >

          <button
            id="profileBack"
            class="back"
            type="button"
          >
            ${t("back")}
          </button>


          <div
            id="profileAvatar"
            class="result-icon"
          >
            ?
          </div>


          <h1 id="profileName">
            —
          </h1>


          <p>
            IQ statistikangiz
          </p>


          <div class="full-card">

            <div>
              <span>Eng yaxshi IQ</span>
              <strong id="bestIQ">—</strong>
            </div>

            <div>
              <span>Reyting</span>
              <strong id="profileRank">—</strong>
            </div>

            <div>
              <span>Testlar</span>
              <strong id="profileAttempts">0</strong>
            </div>

            <div>
              <span>Takliflar</span>
              <strong id="profileReferrals">0</strong>
            </div>

          </div>

        </section>


        <!-- LANGUAGE -->

        <div
          id="languageModal"
          style="
            display:none;
            position:fixed;
            inset:0;
            z-index:9999;
            background:rgba(0,0,0,.72);
            padding:28vh 20px 0;
          "
        >

          <div
            style="
              max-width:420px;
              margin:auto;
              background:#171a29;
              border:1px solid #353b56;
              border-radius:24px;
              padding:20px;
            "
          >

            <h3>
              Tilni tanlang
            </h3>

            <button
              class="secondary language-option"
              data-language="uz"
              type="button"
            >
              🇺🇿 O‘zbekcha
            </button>

            <button
              class="secondary language-option"
              data-language="ru"
              type="button"
            >
              🇷🇺 Русский
            </button>

            <button
              class="secondary language-option"
              data-language="en"
              type="button"
            >
              🇬🇧 English
            </button>

          </div>

        </div>


        <div
          id="toast"
          class="toast"
        ></div>

      </main>
    `;
  }


  function showScreen(id) {
    const screens = [
      "homeScreen",
      "testScreen",
      "resultScreen",
      "rankingScreen",
      "profileScreen"
    ];

    screens.forEach(screen => {
      const element = $(screen);

      if (!element) return;

      element.style.display =
        screen === id ? "block" : "none";
    });

    try {
      window.scrollTo({
        top: 0,
        behavior: "instant"
      });
    } catch {
      window.scrollTo(0, 0);
    }
  }


  function showToast(message) {
    const element = $("toast");

    if (!element) return;

    element.textContent = String(message || "");

    element.classList.add("show");

    clearTimeout(showToast.timer);

    showToast.timer = setTimeout(() => {
      element.classList.remove("show");
    }, 2800);
  }


  /*
   * =========================================================
   * HOME
   * =========================================================
   */

  function renderHome() {
    stopTimer();

    state.session = null;
    state.result = null;
    state.finishing = false;

    showScreen("homeScreen");

    $("startButton").onclick = startTest;
    $("rankingButton").onclick = loadRanking;
    $("profileButton").onclick = loadProfile;
    $("languageButton").onclick = openLanguageModal;
  }


  /*
   * =========================================================
   * LANGUAGE
   * =========================================================
   */

  function openLanguageModal() {
    const modal = $("languageModal");

    if (!modal) return;

    modal.style.display = "block";
  }


  function bindLanguages() {
    document
      .querySelectorAll(".language-option")
      .forEach(button => {

        button.onclick = () => {

          const language =
            button.dataset.language;

          if (!TEXT[language]) return;

          state.lang = language;

          localStorage.setItem(
            "iq_lang",
            language
          );

          $("languageModal").style.display =
            "none";

          buildUI();
          bindLanguages();
          renderHome();
        };

      });
  }


  /*
   * =========================================================
   * TEST START
   * =========================================================
   */

  async function startTest() {

    if (state.busy || state.finishing) {
      return;
    }

    state.busy = true;

    showToast(t("loading"));

    try {

      const local = loadSession();

      /*
       * If Telegram network disappears after
       * the test has already started, continue
       * from localStorage.
       */

      if (
        local &&
        local.answers.length < COUNT &&
        navigator.onLine === false
      ) {

        state.session = {
          index:
            Number(local.index) ||
            local.answers.length,

          answers:
            local.answers.slice(),

          elapsed:
            Number(local.elapsed) || 0
        };

        state.started =
          Number(local.started) ||
          (
            Date.now() -
            state.session.elapsed * 1000
          );

        renderQuestion();

        return;
      }


      const data = await api(
        "/api/session/start",
        {
          method: "POST",

          body: JSON.stringify({
            language: state.lang
          })
        }
      );


      state.session = {
        index:
          Number(data.index) || 0,

        answers:
          Array.isArray(data.answers)
            ? data.answers.slice(0, COUNT)
            : [],

        elapsed:
          Number(data.elapsed) || 0
      };


      state.started =
        Date.now() -
        state.session.elapsed * 1000;


      saveSession();

      renderQuestion();

    } catch (error) {

      console.error(
        "[IQTestPro] start error",
        error
      );

      if (
        error.status === 402 ||
        error.code === "PAID_RETEST"
      ) {

        showToast(t("paid"));

      } else if (
        error.code === "INVALID_INIT_DATA"
      ) {

        showToast(
          "Ilovani Telegram ichidan oching."
        );

      } else {

        showToast(t("error"));

      }

    } finally {

      state.busy = false;

    }
  }


  /*
   * =========================================================
   * QUESTION
   * =========================================================
   */

  function renderQuestion() {

    if (!state.session) {
      return;
    }

    const index =
      Number(state.session.index);


    if (index >= COUNT) {
      finishTest();
      return;
    }


    const question =
      QUESTIONS[index];


    if (!question) {
      showToast(t("error"));
      return;
    }


    $("questionNumber").textContent =
      `${String(index + 1).padStart(2, "0")} / ${COUNT}`;


    $("progressBar").style.width =
      `${((index + 1) / COUNT) * 100}%`;


    $("questionText").textContent =
      question[0];


    const answers =
      $("answers");


    answers.innerHTML = "";


    const selected =
      state.session.answers[index];


    question[1].forEach(
      (option, optionIndex) => {

        const button =
          document.createElement("button");

        button.type = "button";

        button.className =
          "option";


        button.innerHTML = `
          <span>
            ${LETTERS[optionIndex]}
          </span>

          <b>
            ${escapeHTML(option)}
          </b>
        `;


        if (
          Number(selected) === optionIndex
        ) {

          button.classList.add(
            "selected"
          );

        }


        button.onclick = () => {
          selectAnswer(optionIndex);
        };


        answers.appendChild(button);

      }
    );


    $("nextButton").disabled =
      !Number.isInteger(
        Number(selected)
      );


    $("nextButton").onclick = () => {

      const answer =
        Number(
          state.session.answers[index]
        );

      if (
        Number.isInteger(answer)
      ) {

        selectAnswer(answer);

      }

    };


    $("timer").textContent =
      formatTime(getElapsed());


    $("backButton").onclick = () => {

      const leave =
        window.confirm(
          "Testdan chiqilsinmi? Progress saqlanadi."
        );

      if (leave) {
        renderHome();
      }

    };


    saveSession();

    showScreen("testScreen");

    startTimer();
  }


  function selectAnswer(optionIndex) {

    if (
      !state.session ||
      state.finishing
    ) {
      return;
    }


    const index =
      Number(state.session.index);


    if (
      !Number.isInteger(optionIndex) ||
      optionIndex < 0 ||
      optionIndex > 3
    ) {
      return;
    }


    state.session.answers[index] =
      optionIndex;


    state.session.index =
      index + 1;


    state.session.elapsed =
      getElapsed();


    saveSession();


    if (
      state.session.index >= COUNT
    ) {

      finishTest();

    } else {

      renderQuestion();

    }
  }


  /*
   * =========================================================
   * TIMER
   * =========================================================
   */

  function startTimer() {

    stopTimer();

    const update = () => {

      if (!state.session) {
        return;
      }

      const timer =
        $("timer");

      if (timer) {
        timer.textContent =
          formatTime(getElapsed());
      }

    };


    update();

    state.timer =
      setInterval(update, 500);
  }


  function stopTimer() {

    if (state.timer) {

      clearInterval(
        state.timer
      );

      state.timer = null;
    }
  }


  /*
   * =========================================================
   * FINISH
   * =========================================================
   */

  async function finishTest() {

    if (
      state.finishing ||
      !state.session
    ) {
      return;
    }


    state.finishing = true;

    stopTimer();


    const answers =
      Array.isArray(
        state.session.answers
      )
        ? state.session.answers.slice(
            0,
            COUNT
          )
        : [];


    if (answers.length !== COUNT) {

      state.finishing = false;

      showToast(t("error"));

      return;
    }


    try {

      /*
       * IMPORTANT:
       *
       * No network request happens
       * during individual questions.
       *
       * All 18 answers are sent once
       * at the end.
       */

      await api(
        "/api/session/sync",
        {
          method: "POST",

          body: JSON.stringify({
            answers
          })
        }
      );


      const result =
        await api(
          "/api/session/finish",
          {
            method: "POST",
            body: "{}"
          }
        );


      state.result =
        result;

      state.session =
        null;

      clearSession();

      renderResult();

    } catch (error) {

      console.error(
        "[IQTestPro] finish error",
        error
      );


      state.finishing = false;


      if (
        navigator.onLine === false
      ) {

        showToast(
          t("offline")
        );

      } else {

        showToast(
          t("error")
        );

      }

    } finally {

      state.finishing = false;

    }
  }


  /*
   * =========================================================
   * RESULT
   * =========================================================
   */

  function renderResult() {

    stopTimer();

    showScreen(
      "resultScreen"
    );


    const result =
      state.result || {};


    $("iqScore").textContent =
      result.iq ?? "—";


    $("correctCount").textContent =
      `${result.correct ?? "—"} / ${COUNT}`;


    $("resultTime").textContent =
      formatTime(
        result.elapsed ?? 0
      );


    $("resultRank").textContent =
      result.rank == null
        ? "—"
        : `#${result.rank}`;


    $("resultRaw").textContent =
      result.raw ?? "—";


    $("certificateButton").onclick =
      getCertificate;


    $("shareButton").onclick =
      shareResult;


    $("homeButton").onclick =
      renderHome;
  }


  /*
   * =========================================================
   * RANKING
   * =========================================================
   */

  async function loadRanking() {

    showScreen(
      "rankingScreen"
    );


    $("rankingBack").onclick =
      renderHome;


    const list =
      $("rankingList");


    list.innerHTML =
      "<p>Yuklanmoqda…</p>";


    try {

      const data =
        await api(
          "/api/ranking",
          {
            method: "GET"
          }
        );


      const items =
        Array.isArray(data.items)
          ? data.items
          : [];


      if (!items.length) {

        list.innerHTML =
          "<p>Hali reyting ma’lumotlari yo‘q.</p>";

        return;
      }


      list.innerHTML =
        items
          .map(
            (item, index) => {

              const name =
                escapeHTML(
                  item.first_name ||
                  item.username ||
                  "User"
                );


              const score =
                escapeHTML(
                  item.best_score ??
                  "—"
                );


              return `
                <div class="result-card">

                  <span>
                    #${index + 1}
                    ${name}
                  </span>

                  <strong>
                    ${score}
                  </strong>

                </div>
              `;

            }
          )
          .join("");

    } catch (error) {

      console.error(
        "[IQTestPro] ranking error",
        error
      );

      list.innerHTML =
        "<p>Reytingni yuklab bo‘lmadi.</p>";
    }
  }


  /*
   * =========================================================
   * PROFILE
   * =========================================================
   */

  async function loadProfile() {

    showScreen(
      "profileScreen"
    );


    $("profileBack").onclick =
      renderHome;


    try {

      const data =
        await api(
          "/api/profile",
          {
            method: "GET"
          }
        );


      const name =
        data.first_name ||
        data.username ||
        "User";


      $("profileName").textContent =
        name;


      $("profileAvatar").textContent =
        name
          .trim()
          .charAt(0)
          .toUpperCase() ||
        "?";


      $("bestIQ").textContent =
        data.best_score ??
        "—";


      $("profileRank").textContent =
        data.rank == null
          ? "—"
          : `#${data.rank}`;


      $("profileAttempts").textContent =
        data.attempts ??
        0;


      $("profileReferrals").textContent =
        data.referrals ??
        0;

    } catch (error) {

      console.error(
        "[IQTestPro] profile error",
        error
      );

      showToast(
        t("noData")
      );
    }
  }


  /*
   * =========================================================
   * CERTIFICATE
   * =========================================================
   */

  async function getCertificate() {

    try {

      const response =
        await fetch(
          "/api/certificate",
          {
            method: "GET",
            cache: "no-store",

            headers: {
              "X-Telegram-Init-Data":
                getInitData()
            }
          }
        );


      if (!response.ok) {

        showToast(
          "Sertifikat hozircha mavjud emas."
        );

        return;
      }


      const blob =
        await response.blob();


      const url =
        URL.createObjectURL(blob);


      const overlay =
        document.createElement(
          "div"
        );


      overlay.style.cssText = `
        position:fixed;
        inset:0;
        z-index:99999;
        background:rgba(0,0,0,.94);
        padding:20px;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        gap:15px;
      `;


      overlay.innerHTML = `
        <img
          src="${url}"
          alt="Certificate"
          style="
            max-width:100%;
            max-height:80vh;
            border-radius:18px;
            object-fit:contain;
          "
        >

        <button
          class="primary"
          type="button"
          style="max-width:520px"
        >
          ${t("back")}
        </button>
      `;


      overlay
        .querySelector("button")
        .onclick = () => {

          URL.revokeObjectURL(
            url
          );

          overlay.remove();
        };


      document.body.appendChild(
        overlay
      );

    } catch (error) {

      console.error(
        "[IQTestPro] certificate error",
        error
      );

      showToast(
        "Sertifikatni olishda xatolik."
      );
    }
  }


  /*
   * =========================================================
   * SHARE
   * =========================================================
   */

  function shareResult() {

    if (!state.result) {
      return;
    }


    const text =
      `🧠 IQTestPro\n` +
      `IQ SCORE: ${state.result.iq ?? "—"}\n` +
      `${state.result.correct ?? "—"}/${COUNT}`;


    const url =
      `${location.origin}/app`;


    const telegramURL =
      `https://t.me/share/url?` +
      `url=${encodeURIComponent(url)}` +
      `&text=${encodeURIComponent(text)}`;


    try {

      if (tg?.openTelegramLink) {

        tg.openTelegramLink(
          telegramURL
        );

        return;
      }


      if (navigator.share) {

        navigator.share({
          text,
          url
        }).catch(() => {});

        return;
      }


      if (
        navigator.clipboard?.writeText
      ) {

        navigator.clipboard
          .writeText(text)
          .then(() => {
            showToast(
              "Natija nusxalandi."
            );
          });

      }

    } catch (error) {

      console.error(
        "[IQTestPro] share error",
        error
      );

    }
  }


  /*
   * =========================================================
   * BOOT
   * =========================================================
   */

  function bindEvents() {

    bindLanguages();

    $("languageButton").onclick =
      openLanguageModal;

    $("startButton").onclick =
      startTest;

    $("rankingButton").onclick =
      loadRanking;

    $("profileButton").onclick =
      loadProfile;
  }


  function boot() {

    telegramReady();

    buildUI();

    bindEvents();

    renderHome();

    console.log(
      "[IQTestPro] 18-question app loaded"
    );
  }


  window.addEventListener(
    "online",
    () => {

      if (
        state.session &&
        Array.isArray(
          state.session.answers
        ) &&
        state.session.answers.length === COUNT &&
        !state.finishing
      ) {

        finishTest();

      }

    }
  );


  window.IQTestPro = {
    state,
    startTest,
    finishTest,
    renderHome
  };


  if (
    document.readyState ===
    "loading"
  ) {

    document.addEventListener(
      "DOMContentLoaded",
      boot,
      { once: true }
    );

  } else {

    boot();

  }

})();