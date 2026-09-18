(function () {
    "use strict";

    console.log("[ZAKO IQ PAYMENT] payment.js loaded");

    let currentPayment = null;
    let pollingTimer = null;
    let modal = null;

    function getTelegram() {
        return window.Telegram?.WebApp || null;
    }

    function getInitData() {
        const telegram = getTelegram();

        return telegram?.initData || "";
    }

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

        let data = null;

        try {
            data = await response.json();
        } catch {
            data = null;
        }

        if (!response.ok) {
            const error = new Error(
                data?.detail ||
                data?.message ||
                `HTTP_${response.status}`
            );

            error.status = response.status;
            error.detail = data?.detail || "";

            throw error;
        }

        return data;
    }

    function money(value) {
        return Number(value || 0).toLocaleString("uz-UZ");
    }

    function escapeHTML(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function addStyles() {
        if (document.getElementById("zako-payment-styles")) {
            return;
        }

        const style = document.createElement("style");

        style.id = "zako-payment-styles";

        style.textContent = `
            .zako-pay-overlay {
                position: fixed;
                inset: 0;
                z-index: 999999;
                background: rgba(0,0,0,.82);
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 16px;
                box-sizing: border-box;
            }

            .zako-pay-modal {
                width: 100%;
                max-width: 520px;
                max-height: 90vh;
                overflow-y: auto;
                background: #10131d;
                color: #fff;
                border: 1px solid rgba(255,255,255,.12);
                border-radius: 24px;
                padding: 22px;
                box-sizing: border-box;
                box-shadow: 0 20px 80px rgba(0,0,0,.6);
            }

            .zako-pay-title {
                font-size: 23px;
                font-weight: 900;
                margin-bottom: 8px;
            }

            .zako-pay-subtitle {
                color: #aab1c2;
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 18px;
            }

            .zako-pay-price {
                font-size: 30px;
                font-weight: 900;
                text-align: center;
                padding: 18px;
                border-radius: 18px;
                background: rgba(139,108,255,.14);
                border: 1px solid rgba(139,108,255,.28);
                margin-bottom: 18px;
            }

            .zako-pay-card {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                padding: 14px;
                margin-bottom: 10px;
                border-radius: 16px;
                background: #171b27;
                border: 1px solid rgba(255,255,255,.08);
            }

            .zako-pay-card-info {
                min-width: 0;
            }

            .zako-pay-card-number {
                font-size: 16px;
                font-weight: 800;
                word-break: break-all;
            }

            .zako-pay-card-holder {
                color: #969daf;
                font-size: 12px;
                margin-top: 4px;
            }

            .zako-pay-copy {
                flex-shrink: 0;
                border: 0;
                border-radius: 12px;
                padding: 9px 12px;
                background: #292f40;
                color: #fff;
                font-weight: 800;
                cursor: pointer;
            }

            .zako-pay-main {
                width: 100%;
                border: 0;
                border-radius: 16px;
                padding: 15px;
                margin-top: 10px;
                background: #8b6cff;
                color: #fff;
                font-size: 16px;
                font-weight: 800;
                cursor: pointer;
            }

            .zako-pay-secondary {
                width: 100%;
                border: 1px solid rgba(255,255,255,.12);
                border-radius: 16px;
                padding: 14px;
                margin-top: 10px;
                background: transparent;
                color: #fff;
                font-size: 15px;
                font-weight: 700;
                cursor: pointer;
            }

            .zako-pay-status {
                text-align: center;
                color: #aab1c2;
                font-size: 13px;
                line-height: 1.5;
                margin-top: 14px;
            }

            .zako-pay-success {
                text-align: center;
                padding: 15px 0;
            }

            .zako-pay-success-icon {
                font-size: 52px;
                margin-bottom: 10px;
            }

            .zako-pay-loading {
                text-align: center;
                padding: 35px 10px;
                color: #aab1c2;
            }
        `;

        document.head.appendChild(style);
    }

    function closePayment() {
        if (pollingTimer) {
            clearInterval(pollingTimer);
            pollingTimer = null;
        }

        if (modal) {
            modal.remove();
            modal = null;
        }

        currentPayment = null;
    }

    function createModal() {
        addStyles();

        closePayment();

        modal = document.createElement("div");

        modal.className = "zako-pay-overlay";

        modal.innerHTML = `
            <div class="zako-pay-modal">

                <div class="zako-pay-title">
                    💳 To‘lov
                </div>

                <div class="zako-pay-subtitle">
                    Keyingi IQ testni boshlash uchun
                    to‘lovni amalga oshiring.
                </div>

                <div id="zakoPayContent">
                    <div class="zako-pay-loading">
                        To‘lov ma’lumotlari yuklanmoqda...
                    </div>
                </div>

            </div>
        `;

        document.body.appendChild(modal);
    }

    function showPaymentContent(data) {
        const content =
            document.getElementById("zakoPayContent");

        if (!content) {
            return;
        }

        const cards = Array.isArray(data.cards)
            ? data.cards
            : [];

        let cardsHTML = "";

        cards.forEach(card => {
            cardsHTML += `
                <div class="zako-pay-card">

                    <div class="zako-pay-card-info">

                        <div class="zako-pay-card-number">
                            ${escapeHTML(card.card_number)}
                        </div>

                        <div class="zako-pay-card-holder">
                            ${escapeHTML(card.holder || "")}
                        </div>

                    </div>

                    <button
                        type="button"
                        class="zako-pay-copy"
                        data-card="${escapeHTML(card.card_number)}"
                    >
                        Nusxa
                    </button>

                </div>
            `;
        });

        content.innerHTML = `
            <div class="zako-pay-price">
                ${money(data.amount)} so‘m
            </div>

            ${
                cardsHTML ||
                `
                <div class="zako-pay-status">
                    ❌ Hozircha faol karta mavjud emas.
                </div>
                `
            }

            <button
                type="button"
                class="zako-pay-main"
                id="zakoOpenBotPayment"
            >
                🤖 Botga o'tish va chek yuborish
            </button>

            <button
                type="button"
                class="zako-pay-secondary"
                id="zakoCheckPayment"
            >
                🔄 To‘lovni tekshirish
            </button>

            <button
                type="button"
                class="zako-pay-secondary"
                id="zakoClosePayment"
            >
                Yopish
            </button>

            <div
                class="zako-pay-status"
                id="zakoPaymentStatus"
            >
                1. Kartaga pul o'tkazing.
                <br>
                2. Chekni botga yuboring.
                <br>
                3. Admin tasdiqlashini kuting.
            </div>
        `;

        document
            .querySelectorAll(".zako-pay-copy")
            .forEach(button => {

                button.addEventListener(
                    "click",
                    async () => {

                        const card =
                            button.getAttribute(
                                "data-card"
                            ) || "";

                        try {
                            await navigator.clipboard
                                .writeText(card);

                            const old =
                                button.textContent;

                            button.textContent = "✓";

                            setTimeout(() => {
                                button.textContent = old;
                            }, 1200);

                        } catch {
                            alert(
                                "Karta raqami: " +
                                card
                            );
                        }
                    }
                );
            });

        document
            .getElementById("zakoOpenBotPayment")
            ?.addEventListener(
                "click",
                openBotPayment
            );

        document
            .getElementById("zakoCheckPayment")
            ?.addEventListener(
                "click",
                checkPayment
            );

        document
            .getElementById("zakoClosePayment")
            ?.addEventListener(
                "click",
                closePayment
            );
    }

    async function openBotPayment() {
        if (!currentPayment) {
            return;
        }

        const botUsername =
            window.__ZAKO_BOT_USERNAME ||
            "iqtest_ubot";

        const url =
            `https://t.me/${botUsername}?start=pay_${currentPayment.payment_id}`;

        const telegram = getTelegram();

        try {
            if (
                telegram &&
                typeof telegram.openTelegramLink === "function"
            ) {
                telegram.openTelegramLink(url);
            } else {
                window.open(
                    url,
                    "_blank"
                );
            }
        } catch {
            window.open(
                url,
                "_blank"
            );
        }

        const status =
            document.getElementById(
                "zakoPaymentStatus"
            );

        if (status) {
            status.innerHTML =
                "Botga o'ting → chek/skrinshotni yuboring → admin tasdiqlashini kuting → keyin Mini App'ga qayting.";
        }
    }

    async function checkPayment() {
        if (!currentPayment) {
            return;
        }

        const status =
            document.getElementById(
                "zakoPaymentStatus"
            );

        if (status) {
            status.textContent =
                "⏳ To‘lov holati tekshirilmoqda...";
        }

        try {
            const data =
                await api(
                    `/api/payment/${currentPayment.payment_id}`
                );

            if (data.status === "approved") {
                paymentApproved();
                return;
            }

            if (data.status === "rejected") {

                if (status) {
                    status.textContent =
                        "❌ To‘lov admin tomonidan rad etilgan.";
                }

                return;
            }

            if (status) {
                status.innerHTML =
                    "⏳ To‘lov hali tasdiqlanmagan.<br>Chek yuborganingizni tekshiring.";
            }

        } catch (error) {

            console.error(
                "[ZAKO IQ PAYMENT] status:",
                error
            );

            if (status) {
                status.textContent =
                    "❌ Tekshirishda xatolik yuz berdi.";
            }
        }
    }

    function startPolling() {
        if (pollingTimer) {
            clearInterval(pollingTimer);
        }

        pollingTimer =
            setInterval(
                checkPayment,
                7000
            );
    }

    function paymentApproved() {

        if (pollingTimer) {
            clearInterval(pollingTimer);
            pollingTimer = null;
        }

        const content =
            document.getElementById(
                "zakoPayContent"
            );

        if (!content) {
            return;
        }

        content.innerHTML = `
            <div class="zako-pay-success">

                <div class="zako-pay-success-icon">
                    ✅
                </div>

                <div class="zako-pay-title">
                    To‘lov tasdiqlandi
                </div>

                <div class="zako-pay-subtitle">
                    Yangi testingiz ochilmoqda...
                </div>

            </div>
        `;

        setTimeout(() => {

            closePayment();

            /*
             * To‘lov tasdiqlangandan keyin
             * app.js dagi startTest() ishlaydi.
             */
            if (
                typeof window.startTest ===
                "function"
            ) {
                window.startTest();
            } else {
                window.location.reload();
            }

        }, 700);
    }

    async function openPayment() {

        createModal();

        try {

            const data =
                await api(
                    "/api/payment/create",
                    {
                        method: "POST",

                        body: JSON.stringify({
                            purpose: "retest"
                        })
                    }
                );

            if (
                !data ||
                !data.payment_id
            ) {
                throw new Error(
                    "INVALID_PAYMENT"
                );
            }

            currentPayment = data;

if (data.status === "approved" || data.already_approved === true) {
    paymentApproved();
    return;
}

showPaymentContent(data);

startPolling();

        } catch (error) {

            console.error(
                "[ZAKO IQ PAYMENT] create:",
                error
            );

            const content =
                document.getElementById(
                    "zakoPayContent"
                );

            if (!content) {
                return;
            }

            if (
                error.detail ===
                "NO_PAYMENT_CARD"
            ) {

                content.innerHTML = `
                    <div class="zako-pay-status">
                        ❌ Hozircha faol karta mavjud emas.
                    </div>

                    <button
                        type="button"
                        class="zako-pay-secondary"
                        id="zakoClosePayment"
                    >
                        Yopish
                    </button>
                `;

            } else {

                content.innerHTML = `
                    <div class="zako-pay-status">
                        ❌ To‘lov oynasini ochishda xatolik.
                        <br><br>
                        Qayta urinib ko‘ring.
                    </div>

                    <button
                        type="button"
                        class="zako-pay-secondary"
                        id="zakoClosePayment"
                    >
                        Yopish
                    </button>
                `;
            }

            document
                .getElementById(
                    "zakoClosePayment"
                )
                ?.addEventListener(
                    "click",
                    closePayment
                );
        }
    }

    /*
     * MUHIM:
     *
     * Endi ikkala tugmani ham ushlaymiz:
     *
     * #retestBtn
     * #startBtn
     *
     * #startBtn kerak, chunki foydalanuvchi
     * bosh sahifadan qayta test boshlashi mumkin.
     */

    document.addEventListener(
        "click",
        function (event) {

            const button =
                event.target.closest?.(
                    "#retestBtn, #startBtn"
                );

            if (!button) {
                return;
            }

            event.preventDefault();
            event.stopImmediatePropagation();

            openPayment();
        },
        true
    );

    window.openZakoPayment =
        openPayment;

    console.log(
        "[ZAKO IQ PAYMENT] ready"
    );

})();