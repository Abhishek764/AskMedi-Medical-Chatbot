"use strict";

const state = window.ASKMEDI;
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("msg");
const sendBtn = document.getElementById("send");
const stopBtn = document.getElementById("stop");
const convoList = document.getElementById("convo-list");
let controller = null;

function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}

function renderMarkdown(text) {
    // Treat all content as untrusted: parse markdown then sanitize the HTML.
    if (window.marked && window.DOMPurify) {
        const raw = window.marked.parse(text, { breaks: true });
        return window.DOMPurify.sanitize(raw);
    }
    return escapeHtml(text).replace(/\n/g, "<br>");
}

function addMessage(role, content) {
    const wrap = document.createElement("div");
    wrap.className = "msg msg-" + role;
    const body = document.createElement("div");
    body.className = "msg-body";
    if (role === "assistant") {
        body.innerHTML = renderMarkdown(content);
    } else {
        body.textContent = content;
    }
    wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return body;
}

function setStreaming(on) {
    sendBtn.disabled = on;
    input.disabled = on;
    stopBtn.hidden = !on;
}

async function loadMessages(id) {
    messagesEl.innerHTML = "";
    const res = await fetch(`/api/conversations/${id}/messages`);
    if (!res.ok) return;
    const data = await res.json();
    data.messages.forEach((m) => addMessage(m.role, m.content));
}

function selectConversation(id) {
    state.currentConversationId = id;
    document.querySelectorAll(".convo-item").forEach((el) => {
        el.classList.toggle("active", String(el.dataset.id) === String(id));
    });
    loadMessages(id);
}

function addConversationToList(id, title) {
    const li = document.createElement("li");
    li.className = "convo-item active";
    li.dataset.id = id;
    const titleSpan = document.createElement("span");
    titleSpan.className = "convo-title";
    titleSpan.textContent = title;
    const delBtn = document.createElement("button");
    delBtn.className = "convo-del";
    delBtn.title = "Delete";
    delBtn.textContent = "×";
    delBtn.setAttribute("data-id", id);
    li.append(titleSpan, delBtn);
    convoList.prepend(li);
}

async function sendMessage(text) {
    addMessage("user", text);
    const answerBody = addMessage("assistant", "");
    let answer = "";
    setStreaming(true);
    controller = new AbortController();

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": state.csrfToken,
            },
            body: JSON.stringify({
                message: text,
                conversation_id: state.currentConversationId,
            }),
            signal: controller.signal,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            answerBody.textContent = err.error || "Request failed.";
            return;
        }

        if (!res.body) {
            answerBody.textContent = "Streaming not supported in this browser.";
            return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop();
            for (const part of parts) {
                const line = part.replace(/^data: /, "").trim();
                if (!line) continue;
                let evt;
                try { evt = JSON.parse(line); } catch { continue; }
                if (evt.type === "meta") {
                    if (!state.currentConversationId) {
                        state.currentConversationId = evt.conversation_id;
                        addConversationToList(evt.conversation_id, text.slice(0, 60));
                    }
                } else if (evt.type === "token") {
                    answer += evt.content;
                    answerBody.innerHTML = renderMarkdown(answer);
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                } else if (evt.type === "done") {
                    if (evt.sources && evt.sources.length) {
                        const s = document.createElement("div");
                        s.className = "sources";
                        s.textContent = "Sources: " + evt.sources.join(", ");
                        answerBody.parentElement.appendChild(s);
                    }
                } else if (evt.type === "error") {
                    answerBody.textContent = evt.message || "Generation failed.";
                }
            }
        }
    } catch (e) {
        if (e.name !== "AbortError") {
            answerBody.textContent = "Network error.";
        }
    } finally {
        setStreaming(false);
        controller = null;
    }
}

form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendMessage(text);
});

input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
    }
});

stopBtn.addEventListener("click", () => {
    if (controller) controller.abort();
});

document.getElementById("new-chat").addEventListener("click", () => {
    state.currentConversationId = null;
    messagesEl.innerHTML = "";
    document.querySelectorAll(".convo-item").forEach((el) => el.classList.remove("active"));
    input.focus();
});

convoList.addEventListener("click", async (e) => {
    const del = e.target.closest(".convo-del");
    if (del) {
        e.stopPropagation();
        const id = del.dataset.id;
        const res = await fetch(`/api/conversations/${id}`, {
            method: "DELETE",
            headers: { "X-CSRFToken": state.csrfToken },
        });
        if (res.ok) {
            del.closest(".convo-item").remove();
            if (String(state.currentConversationId) === String(id)) {
                state.currentConversationId = null;
                messagesEl.innerHTML = "";
            }
        }
        return;
    }
    const item = e.target.closest(".convo-item");
    if (item) selectConversation(item.dataset.id);
});
