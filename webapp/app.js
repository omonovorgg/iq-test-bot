(() => {
  "use strict";

  const tg = window.Telegram?.WebApp;

  if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#0a0e1a");
    tg.setBackgroundColor("#0a0e1a");
  }

  const $ = (id) => document.getElementById(id);

  const state = {
    bootstrap: null,
    profile: null,
    test: null,
    questions: [],
    answers: [],
    current: 0,
    selected: null,
    timer: null,
    secondsLeft: 30 * 60,
    testType: "IQ",
    lastResult: null,
    battle: null
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

  function showScreen(id) {
    screens.forEach((name) => {
      const el = $(name);
      if (el) el.classList.toggle("hidden", name !== id);
    });

    window.scrollTo({
      top: 0,
      behavior: "instant"
    });
  }

  function toast(message, duration = 2800) {
    const el = $("toast");
    if (!el) return;

    el.textContent = message;
    el.classList.add("show");

    clearTimeout(toast.timer);

    toast.timer = setTimeout(() => {
      el.classList.remove("show");
    }, duration);
  }

  function haptic(type = "light") {
    try {
      if (!tg?.HapticFeedback) return;

      if (type === "success") {
        tg.HapticFeedback.notificationOccurred("success");
      } else if (type === "error") {
        tg.HapticFeedback.notificationOccurred("error");
      } else {
        tg.HapticFeedback.impactOccurred("light");
      }
    } catch (_) {}
  }

  function initData() {
    return tg?.initData || "";
  }

  async function api(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData(),
      ...(options.headers || {})
    };

    const response = await fetch(path, {
      ...options,
      headers
    });

    let data = null;

    try {
      data = await response.json();
    } catch (_) {
      throw new Error("Server noto‘g‘ri javob qaytardi.");
    }

    if (!response.ok || data?.ok === false) {
      throw new Error(
        data?.error ||
        data?.message ||
        `Server xatosi: ${response.status}`
      );
    }

    return data;
  }

  function telegramUser() {
    try {
      return tg?.initDataUnsafe?.user || {};
    } catch (_) {
      return {};
    }
  }

  function formatNumber(value) {
    return Number(value || 0).toLocaleString("uz-UZ");
  }

  function money(value) {
    return `${formatNumber(value)} so‘m`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderUser() {
    const user = state.bootstrap?.user || telegramUser();

    const name =
      user?.first_name ||
      state.profile?.full_name?.split(" ")[0] ||
      "Do‘st";

    $("userName").textContent = name;

    if (state.profile) {
      $("fullName").value =
        state.profile.full_name || "";

      $("gender").value =
        state.profile.gender || "";

      $("age").value =
        state.profile.age || "";

      $("country").value =
        state.profile.country || "";
    }
  }

  function updateUnlocks() {
    const hasIQ = Boolean(state.bootstrap?.hasIQ);
    const hasEQ = Boolean(state.bootstrap?.hasEQ);
    const hasPQ = Boolean(state.bootstrap?.hasPQ);

    const eq = document.querySelector('[data-test="EQ"]');
    const pq = document.querySelector('[data-test="PQ"]');
    const profileCard = $("profileCard");

    if (eq) {
      eq.classList.toggle("locked", !hasIQ);

      const text = eq.querySelector("small");

      if (text) {
        text.textContent = hasIQ
          ? "6 vaziyatli savol"
          : "IQdan keyin ochiladi";
      }
    }

    if (pq) {
      pq.classList.toggle("locked", !hasEQ);

      const text = pq.querySelector("small");

      if (text) {
        text.textContent = hasEQ
          ? "6 xulq-atvor savoli"
          : "EQdan keyin ochiladi";
      }
    }

    if (profileCard) {
      const unlocked = hasIQ && hasEQ && hasPQ;

      profileCard.classList.toggle(
        "locked",
        !unlocked
      );

      const text = profileCard.querySelector("small");

      if (text) {
        text.textContent = unlocked
          ? "Shaxsiy tahlilingiz"
          : "IQ + EQ + PQdan keyin";
      }
    }
  }

  async function bootstrap() {
    try {
      const data = await api("/api/bootstrap");

      state.bootstrap = data;
      state.profile = data.profile || null;

      renderUser();
      updateUnlocks();
      showScreen("homeScreen");

      loadLiveStats();

    } catch (error) {
      console.error(error);

      showScreen("homeScreen");

      toast(
        error.message ||
        "Ma’lumotlarni yuklashda xatolik."
      );
    }
  }

  async function loadLiveStats() {
    try {
      const data = await api("/api/stats/live");

      $("liveTotal").textContent =
        formatNumber(data.total);

      $("liveOnline").textContent =
        formatNumber(data.online);

    } catch (_) {
      $("liveTotal").textContent = "—";
      $("liveOnline").textContent = "—";
    }
  }

  setInterval(loadLiveStats, 5000);

  function renderMatrixCell(cell) {
    if (!cell) return "";

    if (cell.type === "question") {
      return `
        <div class="matrix-cell question">?</div>
      `;
    }

    const svg = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "svg"
    );

    svg.setAttribute("viewBox", "0 0 44 44");

    const group = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "g"
    );

    const stroke = "#dce3f7";
    const fill = "#a78bfa";

    if (cell.type === "dot") {
      const count = Math.max(
        1,
        Math.min(9, Number(cell.count || 1))
      );

      const positions = [
        [13, 13],
        [22, 13],
        [31, 13],
        [13, 22],
        [22, 22],
        [31, 22],
        [13, 31],
        [22, 31],
        [31, 31]
      ];

      for (let i = 0; i < count; i++) {
        const c = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "circle"
        );

        c.setAttribute("cx", positions[i][0]);
        c.setAttribute("cy", positions[i][1]);
        c.setAttribute("r", "3");
        c.setAttribute("fill", fill);

        group.appendChild(c);
      }
    }

    else if (cell.type === "shape") {
      const shape = cell.shape || "circle";
      const isEmpty = cell.fill === "empty";

      if (shape === "square") {
        const r = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "rect"
        );

        r.setAttribute("x", "11");
        r.setAttribute("y", "11");
        r.setAttribute("width", "22");
        r.setAttribute("height", "22");
        r.setAttribute(
          "fill",
          isEmpty ? "none" : fill
        );
        r.setAttribute("stroke", stroke);
        r.setAttribute("stroke-width", "2");

        group.appendChild(r);
      }

      else if (shape === "triangle") {
        const p = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "polygon"
        );

        p.setAttribute(
          "points",
          "22,8 36,34 8,34"
        );

        p.setAttribute(
          "fill",
          isEmpty ? "none" : fill
        );

        p.setAttribute("stroke", stroke);
        p.setAttribute("stroke-width", "2");

        group.appendChild(p);
      }

      else {
        const c = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "circle"
        );

        c.setAttribute("cx", "22");
        c.setAttribute("cy", "22");
        c.setAttribute("r", "12");
        c.setAttribute(
          "fill",
          isEmpty ? "none" : fill
        );
        c.setAttribute("stroke", stroke);
        c.setAttribute("stroke-width", "2");

        group.appendChild(c);
      }
    }

    else if (cell.type === "rotate") {
      const angle = Number(cell.angle || 0);

      const p = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "polygon"
      );

      p.setAttribute(
        "points",
        "22,6 36,22 22,38 8,22"
      );

      p.setAttribute(
        "fill",
        cell.fill === "empty"
          ? "none"
          : fill
      );

      p.setAttribute("stroke", stroke);
      p.setAttribute("stroke-width", "2");
      p.setAttribute(
        "transform",
        `rotate(${angle} 22 22)`
      );

      group.appendChild(p);
    }

    else if (cell.type === "size") {
      const sizeMap = {
        small: 7,
        medium: 12,
        large: 17
      };

      const radius =
        sizeMap[cell.size] || 12;

      const c = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle"
      );

      c.setAttribute("cx", "22");
      c.setAttribute("cy", "22");
      c.setAttribute("r", radius);
      c.setAttribute("fill", fill);
      c.setAttribute("stroke", stroke);
      c.setAttribute("stroke-width", "1.5");

      group.appendChild(c);
    }

    else if (cell.type === "grid") {
      const pos = cell.pos || "center";

      const positions = {
        tl: [8, 8],
        tc: [22, 8],
        tr: [36, 8],
        ml: [8, 22],
        center: [22, 22],
        mr: [36, 22],
        bl: [8, 36],
        bc: [22, 36],
        br: [36, 36]
      };

      const [x, y] =
        positions[pos] ||
        positions.center;

      const c = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle"
      );

      c.setAttribute("cx", x);
      c.setAttribute("cy", y);
      c.setAttribute("r", "5");
      c.setAttribute("fill", fill);

      group.appendChild(c);
    }

    else if (cell.type === "num") {
      const text =
        document.createElementNS(
          "http://www.w3.org/2000/svg",
          "text"
        );

      text.setAttribute("x", "22");
      text.setAttribute("y", "29");
      text.setAttribute(
        "text-anchor",
        "middle"
      );
      text.setAttribute(
        "font-size",
        "18"
      );
      text.setAttribute(
        "font-family",
        "Inter, sans-serif"
      );
      text.setAttribute(
        "font-weight",
        "800"
      );
      text.setAttribute(
        "fill",
        "#dce3f7"
      );

      text.textContent =
        String(cell.val ?? "");

      group.appendChild(text);
    }

    else if (cell.type === "combo") {
      const shapes =
        Array.isArray(cell.shapes)
          ? cell.shapes
          : [];

      shapes.slice(0, 3).forEach(
        (shape, index) => {
          const offset =
            (index - 1) * 9;

          if (shape === "circle") {
            const c =
              document.createElementNS(
                "http://www.w3.org/2000/svg",
                "circle"
              );

            c.setAttribute(
              "cx",
              String(22 + offset)
            );

            c.setAttribute("cy", "22");
            c.setAttribute("r", "7");
            c.setAttribute(
              "fill",
              cell.fill === "empty"
                ? "none"
                : fill
            );
            c.setAttribute(
              "stroke",
              stroke
            );

            group.appendChild(c);
          }

          if (shape === "square") {
            const r =
              document.createElementNS(
                "http://www.w3.org/2000/svg",
                "rect"
              );

            r.setAttribute(
              "x",
              String(15 + offset)
            );

            r.setAttribute("y", "15");
            r.setAttribute("width", "14");
            r.setAttribute("height", "14");
            r.setAttribute(
              "fill",
              cell.fill === "empty"
                ? "none"
                : fill
            );
            r.setAttribute(
              "stroke",
              stroke
            );

            group.appendChild(r);
          }
        }
      );
    }

    svg.appendChild(group);

    return svg.outerHTML;
  }

  function renderQuestion() {
    const question =
      state.questions[state.current];

    if (!question) return;

    const total =
      state.questions.length;

    const number =
      state.current + 1;

    $("questionLabel").textContent =
      `Q${number}`;

    $("difficulty").textContent =
      question.difficulty ||
      (
        number <= 6
          ? "EASY"
          : number <= 12
            ? "MEDIUM"
            : "HARD"
      );

    $("questionText").textContent =
      question.text ||
      "Qaysi variant mantiqiy ravishda yetishmayapti?";

    $("progressBar").style.width =
      `${(number / total) * 100}%`;

    const matrix =
      $("matrix");

    matrix.innerHTML = "";

    const cells =
      Array.isArray(question.matrix)
        ? question.matrix
        : [];

    cells.forEach((cell) => {
      const wrapper =
        document.createElement("div");

      wrapper.className =
        "matrix-cell";

      if (cell?.type === "question") {
        wrapper.classList.add("question");
        wrapper.textContent = "?";
      } else {
        wrapper.innerHTML =
          renderMatrixCell(cell);
      }

      matrix.appendChild(wrapper);
    });

    const options =
      $("options");

    options.innerHTML = "";

    const letters = ["A", "B", "C", "D"];

    const answerOptions =
      Array.isArray(question.options)
        ? question.options
        : [];

    answerOptions.forEach(
      (option, index) => {

        const button =
          document.createElement("button");

        button.className = "option";

        button.innerHTML = `
          <span class="letter">
            ${letters[index]}
          </span>
          ${renderMatrixCell(option)}
        `;

        button.addEventListener(
          "click",
          () => selectAnswer(index)
        );

        options.appendChild(button);
      }
    );

    state.selected =
      state.answers[state.current] ??
      null;

    if (state.selected !== null) {
      const selected =
        options.children[state.selected];

      if (selected) {
        selected.classList.add("selected");
      }

      $("nextQuestion").disabled = false;
    } else {
      $("nextQuestion").disabled = true;
    }

    $("nextQuestion").textContent =
      number === total
        ? "Natijani ko‘rish"
        : "Davom etish";
  }

  function selectAnswer(index) {
    state.selected = index;
    state.answers[state.current] = index;

    [...$("options").children].forEach(
      (element, i) => {
        element.classList.toggle(
          "selected",
          i === index
        );
      }
    );

    $("nextQuestion").disabled = false;

    haptic("light");
  }

  function startTimer() {
    clearInterval(state.timer);

    state.secondsLeft = 30 * 60;

    updateTimer();

    state.timer = setInterval(() => {

      state.secondsLeft--;

      updateTimer();

      if (state.secondsLeft <= 0) {
        clearInterval(state.timer);
        submitTest();
      }

    }, 1000);
  }

  function updateTimer() {
    const min =
      Math.floor(state.secondsLeft / 60)
        .toString()
        .padStart(2, "0");

    const sec =
      (state.secondsLeft % 60)
        .toString()
        .padStart(2, "0");

    $("timer").textContent =
      `${min}:${sec}`;
  }

  function stopTimer() {
    clearInterval(state.timer);
    state.timer = null;
  }

  async function openTest(type) {
    state.testType = type;

    try {
      const data =
        await api(
          `/api/test/start?type=${encodeURIComponent(type)}`
        );

      state.test =
        data.session || data;

      state.questions =
        data.questions || [];

      state.answers =
        new Array(state.questions.length)
          .fill(null);

      state.current = 0;
      state.selected = null;

      if (!state.questions.length) {
        throw new Error(
          "Test savollari topilmadi."
        );
      }

      localStorage.setItem(
        `iqtest_${type}_session`,
        JSON.stringify({
          session_id:
            state.test.session_id ||
            state.test.id ||
            null,
          answers: state.answers,
          current: 0
        })
      );

      showScreen("testScreen");
      renderQuestion();
      startTimer();

    } catch (error) {

      if (
        type !== "IQ" &&
        error.message
          ?.toLowerCase()
          .includes("payment")
      ) {
        await openPayment(type);
        return;
      }

      toast(
        error.message ||
        "Testni ochib bo‘lmadi.",
        3500
      );
    }
  }

  function nextQuestion() {
    if (state.selected === null) {
      toast("Avval javobni tanlang.");
      return;
    }

    const total =
      state.questions.length;

    if (state.current >= total - 1) {
      submitTest();
      return;
    }

    state.current++;
    state.selected =
      state.answers[state.current] ??
      null;

    localStorage.setItem(
      `iqtest_${state.testType}_session`,
      JSON.stringify({
        session_id:
          state.test?.session_id ||
          state.test?.id ||
          null,
        answers: state.answers,
        current: state.current
      })
    );

    renderQuestion();

    window.scrollTo({
      top: 0,
      behavior: "smooth"
    });
  }

  async function submitTest() {
    stopTimer();

    if (!state.test) {
      toast("Test sessiyasi topilmadi.");
      return;
    }

    showScreen("loadingResult");

    try {
      const sessionId =
        state.test.session_id ||
        state.test.id;

      const payload = {
        session_id: sessionId,
        test_type: state.testType,
        answers: state.answers
      };

      const result =
        await api(
          "/api/test/submit",
          {
            method: "POST",
            body: JSON.stringify(payload)
          }
        );

      state.lastResult =
        result.result || result;

      localStorage.removeItem(
        `iqtest_${state.testType}_session`
      );

      if (state.bootstrap) {
        if (state.testType === "IQ") {
          state.bootstrap.hasIQ = true;
        }

        if (state.testType === "EQ") {
          state.bootstrap.hasEQ = true;
        }

        if (state.testType === "PQ") {
          state.bootstrap.hasPQ = true;
        }
      }

      updateUnlocks();
      renderResult();

      haptic("success");

    } catch (error) {

      showScreen("testScreen");

      toast(
        error.message ||
        "Natijani yuborishda xatolik.",
        4000
      );
    }
  }

  function renderResult() {
    const result =
      state.lastResult || {};

    const score =
      result.iq_score ??
      result.score ??
      result.percentage ??
      0;

    $("resultScore").textContent =
      Math.round(Number(score));

    $("resultLevel").textContent =
      result.level ||
      "Natija";

    $("resultCorrect").textContent =
      result.correct != null
        ? `${result.correct} / ${result.total || state.questions.length} to‘g‘ri javob`
        : result.description ||
          "Natijangiz saqlandi.";

    showScreen("resultScreen");
  }

  async function openPayment(type) {
    try {
      const data =
        await api(
          `/api/payment/info?type=${encodeURIComponent(type)}`
        );

      const card =
        data.card || {};

      const price =
        data.price || 0;

      $("paymentAmount").textContent =
        money(price);

      $("cardNumber").textContent =
        card.number ||
        "Karta mavjud emas";

      $("cardHolder").textContent =
        card.holder || "";

      $("cardBank").textContent =
        card.bank || "";

      $("paymentStatus").textContent =
        data.status
          ? `Status: ${data.status}`
          : "";

      showScreen("paymentScreen");

    } catch (error) {
      toast(
        error.message ||
        "To‘lov ma’lumotlarini olishda xatolik."
      );
    }
  }

  async function sendReceipt() {
    const receipt =
      $("receiptInput").value.trim();

    if (!receipt) {
      toast("Receipt file_id kiriting.");
      return;
    }

    const button =
      $("sendReceipt");

    button.disabled = true;
    button.textContent =
      "Yuborilmoqda…";

    try {

      const data =
        await api(
          "/api/payment/submit",
          {
            method: "POST",
            body: JSON.stringify({
              test_type:
                state.testType,
              receipt
            })
          }
        );

      $("paymentStatus").textContent =
        data.message ||
        "To‘lov admin tekshiruviga yuborildi.";

      toast(
        "To‘lov yuborildi.",
        3000
      );

    } catch (error) {

      toast(
        error.message ||
        "Receipt yuborilmadi.",
        3500
      );

    } finally {

      button.disabled = false;
      button.textContent =
        "Receipt yuborish";
    }
  }

  async function saveProfile() {
    const fullName =
      $("fullName").value.trim();

    const gender =
      $("gender").value;

    const age =
      Number($("age").value);

    const country =
      $("country").value;

    if (!fullName) {
      toast("Ism va familiyani kiriting.");
      return;
    }

    if (!gender) {
      toast("Jinsni tanlang.");
      return;
    }

    if (!age || age < 10 || age > 120) {
      toast("Yoshni to‘g‘ri kiriting.");
      return;
    }

    if (!country) {
      toast("Davlatni tanlang.");
      return;
    }

    const button =
      $("saveProfile");

    button.disabled = true;
    button.textContent =
      "Saqlanmoqda…";

    try {

      const data =
        await api(
          "/api/profile/save",
          {
            method: "POST",
            body: JSON.stringify({
              full_name: fullName,
              gender,
              age,
              country
            })
          }
        );

      state.profile =
        data.profile || {
          full_name: fullName,
          gender,
          age,
          country
        };

      renderUser();

      toast(
        "Profil saqlandi.",
        2500
      );

      showScreen("homeScreen");

    } catch (error) {

      toast(
        error.message ||
        "Profil saqlanmadi.",
        3500
      );

    } finally {

      button.disabled = false;
      button.textContent =
        "Saqlash";
    }
  }

  async function openRanking() {
    showScreen("rankingScreen");

    const list =
      $("rankingList");

    list.innerHTML = `
      <div class="glass" style="
        padding:30px;
        text-align:center;
        border-radius:20px
      ">
        Yuklanmoqda…
      </div>
    `;

    try {

      const data =
        await api("/api/ranking");

      const rows =
        data.ranking ||
        data.results ||
        data.users ||
        [];

      if (!rows.length) {
        list.innerHTML = `
          <div class="glass" style="
            padding:30px;
            text-align:center;
            border-radius:20px
          ">
            Hozircha reyting bo‘sh.
          </div>
        `;
        return;
      }

      list.innerHTML = rows
        .map((row, index) => {

          const position =
            row.position ||
            index + 1;

          const name =
            row.full_name ||
            row.name ||
            "Foydalanuvchi";

          const score =
            row.iq_score ??
            row.score ??
            0;

          return `
            <div class="rank-row">
              <span class="rank-pos">
                #${position}
              </span>

              <div>
                <b>
                  ${escapeHtml(name)}
                </b>

                <small>
                  IQ natijasi
                </small>
              </div>

              <strong>
                ${escapeHtml(score)}
              </strong>
            </div>
          `;
        })
        .join("");

    } catch (error) {

      list.innerHTML = `
        <div class="glass" style="
          padding:30px;
          text-align:center;
          border-radius:20px
        ">
          Reytingni yuklab bo‘lmadi.
        </div>
      `;

      toast(
        error.message ||
        "Reyting xatosi."
      );
    }
  }

  async function openCertificate() {
    showScreen("certificateScreen");

    const box =
      $("certificateBox");

    box.innerHTML = `
      <div style="padding:30px">
        Yuklanmoqda…
      </div>
    `;

    try {

      const data =
        await api("/api/certificate");

      const certificate =
        data.certificate ||
        data;

      if (!certificate ||
          !certificate.verification_code) {

        box.innerHTML = `
          <div>
            <div style="font-size:50px">
              📜
            </div>

            <h3>
              Sertifikat hali mavjud emas
            </h3>

            <p style="
              color:#8993ad;
              font-size:12px
            ">
              Avval IQ testini yakunlang.
            </p>
          </div>
        `;

        return;
      }

      box.innerHTML = `
        <div style="font-size:50px">
          🧠
        </div>

        <span class="pill">
          IQ TEST BOT
        </span>

        <h2>
          SERTIFIKAT
        </h2>

        <p>
          AQLLIY SALOHIYAT TO‘G‘RISIDA
        </p>

        <h3>
          ${escapeHtml(
            certificate.full_name || ""
          )}
        </h3>

        <p>
          IQ:
          <strong>
            ${escapeHtml(
              certificate.score ??
              certificate.iq_score ??
              ""
            )}
          </strong>
        </p>

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

        <button
          id="openCertificateBot"
          class="primary"
        >
          Telegramda ochish
        </button>
      `;

      $("openCertificateBot")
        ?.addEventListener(
          "click",
          () => {
            if (tg?.openTelegramLink &&
                certificate.telegram_url) {

              tg.openTelegramLink(
                certificate.telegram_url
              );

            } else if (
              certificate.telegram_url
            ) {

              window.open(
                certificate.telegram_url,
                "_blank"
              );
            }
          }
        );

    } catch (error) {

      box.innerHTML = `
        <div>
          Sertifikatni yuklab bo‘lmadi.
        </div>
      `;

      toast(
        error.message ||
        "Sertifikat xatosi."
      );
    }
  }

  async function createBattle() {
    const button =
      $("createBattle");

    button.disabled = true;
    button.textContent =
      "Yaratilmoqda…";

    try {

      const data =
        await api(
          "/api/battle/create",
          {
            method: "POST",
            body: JSON.stringify({})
          }
        );

      state.battle =
        data.battle || data;

      renderBattle();

      haptic("success");

    } catch (error) {

      toast(
        error.message ||
        "Battle yaratilmadi.",
        3500
      );

    } finally {

      button.disabled = false;
      button.textContent =
        "Battle yaratish";
    }
  }

  async function joinBattle() {
    const code =
      $("battleCode")
        .value
        .trim()
        .toUpperCase();

    if (!/^[A-Z0-9]{4}$/.test(code)) {
      toast(
        "4 belgili battle kodini kiriting."
      );
      return;
    }

    const button =
      $("joinBattle");

    button.disabled = true;
    button.textContent =
      "Qo‘shilmoqda…";

    try {

      const data =
        await api(
          "/api/battle/join",
          {
            method: "POST",
            body: JSON.stringify({
              code
            })
          }
        );

      state.battle =
        data.battle || data;

      renderBattle();

      haptic("success");

    } catch (error) {

      toast(
        error.message ||
        "Battlega qo‘shilib bo‘lmadi.",
        3500
      );

    } finally {

      button.disabled = false;
      button.textContent =
        "Kod bilan kirish";
    }
  }

  function renderBattle() {
    const info =
      $("battleInfo");

    const battle =
      state.battle || {};

    const code =
      battle.code ||
      battle.battle_code;

    if (!code) {
      info.innerHTML = "";
      return;
    }

    const status =
      battle.status || "waiting";

    info.innerHTML = `
      <div class="glass" style="
        margin-top:16px;
        padding:18px;
        border-radius:18px;
        text-align:center
      ">

        <small style="
          display:block;
          color:#8993ad
        ">
          Battle kodi
        </small>

        <strong style="
          display:block;
          font-size:34px;
          letter-spacing:.25em;
          margin:8px 0
        ">
          ${escapeHtml(code)}
        </strong>

        <small style="
          color:#9da7c0
        ">
          Status:
          ${escapeHtml(status)}
        </small>

        ${
          status === "ready"
            ? `
              <button
                id="startBattle"
                class="primary"
                style="margin-top:14px"
              >
                Battle boshlash
              </button>
            `
            : `
              <p style="
                color:#8993ad;
                font-size:11px;
                margin:12px 0 0
              ">
                Raqib va to‘lov tasdig‘i kutilmoqda.
              </p>
            `
        }

      </div>
    `;

    $("startBattle")
      ?.addEventListener(
        "click",
        () => {
          startBattleTest();
        }
      );
  }

  async function startBattleTest() {
    if (!state.battle) {
      toast("Battle topilmadi.");
      return;
    }

    try {

      const id =
        state.battle.id ||
        state.battle.battle_id;

      const data =
        await api(
          `/api/battle/start`,
          {
            method: "POST",
            body: JSON.stringify({
              battle_id: id
            })
          }
        );

      state.testType = "BATTLE";

      state.test =
        data.session || data;

      state.questions =
        data.questions || [];

      state.answers =
        new Array(
          state.questions.length
        ).fill(null);

      state.current = 0;
      state.selected = null;

      if (!state.questions.length) {
        throw new Error(
          "Battle savollari topilmadi."
        );
      }

      showScreen("testScreen");
      renderQuestion();
      startTimer();

    } catch (error) {

      toast(
        error.message ||
        "Battle boshlanmadi.",
        3500
      );
    }
  }

  function goBackHome() {
    stopTimer();
    showScreen("homeScreen");
  }

  document.addEventListener(
    "click",
    async (event) => {

      const nav =
        event.target.closest(
          "[data-nav]"
        );

      if (nav) {

        const target =
          nav.dataset.nav;

        if (target === "home") {
          showScreen("homeScreen");
        }

        if (target === "ranking") {
          await openRanking();
        }

        if (target === "certificate") {
          await openCertificate();
        }

        if (target === "profile") {
          renderUser();
          showScreen("profileScreen");
        }

        return;
      }

      const back =
        event.target.closest("[data-back]");

      if (back) {
        goBackHome();
        return;
      }

      const testCard =
        event.target.closest(
          ".test-card[data-test]"
        );

      if (testCard) {

        const type =
          testCard.dataset.test;

        const hasIQ =
          Boolean(state.bootstrap?.hasIQ);

        const hasEQ =
          Boolean(state.bootstrap?.hasEQ);

        if (type === "EQ" && !hasIQ) {
          toast(
            "Avval IQ testini yakunlang."
          );
          return;
        }

        if (
          type === "PQ" &&
          !hasEQ
        ) {
          toast(
            "Avval EQ testini yakunlang."
          );
          return;
        }

        await openTest(type);
        return;
      }
    }
  );

  $("nextQuestion")
    ?.addEventListener(
      "click",
      nextQuestion
    );

  $("saveProfile")
    ?.addEventListener(
      "click",
      saveProfile
    );

  $("profileTopBtn")
    ?.addEventListener(
      "click",
      () => {
        renderUser();
        showScreen("profileScreen");
      }
    );

  $("profileCard")
    ?.addEventListener(
      "click",
      () => {

        const unlocked =
          state.bootstrap?.hasIQ &&
          state.bootstrap?.hasEQ &&
          state.bootstrap?.hasPQ;

        if (!unlocked) {
          toast(
            "IQ, EQ va PQ testlarini yakunlang."
          );
          return;
        }

        renderUser();
        showScreen("profileScreen");
      }
    );

  $("battleCard")
    ?.addEventListener(
      "click",
      () => {
        showScreen("battleScreen");
      }
    );

  $("createBattle")
    ?.addEventListener(
      "click",
      createBattle
    );

  $("joinBattle")
    ?.addEventListener(
      "click",
      joinBattle
    );

  $("sendReceipt")
    ?.addEventListener(
      "click",
      sendReceipt
    );

  $("copyCard")
    ?.addEventListener(
      "click",
      async () => {

        const value =
          $("cardNumber")
            .textContent
            .trim();

        if (!value) return;

        try {

          await navigator.clipboard.writeText(
            value
          );

          toast(
            "Karta raqami nusxalandi."
          );

          haptic("success");

        } catch (_) {

          toast(
            "Nusxalash imkoni bo‘lmadi."
          );
        }
      }
    );

  $("sharePayment")
    ?.addEventListener(
      "click",
      () => {

        const username =
          state.bootstrap?.admin_username ||
          "";

        if (username && tg?.openTelegramLink) {
          tg.openTelegramLink(
            `https://t.me/${username}`
          );
        } else {
          toast(
            "Telegram admin havolasi mavjud emas."
          );
        }
      }
    );

  $("certificateBtn")
    ?.addEventListener(
      "click",
      openCertificate
    );

  $("testBack")
    ?.addEventListener(
      "click",
      () => {

        const confirmed =
          window.confirm(
            "Testdan chiqmoqchimisiz? Progress saqlanadi."
          );

        if (confirmed) {
          stopTimer();
          showScreen("homeScreen");
        }
      }
    );

  $("battleCode")
    ?.addEventListener(
      "input",
      (event) => {

        event.target.value =
          event.target.value
            .toUpperCase()
            .replace(/[^A-Z0-9]/g, "")
            .slice(0, 4);
      }
    );

  document.addEventListener(
    "visibilitychange",
    () => {

      if (
        document.visibilityState ===
        "visible"
      ) {
        if (
          state.test &&
          state.questions.length
        ) {
          renderQuestion();
        }

        loadLiveStats();
      }
    }
  );

  window.addEventListener(
    "error",
    (event) => {
      console.error(
        "Frontend error:",
        event.error || event.message
      );
    }
  );

  window.addEventListener(
    "unhandledrejection",
    (event) => {
      console.error(
        "Unhandled promise:",
        event.reason
      );
    }
  );

  bootstrap();

})();