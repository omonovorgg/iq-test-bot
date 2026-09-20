"use strict";

(() => {
  /*
   * =========================================================
   * IQTestPro PAYMENT
   * =========================================================
   *
   * Bu modul:
   *
   * 1. To'lov yaratadi
   * 2. To'lov holatini tekshiradi
   * 3. To'lov ma'lumotlarini Mini App ichida ko'rsatadi
   * 4. Telegram WebApp initData bilan backendga murojaat qiladi
   *
   * Backend endpointlar:
   *
   * POST /api/payment/create
   * GET  /api/payment/{payment_id}
   * POST /api/payment/result/unlock
   *
   * =========================================================
   */

  const PAYMENT = {};

  let currentPayment = null;
  let pollingTimer = null;

  /*
   * ---------------------------------------------------------
   * TELEGRAM
   * ---------------------------------------------------------
   */

  function getTelegram() {
    return window.Telegram?.WebApp || null;
  }

  function getInitData() {
    const telegram = getTelegram();

    return telegram?.initData || "";
  }


  /*
   * ---------------------------------------------------------
   * API
   * ---------------------------------------------------------
   */

  async function api(path, options = {}) {

    const headers = {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
      ...(options.headers || {})
    };

    const response = await fetch(path, {
      ...options,
      headers,
      cache: "no-store"
    });


    let data = {};

    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }


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


  /*
   * ---------------------------------------------------------
   * CREATE PAYMENT
   * ---------------------------------------------------------
   */

  async function createPayment(
    purpose = "retest"
  ) {

    try {

      const data =
        await api(
          "/api/payment/create",
          {
            method: "POST",

            body: JSON.stringify({
              purpose
            })
          }
        );


      currentPayment = {
        id:
          Number(data.payment_id),

        amount:
          Number(data.amount || 0),

        purpose:
          data.purpose || purpose,

        status:
          data.status || "pending",

        cards:
          Array.isArray(data.cards)
            ? data.cards
            : []
      };


      return currentPayment;

    } catch (error) {

      console.error(
        "[IQTestPro Payment] create error:",
        error
      );

      throw error;
    }
  }


  /*
   * ---------------------------------------------------------
   * GET PAYMENT STATUS
   * ---------------------------------------------------------
   */

  async function getPaymentStatus(
    paymentId
  ) {

    if (!paymentId) {
      throw new Error(
        "PAYMENT_ID_REQUIRED"
      );
    }


    try {

      const data =
        await api(
          `/api/payment/${encodeURIComponent(paymentId)}`,
          {
            method: "GET"
          }
        );


      currentPayment = {
        ...(currentPayment || {}),

        id:
          Number(
            data.payment_id ??
            paymentId
          ),

        amount:
          Number(
            data.amount ??
            currentPayment?.amount ??
            0
          ),

        purpose:
          data.purpose ??
          currentPayment?.purpose ??
          "retest",

        status:
          data.status ||
          "pending",

        cards:
          Array.isArray(data.cards)
            ? data.cards
            : (
              currentPayment?.cards ||
              []
            )
      };


      return currentPayment;

    } catch (error) {

      console.error(
        "[IQTestPro Payment] status error:",
        error
      );

      throw error;
    }
  }


  /*
   * ---------------------------------------------------------
   * START POLLING
   * ---------------------------------------------------------
   */

  function stopPolling() {

    if (pollingTimer) {

      clearInterval(
        pollingTimer
      );

      pollingTimer = null;
    }
  }


  function startPolling(
    paymentId,
    options = {}
  ) {

    stopPolling();


    const interval =
      Number(
        options.interval || 3000
      );


    const maxAttempts =
      Number(
        options.maxAttempts || 100
      );


    let attempts = 0;


    pollingTimer =
      setInterval(
        async () => {

          attempts += 1;


          try {

            const payment =
              await getPaymentStatus(
                paymentId
              );


            if (
              payment.status ===
              "approved"
            ) {

              stopPolling();


              if (
                typeof options.onApproved ===
                "function"
              ) {

                options.onApproved(
                  payment
                );
              }

              return;
            }


            if (
              payment.status ===
              "rejected"
            ) {

              stopPolling();


              if (
                typeof options.onRejected ===
                "function"
              ) {

                options.onRejected(
                  payment
                );
              }

              return;
            }


            if (
              attempts >= maxAttempts
            ) {

              stopPolling();


              if (
                typeof options.onTimeout ===
                "function"
              ) {

                options.onTimeout(
                  payment
                );
              }

            }

          } catch (error) {

            console.error(
              "[IQTestPro Payment] polling error:",
              error
            );


            if (
              attempts >= maxAttempts
            ) {

              stopPolling();


              if (
                typeof options.onError ===
                "function"
              ) {

                options.onError(
                  error
                );
              }

            }

          }

        },
        interval
      );


    return stopPolling;
  }


  /*
   * ---------------------------------------------------------
   * RESULT PAYMENT UNLOCK
   * ---------------------------------------------------------
   */

  async function unlockResult(
    paymentId
  ) {

    if (!paymentId) {

      throw new Error(
        "PAYMENT_ID_REQUIRED"
      );
    }


    try {

      const data =
        await api(
          "/api/payment/result/unlock",
          {
            method: "POST",

            body: JSON.stringify({
              payment_id:
                Number(paymentId)
            })
          }
        );


      return data;

    } catch (error) {

      console.error(
        "[IQTestPro Payment] result unlock error:",
        error
      );

      throw error;
    }
  }


  /*
   * ---------------------------------------------------------
   * PAYMENT UI
   * ---------------------------------------------------------
   *
   * Bu funksiya boshqa app.js kodlari uchun
   * oddiy modal yaratadi.
   *
   * Agar app.js o'z payment UI'sini ishlatsa,
   * bu modal ishlatilishi shart emas.
   */

  function removePaymentModal() {

    const existing =
      document.getElementById(
        "iq-payment-modal"
      );

    if (existing) {
      existing.remove();
    }
  }


  function escapeHTML(value) {

    return String(
      value ?? ""
    ).replace(
      /[&<>"']/g,
      character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[character]
    );
  }


  function showPaymentModal(
    payment,
    options = {}
  ) {

    removePaymentModal();


    const cards =
      Array.isArray(payment.cards)
        ? payment.cards
        : [];


    const cardHTML =
      cards.length
        ? cards
            .map(card => {

              const number =
                escapeHTML(
                  card.card_number ||
                  card.number ||
                  ""
                );

              const holder =
                escapeHTML(
                  card.holder ||
                  ""
                );


              return `
                <div
                  style="
                    padding:14px;
                    margin-top:10px;
                    border-radius:16px;
                    background:rgba(255,255,255,.05);
                    border:1px solid rgba(255,255,255,.09);
                  "
                >

                  <div
                    style="
                      font-size:17px;
                      font-weight:800;
                      letter-spacing:1px;
                    "
                  >
                    ${number}
                  </div>

                  ${
                    holder
                      ? `
                        <div
                          style="
                            margin-top:5px;
                            opacity:.65;
                            font-size:13px;
                          "
                        >
                          ${holder}
                        </div>
                      `
                      : ""
                  }

                </div>
              `;

            })
            .join("")
        : `
          <div
            style="
              padding:14px;
              border-radius:14px;
              background:rgba(255,255,255,.05);
              opacity:.75;
            "
          >
            To'lov kartasi mavjud emas.
          </div>
        `;


    const modal =
      document.createElement(
        "div"
      );


    modal.id =
      "iq-payment-modal";


    modal.style.cssText = `
      position:fixed;
      inset:0;
      z-index:99999;
      display:flex;
      align-items:flex-end;
      justify-content:center;
      background:rgba(0,0,0,.72);
      padding:14px;
      box-sizing:border-box;
    `;


    modal.innerHTML = `
      <div
        style="
          width:100%;
          max-width:520px;
          max-height:90vh;
          overflow:auto;
          background:#111524;
          border:1px solid rgba(255,255,255,.10);
          border-radius:28px;
          padding:22px;
          box-sizing:border-box;
          color:#fff;
          box-shadow:0 25px 80px rgba(0,0,0,.55);
        "
      >

        <div
          style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:10px;
          "
        >

          <h2
            style="
              margin:0;
              font-size:21px;
            "
          >
            💳 To'lov
          </h2>

          <button
            id="iq-payment-close"
            type="button"
            style="
              width:38px;
              height:38px;
              border:0;
              border-radius:50%;
              background:rgba(255,255,255,.08);
              color:#fff;
              font-size:20px;
            "
          >
            ×
          </button>

        </div>


        <div
          style="
            margin-top:18px;
            padding:18px;
            border-radius:20px;
            background:
              linear-gradient(
                135deg,
                rgba(126,87,255,.20),
                rgba(45,163,255,.10)
              );
            border:1px solid rgba(126,87,255,.22);
          "
        >

          <div
            style="
              font-size:13px;
              opacity:.65;
            "
          >
            Summa
          </div>

          <div
            style="
              margin-top:4px;
              font-size:30px;
              font-weight:900;
            "
          >
            ${Number(
              payment.amount || 0
            ).toLocaleString("uz-UZ")} so'm
          </div>

        </div>


        <div
          style="
            margin-top:20px;
            font-size:14px;
            opacity:.72;
            line-height:1.5;
          "
        >
          To'lovni kartalardan biriga amalga
          oshiring. Keyin chek yoki skrinshotni
          Telegram botga yuboring.
        </div>


        <div
          style="
            margin-top:15px;
          "
        >

          <b
            style="
              font-size:14px;
            "
          >
            To'lov kartalari
          </b>

          ${cardHTML}

        </div>


        <div
          style="
            margin-top:20px;
            padding:14px;
            border-radius:16px;
            background:rgba(255,193,7,.08);
            border:1px solid rgba(255,193,7,.15);
            color:#f3d77a;
            font-size:13px;
            line-height:1.5;
          "
        >
          ⏳ Chek yuborilgach admin tasdiqlaydi.
          Tasdiqlangandan keyin test avtomatik
          ochiladi.
        </div>


        <button
          id="iq-payment-open-bot"
          type="button"
          style="
            width:100%;
            margin-top:18px;
            height:52px;
            border:0;
            border-radius:17px;
            background:
              linear-gradient(
                135deg,
                #7657ff,
                #4a8dff
              );
            color:#fff;
            font-size:15px;
            font-weight:800;
          "
        >
          📩 Botga chek yuborish
        </button>


        <button
          id="iq-payment-refresh"
          type="button"
          style="
            width:100%;
            margin-top:10px;
            height:48px;
            border:1px solid rgba(255,255,255,.10);
            border-radius:16px;
            background:rgba(255,255,255,.05);
            color:#fff;
            font-size:14px;
            font-weight:700;
          "
        >
          🔄 To'lov holatini tekshirish
        </button>

      </div>
    `;


    document.body.appendChild(
      modal
    );


    document
      .getElementById(
        "iq-payment-close"
      )
      ?.addEventListener(
        "click",
        () => {
          removePaymentModal();
        }
      );


    document
      .getElementById(
        "iq-payment-refresh"
      )
      ?.addEventListener(
        "click",
        async () => {

          const button =
            document.getElementById(
              "iq-payment-refresh"
            );

          if (button) {
            button.disabled = true;
            button.textContent =
              "Tekshirilmoqda…";
          }


          try {

            const updated =
              await getPaymentStatus(
                payment.id
              );


            if (
              updated.status ===
              "approved"
            ) {

              stopPolling();

              removePaymentModal();


              if (
                typeof options.onApproved ===
                "function"
              ) {

                options.onApproved(
                  updated
                );

              }

              return;
            }


            if (
              updated.status ===
              "rejected"
            ) {

              stopPolling();

              if (button) {
                button.disabled =
                  false;

                button.textContent =
                  "🔄 To'lov holatini tekshirish";
              }


              if (
                typeof options.onRejected ===
                "function"
              ) {

                options.onRejected(
                  updated
                );

              }

              return;
            }


            if (button) {

              button.disabled =
                false;

              button.textContent =
                "🔄 Hali tasdiqlanmagan";
            }

          } catch (error) {

            console.error(
              "[IQTestPro Payment] refresh error:",
              error
            );


            if (button) {

              button.disabled =
                false;

              button.textContent =
                "🔄 Qayta tekshirish";
            }

          }

        }
      );


    document
      .getElementById(
        "iq-payment-open-bot"
      )
      ?.addEventListener(
        "click",
        () => {

          const telegram =
            getTelegram();


          /*
           * Telegram bot username backend
           * config orqali kelishi mumkin.
           */

          const username =
            payment.bot_username ||
            window.IQTestPro?.botUsername ||
            "";


          if (
            username &&
            telegram?.openTelegramLink
          ) {

            telegram.openTelegramLink(
              `https://t.me/${username}?start=pay_${payment.id}`
            );

            return;
          }


          /*
           * Agar bot username frontendda
           * mavjud bo'lmasa, Telegram chat
           * uchun oddiy share/open fallback.
           */

          const url =
            `https://t.me/share/url?` +
            `text=${encodeURIComponent(
              `To'lov #${payment.id} uchun chek yuboraman`
            )}`;


          if (
            telegram?.openTelegramLink
          ) {

            telegram.openTelegramLink(
              url
            );

          } else {

            window.open(
              url,
              "_blank"
            );

          }

        }
      );


    /*
     * Har 4 sekundda holatni tekshirish.
     */

    startPolling(
      payment.id,
      {
        interval:4000,

        maxAttempts:225,

        onApproved: paymentData => {

          removePaymentModal();


          if (
            typeof options.onApproved ===
            "function"
          ) {

            options.onApproved(
              paymentData
            );

          }

        },

        onRejected: paymentData => {

          if (
            typeof options.onRejected ===
            "function"
          ) {

            options.onRejected(
              paymentData
            );

          }

        },

        onTimeout: paymentData => {

          if (
            typeof options.onTimeout ===
            "function"
          ) {

            options.onTimeout(
              paymentData
            );

          }

        }

      }
    );


    return modal;
  }


  /*
   * ---------------------------------------------------------
   * HIGH LEVEL START
   * ---------------------------------------------------------
   */

  async function openPayment(
    purpose = "retest",
    options = {}
  ) {

    try {

      const payment =
        await createPayment(
          purpose
        );


      /*
       * Backend cards qaytarmasa,
       * status endpointdan yana olish.
       */

      if (
        !payment.cards ||
        !payment.cards.length
      ) {

        try {

          const updated =
            await getPaymentStatus(
              payment.id
            );

          Object.assign(
            payment,
            updated
          );

        } catch (_) {}

      }


      showPaymentModal(
        payment,
        options
      );


      return payment;

    } catch (error) {

      console.error(
        "[IQTestPro Payment] open error:",
        error
      );


      if (
        typeof options.onError ===
        "function"
      ) {

        options.onError(
          error
        );

      }


      throw error;
    }
  }


  /*
   * ---------------------------------------------------------
   * PUBLIC API
   * ---------------------------------------------------------
   */

  PAYMENT.create =
    createPayment;

  PAYMENT.status =
    getPaymentStatus;

  PAYMENT.open =
    openPayment;

  PAYMENT.unlockResult =
    unlockResult;

  PAYMENT.startPolling =
    startPolling;

  PAYMENT.stopPolling =
    stopPolling;

  PAYMENT.remove =
    removePaymentModal;

  PAYMENT.current =
    () => currentPayment;


  window.IQTestProPayment =
    PAYMENT;


  console.log(
    "[IQTestPro] payment.js loaded"
  );

})();