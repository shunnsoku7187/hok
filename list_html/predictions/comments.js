(() => {
    "use strict";

    const API_URL = "../api/prediction_comments.php";
    const POLL_INTERVAL_MS = 10000;
    const roundId = document.body.dataset.roundId;
    const form = document.getElementById("comment-form");
    const nicknameInput = document.getElementById("comment-nickname");
    const heroInput = document.getElementById("comment-hero");
    const bodyInput = document.getElementById("comment-body");
    const bodyLabel = document.getElementById("comment-body-label");
    const predictionFields = document.getElementById("prediction-fields");
    const submitButton = document.getElementById("comment-submit");
    const list = document.getElementById("comment-list");
    const count = document.getElementById("comment-count");
    const status = document.getElementById("comment-status");
    let requestInFlight = false;
    let replyTarget = null;

    function voterToken() {
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

    const token = voterToken();

    function formatDate(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime())
            ? ""
            : new Intl.DateTimeFormat("ja-JP", {
                year: "numeric", month: "2-digit", day: "2-digit",
                hour: "2-digit", minute: "2-digit",
            }).format(date);
    }

    function setStatus(message, isError = false) {
        status.textContent = message;
        status.classList.toggle("error", isError);
    }

    function actionButton(label, className, onClick) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = className;
        button.textContent = label;
        button.addEventListener("click", onClick);
        return button;
    }

    function setReplyTarget(comment = null) {
        replyTarget = comment;
        const replying = comment !== null;
        predictionFields.hidden = replying;
        heroInput.required = !replying;
        bodyLabel.textContent = replying ? "コメント本文" : "予想理由";
        submitButton.textContent = replying ? "返信する" : "予想を投稿";
        document.getElementById("reply-target").hidden = !replying;
        if (replying) {
            document.getElementById("reply-target-name").textContent = `${comment.nickname} #${comment.id} へ返信`;
            bodyInput.focus();
        }
    }

    function renderComment(comment, childrenByParent, depth = 0) {
        const item = document.createElement("article");
        item.className = `comment-item depth-${Math.min(depth, 2)}`;
        item.dataset.commentId = String(comment.id);

        const header = document.createElement("div");
        header.className = "comment-meta";
        const author = document.createElement("strong");
        author.textContent = comment.nickname;
        const id = document.createElement("span");
        id.textContent = `#${comment.id}`;
        const time = document.createElement("time");
        time.dateTime = comment.created_at;
        time.textContent = formatDate(comment.created_at);
        header.append(author, id, time);

        if (comment.parent_id === null && comment.hero && comment.direction) {
            const prediction = document.createElement("div");
            prediction.className = "comment-prediction";
            const hero = document.createElement("strong");
            hero.textContent = comment.hero;
            const direction = document.createElement("span");
            direction.className = `comment-direction ${comment.direction}`;
            direction.textContent = comment.direction === "buff" ? "上方修正" : "下方修正";
            prediction.append(hero, direction);
            item.append(header, prediction);
        } else {
            item.append(header);
        }

        const body = document.createElement("p");
        body.className = "comment-body";
        body.textContent = comment.body;

        item.append(body);
        if (!comment.deleted) {
            const actions = document.createElement("div");
            actions.className = "comment-actions";
            const like = actionButton(
                `賛成 ${comment.like_count}`,
                `comment-action like-action${comment.liked_by_me ? " selected" : ""}`,
                () => sendAction({ action: "like", comment_id: comment.id }),
            );
            like.setAttribute("aria-pressed", String(comment.liked_by_me));
            const reply = actionButton("返信", "comment-action", () => setReplyTarget(comment));
            actions.append(like, reply);
            item.append(actions);
        } else {
            item.classList.add("deleted");
        }

        const replies = childrenByParent.get(comment.id) || [];
        if (replies.length) {
            const replyList = document.createElement("div");
            replyList.className = "comment-replies";
            replies.forEach((child) => replyList.append(renderComment(child, childrenByParent, depth + 1)));
            item.append(replyList);
        }
        return item;
    }

    function render(data) {
        count.textContent = `${data.comment_count}件`;
        list.replaceChildren();
        const childrenByParent = new Map();
        data.comments.forEach((comment) => {
            const key = comment.parent_id || 0;
            if (!childrenByParent.has(key)) childrenByParent.set(key, []);
            childrenByParent.get(key).push(comment);
        });
        const roots = childrenByParent.get(0) || [];
        roots.slice().reverse().forEach((comment) => list.append(renderComment(comment, childrenByParent)));
        if (!roots.length) {
            const empty = document.createElement("p");
            empty.className = "comment-empty";
            empty.textContent = "まだコメントはありません。最初の予想を書いてみましょう。";
            list.append(empty);
        }
        setStatus("コメントを更新しました");
    }

    async function fetchComments() {
        if (requestInFlight) return;
        requestInFlight = true;
        try {
            const url = `${API_URL}?round_id=${encodeURIComponent(roundId)}&voter_token=${encodeURIComponent(token)}&_=${Date.now()}`;
            const response = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "コメントを取得できませんでした");
            render(data);
        } catch (error) {
            setStatus(error.message, true);
        } finally {
            requestInFlight = false;
        }
    }

    async function sendAction(action) {
        submitButton.disabled = true;
        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json", Accept: "application/json" },
                body: JSON.stringify({ round_id: roundId, voter_token: token, ...action }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "操作を完了できませんでした");
            render(data);
            return true;
        } catch (error) {
            setStatus(error.message, true);
            return false;
        } finally {
            submitButton.disabled = false;
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const success = await sendAction({
            action: "create",
            nickname: nicknameInput.value,
            body: bodyInput.value,
            hero: replyTarget ? null : heroInput.value,
            direction: replyTarget
                ? null
                : form.querySelector('input[name="comment-direction"]:checked')?.value,
            parent_id: replyTarget?.id ?? null,
        });
        if (success) {
            bodyInput.value = "";
            if (!replyTarget) heroInput.value = "";
            setReplyTarget();
        }
    });

    document.getElementById("reply-cancel").addEventListener("click", () => {
        setReplyTarget();
    });

    fetchComments();
    window.setInterval(fetchComments, POLL_INTERVAL_MS);
})();
