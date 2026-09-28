(() => {
  "use strict";

  const tg = window.Telegram?.WebApp || null;
  if (tg) {
    try { tg.ready(); tg.expand(); } catch (_) {}
  }

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  const setText = (sel, value) => { const el = $(sel); if (el) el.textContent = value; return el; };
  const state = {
    user: null, lang: "uz", prices: {}, questions: [],
    sessionId: null, testType: null, mode: "NORMAL",
    index: 0, answers: {}, selected: null, startedAt: 0,
    attemptId: null, paymentId: null, paymentAttemptId: null,
    battleId: null, battlePolling: null, paymentPolling: null, busy: false,
    profileStats: {}, recovery: null
  };

  const screens = ["loadingScreen","homeScreen","profileScreen","testScreen","loadingResult","paymentScreen","resultScreen","rankingScreen","certificateScreen","battleScreen"];
  const I18N = {
    uz: {
      home_greet:"Salom, {name} 👋", hero_pill:"18 TA MANTIQIY PUZZLE", hero_title:"IQ darajangizni sinab ko‘ring", hero_text:"Diqqat, naqsh va mantiq asosidagi test.", live_total:"Botga qo‘shilganlar", live_now:"Hozir", live_people:"kishi onlayn", tests:"Testlar", sequence:"ketma-ket ochiladi", iq_desc:"18 mantiqiy puzzle", eq_locked:"IQdan keyin ochiladi", eq_open:"Ochilgan", pq_locked:"EQdan keyin ochiladi", profile:"Shaxsiy profil", profile_after:"IQ + EQ + PQdan keyin", battle:"Battle", battle_desc:"Do‘stingiz bilan asynchronous duel", home:"Home", ranking:"Reyting", certificate:"Sertifikat", profile_nav:"Profil",
      profile_title:"Profil", name_label:"Ism / familiya", name_placeholder:"Ismingiz", gender_label:"Jins", select:"Tanlang", male:"O‘g‘il", female:"Qiz", age_label:"Yosh", country_label:"Davlat", save:"Saqlash",
      q_label:"Q", easy:"OSON", medium:"O‘RTA", hard:"QIYIN", battle_label:"BATTLE", matrix_q:"Qaysi variant matritsani to‘ldiradi?", question:"Savol", next:"Davom etish", see_result:"Natijani ko‘rish", loading_result:"Natija tayyorlanmoqda", checked:"✓ Javoblar tekshirildi", scoring:"✓ Ball hisoblanmoqda", profile_updated:"✓ Profil yangilanmoqda",
      payment:"To‘lov", payment_wait:"NATIJA UCHUN TO‘LOV", payment_text:"Natijangiz tayyor. Uni ochish uchun quyidagi to‘lovni amalga oshirib, chekni yuboring.", copy:"Nusxa", open_bot:"Telegram botini ochish", receipt:"To‘lov cheki", choose_file:"Fayl tanlang", send_receipt:"Receipt yuborish", pay_pending:"Receipt yuborildi. Admin tasdig‘i kutilmoqda.", pay_approved:"✅ To‘lov tasdiqlandi. Keyingi bosqich ochildi.", pay_rejected:"❌ To‘lov tasdiqlanmadi. Admin receiptni rad etdi.", pay_waiting:"Receipt kutilmoqda.", next_result:"📊 Natijani ko‘rish", next_battle:"⚔️ Battle’ga o‘tish", home_btn:"🏠 Bosh sahifaga qaytish", retry_receipt:"🔄 Receiptni qayta yuborish", receipt_resend:"Receiptni qayta yuboring.",
      result:"Natija", iq_done:"IQ TEST YAKUNLANDI", eq_done:"EQ TEST YAKUNLANDI", pq_done:"PQ TEST YAKUNLANDI", score_indicator:"Test ko‘rsatkichi", question_stat:"savol", correct:"to‘g‘ri", time:"vaqt", per_question:"s/savol", accuracy:"Aniqlik", rank:"Reytingdagi o‘rningiz", rank_compare:"Natijalar bilan taqqoslash", your_result:"Sizning natijangiz", next_stage:"Keyingi bosqich", eq_open_title:"EQ testi ochildi", eq_open_text:"Emotsional intellekt bo‘yicha testni ham topshirib ko‘ring.", start_eq:"🎭 EQ testini boshlash", pq_open_title:"PQ testi ochildi", pq_open_text:"Rejalashtirish va amaliy fikrlash bo‘yicha testni topshiring.", start_pq:"🧩 PQ testini boshlash", profile_open_title:"Shaxsiy profil ochildi", profile_open_text:"IQ, EQ va PQ natijalaringiz asosida profilingizni ko‘ring.", open_profile:"⭐ Profilni ko‘rish", no_next:"Barcha testlar yakunlandi", certificate_btn:"📄 Sertifikatni olish", share:"↗ Natijani ulashish", retry:"↻  Qayta topshirish", ranking_first:"Birinchi natijangiz", ranking_total:"{n} ta natija ichida", no_ranking:"Reyting hali shakllanmagan",
      test_result_summary:"{correct} ta savolga to‘g‘ri javob berdingiz. Natijangiz {score} va test darajasi “{level}” sifatida hisoblandi.", behavior_summary:"Test natijangiz {score}% ko‘rsatkich bilan yakunlandi.",
      certificate_screen:"Sertifikat", battle_screen:"Battle", battle_title:"⚔️ Asynchronous duel", battle_desc2:"4 belgili kod yarating yoki do‘stingiz kodini kiriting.", create_battle:"Battle yaratish", or:"yoki", join:"Kod bilan kirish", code_placeholder:"AB12", waiting_opponent:"Opponent kutilmoqda…", battle_found:"Battle topildi. Endi o‘z to‘lovingizni yuboring.", start_payment:"To‘lovni boshlash", waiting_payment:"To‘lov kutilmoqda…",
      error_profile:"Profil ma’lumotlarini to‘liq kiriting", error_payment:"Payment topilmadi", error_receipt:"Receipt rasmini tanlang", error_server:"Server javobi juda uzoq davom etdi.", saved:"Profil saqlandi", copied:"Karta nusxalandi", copy_fail:"Nusxalash imkoni bo‘lmadi", receipt_sent:"Receipt yuborildi", approved_toast:"To‘lov tasdiqlandi", test_info_start:"Testni boshlash", test_info_cancel:"Hozir emas", test_info_iq_title:"IQ testi haqida", test_info_eq_title:"EQ testi haqida", test_info_pq_title:"PQ testi haqida", test_info_iq_desc:"18 ta mantiqiy matritsa. Diqqat, naqsh va mantiqiy bog‘lanishlarni tahlil qilasiz.", test_info_eq_desc:"6 ta vaziyatli savol. Hissiy vaziyatlarda qaror va muloqot uslubingizni tekshiradi.", test_info_pq_desc:"6 ta vaziyatli savol. Rejalashtirish va amaliy qaror qabul qilish yondashuvingizni tekshiradi.", test_info_paid_reason:"To‘lov testni ishlab chiqish, server va natijalarni qayta ishlash xarajatlarini qoplashga yordam beradi. Testni yakunlaganingizdan keyin natijani ochish uchun to‘lov kerak bo‘ladi.", test_info_free:"Ushbu test hozir bepul. Testni yakunlaganingizdan so‘ng natijangiz darhol ko‘rsatiladi.",
      personal_wait:"IQ + EQ + PQ testlarini yakunlaganingizdan keyin tahlil shu yerda ochiladi.",
      strengths:"Kuchli tomonlar", development:"Rivojlanish nuqtalari", cert_empty:"Sertifikat yo‘q", cert_empty_text:"IQ testini yakunlang va natija ochilgach sertifikat yaratiladi.", cert_open:"PNG ochish",
    },
    ru: {
      home_greet:"Привет, {name} 👋", hero_pill:"18 ЛОГИЧЕСКИХ ЗАДАЧ", hero_title:"Проверьте свой уровень IQ", hero_text:"Тест на внимание, закономерности и логику.", live_total:"Всего участников", live_now:"Сейчас", live_people:"человек онлайн", tests:"Тесты", sequence:"открываются по порядку", iq_desc:"18 логических задач", eq_locked:"После IQ", eq_open:"Открыт", pq_locked:"После EQ", profile:"Личный профиль", profile_after:"После IQ + EQ + PQ", battle:"Battle", battle_desc:"Асинхронная дуэль с другом", home:"Главная", ranking:"Рейтинг", certificate:"Сертификат", profile_nav:"Профиль",
      profile_title:"Профиль", name_label:"Имя / фамилия", name_placeholder:"Ваше имя", gender_label:"Пол", select:"Выберите", male:"Мужской", female:"Женский", age_label:"Возраст", country_label:"Страна", save:"Сохранить",
      q_label:"В", easy:"ЛЕГКО", medium:"СРЕДНЕ", hard:"СЛОЖНО", battle_label:"BATTLE", matrix_q:"Какой вариант заполнит матрицу?", question:"Вопрос", next:"Продолжить", see_result:"Посмотреть результат", loading_result:"Готовим результат", checked:"✓ Ответы проверены", scoring:"✓ Баллы рассчитаны", profile_updated:"✓ Профиль обновлён",
      payment:"Оплата", payment_wait:"ОПЛАТА ДЛЯ ОТКРЫТИЯ РЕЗУЛЬТАТА", payment_text:"Ваш результат готов. Чтобы открыть его, выполните оплату ниже и отправьте чек.", copy:"Копировать", open_bot:"Открыть Telegram-бота", receipt:"Чек оплаты", choose_file:"Выбрать файл", send_receipt:"Отправить чек", pay_pending:"Чек отправлен. Ожидается подтверждение администратора.", pay_approved:"✅ Оплата подтверждена. Следующий этап открыт.", pay_rejected:"❌ Оплата не подтверждена. Администратор отклонил чек.", pay_waiting:"Ожидается чек.", next_result:"📊 Посмотреть результат", next_battle:"⚔️ Перейти в Battle", home_btn:"🏠 На главную", retry_receipt:"🔄 Отправить чек снова", receipt_resend:"Отправьте чек повторно.",
      result:"Результат", iq_done:"IQ ТЕСТ ЗАВЕРШЁН", eq_done:"EQ ТЕСТ ЗАВЕРШЁН", pq_done:"PQ ТЕСТ ЗАВЕРШЁН", score_indicator:"Показатель теста", question_stat:"вопросов", correct:"верно", time:"время", per_question:"сек/вопрос", accuracy:"Точность", rank:"Место в рейтинге", rank_compare:"Сравнение с результатами", your_result:"Ваш результат", next_stage:"Следующий этап", eq_open_title:"EQ тест открыт", eq_open_text:"Проверьте также свой эмоциональный интеллект.", start_eq:"🎭 Начать EQ тест", pq_open_title:"PQ тест открыт", pq_open_text:"Пройдите тест на планирование и практическое мышление.", start_pq:"🧩 Начать PQ тест", profile_open_title:"Личный профиль открыт", profile_open_text:"Посмотрите профиль на основе результатов IQ, EQ и PQ.", open_profile:"⭐ Открыть профиль", no_next:"Все тесты завершены", certificate_btn:"📄 Получить сертификат", share:"↗ Поделиться результатом", retry:"↻  Пройти ещё раз", ranking_first:"Ваш первый результат", ranking_total:"Среди {n} результатов", no_ranking:"Рейтинг пока не сформирован",
      test_result_summary:"Вы ответили правильно на {correct} вопросов. Ваш результат — {score}, уровень теста — «{level}».", behavior_summary:"Результат теста завершён с показателем {score}%.",
      certificate_screen:"Сертификат", battle_screen:"Battle", battle_title:"⚔️ Асинхронная дуэль", battle_desc2:"Создайте 4-значный код или введите код друга.", create_battle:"Создать Battle", or:"или", join:"Войти по коду", code_placeholder:"AB12", waiting_opponent:"Ожидается соперник…", battle_found:"Battle найден. Теперь отправьте свою оплату.", start_payment:"Начать оплату", waiting_payment:"Ожидается оплата…",
      error_profile:"Заполните все данные профиля", error_payment:"Платёж не найден", error_receipt:"Выберите изображение чека", error_server:"Сервер отвечает слишком долго.", saved:"Профиль сохранён", copied:"Карта скопирована", copy_fail:"Не удалось скопировать", receipt_sent:"Чек отправлен", approved_toast:"Оплата подтверждена", test_info_start:"Начать тест", test_info_cancel:"Не сейчас", test_info_iq_title:"Об IQ тесте", test_info_eq_title:"Об EQ тесте", test_info_pq_title:"О PQ тесте", test_info_iq_desc:"18 логических матриц. Проверяет внимание, закономерности и логические связи.", test_info_eq_desc:"6 ситуационных вопросов. Проверяет подход к эмоциям, решениям и общению.", test_info_pq_desc:"6 ситуационных вопросов. Проверяет планирование и практический подход к решениям.", test_info_paid_reason:"Оплата помогает покрывать расходы на разработку теста, сервер и обработку результатов. После завершения теста оплата нужна, чтобы открыть результат.", test_info_free:"Сейчас этот тест бесплатный. После завершения результат будет показан сразу.",
      personal_wait:"Анализ откроется после завершения IQ + EQ + PQ.", strengths:"Сильные стороны", development:"Точки развития", cert_empty:"Сертификата нет", cert_empty_text:"Завершите IQ тест — сертификат появится после открытия результата.", cert_open:"Открыть PNG",
    },
    en: {
      home_greet:"Hi, {name} 👋", hero_pill:"18 LOGIC PUZZLES", hero_title:"Test your IQ level", hero_text:"A test of attention, patterns and logic.", live_total:"Total participants", live_now:"Now", live_people:"people online", tests:"Tests", sequence:"unlock in sequence", iq_desc:"18 logic puzzles", eq_locked:"After IQ", eq_open:"Open", pq_locked:"After EQ", profile:"Personal profile", profile_after:"After IQ + EQ + PQ", battle:"Battle", battle_desc:"Asynchronous duel with a friend", home:"Home", ranking:"Ranking", certificate:"Certificate", profile_nav:"Profile",
      profile_title:"Profile", name_label:"Name / surname", name_placeholder:"Your name", gender_label:"Gender", select:"Select", male:"Male", female:"Female", age_label:"Age", country_label:"Country", save:"Save",
      q_label:"Q", easy:"EASY", medium:"MEDIUM", hard:"HARD", battle_label:"BATTLE", matrix_q:"Which option completes the matrix?", question:"Question", next:"Continue", see_result:"View result", loading_result:"Preparing result", checked:"✓ Answers checked", scoring:"✓ Score calculated", profile_updated:"✓ Profile updated",
      payment:"Payment", payment_wait:"PAYMENT TO UNLOCK RESULT", payment_text:"Your result is ready. Complete the payment below and send the receipt to unlock it.", copy:"Copy", open_bot:"Open Telegram bot", receipt:"Payment receipt", choose_file:"Choose file", send_receipt:"Send receipt", pay_pending:"Receipt sent. Waiting for admin approval.", pay_approved:"✅ Payment approved. Next step is open.", pay_rejected:"❌ Payment not approved. The admin rejected the receipt.", pay_waiting:"Waiting for receipt.", next_result:"📊 View result", next_battle:"⚔️ Go to Battle", home_btn:"🏠 Back to home", retry_receipt:"🔄 Send receipt again", receipt_resend:"Please send the receipt again.",
      result:"Result", iq_done:"IQ TEST COMPLETED", eq_done:"EQ TEST COMPLETED", pq_done:"PQ TEST COMPLETED", score_indicator:"Test indicator", question_stat:"questions", correct:"correct", time:"time", per_question:"sec/question", accuracy:"Accuracy", rank:"Your ranking", rank_compare:"Compared with results", your_result:"Your result", next_stage:"Next stage", eq_open_title:"EQ test unlocked", eq_open_text:"You can also test your emotional intelligence.", start_eq:"🎭 Start EQ test", pq_open_title:"PQ test unlocked", pq_open_text:"Take the planning and practical thinking test.", start_pq:"🧩 Start PQ test", profile_open_title:"Personal profile unlocked", profile_open_text:"View your profile based on IQ, EQ and PQ results.", open_profile:"⭐ View profile", no_next:"All tests completed", certificate_btn:"📄 Get certificate", share:"↗ Share result", retry:"↻  Retake test", ranking_first:"Your first result", ranking_total:"Among {n} results", no_ranking:"Ranking is not formed yet",
      test_result_summary:"You answered {correct} questions correctly. Your result is {score}, with the test level “{level}”.", behavior_summary:"Your test result finished at {score}%.",
      certificate_screen:"Certificate", battle_screen:"Battle", battle_title:"⚔️ Asynchronous duel", battle_desc2:"Create a 4-character code or enter your friend’s code.", create_battle:"Create Battle", or:"or", join:"Join by code", code_placeholder:"AB12", waiting_opponent:"Waiting for opponent…", battle_found:"Battle found. Now submit your payment.", start_payment:"Start payment", waiting_payment:"Waiting for payment…",
      error_profile:"Complete all profile fields", error_payment:"Payment not found", error_receipt:"Choose the receipt image", error_server:"The server is taking too long to respond.", saved:"Profile saved", copied:"Card copied", copy_fail:"Could not copy", receipt_sent:"Receipt sent", approved_toast:"Payment approved", test_info_start:"Start test", test_info_cancel:"Not now", test_info_iq_title:"About the IQ test", test_info_eq_title:"About the EQ test", test_info_pq_title:"About the PQ test", test_info_iq_desc:"18 logic matrices. It checks attention, patterns and logical connections.", test_info_eq_desc:"6 situational questions. It checks how you approach emotions, decisions and communication.", test_info_pq_desc:"6 situational questions. It checks planning and practical decision-making.", test_info_paid_reason:"Payment helps cover test development, server and result-processing costs. After you finish the test, payment is required to unlock the result.", test_info_free:"This test is currently free. Your result will be shown immediately after completion.",
      personal_wait:"Analysis unlocks after completing IQ + EQ + PQ.", strengths:"Strengths", development:"Development areas", cert_empty:"No certificate", cert_empty_text:"Complete the IQ test; the certificate appears after the result opens.", cert_open:"Open PNG",
    }
  };

  function tx(key, vars = {}) {
    const dict = I18N[state.lang] || I18N.uz;
    let value = dict[key] ?? I18N.uz[key] ?? key;
    return String(value).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
  }

  function localizeLevel(level) {
    const m={
      "Boshlang‘ich":{uz:"Boshlang‘ich",ru:"Начальный",en:"Beginner"},
      "O‘rtacha":{uz:"O‘rtacha",ru:"Средний",en:"Average"},
      "Yaxshi":{uz:"Yaxshi",ru:"Хороший",en:"Good"},
      "Yuqori":{uz:"Yuqori",ru:"Высокий",en:"High"},
      "Juda yuqori":{uz:"Juda yuqori",ru:"Очень высокий",en:"Very high"}
    };
    return m[level]?.[state.lang] || level || "—";
  }

  function applyLanguage(lang) {
    state.lang = I18N[lang] ? lang : "uz";
    document.documentElement.lang = state.lang;
    const text = (sel, key) => { const el = $(sel); if (el) el.textContent = tx(key); };
    const home = $("#homeScreen");
    if (home) {
      const greet=$("#homeScreen .topbar h1"); if(greet) greet.innerHTML = `${tx("home_greet", {name: state.user?.first_name || (state.lang === "ru" ? "Друг" : state.lang === "en" ? "Friend" : "Do‘st")})}`;
      setText(".hero-copy .pill", tx("hero_pill"));
      setText(".hero-copy h2", tx("hero_title")); setText(".hero-copy p", tx("hero_text"));
      setText(".live-card > div:first-child small", tx("live_total")); setText(".online div small:first-child", tx("live_now")); setText(".online div small:last-child", tx("live_people"));
      setText(".section-title h3", tx("tests")); setText(".section-title span", tx("sequence"));
      setText(".test-card.iq small", tx("iq_desc")); setText("#eqState", state.user?.hasIQ ? tx("eq_open") : tx("eq_locked")); setText("#pqState", state.user?.hasEQ ? tx("eq_open") : tx("pq_locked"));
      setText("#profileCard b", tx("profile")); setText("#profileCard small", tx("profile_after")); setText("#battleCard b", tx("battle")); setText("#battleCard small", tx("battle_desc"));
      const nav = $$('[data-nav]'); if (nav[0]) nav[0].querySelector('small').textContent=tx('home'); if(nav[1])nav[1].querySelector('small').textContent=tx('ranking'); if(nav[2])nav[2].querySelector('small').textContent=tx('certificate'); if(nav[3])nav[3].querySelector('small').textContent=tx('profile_nav');
    }
    text("#profileScreen .subbar h2", "profile_title"); text("#saveProfile", "save");
    const labels = $("#profileScreen"); if(labels){ const ls=labels.querySelectorAll('label'); if(ls[0])ls[0].firstChild.textContent=tx('name_label'); if(ls[1])ls[1].firstChild.textContent=tx('gender_label'); if(ls[2])ls[2].firstChild.textContent=tx('age_label'); if(ls[3])ls[3].firstChild.textContent=tx('country_label'); $("#fullName").placeholder=tx('name_placeholder'); }
    const g=$("#gender"); if(g){g.options[0].text=tx('select');g.options[1].text=tx('male');g.options[2].text=tx('female');}
    const c=$("#country"); if(c && c.options[0])c.options[0].text=tx('select');
    text("#paymentScreen .subbar h2","payment"); text("#paymentScreen .payment-card .pill","payment_wait"); setText("#paymentScreen .payment-card p",tx('payment_text')); text("#copyCard","copy"); text("#sharePayment","open_bot"); const fileLabel=$("#paymentScreen .file-label"); if(fileLabel && fileLabel.firstChild) fileLabel.firstChild.textContent=tx('receipt'); text("#sendReceipt","send_receipt");
    text("#resultScreen .subbar h2","result"); text("#certificateBtn span","certificate_btn"); text("#shareResultBtn span","share"); text("#retryIqBtn","retry");
    const resultStats=$("#resultScreen .result-stats"); if(resultStats){ const sm=resultStats.querySelectorAll('small'); if(sm[0])sm[0].textContent=tx('question_stat');if(sm[1])sm[1].textContent=tx('correct');if(sm[2])sm[2].textContent=tx('time');if(sm[3])sm[3].textContent=tx('per_question'); }
    text("#resultScreen .result-detail-card:first-child small","accuracy"); text("#resultScreen .result-detail-card:nth-child(2) small","rank"); text("#resultScreen .result-summary h3","your_result"); text("#nextStageLabel","next_stage");
    text("#rankingScreen .subbar h2","ranking"); text("#certificateScreen .subbar h2","certificate_screen"); text("#battleScreen .subbar h2","battle_screen"); text("#battleScreen .battle-panel h2","battle_title");
    const bp=$("#battleScreen .battle-panel p"); if(bp)bp.textContent=tx('battle_desc2'); text("#createBattle","create_battle"); text("#joinBattle","join"); const div=$("#battleScreen .divider"); if(div)div.textContent=tx('or'); const bc=$("#battleCode"); if(bc)bc.placeholder=tx('code_placeholder');
  }


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

  function ensureTestInfoModal() {
    let modal = $("#testInfoModal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "testInfoModal";
    modal.className = "test-info-modal hidden";
    modal.innerHTML = `
      <div class="test-info-backdrop"></div>
      <div class="test-info-dialog" role="dialog" aria-modal="true" aria-labelledby="testInfoTitle">
        <div class="test-info-icon" id="testInfoIcon">🧠</div>
        <span class="eyebrow">TEST MA’LUMOTI</span>
        <h2 id="testInfoTitle">IQ testi haqida</h2>
        <p id="testInfoDescription"></p>
        <div class="test-info-points" id="testInfoPoints"></div>
        <div class="test-info-price hidden" id="testInfoPrice"></div>
        <div class="test-info-note hidden" id="testInfoNote"></div>
        <div class="test-info-actions">
          <button id="testInfoCancel" class="secondary"></button>
          <button id="testInfoStart" class="primary"></button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    $("#testInfoCancel").onclick = () => { modal.classList.add("hidden"); state.testInfo = null; };
    $("#testInfoStart").onclick = async () => {
      const pending = state.testInfo;
      modal.classList.add("hidden");
      state.testInfo = null;
      if (pending?.type) await startTest(pending.type, false, true);
    };
    return modal;
  }

  function showTestInfo(type) {
    const modal = ensureTestInfoModal();
    const baseKey = {IQ:"iq_price", EQ:"eq_price", PQ:"pq_price"}[type];
    const retryKey = {IQ:"iq_retry_price", EQ:"eq_retry_price", PQ:"pq_retry_price"}[type];
    const hasPrevious = type === "IQ" ? Boolean(state.user?.hasIQ) : type === "EQ" ? Boolean(state.user?.hasEQ) : Boolean(state.user?.hasPQ);
    const key = hasPrevious ? retryKey : baseKey;
    const price = Number(state.prices?.[key] || 0);
    const titleKey = {IQ:"test_info_iq_title",EQ:"test_info_eq_title",PQ:"test_info_pq_title"}[type];
    const descKey = {IQ:"test_info_iq_desc",EQ:"test_info_eq_desc",PQ:"test_info_pq_desc"}[type];
    const icon = {IQ:"🧠",EQ:"🎭",PQ:"🧩"}[type];
    $("#testInfoIcon").textContent = icon;
    $("#testInfoTitle").textContent = tx(titleKey);
    $("#testInfoDescription").textContent = tx(descKey);
    $("#testInfoCancel").textContent = tx("test_info_cancel");
    $("#testInfoStart").textContent = tx("test_info_start");
    const count = type === "IQ" ? 18 : 6;
    $("#testInfoPoints").innerHTML = `<div><b>⏱</b><span>30 daqiqa</span></div><div><b>✓</b><span>${count} ta savol</span></div><div><b>🔒</b><span>${type === "IQ" ? "Natija va sertifikat" : "Natija"}</span></div>`;
    const priceBox = $("#testInfoPrice");
    const note = $("#testInfoNote");
    if (price > 0) {
      priceBox.classList.remove("hidden");
      priceBox.innerHTML = `<small>Natijani ochish</small><strong>${price.toLocaleString("uz-UZ")} so‘m</strong>`;
      note.classList.remove("hidden");
      note.textContent = tx("test_info_paid_reason");
    } else {
      priceBox.classList.add("hidden");
      note.classList.remove("hidden");
      note.textContent = tx("test_info_free");
    }
    state.testInfo = { type };
    modal.classList.remove("hidden");
  }

  function ensureRecoveryModal() {
    let modal = $("#recoveryModal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "recoveryModal";
    modal.className = "recovery-modal hidden";
    modal.innerHTML = `
      <div class="recovery-backdrop"></div>
      <div class="recovery-dialog" role="dialog" aria-modal="true" aria-labelledby="recoveryTitle">
        <div class="recovery-icon">↻</div>
        <span class="eyebrow" id="recoveryKicker">DAVOM ETTIRISH</span>
        <h2 id="recoveryTitle">Sizda yakunlanmagan jarayon bor</h2>
        <p id="recoveryText"></p>
        <div class="recovery-actions">
          <button id="recoveryCancel" class="secondary">Bekor qilish</button>
          <button id="recoveryContinue" class="primary">Davom etish</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    $("#recoveryCancel").onclick = async () => { await cancelRecovery(); };
    $("#recoveryContinue").onclick = async () => { await continueRecovery(); };
    return modal;
  }

  function showRecoveryModal(kind, payload) {
    state.recovery = { kind, payload };
    const modal = ensureRecoveryModal();
    const title = $("#recoveryTitle");
    const text = $("#recoveryText");
    const continueBtn = $("#recoveryContinue");
    const cancelBtn = $("#recoveryCancel");
    if (kind === "payment") {
      title.textContent = "Sizda yakunlanmagan to‘lov bor";
      text.textContent = `To‘lov (${Number(payload.amount || 0).toLocaleString("uz-UZ")} so‘m) yakunlanmagan. To‘lovni davom ettirasizmi yoki bekor qilasizmi?`;
      continueBtn.textContent = "To‘lovni davom ettirish";
      cancelBtn.textContent = "To‘lovni bekor qilish";
    } else {
      const type = payload.test_type || "IQ";
      title.textContent = "Sizda yakunlanmagan test bor";
      text.textContent = `${type} testi ${Number(payload.current_index || 0) + 1}-savoldan davom etadi. Testni davom ettirasizmi yoki butunlay bekor qilasizmi?`;
      continueBtn.textContent = "Testni davom ettirish";
      cancelBtn.textContent = "Testni bekor qilish";
    }
    modal.classList.remove("hidden");
  }

  function hideRecoveryModal() {
    const modal = $("#recoveryModal");
    if (modal) modal.classList.add("hidden");
    state.recovery = null;
  }

  async function continueRecovery() {
    const recovery = state.recovery;
    if (!recovery || state.busy) return;
    try {
      state.busy = true;
      hideRecoveryModal();
      if (recovery.kind === "payment") {
        const p = recovery.payload;
        state.paymentId = p.id; state.paymentAttemptId = p.attempt_id; state.battleId = p.battle_id || null;
        await renderPayment(p);
        show("paymentScreen");
      } else {
        await restoreServerActive(recovery.payload);
      }
    } catch (e) {
      toast(e.message || "Davom ettirib bo‘lmadi");
    } finally { state.busy = false; }
  }

  async function cancelRecovery() {
    const recovery = state.recovery;
    if (!recovery || state.busy) return;
    try {
      state.busy = true;
      if (recovery.kind === "payment") {
        await api(`/api/payment/${recovery.payload.id}/cancel`, { method:"POST", body:"{}" });
        if (Number(state.paymentId) === Number(recovery.payload.id)) { state.paymentId = null; state.paymentAttemptId = null; }
      } else {
        await api(`/api/test/${encodeURIComponent(recovery.payload.session_id)}/cancel`, { method:"POST", body:"{}" });
        if (String(state.sessionId) === String(recovery.payload.session_id)) { clearProgress(); state.sessionId = null; state.questions = []; state.answers = {}; }
      }
      hideRecoveryModal();
      show("homeScreen");
      toast("Bekor qilindi. Keyingi safar bu jarayon qayta ochilmaydi.");
    } catch (e) {
      toast(e.message || "Bekor qilib bo‘lmadi");
    } finally { state.busy = false; }
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

  // Normalize question payloads coming from PostgreSQL/API.
  // Older sessions may contain JSONB as a JSON string; never let a string
  // length become the question count (e.g. Q3/16973).
  function normalizeQuestions(raw, type) {
    let value = raw;
    for (let i = 0; i < 3 && typeof value === "string"; i++) {
      try { value = JSON.parse(value); } catch (_) { value = null; break; }
    }
    if (!Array.isArray(value)) return [];
    const expected = type === "IQ" ? 18 : 6;
    return value.length === expected ? value : [];
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
    $("#questionLabel").textContent = `${tx("q_label")}${state.index + 1}/${state.questions.length}`;
    const diff = state.mode === "BATTLE" ? tx("battle_label") : state.testType === "IQ" ? tx(difficulty(state.index) === "EASY" ? "easy" : difficulty(state.index) === "MEDIUM" ? "medium" : "hard") : state.testType;
    $("#difficulty").textContent = diff;
    $("#progressBar").style.width = `${((state.index) / Math.max(1, state.questions.length)) * 100}%`;
    $("#questionText").textContent = state.testType === "IQ" ? tx("matrix_q") : q.text || tx("question");

    const matrix = $("#matrix");
    matrix.innerHTML = "";
    matrix.classList.toggle("hidden", state.testType !== "IQ");
    if (state.testType === "IQ") (q.matrix || []).forEach((cell) => matrix.appendChild(renderCell(cell)));

    const options = $("#options");
    options.innerHTML = "";
    (q.options || []).forEach((option, i) => options.appendChild(renderOption(option, i)));
    $("#nextQuestion").textContent = state.index === state.questions.length - 1 ? tx("see_result") : tx("next");
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

  async function startTest(type, profileConfirmed = false, infoConfirmed = false) {
    if (state.busy) return;

    if (type === "EQ" && !state.user.hasIQ) { toast(tx("eq_locked")); return; }
    if (type === "PQ" && !state.user.hasEQ) { toast(tx("pq_locked")); return; }

    // Ask for personal data only once. After it is saved, future tests start
    // directly; the Profile screen remains available separately for editing.
    if (!infoConfirmed) {
      showTestInfo(type);
      return;
    }

    const profileReady = Boolean(
      state.user?.full_name && state.user?.gender &&
      state.user?.age && state.user?.country
    );
    if (!profileReady && !profileConfirmed) {
      state.pendingType = type;
      fillProfileFields();
      $("#profileOverview")?.classList.add("hidden");
      $("#profileEditor")?.classList.remove("hidden");
      show("profileScreen");
      return;
    }

    try {
      state.busy = true;
      const d = await api("/api/test/start", { method:"POST", body:JSON.stringify({ test_type:type }) });
      const questions = normalizeQuestions(d.questions, type);
      if (!questions.length) throw new Error("Test savollari topilmadi. Testni qayta boshlang.");

      state.mode = "NORMAL";
      state.testType = type;
      state.questions = questions;
      state.sessionId = d.session_id;
      state.answers = d.answers && typeof d.answers === "object" ? d.answers : {};
      state.index = Number.isInteger(Number(d.current_index))
        ? Number(d.current_index)
        : 0;
      state.index = Math.max(0, Math.min(state.index, state.questions.length - 1));
      state.startedAt = d.started_at ? Date.parse(d.started_at) : Date.now();
      saveProgress();
      show("testScreen");
      renderQuestion();
      startTimer();
      if (d.resumed) toast("Test saqlangan joyidan davom etdi.");
    } catch (e) { toast(e.message); }
    finally { state.busy = false; }
  }

  async function finishTest() {
    if (state.busy || !state.questions.length) return;
    clearInterval(window.__timer);
    if (state.selected !== null) state.answers[String(state.index + 1)] = state.selected;
    saveProgress();
    applyLoadingLanguage();
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

  function applyLoadingLanguage() {
    const el=$("#loadingResult"); if(!el) return;
    const h=el.querySelector("h2"); if(h)h.textContent=tx("loading_result");
    const spans=el.querySelectorAll(".check-list span"); if(spans[0])spans[0].textContent=tx("checked"); if(spans[1])spans[1].textContent=tx("scoring"); if(spans[2])spans[2].textContent=tx("profile_updated");
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
    // Refresh authoritative completion/profile statistics after every visible result.
    try {
      const fresh = await api("/api/bootstrap");
      state.user = fresh.user || state.user;
      state.profileStats = fresh.profile_stats || state.profileStats || {};
      updateHomeLocks();
    } catch (_) {}
    const questionCount = Number(d.question_count || (state.testType === "IQ" ? 18 : 6));
    const correct = Number(d.correct_count || 0);
    const accuracy = Math.max(0, Math.min(100, Number(d.accuracy ?? (questionCount ? Math.round(correct / questionCount * 100) : 0))));
    const duration = Math.max(0, Number(d.duration || 0));
    const avg = Number(d.avg_time || (questionCount && duration ? duration / questionCount : 0));
    const score = Number(d.score || 0);

    $("#resultBadge").textContent = state.testType === "IQ" ? tx("iq_done") : state.testType === "EQ" ? tx("eq_done") : tx("pq_done");
    $("#resultUnit").textContent = state.testType === "IQ" ? "IQ" : "%";
    $("#resultScore").textContent = score;
    const displayLevel = state.testType === "IQ" ? localizeLevel(d.level) : (d.level || (state.lang === "ru" ? "Результат" : state.lang === "en" ? "Result" : "Natija"));
    $("#resultLevel").textContent = displayLevel;
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
      $("#resultRankText").textContent = total > 1 ? tx("ranking_total", {n:total}) : tx("ranking_first");
    } else {
      $("#resultRank").textContent = "—";
      $("#resultRankText").textContent = tx("no_ranking");
    }

    $("#resultSummaryText").textContent = state.testType === "IQ"
      ? tx("test_result_summary", {correct, score, level:displayLevel})
      : tx("behavior_summary", {score});

    const nextBtn=$("#startEqFromResult");
    const nextCard=$(".next-stage-card");
    if (state.testType === "IQ") {
      $("#nextStageTitle").textContent=tx("eq_open_title"); $("#nextStageText").textContent=tx("eq_open_text"); nextBtn.textContent=tx("start_eq"); nextBtn.classList.remove("hidden");
      nextBtn.onclick=()=>startTest("EQ"); if(nextCard)nextCard.classList.remove("hidden");
    } else if (state.testType === "EQ") {
      $("#nextStageTitle").textContent=tx("pq_open_title"); $("#nextStageText").textContent=tx("pq_open_text"); nextBtn.textContent=tx("start_pq"); nextBtn.classList.remove("hidden");
      nextBtn.onclick=()=>startTest("PQ"); if(nextCard)nextCard.classList.remove("hidden");
    } else {
      $("#nextStageTitle").textContent=tx("profile_open_title"); $("#nextStageText").textContent=tx("profile_open_text"); nextBtn.textContent=tx("open_profile"); nextBtn.classList.remove("hidden");
      nextBtn.onclick=()=>{renderPersonalProfile();show("profileScreen")}; if(nextCard)nextCard.classList.remove("hidden");
    }
    applyLanguage(state.lang);
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
      box.innerHTML = `<button id="paymentNextBtn" class="primary">${tx("next_battle")}</button>`;
      $("#paymentNextBtn").onclick = async () => {
        show("battleScreen");
        await checkBattleReady(true);
        startBattlePolling();
      };
    } else if (state.paymentAttemptId) {
      box.innerHTML = `<button id="paymentNextBtn" class="primary">${tx("next_result")}</button>`;
      $("#paymentNextBtn").onclick = async () => {
        try { await showResult(state.paymentAttemptId); } catch (e) { toast(e.message); }
      };
    } else {
      box.innerHTML = `<button id="paymentNextBtn" class="primary">${tx("home_btn")}</button>`;
      $("#paymentNextBtn").onclick = () => show("homeScreen");
    }
  }

  function renderRejectedPaymentAction() {
    const box = paymentActions();
    box.innerHTML = `<button id="paymentHomeBtn" class="secondary">${tx("home_btn")}</button>
      <button id="paymentRetryBtn" class="primary" style="margin-top:8px">${tx("retry_receipt")}</button>`;
    $("#paymentHomeBtn").onclick = () => show("homeScreen");
    $("#paymentRetryBtn").onclick = () => {
      $("#paymentStatus").textContent = tx("receipt_resend");
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
      $("#paymentStatus").textContent = tx("pay_approved");
      $("#receiptFile").disabled = true;
      $("#sendReceipt").disabled = true;
      renderApprovedPaymentAction();
    } else if (d.status === "rejected") {
      $("#paymentStatus").textContent = tx("pay_rejected");
      renderRejectedPaymentAction();
    } else if (d.receipt_file_id) {
      $("#paymentStatus").textContent = tx("pay_pending");
    } else {
      $("#paymentStatus").textContent = card ? tx("payment_text") : tx("pay_waiting");
    }
    const paymentCard = $("#paymentScreen .payment-card");
    if (paymentCard) {
      let guide = paymentCard.querySelector(".payment-guide");
      if (!guide) {
        guide = document.createElement("div");
        guide.className = "payment-guide";
        $("#paymentAmount")?.insertAdjacentElement("afterend", guide);
      }
      guide.innerHTML = d.status === "approved"
        ? `<b>Natijangiz ochildi</b><span>Quyidagi tugma orqali natijangizga qaytishingiz mumkin.</span>`
        : `<b>Natijangizni ochish uchun</b><span>Kartadagi summani yuboring, so‘ng to‘lov chekini yuklang. Admin tekshirganidan keyin natija avtomatik ochiladi.</span>`;
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
        $("#paymentStatus").textContent = tx("pay_approved");
        $("#receiptFile").disabled = true;
        $("#sendReceipt").disabled = true;
        clearPaymentActions();
        renderApprovedPaymentAction();
      } else if (mine.status === "rejected") {
        $("#paymentStatus").textContent = tx("pay_rejected");
        $("#receiptFile").disabled = false;
        $("#sendReceipt").disabled = false;
        clearPaymentActions();
        renderRejectedPaymentAction();
      } else if (mine.receipt_file_id) {
        $("#paymentStatus").textContent = tx("pay_pending");
      } else {
        $("#paymentStatus").textContent = tx("payment_text");
      }
    } catch (_) {}
  }

  async function sendReceipt() {
    if (!state.paymentId) { toast(tx("error_payment")); return; }
    const file = $("#receiptFile")?.files?.[0];
    const legacy = $("#receiptInput")?.value.trim();
    if (!file && !legacy) { toast(tx("error_receipt")); return; }
    try {
      const fd = new FormData();
      if (file) fd.append("receipt", file, file.name);
      else fd.append("receipt_file_id", legacy);
      const d = await api(`/api/payment/${state.paymentId}/receipt`, { method:"POST", body:fd });
      clearPaymentActions();
      $("#paymentStatus").textContent = d.status === "approved" ? "✅ To‘lov tasdiqlandi. Keyingi bosqich ochildi." : "Receipt yuborildi. Admin tasdig‘i kutilmoqda.";
      toast(d.status === "approved" ? tx("approved_toast") : tx("receipt_sent"));
      if (d.status === "approved") renderApprovedPaymentAction();
      else if (state.battleId) startBattlePolling();
    } catch (e) { toast(e.message); }
  }

  async function loadHome() {
    const d = await api("/api/bootstrap");
    state.user = d.user;
    state.lang = d.user.language || "uz";
    applyLanguage(state.lang);
    state.prices = d.prices || {};
    state.questions = d.questions || [];
    state.profileStats = d.profile_stats || {};
    setText("#userName", d.user?.first_name || "Do‘st");
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

    // Do not force the user back into an unfinished flow. Ask once per active
    // server-side process; if they choose cancel, the server marks it cancelled
    // so the prompt will not return after reopening the Mini App.
    // Always ask before restoring an unfinished server-side process. The
    // server payload is authoritative, so an old localStorage snapshot can
    // never silently reopen the test.
    if (d.pending_payment) {
      showRecoveryModal("payment", d.pending_payment);
    } else if (d.active_test?.session_id) {
      showRecoveryModal("test", d.active_test);
    } else {
      clearProgress();
    }
  }

  function updateHomeLocks() {
    $("#eqState").textContent = state.user.hasIQ ? tx("eq_open") : tx("eq_locked");
    $("#pqState").textContent = state.user.hasEQ ? tx("eq_open") : tx("pq_locked");
    $(".test-card[data-test=EQ]")?.classList.toggle("locked", !state.user.hasIQ);
    $(".test-card[data-test=PQ]")?.classList.toggle("locked", !state.user.hasEQ);
    $("#profileCard")?.classList.toggle("locked", !state.user.hasPQ);
  }

  async function restoreServerActive(active) {
    if (!active?.session_id) return false;
    const questions = normalizeQuestions(active.questions, active.test_type);
    if (!questions.length) return false;

    state.mode = "NORMAL";
    state.sessionId = String(active.session_id);
    state.testType = active.test_type;
    state.questions = questions;
    state.answers = active.answers && typeof active.answers === "object" ? active.answers : {};
    state.index = Math.max(0, Math.min(
      Number(active.current_index) || 0, questions.length - 1
    ));
    state.startedAt = active.started_at ? Date.parse(active.started_at) : Date.now();
    saveProgress();
    show("testScreen");
    renderQuestion();
    startTimer();
    toast("Test saqlangan joyidan davom etdi.");
    return true;
  }

  async function restoreProgress() {
    let saved;
    try { saved = JSON.parse(localStorage.getItem("iq_test_progress") || "null"); } catch (_) { saved = null; }
    if (!saved?.sessionId) return false;
    try {
      const d = await api(`/api/test/${saved.sessionId}/resume`);
      if (d.status === "completed" || d.status === "expired") { clearProgress(); return false; }
      return await restoreServerActive({
        session_id: saved.sessionId,
        test_type: d.test_type,
        questions: d.questions,
        answers: d.answers || saved.answers || {},
        current_index: Number.isInteger(Number(d.current_index)) ? Number(d.current_index) : Number(saved.index || 0),
        started_at: d.started_at || saved.startedAt
      });
    } catch (_) {
      clearProgress();
      return false;
    }
  }

  async function updateLive() {
    try {
      const d = await api("/api/stats/live");
      animateNumber($("#liveTotal"), d.total);
      animateNumber($("#liveOnline"), d.online);
    } catch (_) {}
  }

  function animateNumber(el, n) { if (el) el.textContent = Number(n || 0).toLocaleString("uz-UZ"); }

  function fillProfileFields() {
    $("#fullName").value = state.user?.full_name || "";
    $("#gender").value = state.user?.gender || "";
    $("#age").value = state.user?.age || "";
    $("#country").value = state.user?.country || "";
  }

  async function saveProfile() {
    const age = Number($("#age").value);
    const body = {
      full_name: $("#fullName").value.trim(), gender: $("#gender").value,
      age, country: $("#country").value
    };
    if (!body.full_name || !body.gender || !body.country || !Number.isInteger(age) || age < 10 || age > 120) {
      toast(tx("error_profile")); return;
    }
    try {
      state.busy = true;
      await api("/api/profile/save", { method:"POST", body:JSON.stringify(body) });
      state.user = { ...state.user, ...body };
      setText("#userName", state.user?.first_name || "Do‘st");
      updateHomeLocks();
      renderPersonalProfile();
      toast(tx("saved"));
      const pending = state.pendingType;
      delete state.pendingType;
      if (pending) setTimeout(() => startTest(pending, true, true), 250);
      else if (state.user?.hasPQ) {
        $("#profileEditor")?.classList.add("hidden");
        $("#profileOverview")?.classList.remove("hidden");
        show("profileScreen");
      } else {
        $("#profileOverview")?.classList.add("hidden");
        $("#profileEditor")?.classList.remove("hidden");
        show("profileScreen");
      }
    } catch (e) { toast(e.message); }
    finally { state.busy = false; }
  }

  function renderPersonalProfile() {
    const box = $("#personalSummary");
    if (!box || !state.user) return;
    const st = state.profileStats || {};
    if (!state.user.hasPQ) {
      box.innerHTML = `
        <div class="profile-locked-card">
          <div class="profile-lock-icon">🔒</div>
          <span class="eyebrow">MAXSUS TAHLIL</span>
          <h3>Siz qanday insonsiz?</h3>
          <p>IQ, EQ va PQ natijalaringiz birlashtirilgach, bu yerda sizning fikrlash uslubingiz, kuchli tomonlaringiz, rivojlanish nuqtalaringiz va shaxsiy statistikangiz ochiladi.</p>
          <div class="profile-lock-progress"><i style="width:${state.user.hasEQ ? 66 : state.user.hasIQ ? 33 : 0}%"></i></div>
          <small>PQ testini yakunlang — shaxsiy tahlil ochiladi.</small>
        </div>`;
      return;
    }

    const initials = (state.user.full_name || state.user.first_name || "U").trim().split(/\s+/).slice(0,2).map(x=>x[0]?.toUpperCase()).join("") || "U";
    setText("#profileAvatar", initials);
    setText("#profileDisplayName", state.user.full_name || state.user.first_name || "Foydalanuvchi");
    setText("#profileMeta", [state.user.country, state.user.age ? `${state.user.age} yosh` : ""].filter(Boolean).join(" • ") || "Profil");

    const iq = st.iq_best == null ? "—" : st.iq_best;
    const eq = st.eq_best == null ? "—" : `${st.eq_best}%`;
    const pq = st.pq_best == null ? "—" : `${st.pq_best}%`;
    const avg = Number(st.avg_percent || 0);
    const accuracy = Number(st.overall_accuracy || 0);
    const totalCorrect = Number(st.total_correct || 0);
    const totalQuestions = Number(st.total_questions || 0);
    const avgTime = Number(st.avg_duration || 0);
    const iqRank = st.iq_rank ? `#${st.iq_rank}` : "—";

    let styleTitle = "Muvozanatli fikrlovchi";
    let styleText = "Sizda mantiq, hissiy anglash va amaliy qarorlar bir-birini to‘ldiradi.";
    if (Number(st.iq_best || 0) >= 120) { styleTitle = "Kuchli analitik"; styleText = "Murakkab naqshlarni ko‘rish va mantiqiy bog‘lanishlarni topish sizning ajralib turadigan jihatlaringizdan biri."; }
    else if (Number(st.eq_best || 0) >= 85) { styleTitle = "Kuchli empatik fikrlovchi"; styleText = "Vaziyat va odamlarning hissiy tomonini hisobga olish sizning kuchli jihatlaringizdan biri."; }
    else if (Number(st.pq_best || 0) >= 85) { styleTitle = "Amaliy strateg"; styleText = "Vazifalarni tartiblash va harakatni rejalashtirish sizning kuchli jihatlaringizdan biri."; }

    const compliment = avg >= 90 ? "Siz testlarni shunchaki topshirmagansiz — uch xil fikrlash yo‘nalishida ham yuqori darajada ishlagansiz." : avg >= 75 ? "Natijalaringiz yaxshi muvozanatlangan. Eng muhimi, siz uch xil yo‘nalishni ham oxirigacha sinab ko‘rdingiz." : "Siz barcha bosqichlarni yakunladingiz. Bu profil endi keyingi natijalarni taqqoslash uchun sizning shaxsiy nuqtangiz bo‘lib xizmat qiladi.";

    box.innerHTML = `
      <div class="profile-section-head"><span>SHAXSIY TAHLIL</span><small>IQ + EQ + PQ</small></div>
      <div class="profile-compliment">
        <div class="compliment-icon">✦</div>
        <div><b>${styleTitle}</b><p>${compliment}</p></div>
      </div>
      <div class="profile-stat-grid">
        <div class="profile-big-stat"><small>🧠 IQ</small><strong>${iq}</strong><span>eng yuqori natija</span></div>
        <div class="profile-big-stat"><small>🎭 EQ</small><strong>${eq}</strong><span>eng yuqori natija</span></div>
        <div class="profile-big-stat"><small>🧩 PQ</small><strong>${pq}</strong><span>eng yuqori natija</span></div>
        <div class="profile-big-stat"><small>⚡ UMUMIY</small><strong>${avg.toFixed(1)}%</strong><span>o‘rtacha ko‘rsatkich</span></div>
      </div>
      <div class="profile-mini-grid">
        <div><small>JAMI JAVOB</small><b>${totalCorrect}/${totalQuestions}</b></div>
        <div><small>ANIQLIK</small><b>${accuracy.toFixed(1)}%</b></div>
        <div><small>IQ REYTING</small><b>${iqRank}</b></div>
        <div><small>O‘RTACHA VAQT</small><b>${avgTime ? Math.round(avgTime) + " s" : "—"}</b></div>
      </div>
      <div class="profile-insight-card"><span>🧠</span><div><b>Fikrlash uslubingiz</b><h3>${styleTitle}</h3><p>${styleText}</p></div></div>
      <div class="profile-insight-card"><span>📈</span><div><b>Rivojlanish nuqtasi</b><h3>Natijani mustahkamlash</h3><p>Qayta topshirganingizda natijalarni oldingi ko‘rsatkichlar bilan taqqoslab, qaysi yo‘nalishda o‘sayotganingizni kuzatish mumkin.</p></div></div>
      <div class="profile-achievements"><div><b>🏆</b><span>Barcha 3 test</span><small>yakunlangan</small></div><div><b>🎯</b><span>${accuracy.toFixed(0)}%</span><small>umumiy aniqlik</small></div><div><b>⚡</b><span>${st.total_tests || 0}</span><small>natija</small></div></div>`;
  }
  async function loadRanking() {
    try {
      const d = await api("/api/ranking");
      const box = $("#rankingList");
      const top10 = Array.isArray(d.ranking) ? d.ranking.slice(0, 10) : [];
      box.innerHTML = top10.length ? top10.map((r, i) =>
        `<div class="rank-row"><span class="rank-pos">#${i + 1}</span><span><b>${escapeHtml(r.name)}</b><small>${escapeHtml(localizeLevel(r.level || ""))}</small></span><strong>${r.score}</strong></div>`
      ).join("") : `<div class="form-card glass empty-state"><b>Hali natijalar yo‘q.</b></div>`;
      show("rankingScreen");
    } catch (e) { toast(e.message); }
  }

  async function loadCertificate() {
    try {
      const d = await api("/api/certificate/mine");
      const c = d.certificate;
      const box = $("#certificateBox");
      if (!box) return;
      if (!c) {
        box.innerHTML = `<div class="certificate-empty">
          <div class="certificate-empty-icon">▣</div>
          <h3>${tx("cert_empty")}</h3>
          <p>${tx("cert_empty_text")}</p>
        </div>`;
        show("certificateScreen");
        return;
      }

      const created = c.created_at ? new Date(c.created_at) : new Date();
      const dateText = created.toLocaleDateString("uz-UZ");
      box.innerHTML = `
        <div class="certificate-premium">
          <div class="certificate-glow"></div>
          <div class="certificate-topline">IQTESTPRO.UZ <span>VERIFIED</span></div>
          <div class="certificate-seal">✓</div>
          <div class="certificate-kicker">AQLNI KASHF ETING</div>
          <h1>SERTIFIKAT</h1>
          <p class="certificate-subtitle">Aqliy salohiyat natijasi</p>
          <div class="certificate-name">${escapeHtml(c.full_name || "Foydalanuvchi")}</div>
          <div class="certificate-score"><strong>${Number(c.score || 0)}</strong><span>IQ</span></div>
          <div class="certificate-level">${escapeHtml(c.level || "")}</div>
          <div class="certificate-meta-grid">
            <div><small>SANA</small><b>${escapeHtml(dateText)}</b></div>
            <div><small>VERIFICATION</small><b>${escapeHtml(c.verification_code || "—")}</b></div>
          </div>
          <div class="certificate-footer">IQ TEST BOT · VERIFIED</div>
        </div>
        <div class="certificate-actions">
          <button id="certDownload" class="primary">📜 ${tx("cert_open")}</button>
        </div>
        <div id="certificateImagePreview" class="certificate-image-preview hidden"></div>`;

      $("#certDownload")?.addEventListener("click", async () => {
        try {
          const blob = await apiBlob(`/api/certificate/${encodeURIComponent(c.certificate_id)}/png`);
          const url = URL.createObjectURL(blob);
          const preview = $("#certificateImagePreview");
          if (preview) {
            preview.classList.remove("hidden");
            preview.innerHTML = `<img src="${url}" alt="IQ sertifikat">`;
            preview.scrollIntoView({ behavior:"smooth", block:"center" });
          }
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
    try { await navigator.clipboard.writeText($("#cardNumber").textContent); toast(tx("copied")); }
    catch (_) { toast(tx("copy_fail")); }
  });
  $("#sendReceipt")?.addEventListener("click", sendReceipt);
  $("#sharePayment")?.addEventListener("click", () => {
    const url = `https://t.me/${encodeURIComponent("iqtest_ubot")}`;
    if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.open(url, "_blank");
  });
  $("#certificateBtn")?.addEventListener("click", loadCertificate);
  // Result next-stage button receives a test-specific handler inside showResult().
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
  $("#profileTopBtn")?.addEventListener("click", () => {
    if (state.user?.hasPQ) {
      renderPersonalProfile();
      $("#profileOverview")?.classList.remove("hidden");
      $("#profileEditor")?.classList.add("hidden");
    } else {
      fillProfileFields();
      $("#profileOverview")?.classList.add("hidden");
      $("#profileEditor")?.classList.remove("hidden");
    }
    show("profileScreen");
  });
  $("#editProfileBtn")?.addEventListener("click", () => {
    fillProfileFields();
    $("#profileOverview")?.classList.add("hidden");
    $("#profileEditor")?.classList.remove("hidden");
    show("profileScreen");
  });
  $("#profileCancel")?.addEventListener("click", () => {
    $("#profileEditor")?.classList.add("hidden");
    $("#profileOverview")?.classList.remove("hidden");
    renderPersonalProfile();
  });
  $("#battleCard")?.addEventListener("click", () => show("battleScreen"));
  $("#profileCard")?.addEventListener("click", () => {
    if (!state.user?.hasPQ) { toast("🔒 Shaxsiy tahlil PQ testidan keyin ochiladi."); return; }
    renderPersonalProfile();
    $("#profileOverview")?.classList.remove("hidden");
    $("#profileEditor")?.classList.add("hidden");
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
      console.error("Mini App bootstrap failed", e);
      show("homeScreen");
      toast(e.message || "Mini App yuklanmadi");
    }
  })();
})();
