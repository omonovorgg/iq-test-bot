"use strict";

/*
 * ============================================================
 * ZAKO IQ — Telegram Mini App
 * app.js
 *
 * VERSION:
 * 2026-09-18
 *
 * IMPORTANT:
 * Backend is the source of truth.
 *
 * Flow:
 * START
 *   ↓
 * ANSWER #1
 *   ↓
 * ANSWER #2
 *   ↓
 * ...
 * ANSWER #16
 *   ↓
 * FINISH
 *
 * NEVER call /finish before /answer #16 succeeds.
 * ============================================================
 */


/* ============================================================
   TELEGRAM
============================================================ */

const tg = window.Telegram?.WebApp || null;


/* ============================================================
   CONSTANTS
============================================================ */

const QUESTIONS_COUNT = 16;

const LETTERS = [
    "A",
    "B",
    "C",
    "D"
];

const SUPPORTED_LANGUAGES = [
    "uz",
    "ru",
    "en"
];


/* ============================================================
   STATE
============================================================ */

const state = {

    lang:
        localStorage.getItem("iq_lang") || "uz",

    screen:
        "home",

    session:
        null,

    result:
        null,

    profile:
        null,

    config: {

        bot_username:
            "",

        zako_url:
            "https://t.me/zako_tbot"
    },

    busy:
        false,

    busyFinish:
        false,

    answerSubmitting:
        false,

    recovering:
        false,

    timer:
        null,

    timerBaseElapsed:
        0,

    timerClientStarted:
        0,

    initialized:
        false
};


/* ============================================================
   TEXT
============================================================ */

const TEXT = {

    uz: {

        eyebrow:
            "16 TA MANTIQIY PUZZLE",

        title:
            "IQ darajangizni\nsinab ko‘ring",

        subtitle:
            "16 ta mantiqiy puzzle orqali fikrlash qobiliyatingizni sinang.",

        start:
            "TESTNI BOSHLASH",

        ranking:
            "Reyting",

        rankingSub:
            "Eng yuqori natijalar",

        profile:
            "Profil",

        profileSub:
            "Natijalaringiz",

        next:
            "DAVOM ETISH",

        finished:
            "TEST YAKUNLANDI",

        yourResult:
            "Sizning natijangiz",

        iqScore:
            "IQ SCORE",

        correct:
            "To‘g‘ri javob",

        time:
            "Vaqt",

        rank:
            "Reyting",

        certificate:
            "SERTIFIKAT OLISH",

        share:
            "NATIJANI ULASHISH",

        improve:
            "IQ'IMNI RIVOJLANTIRISH",

        rankingDesc:
            "Eng yaxshi natijalar",

        profileDesc:
            "Sizning IQ statistikangiz",

        bestIq:
            "ENG YAXSHI IQ",

        tests:
            "Testlar",

        referrals:
            "Takliflar",

        invite:
            "DO‘STLARNI TAKLIF QILISH",

        chooseLanguage:
            "Tilni tanlang",

        logic:
            "MANTIQIY PUZZLE",

        number:
            "SONLI PUZZLE",

        letters:
            "HARFLAR PUZZLE",

        visual:
            "VIZUAL PUZZLE",

        memory:
            "XOTIRA PUZZLE",

        loading:
            "Yuklanmoqda…",

        paid:
            "Birinchi testingiz bepul. Keyingi test narxi 3 000 so‘m.",

        retest:
            "QAYTA TEST — 3 000 SO‘M",

        session:
            "Sizda davom etayotgan test mavjud.",

        sessionContinue:
            "TESTNI DAVOM ETTIRISH",

        error:
            "Xatolik yuz berdi. Qaytadan urinib ko‘ring.",

        network:
            "Internet bilan aloqa uzildi. Qayta urinib ko‘ring.",

        noData:
            "Ma’lumot topilmadi.",

        certificateRequired:
            "Sertifikat uchun 2 ta real taklif kerak.",

        certificateNoResult:
            "Avval IQ testini topshiring.",

        certificateError:
            "Sertifikatni olishda xatolik yuz berdi.",

        resultNote:
            "Bu ZAKO IQ testining taxminiy mahsulot skoridir, klinik IQ baholashi emas.",

        inviteText:
            "Do‘stingizni IQ testga taklif qiling!",

        copied:
            "Natija nusxalandi.",

        shareText:
            "Natijamni ko‘ring!",

        noRanking:
            "Hali reytingda natijalar yo‘q.",

        cannotOpen:
            "Havolani ochib bo‘lmadi.",

        back:
            "ORQAGA",

        home:
            "BOSH SAHIFA",

        leaveTest:
            "Testdan chiqmoqchimisiz? Hozirgi javob saqlanmasligi mumkin.",

        cancel:
            "BEKOR QILISH",

        leave:
            "CHIQISH",

        user:
            "Foydalanuvchi",

        answerAccepted:
            "Javob qabul qilindi."
    },


    ru: {

        eyebrow:
            "16 ЛОГИЧЕСКИХ ЗАДАЧ",

        title:
            "Проверьте\nсвой IQ",

        subtitle:
            "16 логических задач для проверки вашего мышления.",

        start:
            "НАЧАТЬ ТЕСТ",

        ranking:
            "Рейтинг",

        rankingSub:
            "Лучшие результаты",

        profile:
            "Профиль",

        profileSub:
            "Ваша статистика",

        next:
            "ПРОДОЛЖИТЬ",

        finished:
            "ТЕСТ ЗАВЕРШЁН",

        yourResult:
            "Ваш результат",

        iqScore:
            "IQ SCORE",

        correct:
            "Правильных ответов",

        time:
            "Время",

        rank:
            "Рейтинг",

        certificate:
            "ПОЛУЧИТЬ СЕРТИФИКАТ",

        share:
            "ПОДЕЛИТЬСЯ РЕЗУЛЬТАТОМ",

        improve:
            "РАЗВИВАТЬ IQ",

        rankingDesc:
            "Лучшие результаты",

        profileDesc:
            "Ваша статистика IQ",

        bestIq:
            "ЛУЧШИЙ IQ",

        tests:
            "Тесты",

        referrals:
            "Приглашения",

        invite:
            "ПРИГЛАСИТЬ ДРУЗЕЙ",

        chooseLanguage:
            "Выберите язык",

        logic:
            "ЛОГИЧЕСКАЯ ЗАДАЧА",

        number:
            "ЧИСЛОВАЯ ЗАДАЧА",

        letters:
            "БУКВЕННАЯ ЗАДАЧА",

        visual:
            "ВИЗУАЛЬНАЯ ЗАДАЧА",

        memory:
            "ЗАДАЧА НА ПАМЯТЬ",

        loading:
            "Загрузка…",

        paid:
            "Первая попытка бесплатна. Следующий тест — 3 000 сум.",

        retest:
            "ПОВТОРНЫЙ ТЕСТ — 3 000 СУМ",

        session:
            "У вас уже есть незавершённый тест.",

        sessionContinue:
            "ПРОДОЛЖИТЬ ТЕСТ",

        error:
            "Произошла ошибка. Попробуйте ещё раз.",

        network:
            "Соединение с интернетом потеряно. Попробуйте снова.",

        noData:
            "Данные не найдены.",

        certificateRequired:
            "Для сертификата нужны 2 реальных приглашения.",

        certificateNoResult:
            "Сначала пройдите IQ-тест.",

        certificateError:
            "Не удалось получить сертификат.",

        resultNote:
            "Это приблизительный продуктовый балл ZAKO IQ, а не клиническая оценка IQ.",

        inviteText:
            "Приглашаю тебя пройти IQ-тест!",

        copied:
            "Результат скопирован.",

        shareText:
            "Посмотри мой результат!",

        noRanking:
            "В рейтинге пока нет результатов.",

        cannotOpen:
            "Не удалось открыть ссылку.",

        back:
            "НАЗАД",

        home:
            "ГЛАВНАЯ",

        leaveTest:
            "Выйти из теста? Текущий ответ может не сохраниться.",

        cancel:
            "ОТМЕНА",

        leave:
            "ВЫЙТИ",

        user:
            "Пользователь",

        answerAccepted:
            "Ответ принят."
    },


    en: {

        eyebrow:
            "16 LOGIC PUZZLES",

        title:
            "Test\nyour IQ",

        subtitle:
            "Challenge your reasoning with 16 logic puzzles.",

        start:
            "START TEST",

        ranking:
            "Ranking",

        rankingSub:
            "Top results",

        profile:
            "Profile",

        profileSub:
            "Your statistics",

        next:
            "CONTINUE",

        finished:
            "TEST COMPLETE",

        yourResult:
            "Your result",

        iqScore:
            "IQ SCORE",

        correct:
            "Correct answers",

        time:
            "Time",

        rank:
            "Ranking",

        certificate:
            "GET CERTIFICATE",

        share:
            "SHARE RESULT",

        improve:
            "DEVELOP MY IQ",

        rankingDesc:
            "Top results",

        profileDesc:
            "Your IQ statistics",

        bestIq:
            "BEST IQ",

        tests:
            "Tests",

        referrals:
            "Invites",

        invite:
            "INVITE FRIENDS",

        chooseLanguage:
            "Choose language",

        logic:
            "LOGIC PUZZLE",

        number:
            "NUMBER PUZZLE",

        letters:
            "LETTER PUZZLE",

        visual:
            "VISUAL PUZZLE",

        memory:
            "MEMORY PUZZLE",

        loading:
            "Loading…",

        paid:
            "Your first attempt is free. The next test costs 3,000 UZS.",

        retest:
            "RETAKE TEST — 3,000 UZS",

        session:
            "You already have an unfinished test.",

        sessionContinue:
            "CONTINUE TEST",

        error:
            "Something went wrong. Please try again.",

        network:
            "Internet connection lost. Please try again.",

        noData:
            "No data found.",

        certificateRequired:
            "2 real invites are required for the certificate.",

        certificateNoResult:
            "Take the IQ test first.",

        certificateError:
            "Could not get the certificate.",

        resultNote:
            "This is an approximate ZAKO IQ product score, not a clinical IQ assessment.",

        inviteText:
            "Try this IQ test!",

        copied:
            "Result copied.",

        shareText:
            "Check out my result!",

        noRanking:
            "There are no ranking results yet.",

        cannotOpen:
            "Could not open the link.",

        back:
            "BACK",

        home:
            "HOME",

        leaveTest:
            "Leave the test? Your current answer may not be saved.",

        cancel:
            "CANCEL",

        leave:
            "LEAVE",

        user:
            "User",

        answerAccepted:
            "Answer accepted."
    }
};


/* ============================================================
   QUESTIONS
============================================================ */

const QUESTIONS = [

    {
        category: "logic",

        text: {
            uz:
                "Qaysi belgi ketma-ketlikni davom ettiradi?",

            ru:
                "Какой символ продолжает последовательность?",

            en:
                "Which symbol continues the sequence?"
        },

        puzzle: `
            <svg viewBox="0 0 360 220"
                 role="img"
                 aria-label="Pattern puzzle">

                <g fill="none"
                   stroke="currentColor"
                   stroke-width="4"
                   stroke-linecap="round"
                   stroke-linejoin="round">

                    <circle cx="65" cy="55" r="18"/>
                    <path d="M120 37 L138 73 L102 73 Z"/>
                    <circle cx="190" cy="55" r="18"/>
                    <path d="M245 37 L263 73 L227 73 Z"/>

                    <path d="M47 110 L65 146 L83 110 Z"/>
                    <circle cx="120" cy="128" r="18"/>
                    <path d="M172 110 L190 146 L208 110 Z"/>
                    <circle cx="245" cy="128" r="18"/>

                    <circle cx="190" cy="182" r="18"/>
                    <path d="M245 164 L263 200 L227 200 Z"/>

                </g>

                <text x="292"
                      y="195"
                      font-size="44"
                      font-weight="800"
                      fill="currentColor">?</text>

            </svg>
        `,

        options: {
            uz: ["●", "▲", "■", "◆"],
            ru: ["●", "▲", "■", "◆"],
            en: ["●", "▲", "■", "◆"]
        }
    },


    {
        category: "number",

        text: {
            uz:
                "Qaysi son yetishmayapti?\n\n4 → 9\n6 → 15\n8 → 21\n11 → ?",

            ru:
                "Какого числа не хватает?\n\n4 → 9\n6 → 15\n8 → 21\n11 → ?",

            en:
                "Which number is missing?\n\n4 → 9\n6 → 15\n8 → 21\n11 → ?"
        },

        options: {
            uz: ["27", "30", "32", "33"],
            ru: ["27", "30", "32", "33"],
            en: ["27", "30", "32", "33"]
        }
    },


    {
        category: "number",

        text: {
            uz:
                "Sonlar ketma-ketligini davom ettiring:\n\n2, 6, 12, 20, 30, ?",

            ru:
                "Продолжите последовательность:\n\n2, 6, 12, 20, 30, ?",

            en:
                "Continue the sequence:\n\n2, 6, 12, 20, 30, ?"
        },

        options: {
            uz: ["40", "41", "42", "44"],
            ru: ["40", "41", "42", "44"],
            en: ["40", "41", "42", "44"]
        }
    },


    {
        category: "visual",

        text: {
            uz:
                "Naqshdagi yetishmayotgan juftlikni toping.",

            ru:
                "Найдите недостающую пару в узоре.",

            en:
                "Find the missing pair in the pattern."
        },

        puzzle: `
            <svg viewBox="0 0 360 230"
                 role="img"
                 aria-label="Matrix puzzle">

                <g fill="none"
                   stroke="currentColor"
                   stroke-width="4">

                    <rect x="20" y="20"
                          width="85"
                          height="75"
                          rx="12"/>

                    <circle cx="62"
                            cy="57"
                            r="17"/>

                    <rect x="137" y="20"
                          width="85"
                          height="75"
                          rx="12"/>

                    <path d="M179 38 L196 72 L162 72 Z"/>

                    <rect x="254" y="20"
                          width="85"
                          height="75"
                          rx="12"/>

                    <circle cx="296"
                            cy="57"
                            r="17"/>

                    <rect x="20" y="125"
                          width="85"
                          height="75"
                          rx="12"/>

                    <path d="M62 143 L79 177 L45 177 Z"/>

                    <rect x="137" y="125"
                          width="85"
                          height="75"
                          rx="12"/>

                    <rect x="254" y="125"
                          width="85"
                          height="75"
                          rx="12"/>

                </g>

                <text x="294"
                      y="180"
                      font-size="42"
                      font-weight="800"
                      fill="currentColor">?</text>

            </svg>
        `,

        options: {
            uz: ["◇ □", "○ □", "◇ ○", "△ □"],
            ru: ["◇ □", "○ □", "◇ ○", "△ □"],
            en: ["◇ □", "○ □", "◇ ○", "△ □"]
        }
    },


    {
        category: "letters",

        text: {
            uz:
                "Harflar ketma-ketligini davom ettiring:\n\nB, E, I, N, T, ?",

            ru:
                "Продолжите последовательность букв:\n\nB, E, I, N, T, ?",

            en:
                "Continue the letter sequence:\n\nB, E, I, N, T, ?"
        },

        options: {
            uz: ["Y", "Z", "A", "B"],
            ru: ["Y", "Z", "A", "B"],
            en: ["Y", "Z", "A", "B"]
        }
    },


    {
        category: "number",

        text: {
            uz:
                "Sonlar ketma-ketligini davom ettiring:\n\n3, 7, 15, 31, 63, ?",

            ru:
                "Продолжите последовательность:\n\n3, 7, 15, 31, 63, ?",

            en:
                "Continue the sequence:\n\n3, 7, 15, 31, 63, ?"
        },

        options: {
            uz: ["95", "111", "127", "129"],
            ru: ["95", "111", "127", "129"],
            en: ["95", "111", "127", "129"]
        }
    },


    {
        category: "logic",

        text: {
            uz:
                "Faqat bitta yozuv rost.\n\nQizil: “Kalit ko‘k qutida.”\nKo‘k: “Kalit ko‘k qutida emas.”\nYashil: “Kalit qizil qutida emas.”\n\nKalit qaysi qutida?",

            ru:
                "Только одно утверждение истинно.\n\nКрасная: «Ключ в синей коробке».\nСиняя: «Ключ не в синей коробке».\nЗелёная: «Ключ не в красной коробке».\n\nВ какой коробке ключ?",

            en:
                "Only one statement is true.\n\nRed: “The key is in the blue box.”\nBlue: “The key is not in the blue box.”\nGreen: “The key is not in the red box.”\n\nWhich box contains the key?"
        },

        puzzle: `
            <svg viewBox="0 0 360 180"
                 role="img"
                 aria-label="Three boxes">

                <g fill="none"
                   stroke="currentColor"
                   stroke-width="4">

                    <rect x="18"
                          y="42"
                          width="98"
                          height="92"
                          rx="16"/>

                    <rect x="131"
                          y="42"
                          width="98"
                          height="92"
                          rx="16"/>

                    <rect x="244"
                          y="42"
                          width="98"
                          height="92"
                          rx="16"/>

                </g>

                <text x="42"
                      y="96"
                      font-size="15"
                      font-weight="800"
                      fill="currentColor">
                    QIZIL
                </text>

                <text x="158"
                      y="96"
                      font-size="15"
                      font-weight="800"
                      fill="currentColor">
                    KO‘K
                </text>

                <text x="262"
                      y="96"
                      font-size="15"
                      font-weight="800"
                      fill="currentColor">
                    YASHIL
                </text>

            </svg>
        `,

        options: {
            uz: [
                "Qizil",
                "Ko‘k",
                "Yashil",
                "Aniqlab bo‘lmaydi"
            ],

            ru: [
                "Красная",
                "Синяя",
                "Зелёная",
                "Нельзя определить"
            ],

            en: [
                "Red",
                "Blue",
                "Green",
                "Cannot determine"
            ]
        }
    },


    {
        category: "visual",

        text: {
            uz:
                "Belgi 90° buriladi va rang navbat bilan o‘zgaradi. Keyingi belgi qaysi?",

            ru:
                "Символ поворачивается на 90°, а цвет чередуется. Какой следующий?",

            en:
                "The symbol rotates 90° and the color alternates. What comes next?"
        },

        puzzle: `
            <svg viewBox="0 0 360 170"
                 role="img"
                 aria-label="Rotation sequence">

                <text x="20"
                      y="105"
                      font-size="39"
                      fill="currentColor">
                    ○↑
                </text>

                <text x="92"
                      y="105"
                      font-size="28"
                      fill="currentColor">
                    →
                </text>

                <text x="132"
                      y="105"
                      font-size="39"
                      fill="currentColor">
                    ●→
                </text>

                <text x="212"
                      y="105"
                      font-size="28"
                      fill="currentColor">
                    →
                </text>

                <text x="252"
                      y="105"
                      font-size="39"
                      fill="currentColor">
                    ○↓
                </text>

            </svg>
        `,

        options: {
            uz: ["○↑", "○→", "●↑", "●↓"],
            ru: ["○↑", "○→", "●↑", "●↓"],
            en: ["○↑", "○→", "●↑", "●↓"]
        }
    },


    {
        category: "logic",

        text: {
            uz:
                "A B dan oldin.\nB D dan oldin.\nD E dan oldin.\nC A dan keyin.\n\nQaysi tartib mumkin?",

            ru:
                "A перед B.\nB перед D.\nD перед E.\nC после A.\n\nКакой порядок возможен?",

            en:
                "A is before B.\nB is before D.\nD is before E.\nC is after A.\n\nWhich order is possible?"
        },

        options: {
            uz: [
                "B-A-D-E-C",
                "A-C-B-D-E",
                "D-A-B-C-E",
                "E-D-B-A-C"
            ],

            ru: [
                "B-A-D-E-C",
                "A-C-B-D-E",
                "D-A-B-C-E",
                "E-D-B-A-C"
            ],

            en: [
                "B-A-D-E-C",
                "A-C-B-D-E",
                "D-A-B-C-E",
                "E-D-B-A-C"
            ]
        }
    },


    {
        category: "number",

        text: {
            uz:
                "Qoidani toping:\n\n2 × 3 + 2 = 8\n3 × 4 + 3 = 15\n4 × 5 + 4 = 24\n5 × 6 + 5 = ?",

            ru:
                "Найдите правило:\n\n2 × 3 + 2 = 8\n3 × 4 + 3 = 15\n4 × 5 + 4 = 24\n5 × 6 + 5 = ?",

            en:
                "Find the rule:\n\n2 × 3 + 2 = 8\n3 × 4 + 3 = 15\n4 × 5 + 4 = 24\n5 × 6 + 5 = ?"
        },

        options: {
            uz: ["30", "32", "35", "36"],
            ru: ["30", "32", "35", "36"],
            en: ["30", "32", "35", "36"]
        }
    },


    {
        category: "number",

        text: {
            uz:
                "Qaysi son yetishmayapti?\n\n1, 4, 10, 22, 46, ?",

            ru:
                "Какого числа не хватает?\n\n1, 4, 10, 22, 46, ?",

            en:
                "Which number is missing?\n\n1, 4, 10, 22, 46, ?"
        },

        options: {
            uz: ["82", "90", "94", "96"],
            ru: ["82", "90", "94", "96"],
            en: ["82", "90", "94", "96"]
        }
    },


    {
        category: "logic",

        text: {
            uz:
                "Qoida:\nAgar kartaning old tomonida unli harf bo‘lsa, orqasida juft son bo‘lishi kerak.\n\nQaysi kartalarni albatta tekshirish kerak?",

            ru:
                "Правило:\nЕсли на одной стороне карты гласная, на другой должно быть чётное число.\n\nКакие карты нужно проверить?",

            en:
                "Rule:\nIf a card has a vowel on one side, it must have an even number on the other side.\n\nWhich cards must be checked?"
        },

        puzzle: `
            <svg viewBox="0 0 360 155"
                 role="img"
                 aria-label="Cards">

                <g fill="none"
                   stroke="currentColor"
                   stroke-width="4">

                    <rect x="15"
                          y="18"
                          width="72"
                          height="115"
                          rx="13"/>

                    <rect x="101"
                          y="18"
                          width="72"
                          height="115"
                          rx="13"/>

                    <rect x="187"
                          y="18"
                          width="72"
                          height="115"
                          rx="13"/>

                    <rect x="273"
                          y="18"
                          width="72"
                          height="115"
                          rx="13"/>

                </g>

                <text x="38"
                      y="91"
                      font-size="42"
                      font-weight="800"
                      fill="currentColor">
                    A
                </text>

                <text x="124"
                      y="91"
                      font-size="42"
                      font-weight="800"
                      fill="currentColor">
                    D
                </text>

                <text x="208"
                      y="91"
                      font-size="42"
                      font-weight="800"
                      fill="currentColor">
                    4
                </text>

                <text x="296"
                      y="91"
                      font-size="42"
                      font-weight="800"
                      fill="currentColor">
                    7
                </text>

            </svg>
        `,

        options: {
            uz: [
                "Faqat A",
                "A va 7",
                "D va 4",
                "4 va 7"
            ],

            ru: [
                "Только A",
                "A и 7",
                "D и 4",
                "4 и 7"
            ],

            en: [
                "Only A",
                "A and 7",
                "D and 4",
                "4 and 7"
            ]
        }
    },


    {
        category: "memory",

        text: {
            uz:
                "K — 7 — ▲ — M — 3 — ● — R — 9\n\n▲ belgisidan 3 ta o‘rin keyin nima turibdi?",

            ru:
                "K — 7 — ▲ — M — 3 — ● — R — 9\n\nЧто находится через 3 позиции после ▲?",

            en:
                "K — 7 — ▲ — M — 3 — ● — R — 9\n\nWhat is 3 positions after ▲?"
        },

        options: {
            uz: ["M", "3", "●", "R"],
            ru: ["M", "3", "●", "R"],
            en: ["M", "3", "●", "R"]
        }
    },


    {
        category: "logic",

        text: {
            uz:
                "Barcha A lar B.\nBa’zi B lar C.\n\nQaysi xulosa majburiy ravishda to‘g‘ri?",

            ru:
                "Все A являются B.\nНекоторые B являются C.\n\nКакой вывод обязательно верен?",

            en:
                "All A are B.\nSome B are C.\n\nWhich conclusion is necessarily true?"
        },

        options: {
            uz: [
                "Ba’zi A lar C",
                "Ba’zi A lar C ekanini aniqlab bo‘lmaydi",
                "Barcha C lar A",
                "Barcha B lar A"
            ],

            ru: [
                "Некоторые A — C",
                "Нельзя определить, есть ли A среди C",
                "Все C — A",
                "Все B — A"
            ],

            en: [
                "Some A are C",
                "Cannot determine whether any A are C",
                "All C are A",
                "All B are A"
            ]
        }
    },


    {
        category: "number",

        text: {
            uz:
                "Ketma-ketlikni davom ettiring:\n\n4, 9, 19, 39, 79, ?",

            ru:
                "Продолжите последовательность:\n\n4, 9, 19, 39, 79, ?",

            en:
                "Continue the sequence:\n\n4, 9, 19, 39, 79, ?"
        },

        options: {
            uz: ["149", "159", "169", "179"],
            ru: ["149", "159", "169", "179"],
            en: ["149", "159", "169", "179"]
        }
    },


    {
        category: "number",

        text: {
            uz:
                "Yakuniy ketma-ketlik:\n\n3, 7, 15, 31, 63, 127, ?",

            ru:
                "Финальная последовательность:\n\n3, 7, 15, 31, 63, 127, ?",

            en:
                "Final sequence:\n\n3, 7, 15, 31, 63, 127, ?"
        },

        options: {
            uz: ["191", "223", "255", "257"],
            ru: ["191", "223", "255", "257"],
            en: ["191", "223", "255", "257"]
        }
    }

];


/* ============================================================
   HELPERS
============================================================ */

function tr(key) {

    return (
        TEXT[state.lang]?.[key] ??
        TEXT.uz?.[key] ??
        key
    );
}


function escapeHTML(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatTime(seconds) {

    const total =
        Math.max(
            0,
            Math.floor(
                Number(seconds) || 0
            )
        );

    const minutes =
        Math.floor(
            total / 60
        );

    const secs =
        total % 60;

    return (
        String(minutes).padStart(2, "0") +
        ":" +
        String(secs).padStart(2, "0")
    );
}


function telegramInitData() {

    return tg?.initData || "";
}


function telegramUser() {

    return tg?.initDataUnsafe?.user || null;
}


function showToast(message) {

    const toast =
        document.getElementById("toast");

    if (!toast) {
        return;
    }

    toast.textContent =
        String(message);

    toast.classList.add("show");

    clearTimeout(
        showToast.timeout
    );

    showToast.timeout =
        setTimeout(
            () => {
                toast.classList.remove("show");
            },
            2600
        );
}


function setBusy(value) {

    state.busy =
        Boolean(value);
}


function categoryText(category) {

    return tr(
        category || "logic"
    );
}


function clampQuestionIndex(index) {

    const value =
        Number(index);

    if (!Number.isFinite(value)) {
        return 0;
    }

    return Math.max(
        0,
        Math.min(
            QUESTIONS_COUNT,
            Math.floor(value)
        )
    );
}


function normalizeAnswers(answers) {

    if (!Array.isArray(answers)) {
        return [];
    }

    return answers
        .slice(0, QUESTIONS_COUNT)
        .map((value) => {

            const number =
                Number(value);

            return (
                Number.isInteger(number) &&
                number >= 0 &&
                number <= 3
            )
                ? number
                : null;
        });
}


/* ============================================================
   API
============================================================ */

async function api(
    path,
    options = {}
) {

    const headers = {

        "Content-Type":
            "application/json",

        "X-Telegram-Init-Data":
            telegramInitData(),

        ...(options.headers || {})
    };


    let response;

    try {

        response =
            await fetch(
                path,
                {
                    ...options,
                    headers,
                    cache: "no-store"
                }
            );

    } catch (error) {

        console.error(
            "Network error:",
            error
        );

        const networkError =
            new Error(
                "NETWORK_ERROR"
            );

        networkError.cause =
            error;

        throw networkError;
    }


    let data = null;


    const contentType =
        response.headers.get(
            "content-type"
        ) || "";


    if (
        contentType.includes(
            "application/json"
        )
    ) {

        try {

            data =
                await response.json();

        } catch {

            data = null;
        }

    } else {

        try {

            const text =
                await response.text();

            data = {
                message:
                    text
            };

        } catch {

            data = null;
        }
    }


    if (!response.ok) {

        const error =
            new Error(
                data?.detail ||
                data?.message ||
                `HTTP_${response.status}`
            );

        error.status =
            response.status;

        error.detail =
            data?.detail ||
            data?.message ||
            "";

        error.data =
            data;

        throw error;
    }


    return data;
}


/* ============================================================
   SCREEN
============================================================ */

function activateScreen(screenId) {

    document
        .querySelectorAll(".screen")
        .forEach(
            (screen) => {

                screen.classList.remove(
                    "active"
                );
            }
        );


    const target =
        document.getElementById(
            screenId
        );


    if (target) {

        target.classList.add(
            "active"
        );
    }


    state.screen =
        screenId.replace(
            "Screen",
            ""
        );


    window.scrollTo({
        top: 0,
        left: 0,
        behavior: "instant"
    });


    updateBackButton();
}


function updateBackButton() {

    const button =
        document.getElementById(
            "backBtn"
        );

    if (!button) {
        return;
    }


    button.style.visibility =
        state.screen === "home"
            ? "hidden"
            : "visible";
}


/* ============================================================
   TELEGRAM SETUP
============================================================ */

function setupTelegram() {

    if (!tg) {

        console.warn(
            "Telegram WebApp SDK unavailable."
        );

        return;
    }


    try {

        tg.ready();

        tg.expand();


        if (
            typeof tg.disableVerticalSwipes ===
            "function"
        ) {

            tg.disableVerticalSwipes();
        }


        if (
            typeof tg.setHeaderColor ===
            "function"
        ) {

            tg.setHeaderColor(
                "#080a10"
            );
        }


        if (
            typeof tg.setBackgroundColor ===
            "function"
        ) {

            tg.setBackgroundColor(
                "#080a10"
            );
        }

    } catch (error) {

        console.warn(
            "Telegram setup:",
            error
        );
    }
}


function applyTheme() {

    if (!tg) {
        return;
    }


    const theme =
        tg.colorScheme || "dark";


    document.body.classList.toggle(
        "light",
        theme === "light"
    );
}


/* ============================================================
   CONFIG
============================================================ */

async function loadConfig() {

    try {

        const config =
            await api(
                "/api/config"
            );


        if (
            !config ||
            typeof config !== "object"
        ) {

            return;
        }


        if (
            typeof config.bot_username ===
            "string"
        ) {

            state.config.bot_username =
                config.bot_username;
        }


        if (
            typeof config.zako_url ===
            "string" &&
            /^https:\/\//i.test(
                config.zako_url
            )
        ) {

            state.config.zako_url =
                config.zako_url;
        }

    } catch (error) {

        console.warn(
            "Config unavailable:",
            error
        );
    }
}


/* ============================================================
   LANGUAGE
============================================================ */

function openLanguageModal() {

    const modal =
        document.getElementById(
            "languageModal"
        );

    if (!modal) {
        return;
    }


    modal.classList.remove(
        "hidden"
    );


    document
        .querySelectorAll(
            ".language-option"
        )
        .forEach(
            (button) => {

                const selected =
                    button.dataset.lang ===
                    state.lang;


                const check =
                    button.querySelector("b");


                if (check) {

                    check.textContent =
                        selected
                            ? "✓"
                            : "";
                }


                button.classList.toggle(
                    "selected",
                    selected
                );
            }
        );
}


function closeLanguageModal() {

    const modal =
        document.getElementById(
            "languageModal"
        );

    if (modal) {

        modal.classList.add(
            "hidden"
        );
    }
}


function setLanguage(language) {

    if (
        !SUPPORTED_LANGUAGES.includes(
            language
        )
    ) {

        return;
    }


    state.lang =
        language;


    localStorage.setItem(
        "iq_lang",
        language
    );


    closeLanguageModal();

    updateLanguageButton();


    if (
        state.screen === "test" &&
        state.session
    ) {

        renderTest();

        return;
    }


    if (
        state.screen === "result" &&
        state.result
    ) {

        renderResult();

        return;
    }


    if (
        state.screen === "ranking"
    ) {

        loadRanking();

        return;
    }


    if (
        state.screen === "profile"
    ) {

        loadProfile();

        return;
    }


    renderHome();
}


function updateLanguageButton() {

    const button =
        document.getElementById(
            "langBtn"
        );


    if (button) {

        button.textContent =
            state.lang.toUpperCase();
    }
}


/* ============================================================
   HOME
============================================================ */

function renderHome() {

    stopTimer();


    activateScreen(
        "homeScreen"
    );


    updateLanguageButton();


    document
        .querySelectorAll(
            "[data-i18n]"
        )
        .forEach(
            (element) => {

                const key =
                    element.dataset.i18n;


                const value =
                    TEXT[state.lang]?.[key];


                if (
                    typeof value ===
                    "string"
                ) {

                    element.textContent =
                        value;
                }
            }
        );
}


/* ============================================================
   SESSION OBJECT
============================================================ */

function buildSession(data) {

    const answers =
        normalizeAnswers(
            data?.answers
        );


    let index =
        clampQuestionIndex(
            data?.index ?? 0
        );


    /*
     * Normal healthy session:
     *
     * index === answers.length
     *
     * Example:
     * 0 answers → index 0
     * 5 answers → index 5
     * 16 answers → index 16
     *
     * We do NOT silently overwrite the backend
     * source of truth.
     */

    return {

        user_id:
            data?.user_id,

        created:
            Boolean(
                data?.created
            ),

        index,

        answers,

        elapsed:
            Math.max(
                0,
                Number(
                    data?.elapsed || 0
                )
            ),

        attempts:
            Number(
                data?.attempts || 0
            ),

        selected:
            null
    };
}


/* ============================================================
   SESSION START
============================================================ */

async function startTest() {
    const startBtn = document.getElementById("startBtn");

    /*
     * HARD LOCK
     *
     * Bir vaqtning o'zida faqat bitta start request.
     * Telegram WebView'da double-tap yoki duplicate event
     * bo'lsa ham ikkinchi request ketmaydi.
     */
    if (
        state.busy ||
        state.answerSubmitting ||
        state.busyFinish
    ) {
        return;
    }

    state.busy = true;

    if (startBtn) {
        startBtn.disabled = true;
        startBtn.setAttribute(
            "aria-busy",
            "true"
        );
    }

    try {
        console.log(
            "[ZAKO IQ] START: request"
        );

        const data = await api(
            "/api/session/start",
            {
                method: "POST",
                body: JSON.stringify({
                    language: state.lang
                })
            }
        );

        console.log(
            "[ZAKO IQ] START: response",
            data
        );

        /*
         * Backend response must be an object.
         */
        if (
            !data ||
            typeof data !== "object"
        ) {
            throw new Error(
                "INVALID_SESSION_RESPONSE"
            );
        }

        /*
         * Validate answers.
         */
        if (
            data.answers !== undefined &&
            !Array.isArray(data.answers)
        ) {
            throw new Error(
                "INVALID_SESSION_ANSWERS"
            );
        }

        /*
         * Build local session.
         */
        const session =
            buildSession(data);

        if (!session) {
            throw new Error(
                "SESSION_BUILD_FAILED"
            );
        }

        state.session =
            session;

        console.log(
            "[ZAKO IQ] SESSION:",
            state.session
        );

        const answerCount =
            Array.isArray(
                state.session.answers
            )
                ? state.session.answers.filter(
                    (value) =>
                        Number.isInteger(value) &&
                        value >= 0 &&
                        value <= 3
                ).length
                : 0;

        /*
         * IMPORTANT:
         *
         * Do not use answers.length here.
         * We need the number of REAL answers.
         */
        if (
            answerCount ===
            QUESTIONS_COUNT
        ) {
            state.session.index =
                QUESTIONS_COUNT;

            console.log(
                "[ZAKO IQ] Session already complete."
            );

            await finishTest();

            return;
        }

        /*
         * An incomplete session can never be
         * sent to /finish.
         */
        if (
            state.session.index >=
                QUESTIONS_COUNT &&
            answerCount <
                QUESTIONS_COUNT
        ) {
            console.error(
                "[ZAKO IQ] INVALID SESSION STATE",
                {
                    index:
                        state.session.index,
                    answerCount,
                    answers:
                        state.session.answers
                }
            );

            /*
             * Try server-side recovery.
             */
            await recoverSession();

            return;
        }

        /*
         * Backend should point at the next
         * unanswered question.
         */
        if (
            state.session.index !==
            answerCount
        ) {
            console.warn(
                "[ZAKO IQ] SESSION INDEX MISMATCH",
                {
                    index:
                        state.session.index,
                    answerCount
                }
            );

            /*
             * Do not blindly continue with a
             * corrupted state.
             */
            await recoverSession();

            return;
        }

        /*
         * Render test.
         */
        console.log(
            "[ZAKO IQ] Rendering test..."
        );

        renderTest();

        /*
         * HARD CHECK:
         * renderTest() must activate testScreen.
         */
        const testScreen =
            document.getElementById(
                "testScreen"
            );

        if (
            !testScreen ||
            !testScreen.classList.contains(
                "active"
            )
        ) {
            console.error(
                "[ZAKO IQ] TEST SCREEN DID NOT ACTIVATE",
                {
                    testScreenExists:
                        Boolean(testScreen),
                    active:
                        testScreen
                            ? testScreen.classList.contains(
                                "active"
                            )
                            : false,
                    session:
                        state.session
                }
            );

            throw new Error(
                "TEST_SCREEN_NOT_ACTIVATED"
            );
        }

        console.log(
            "[ZAKO IQ] TEST STARTED SUCCESSFULLY"
        );

    } catch (error) {
        console.error(
            "[ZAKO IQ] startTest ERROR:",
            error
        );

        handleStartError(
            error
        );

    } finally {
        state.busy =
            false;

        if (startBtn) {
            startBtn.disabled =
                false;

            startBtn.removeAttribute(
                "aria-busy"
            );
        }
    }
}


/* ============================================================
   START ERROR
============================================================ */

function handleStartError(error) {

    if (
        error.status === 402 ||
        error.detail === "PAID_RETEST"
    ) {

        showToast(
            tr("paid")
        );

        return;
    }


    if (
        error.message ===
        "NETWORK_ERROR"
    ) {

        showToast(
            tr("network")
        );

        return;
    }


    if (
        error.detail ===
        "INVALID_INIT_DATA"
    ) {

        showToast(
            "Telegram Mini App auth xatosi."
        );

        return;
    }


    if (
        error.detail ===
        "SESSION_ACTIVE"
    ) {

        showToast(
            tr("session")
        );

        return;
    }


    showToast(
        tr("error")
    );
}


/* ============================================================
   TEST RENDER
============================================================ */

function renderTest() {

    if (!state.session) {

        renderHome();

        return;
    }


    const index =
        clampQuestionIndex(
            state.session.index
        );


    const answerCount =
        Array.isArray(
            state.session.answers
        )
            ? state.session.answers.length
            : 0;


    /*
     * Only render finish state if there
     * are actually 16 accepted answers.
     */

    if (
        answerCount ===
        QUESTIONS_COUNT
    ) {

        state.session.index =
            QUESTIONS_COUNT;

        finishTest();

        return;
    }


    if (
        index >=
        QUESTIONS_COUNT
    ) {

        console.error(
            "Invalid test state:",
            {
                index,
                answerCount
            }
        );


        showToast(
            tr("error")
        );

        return;
    }


    const question =
        QUESTIONS[index];


    if (!question) {

        showToast(
            tr("error")
        );

        return;
    }


    const questionText =
        question.text[state.lang] ||
        question.text.uz;


    const options =
        question.options[state.lang] ||
        question.options.uz;


    const questionNumber =
        String(
            index + 1
        ).padStart(
            2,
            "0"
        );


    const progress =
        Math.min(
            100,
            (
                index /
                QUESTIONS_COUNT
            ) * 100
        );


    const puzzle =
        question.puzzle
            ? `
                <div class="puzzle">
                    ${question.puzzle}
                </div>
              `
            : "";


    const answersHTML =
        options
            .map(
                (
                    option,
                    optionIndex
                ) => {

                    return `
                        <button
                            type="button"
                            class="answer-btn"
                            data-answer="${optionIndex}"
                            aria-label="${escapeHTML(
                                LETTERS[optionIndex] +
                                ": " +
                                option
                            )}"
                        >

                            <span
                                class="answer-letter"
                            >
                                ${LETTERS[optionIndex]}
                            </span>

                            <span
                                class="answer-text"
                            >
                                ${escapeHTML(
                                    option
                                )}
                            </span>

                        </button>
                    `;
                }
            )
            .join("");


    const questionScreen =
        document.getElementById(
            "testScreen"
        );


    if (!questionScreen) {
        return;
    }


    questionScreen.innerHTML = `

        <div class="test-head">

            <div>

                <span id="questionNumber">
                    ${questionNumber} / ${QUESTIONS_COUNT}
                </span>

                <div class="progress">

                    <div
                        id="progressFill"
                        style="width:${progress}%"
                    ></div>

                </div>

            </div>


            <div class="timer">

                <span>◷</span>

                <span id="timer">
                    00:00
                </span>

            </div>

        </div>


        <div class="question-card">

            <div class="question-category">

                ${escapeHTML(
                    categoryText(
                        question.category
                    )
                )}

            </div>


            <h2 id="questionText">
                ${escapeHTML(
                    questionText
                )}
            </h2>


            ${puzzle}

        </div>


        <div
            id="answers"
            class="answers"
        >
            ${answersHTML}
        </div>


        <button
            id="nextBtn"
            class="next-btn"
            type="button"
            disabled
        >

            <span>
                ${escapeHTML(
                    tr("next")
                )}
            </span>

            <span>
                →
            </span>

        </button>
    `;


    activateScreen(
        "testScreen"
    );


    bindTestButtons();


    startTimer();
}


/* ============================================================
   TEST BUTTONS
============================================================ */

function bindTestButtons() {

    document
        .querySelectorAll(
            "[data-answer]"
        )
        .forEach(
            (button) => {

                button.addEventListener(
                    "click",
                    () => {

                        if (
                            state.busy ||
                            state.answerSubmitting
                        ) {

                            return;
                        }


                        const index =
                            Number(
                                button.dataset.answer
                            );


                        selectAnswer(
                            index
                        );
                    }
                );
            }
        );


    const next =
        document.getElementById(
            "nextBtn"
        );


    if (next) {

        next.addEventListener(
            "click",
            submitSelectedAnswer
        );
    }
}


/* ============================================================
   SELECT ANSWER
============================================================ */

function selectAnswer(index) {

    if (
        state.busy ||
        state.answerSubmitting ||
        !state.session
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


    state.session.selected =
        index;


    document
        .querySelectorAll(
            "[data-answer]"
        )
        .forEach(
            (button) => {

                const active =
                    Number(
                        button.dataset.answer
                    ) === index;


                button.classList.toggle(
                    "selected",
                    active
                );


                button.classList.remove(
                    "locked"
                );
            }
        );


    const next =
        document.getElementById(
            "nextBtn"
        );


    if (next) {

        next.disabled =
            false;
    }
}


/* ============================================================
   SUBMIT ANSWER
============================================================ */

async function submitSelectedAnswer() {

    if (
        state.busy ||
        state.answerSubmitting ||
        !state.session
    ) {

        return;
    }


    const selected =
        state.session.selected;


    if (
        selected === null ||
        selected === undefined
    ) {

        return;
    }


    const index =
        Number(
            state.session.index
        );


    if (
        !Number.isInteger(index) ||
        index < 0 ||
        index >= QUESTIONS_COUNT
    ) {

        console.error(
            "Invalid answer index:",
            index
        );

        return;
    }


    state.answerSubmitting =
        true;


    const answerButtons =
        Array.from(
            document.querySelectorAll(
                "[data-answer]"
            )
        );


    const next =
        document.getElementById(
            "nextBtn"
        );


    /*
     * Lock immediately.
     *
     * This is critical because two taps
     * must never create two answer requests.
     */

    answerButtons.forEach(
        (button) => {

            button.disabled =
                true;

            button.classList.add(
                "locked"
            );
        }
    );


    if (next) {

        next.disabled =
            true;
    }


    try {

        const data =
            await api(
                "/api/session/answer",
                {
                    method: "POST",

                    body:
                        JSON.stringify({
                            index,
                            selected
                        })
                }
            );


        /*
         * SERVER ACCEPTED THE ANSWER.
         *
         * Only now do we modify the local
         * session state.
         */

        if (
            !data ||
            typeof data !== "object"
        ) {

            throw new Error(
                "INVALID_ANSWER_RESPONSE"
            );
        }


        const serverIndex =
            clampQuestionIndex(
                data.index ??
                (index + 1)
            );


        if (
            !Array.isArray(
                state.session.answers
            )
        ) {

            state.session.answers = [];
        }


        state.session.answers[index] =
            selected;


        /*
         * Backend should return index + 1.
         * Use server value as authority.
         */

        state.session.index =
            serverIndex;


        state.session.selected =
            null;


        const answerCount =
            state.session.answers
                .filter(
                    (value) =>
                        Number.isInteger(
                            value
                        )
                )
                .length;


        /*
         * FINAL QUESTION
         *
         * /answer succeeded first.
         * Only now is /finish allowed.
         */

        if (
            index ===
            QUESTIONS_COUNT - 1 &&
            answerCount ===
            QUESTIONS_COUNT &&
            serverIndex >=
            QUESTIONS_COUNT
        ) {

            await finishTest();

            return;
        }


        /*
         * Safety:
         *
         * If backend says 16 but local
         * answer count is not 16, NEVER finish.
         */

        if (
            serverIndex >=
            QUESTIONS_COUNT &&
            answerCount <
            QUESTIONS_COUNT
        ) {

            console.error(
                "Server returned completed index without 16 answers:",
                {
                    serverIndex,
                    answerCount
                }
            );


            await recoverSession();

            return;
        }


        renderTest();

    } catch (error) {

        console.error(
            "submitSelectedAnswer:",
            error
        );


        /*
         * Server rejected the answer.
         *
         * Restore the exact question state.
         */

        state.session.index =
            index;

        state.session.selected =
            selected;


        if (
            error.detail ===
            "OUT_OF_ORDER"
        ) {

            await recoverSession();

            return;
        }


        if (
            error.detail ===
            "SESSION_COMPLETE"
        ) {

            await recoverSession();

            return;
        }


        if (
            error.detail ===
            "SESSION_EXPIRED"
        ) {

            showToast(
                tr("session")
            );

            return;
        }


        if (
            error.message ===
            "NETWORK_ERROR"
        ) {

            showToast(
                tr("network")
            );

            return;
        }


        showToast(
            tr("error")
        );

    } finally {

        state.answerSubmitting =
            false;
    }
}


/* ============================================================
   SESSION RECOVERY
============================================================ */

async function recoverSession() {

    if (
        state.recovering
    ) {

        return;
    }


    state.recovering =
        true;


    stopTimer();


    try {

        const data =
            await api(
                "/api/session/start",
                {
                    method: "POST",

                    body:
                        JSON.stringify({
                            language:
                                state.lang
                        })
                }
            );


        if (
            !data ||
            typeof data !== "object"
        ) {

            throw new Error(
                "INVALID_SESSION"
            );
        }


        const recovered =
            buildSession(
                data
            );


        const answerCount =
            recovered.answers.length;


        /*
         * If all 16 answers are really
         * present, finish is safe.
         */

        if (
            answerCount ===
            QUESTIONS_COUNT
        ) {

            recovered.index =
                QUESTIONS_COUNT;

            state.session =
                recovered;

            await finishTest();

            return;
        }


        /*
         * Never finish an incomplete session.
         */

        if (
            recovered.index >=
            QUESTIONS_COUNT &&
            answerCount <
            QUESTIONS_COUNT
        ) {

            console.error(
                "Cannot recover inconsistent session:",
                {
                    index:
                        recovered.index,

                    answers:
                        answerCount
                }
            );


            showToast(
                tr("error")
            );

            return;
        }


        state.session =
            recovered;


        renderTest();

    } catch (error) {

        console.error(
            "recoverSession:",
            error
        );


        if (
            error.status === 402 ||
            error.detail === "PAID_RETEST"
        ) {

            showToast(
                tr("paid")
            );

        } else if (
            error.message ===
            "NETWORK_ERROR"
        ) {

            showToast(
                tr("network")
            );

        } else {

            showToast(
                tr("error")
            );
        }

    } finally {

        state.recovering =
            false;
    }
}


/* ============================================================
   TIMER
============================================================ */

function startTimer() {

    stopTimer();


    if (!state.session) {
        return;
    }


    state.timerBaseElapsed =
        Math.max(
            0,
            Number(
                state.session.elapsed || 0
            )
        );


    state.timerClientStarted =
        Date.now();


    const update = () => {

        const timer =
            document.getElementById(
                "timer"
            );


        if (!timer) {
            return;
        }


        const liveElapsed =
            state.timerBaseElapsed +
            Math.floor(
                (
                    Date.now() -
                    state.timerClientStarted
                ) / 1000
            );


        timer.textContent =
            formatTime(
                liveElapsed
            );
    };


    update();


    state.timer =
        window.setInterval(
            update,
            500
        );
}


function stopTimer() {

    if (
        state.timer !== null
    ) {

        window.clearInterval(
            state.timer
        );

        state.timer =
            null;
    }
}


/* ============================================================
   FINISH
============================================================ */

async function finishTest() {

    stopTimer();


    /*
     * Never finish without a session.
     */

    if (!state.session) {

        return;
    }


    /*
     * CRITICAL SAFETY CHECK.
     *
     * Frontend is not allowed to call /finish
     * unless 16 answers actually exist.
     */

    const answerCount =
        Array.isArray(
            state.session.answers
        )
            ? state.session.answers
                .filter(
                    (value) =>
                        Number.isInteger(
                            value
                        )
                )
                .length
            : 0;


    if (
        answerCount !==
        QUESTIONS_COUNT
    ) {

        console.error(
            "finishTest blocked:",
            {
                answerCount,
                index:
                    state.session.index
            }
        );


        await recoverSession();

        return;
    }


    if (
        state.busyFinish
    ) {

        return;
    }


    state.busyFinish =
        true;


    try {

        const result =
            await api(
                "/api/session/finish",
                {
                    method: "POST",

                    body: "{}"
                }
            );


        if (
            !result ||
            typeof result !== "object"
        ) {

            throw new Error(
                "INVALID_RESULT"
            );
        }


        const iq =
            Number(
                result.iq
            );


        const raw =
            Number(
                result.raw || 0
            );


        const correct =
            Number(
                result.correct || 0
            );


        const elapsed =
            Number(
                result.elapsed || 0
            );


        if (
            !Number.isFinite(iq) ||
            !Number.isFinite(correct) ||
            !Number.isFinite(elapsed)
        ) {

            throw new Error(
                "INVALID_RESULT"
            );
        }


        state.result = {

            iq,

            raw,

            correct,

            elapsed,

            rank:
                result.rank === null ||
                result.rank === undefined
                    ? null
                    : Number(
                        result.rank
                    )
        };


        /*
         * Completed session is safely stored
         * on backend.
         */

        state.session =
            null;


        renderResult();

    } catch (error) {

        console.error(
            "finishTest:",
            error
        );


        if (
            error.detail ===
            "INCOMPLETE"
        ) {

            /*
             * Do not hide the problem.
             * Re-sync with backend.
             */

            await recoverSession();

        } else if (
            error.detail ===
            "SESSION_COMPLETE"
        ) {

            await recoverSession();

        } else if (
            error.detail ===
            "SESSION_EXPIRED"
        ) {

            showToast(
                tr("session")
            );

            state.session =
                null;

            renderHome();

        } else if (
            error.message ===
            "NETWORK_ERROR"
        ) {

            showToast(
                tr("network")
            );

        } else {

            showToast(
                tr("error")
            );
        }

    } finally {

        state.busyFinish =
            false;
    }
}


/* ============================================================
   RESULT
============================================================ */

function renderResult() {

    stopTimer();


    if (!state.result) {

        renderHome();

        return;
    }


    const result =
        state.result;


    const screen =
        document.getElementById(
            "resultScreen"
        );


    if (!screen) {
        return;
    }


    const rank =
        result.rank !== null &&
        result.rank !== undefined
            ? `#${result.rank}`
            : "—";


    screen.innerHTML = `

        <div class="result-header">

            <div class="success-icon">
                ✓
            </div>


            <div class="eyebrow">
                ${escapeHTML(
                    tr("finished")
                )}
            </div>


            <h1>
                ${escapeHTML(
                    tr("yourResult")
                )}
            </h1>

        </div>


        <div class="score-card">

            <span>
                ${escapeHTML(
                    tr("iqScore")
                )}
            </span>


            <strong>
                ${escapeHTML(
                    result.iq
                )}
            </strong>


            <small>
                ${escapeHTML(
                    tr("resultNote")
                )}
            </small>

        </div>


        <div class="result-stats">

            <div>

                <strong>
                    ${escapeHTML(
                        `${result.correct}/${QUESTIONS_COUNT}`
                    )}
                </strong>


                <span>
                    ${escapeHTML(
                        tr("correct")
                    )}
                </span>

            </div>


            <div>

                <strong>
                    ${escapeHTML(
                        formatTime(
                            result.elapsed
                        )
                    )}
                </strong>


                <span>
                    ${escapeHTML(
                        tr("time")
                    )}
                </span>

            </div>


            <div>

                <strong>
                    ${escapeHTML(
                        rank
                    )}
                </strong>


                <span>
                    ${escapeHTML(
                        tr("rank")
                    )}
                </span>

            </div>

        </div>


        <button
            id="certificateBtn"
            class="primary-btn"
            type="button"
        >

            <span>
                🎓
            </span>


            <span>
                ${escapeHTML(
                    tr("certificate")
                )}
            </span>


            <span class="arrow">
                →
            </span>

        </button>


        <button
            id="shareBtn"
            class="secondary-btn"
            type="button"
        >

            <span>
                ↗
            </span>


            <span>
                ${escapeHTML(
                    tr("share")
                )}
            </span>

        </button>


        <button
            id="retestBtn"
            class="secondary-btn"
            type="button"
        >

            <span>
                🔄
            </span>


            <span>
                ${escapeHTML(
                    tr("retest")
                )}
            </span>

        </button>


        <button
            id="zakoBtn"
            class="secondary-btn"
            type="button"
        >

            <span>
                🚀
            </span>


            <span>
                ${escapeHTML(
                    tr("improve")
                )}
            </span>

        </button>
    `;


    activateScreen(
        "resultScreen"
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
            "shareBtn"
        )
        ?.addEventListener(
            "click",
            shareResult
        );


    document
        .getElementById(
            "retestBtn"
        )
        ?.addEventListener(
            "click",
            startRetest
        );


    document
        .getElementById(
            "zakoBtn"
        )
        ?.addEventListener(
            "click",
            openZako
        );
}


/* ============================================================
   RETEST
============================================================ */

async function startRetest() {

    if (
        state.busy ||
        state.answerSubmitting ||
        state.busyFinish
    ) {

        return;
    }


    setBusy(true);


    try {

        const data =
            await api(
                "/api/session/start",
                {
                    method: "POST",

                    body:
                        JSON.stringify({
                            language:
                                state.lang
                        })
                }
            );


        /*
         * If backend eventually supports payment,
         * a new session will be returned here.
         */

        if (
            data &&
            typeof data === "object"
        ) {

            state.session =
                buildSession(
                    data
                );


            const answerCount =
                state.session.answers.length;


            if (
                answerCount ===
                QUESTIONS_COUNT
            ) {

                await finishTest();

                return;
            }


            renderTest();

            return;
        }


        throw new Error(
            "INVALID_SESSION"
        );

    } catch (error) {

        console.error(
            "startRetest:",
            error
        );


        if (
            error.status === 402 ||
            error.detail === "PAID_RETEST"
        ) {

            showToast(
                tr("paid")
            );

        } else if (
            error.message ===
            "NETWORK_ERROR"
        ) {

            showToast(
                tr("network")
            );

        } else {

            showToast(
                tr("error")
            );
        }

    } finally {

        setBusy(false);
    }
}


/* ============================================================
   CERTIFICATE
============================================================ */

async function showCertificate() {

    if (
        state.busy
    ) {

        return;
    }


    setBusy(true);


    try {

        const response =
            await fetch(
                "/api/certificate",
                {
                    method: "GET",

                    headers: {
                        "X-Telegram-Init-Data":
                            telegramInitData()
                    },

                    cache:
                        "no-store"
                }
            );


        if (!response.ok) {

            let detail =
                "";


            try {

                const data =
                    await response.json();

                detail =
                    data?.detail || "";

            } catch {

                detail =
                    "";
            }


            if (
                response.status === 403 ||
                detail ===
                    "REFERRALS_REQUIRED"
            ) {

                showInviteRequirement();

                return;
            }


            if (
                response.status === 404 ||
                detail ===
                    "NO_RESULT"
            ) {

                showToast(
                    tr(
                        "certificateNoResult"
                    )
                );

                return;
            }


            showToast(
                tr(
                    "certificateError"
                )
            );

            return;
        }


        const blob =
            await response.blob();


        const url =
            URL.createObjectURL(
                blob
            );


        const overlay =
            document.createElement(
                "div"
            );


        overlay.style.cssText = `
            position:fixed;
            inset:0;
            z-index:9999;
            padding:
                max(18px, env(safe-area-inset-top))
                16px
                max(18px, env(safe-area-inset-bottom));
            display:flex;
            flex-direction:column;
            align-items:center;
            justify-content:center;
            gap:14px;
            background:rgba(0,0,0,.88);
            backdrop-filter:blur(14px);
            -webkit-backdrop-filter:blur(14px);
        `;


        const image =
            document.createElement(
                "img"
            );


        image.src =
            url;


        image.alt =
            "ZAKO IQ Certificate";


        image.style.cssText = `
            display:block;
            width:min(100%, 620px);
            max-height:78dvh;
            object-fit:contain;
            border-radius:20px;
            box-shadow:
                0 25px 80px rgba(0,0,0,.55);
        `;


        const close =
            document.createElement(
                "button"
            );


        close.className =
            "primary-btn";


        close.type =
            "button";


        close.style.maxWidth =
            "620px";


        close.textContent =
            tr("back");


        close.addEventListener(
            "click",
            () => {

                URL.revokeObjectURL(
                    url
                );

                overlay.remove();
            }
        );


        overlay.appendChild(
            image
        );


        overlay.appendChild(
            close
        );


        document.body.appendChild(
            overlay
        );

    } catch (error) {

        console.error(
            "certificate:",
            error
        );


        showToast(
            tr(
                "certificateError"
            )
        );

    } finally {

        setBusy(false);
    }
}


/* ============================================================
   CERTIFICATE REQUIREMENT
============================================================ */

function showInviteRequirement() {

    const overlay =
        document.createElement(
            "div"
        );


    overlay.style.cssText = `
        position:fixed;
        inset:0;
        z-index:9998;
        padding:
            max(18px, env(safe-area-inset-top))
            18px
            max(18px, env(safe-area-inset-bottom));
        display:flex;
        align-items:center;
        justify-content:center;
        background:rgba(0,0,0,.72);
        backdrop-filter:blur(12px);
        -webkit-backdrop-filter:blur(12px);
    `;


    const card =
        document.createElement(
            "div"
        );


    card.style.cssText = `
        width:min(100%, 480px);
        padding:26px 20px 20px;
        border-radius:26px;
        border:1px solid rgba(255,255,255,.10);
        background:#151a25;
        text-align:center;
        box-shadow:0 25px 80px rgba(0,0,0,.45);
    `;


    card.innerHTML = `

        <div style="
            width:60px;
            height:60px;
            margin:0 auto 16px;
            display:flex;
            align-items:center;
            justify-content:center;
            border-radius:20px;
            background:rgba(139,108,255,.14);
            font-size:28px;
        ">
            🎓
        </div>


        <h2 style="
            margin:0 0 10px;
            font-size:23px;
            line-height:1.2;
        ">
            ${escapeHTML(
                tr("certificate")
            )}
        </h2>


        <p style="
            margin:0 0 20px;
            color:#aeb5c5;
            line-height:1.5;
            font-size:14px;
        ">
            ${escapeHTML(
                tr(
                    "certificateRequired"
                )
            )}
        </p>


        <button
            id="inviteModalBtn"
            class="primary-btn"
            type="button"
        >

            👥

            <span>
                ${escapeHTML(
                    tr("invite")
                )}
            </span>

            <span class="arrow">
                →
            </span>

        </button>


        <button
            id="closeInviteBtn"
            class="secondary-btn"
            type="button"
        >
            ${escapeHTML(
                tr("back")
            )}
        </button>
    `;


    overlay.appendChild(
        card
    );


    document.body.appendChild(
        overlay
    );


    document
        .getElementById(
            "inviteModalBtn"
        )
        ?.addEventListener(
            "click",
            () => {

                overlay.remove();

                shareInvite();
            }
        );


    document
        .getElementById(
            "closeInviteBtn"
        )
        ?.addEventListener(
            "click",
            () => {

                overlay.remove();
            }
        );
}


/* ============================================================
   SHARE
============================================================ */

function webAppPublicURL() {

    return (
        window.location.origin +
        "/app"
    );
}


function openTelegramShare(
    url,
    text
) {

    const shareURL =
        "https://t.me/share/url" +
        "?url=" +
        encodeURIComponent(
            url
        ) +
        "&text=" +
        encodeURIComponent(
            text
        );


    try {

        if (
            tg &&
            typeof tg.openTelegramLink ===
                "function"
        ) {

            tg.openTelegramLink(
                shareURL
            );

            return true;
        }


        window.open(
            shareURL,
            "_blank",
            "noopener,noreferrer"
        );


        return true;

    } catch (error) {

        console.error(
            "Telegram share:",
            error
        );

        return false;
    }
}


async function shareResult() {

    if (!state.result) {
        return;
    }


    const text =
        `🧠 IQ TEST\n\n` +
        `IQ SCORE: ${state.result.iq}\n` +
        `${state.result.correct}/${QUESTIONS_COUNT} • ${formatTime(
            state.result.elapsed
        )}\n\n` +
        `${tr("shareText")}`;


    const opened =
        openTelegramShare(
            webAppPublicURL(),
            text
        );


    if (!opened) {

        await copyText(
            text
        );
    }
}


/* ============================================================
   INVITE
============================================================ */

function getBotUsername() {

    return (
        state.config.bot_username ||
        ""
    )
        .replace(
            /^@/,
            ""
        )
        .trim();
}


function shareInvite() {

    const user =
        telegramUser();


    const userId =
        user?.id;


    const botUsername =
        getBotUsername();


    if (
        !botUsername ||
        !userId
    ) {

        showToast(
            tr("cannotOpen")
        );

        return;
    }


    const inviteURL =
        `https://t.me/${botUsername}` +
        `?start=ref_${userId}`;


    openTelegramShare(
        inviteURL,
        tr("inviteText")
    );
}


/* ============================================================
   COPY
============================================================ */

async function copyText(text) {

    try {

        if (
            navigator.clipboard &&
            typeof navigator.clipboard.writeText ===
                "function"
        ) {

            await navigator.clipboard.writeText(
                text
            );

            showToast(
                tr("copied")
            );

            return true;
        }

    } catch (error) {

        console.warn(
            "Clipboard:",
            error
        );
    }


    showToast(
        tr("cannotOpen")
    );

    return false;
}


/* ============================================================
   ZAKO
============================================================ */

function openZako() {

    const url =
        state.config.zako_url ||
        "https://t.me/zako_tbot";


    try {

        if (
            tg &&
            typeof tg.openTelegramLink ===
                "function"
        ) {

            tg.openTelegramLink(
                url
            );

            return;
        }


        window.open(
            url,
            "_blank",
            "noopener,noreferrer"
        );

    } catch (error) {

        console.error(
            "openZako:",
            error
        );


        showToast(
            tr("cannotOpen")
        );
    }
}


/* ============================================================
   RANKING
============================================================ */

async function loadRanking() {

    if (
        state.busy ||
        state.answerSubmitting
    ) {

        return;
    }


    activateScreen(
        "rankingScreen"
    );


    const screen =
        document.getElementById(
            "rankingScreen"
        );


    if (!screen) {
        return;
    }


    screen.innerHTML = `

        <div class="page-title">

            <div class="page-icon">
                🏆
            </div>


            <h1>
                ${escapeHTML(
                    tr("ranking")
                )}
            </h1>


            <p>
                ${escapeHTML(
                    tr("rankingDesc")
                )}
            </p>

        </div>


        <div
            id="rankingList"
            class="ranking-list"
        >

            <div class="empty-state">
                ${escapeHTML(
                    tr("loading")
                )}
            </div>

        </div>
    `;


    try {

        const data =
            await api(
                "/api/ranking"
            );


        const list =
            document.getElementById(
                "rankingList"
            );


        if (!list) {
            return;
        }


        if (
            !data ||
            !Array.isArray(
                data.items
            ) ||
            data.items.length === 0
        ) {

            list.innerHTML = `

                <div class="empty-state">
                    ${escapeHTML(
                        tr("noRanking")
                    )}
                </div>

            `;

            return;
        }


        list.innerHTML =
            data.items
                .map(
                    (
                        item,
                        index
                    ) => {

                        const name =
                            item.first_name ||
                            item.username ||
                            tr("user");


                        const score =
                            item.best_score ??
                            "—";


                        return `

                            <div
                                class="ranking-row"
                            >

                                <div
                                    class="ranking-position"
                                >
                                    ${index + 1}
                                </div>


                                <div
                                    class="ranking-user"
                                >

                                    <strong>
                                        ${escapeHTML(
                                            name
                                        )}
                                    </strong>


                                    ${
                                        item.username
                                            ? `
                                                <small>
                                                    @${escapeHTML(
                                                        item.username
                                                    )}
                                                </small>
                                              `
                                            : ""
                                    }

                                </div>


                                <div
                                    class="ranking-score"
                                >
                                    IQ ${escapeHTML(
                                        score
                                    )}
                                </div>

                            </div>
                        `;
                    }
                )
                .join("");

    } catch (error) {

        console.error(
            "ranking:",
            error
        );


        const list =
            document.getElementById(
                "rankingList"
            );


        if (list) {

            list.innerHTML = `

                <div class="empty-state">
                    ${escapeHTML(
                        error.message ===
                        "NETWORK_ERROR"
                            ? tr("network")
                            : tr("error")
                    )}
                </div>

            `;
        }
    }
}


/* ============================================================
   PROFILE
============================================================ */

async function loadProfile() {

    if (
        state.busy ||
        state.answerSubmitting
    ) {

        return;
    }


    activateScreen(
        "profileScreen"
    );


    const screen =
        document.getElementById(
            "profileScreen"
        );


    if (!screen) {
        return;
    }


    screen.innerHTML = `

        <div class="page-title">

            <div
                class="profile-avatar"
                id="profileAvatar"
            >
                …
            </div>


            <h1 id="profileName">
                ${escapeHTML(
                    tr("loading")
                )}
            </h1>


            <p>
                ${escapeHTML(
                    tr("profileDesc")
                )}
            </p>

        </div>


        <div
            class="profile-score"
        >

            <span>
                ${escapeHTML(
                    tr("bestIq")
                )}
            </span>


            <strong id="bestIq">
                —
            </strong>

        </div>


        <div class="profile-grid">


            <div class="stat-card">

                <strong id="profileRank">
                    —
                </strong>

                <span>
                    ${escapeHTML(
                        tr("rank")
                    )}
                </span>

            </div>


            <div class="stat-card">

                <strong id="profileAttempts">
                    0
                </strong>

                <span>
                    ${escapeHTML(
                        tr("tests")
                    )}
                </span>

            </div>


            <div class="stat-card">

                <strong id="profileReferrals">
                    0
                </strong>

                <span>
                    ${escapeHTML(
                        tr("referrals")
                    )}
                </span>

            </div>


        </div>


        <button
            id="inviteBtn"
            class="primary-btn"
            type="button"
        >

            👥

            <span>
                ${escapeHTML(
                    tr("invite")
                )}
            </span>

            <span class="arrow">
                →
            </span>

        </button>
    `;


    document
        .getElementById(
            "inviteBtn"
        )
        ?.addEventListener(
            "click",
            shareInvite
        );


    try {

        const profile =
            await api(
                "/api/profile"
            );


        if (
            !profile ||
            typeof profile !== "object"
        ) {

            throw new Error(
                "INVALID_PROFILE"
            );
        }


        state.profile =
            profile;


        const name =
            profile.first_name ||
            profile.username ||
            tr("user");


        const avatar =
            document.getElementById(
                "profileAvatar"
            );


        if (avatar) {

            avatar.textContent =
                String(
                    name
                )
                    .trim()
                    .charAt(0)
                    .toUpperCase() ||
                "?";
        }


        const title =
            document.getElementById(
                "profileName"
            );


        if (title) {

            title.textContent =
                name;
        }


        const score =
            document.getElementById(
                "bestIq"
            );


        if (score) {

            score.textContent =
                profile.best_score ??
                "—";
        }


        const rank =
            document.getElementById(
                "profileRank"
            );


        if (rank) {

            rank.textContent =
                profile.rank
                    ? `#${profile.rank}`
                    : "—";
        }


        const attempts =
            document.getElementById(
                "profileAttempts"
            );


        if (attempts) {

            attempts.textContent =
                profile.attempts ??
                0;
        }


        const referrals =
            document.getElementById(
                "profileReferrals"
            );


        if (referrals) {

            referrals.textContent =
                profile.referrals ??
                0;
        }

    } catch (error) {

        console.error(
            "profile:",
            error
        );


        showToast(
            error.message ===
            "NETWORK_ERROR"
                ? tr("network")
                : tr("noData")
        );
    }
}


/* ============================================================
   NAVIGATION
============================================================ */

function goHome() {

    stopTimer();


    state.session =
        null;


    state.answerSubmitting =
        false;


    renderHome();
}


function handleBack() {

    if (
        state.screen ===
        "home"
    ) {

        return;
    }


    if (
        state.screen ===
        "test"
    ) {

        const leave =
            window.confirm(
                tr("leaveTest")
            );


        if (!leave) {
            return;
        }


        stopTimer();


        state.session =
            null;


        state.answerSubmitting =
            false;


        goHome();

        return;
    }


    goHome();
}


/* ============================================================
   GLOBAL EVENTS
============================================================ */

function bindGlobalEvents() {

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
            loadRanking
        );


    document
        .getElementById(
            "profileBtn"
        )
        ?.addEventListener(
            "click",
            loadProfile
        );


    document
        .getElementById(
            "langBtn"
        )
        ?.addEventListener(
            "click",
            openLanguageModal
        );


    document
        .getElementById(
            "backBtn"
        )
        ?.addEventListener(
            "click",
            handleBack
        );


    document
        .querySelector(
            ".modal-backdrop"
        )
        ?.addEventListener(
            "click",
            closeLanguageModal
        );


    document
        .querySelectorAll(
            ".language-option"
        )
        .forEach(
            (button) => {

                button.addEventListener(
                    "click",
                    () => {

                        setLanguage(
                            button.dataset.lang
                        );
                    }
                );
            }
        );
}


/* ============================================================
   INIT
============================================================ */

async function init() {

    /*
     * Normalize language.
     */

    if (
        !SUPPORTED_LANGUAGES.includes(
            state.lang
        )
    ) {

        state.lang =
            "uz";


        localStorage.setItem(
            "iq_lang",
            "uz"
        );
    }


    /*
     * Telegram must be initialized
     * before authenticated API calls.
     */

    setupTelegram();

    applyTheme();


    /*
     * Bind buttons BEFORE loading config.
     *
     * Therefore a slow /api/config request
     * cannot make the home screen feel dead.
     */

    bindGlobalEvents();


    renderHome();

    updateLanguageButton();


    /*
     * Config is only needed for referral
     * and ZAKO link.
     */

    await loadConfig();


    /*
     * Telegram theme changes.
     */

    if (
        tg &&
        typeof tg.onEvent ===
            "function"
    ) {

        tg.onEvent(
            "themeChanged",
            applyTheme
        );
    }


    state.initialized =
        true;
}


/* ============================================================
   START
============================================================ */

init().catch(
    (error) => {

        console.error(
            "App initialization:",
            error
        );


        showToast(
            tr("error")
        );
    }
);