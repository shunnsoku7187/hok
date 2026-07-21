(() => {
    "use strict";

    const API_URL = "../api/prediction_votes.php";
    const POLL_INTERVAL_MS = 5000;
    const roundId = document.body.dataset.roundId;
    const closesAt = new Date(document.body.dataset.closesAt);
    const resultReady = document.body.dataset.resultReady === "true";
    const cards = [...document.querySelectorAll("[data-prediction-id]")];
    const resultRounds = [...document.querySelectorAll("[data-result-round-id]")];
    const liveStatus = document.getElementById("live-status");
    const toast = document.getElementById("toast");
    let toastTimer;
    let requestInFlight = false;

    function createVoterToken() {
        const storageKey = "hok-prediction-voter-token";
        let token = localStorage.getItem(storageKey);
        if (!token) {
            token = crypto.randomUUID
                ? crypto.randomUUID()
                : `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
            localStorage.setItem(storageKey, token);
        }
        return token;
    }

    const voterToken = createVoterToken();

    function setConnection(state, label) {
        liveStatus.className = `live-status ${state}`;
        liveStatus.lastChild.textContent = label;
    }

    function showToast(message) {
        clearTimeout(toastTimer);
        toast.textContent = message;
        toast.classList.add("visible");
        toastTimer = setTimeout(() => toast.classList.remove("visible"), 2200);
    }

    function setButtonsEnabled(enabled) {
        cards.forEach((card) => {
            card.querySelectorAll(".vote-button").forEach((button) => {
                button.disabled = !enabled;
            });
        });
    }

    function renderMarket(card, market, ownVote) {
        const doCount = market?.do ?? 0;
        const notCount = market?.not ?? 0;
        const total = doCount + notCount;
        const doPercent = total ? Math.round((doCount / total) * 100) : 50;

        card.querySelector(".vote-total").textContent = `${total}票`;
        card.querySelector(".do-count").textContent = `DO ${doCount}票`;
        card.querySelector(".not-count").textContent = `NOT ${notCount}票`;
        card.querySelector(".crowd-do").style.width = `${doPercent}%`;
        card.querySelector(".crowd-not").style.width = `${100 - doPercent}%`;
        card.querySelector(".crowd-track").setAttribute(
            "aria-label",
            total ? `DO ${doPercent}パーセント、NOT ${100 - doPercent}パーセント` : "まだ投票はありません",
        );

        card.querySelectorAll(".vote-button").forEach((button) => {
            const selected = button.dataset.choice === ownVote;
            button.classList.toggle("selected", selected);
            button.setAttribute("aria-pressed", String(selected));
        });
    }

    function render(data) {
        cards.forEach((card) => {
            const predictionId = card.dataset.predictionId;
            renderMarket(card, data.markets[predictionId], data.own_votes?.[predictionId]);
        });

        const closed = data.closed || Date.now() > closesAt.getTime();
        setButtonsEnabled(!closed);
        setConnection(
            closed ? (resultReady ? "result" : "closed") : "online",
            closed ? (resultReady ? "結果発表中" : "投票終了") : "リアルタイム集計中",
        );
    }

    async function fetchVotes() {
        if (requestInFlight) return;
        requestInFlight = true;
        try {
            const url = `${API_URL}?round_id=${encodeURIComponent(roundId)}&voter_token=${encodeURIComponent(voterToken)}&_=${Date.now()}`;
            const response = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "集計を取得できませんでした");
            render(data);
        } catch (error) {
            setButtonsEnabled(false);
            setConnection("error", "集計サーバーに接続できません");
        } finally {
            requestInFlight = false;
        }
    }

    async function submitVote(predictionId, choice) {
        setButtonsEnabled(false);
        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json", Accept: "application/json" },
                body: JSON.stringify({
                    round_id: roundId,
                    prediction_id: predictionId,
                    choice,
                    voter_token: voterToken,
                }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "投票を送信できませんでした");
            render(data);
            showToast(choice === "do" ? "DOに投票しました" : "NOTに投票しました");
        } catch (error) {
            showToast(error.message);
            await fetchVotes();
        }
    }

    cards.forEach((card) => {
        card.querySelectorAll(".vote-button").forEach((button) => {
            button.addEventListener("click", () => submitVote(card.dataset.predictionId, button.dataset.choice));
        });
    });

    async function fetchArchivedResults() {
        await Promise.all(resultRounds.map(async (resultRound) => {
            const resultRoundId = resultRound.dataset.resultRoundId;
            try {
                const url = `${API_URL}?round_id=${encodeURIComponent(resultRoundId)}&_=${Date.now()}`;
                const response = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "最終票を取得できませんでした");
                resultRound.querySelectorAll("[data-result-prediction-id]").forEach((item) => {
                    const market = data.markets?.[item.dataset.resultPredictionId];
                    item.querySelector(".result-vote-summary").textContent = market
                        ? `最終投票 DO ${market.do} / NOT ${market.not}`
                        : "最終投票データなし";
                });
            } catch (_error) {
                resultRound.querySelectorAll(".result-vote-summary").forEach((label) => {
                    label.textContent = "最終投票を取得できません";
                });
            }
        }));
    }

    fetchVotes();
    fetchArchivedResults();
    window.setInterval(fetchVotes, POLL_INTERVAL_MS);
})();
