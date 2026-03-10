/* ============================================================
   HealthBot — Client-side Logic
   ============================================================ */

const API = {
    createSession: (title) =>
        fetch("/api/sessions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
        }).then((r) => r.json()),

    getSessions: () => fetch("/api/sessions").then((r) => r.json()),

    getMessages: (id) => fetch(`/api/sessions/${id}`).then((r) => r.json()),

    deleteSession: (id) =>
        fetch(`/api/sessions/${id}`, { method: "DELETE" }).then((r) => r.json()),

    chat: (sessionId, message) =>
        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, message }),
        }),
};

/* ---------- State ---------- */
let currentSessionId = null;
let isStreaming = false;

/* ---------- DOM Refs ---------- */
const $ = (sel) => document.querySelector(sel);
const sessionListEl = $("#sessionList");
const messagesEl = $("#messages");
const messagesContainerEl = $("#messagesContainer");
const welcomeScreenEl = $("#welcomeScreen");
const inputForm = $("#inputForm");
const messageInput = $("#messageInput");
const sendBtn = $("#sendBtn");
const newChatBtn = $("#newChatBtn");
const sidebarToggle = $("#sidebarToggle");
const sidebar = $("#sidebar");

/* ---------- Initialize ---------- */
document.addEventListener("DOMContentLoaded", init);

async function init() {
    await loadSessions();
    setupEventListeners();
}

/* ---------- Event Listeners ---------- */
function setupEventListeners() {
    newChatBtn.addEventListener("click", createNewSession);

    inputForm.addEventListener("submit", (e) => {
        e.preventDefault();
        handleSend();
    });

    // Auto-resize textarea
    messageInput.addEventListener("input", () => {
        messageInput.style.height = "auto";
        messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + "px";
    });

    // Ctrl/Cmd+Enter to send
    messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Sidebar toggle (mobile)
    sidebarToggle.addEventListener("click", toggleSidebar);

    // Feature card clicks
    document.querySelectorAll(".feature-card").forEach((card) => {
        card.addEventListener("click", async () => {
            const prompt = card.dataset.prompt;
            if (!currentSessionId) {
                await createNewSession();
            }
            messageInput.value = prompt;
            handleSend();
        });
    });
}

/* ---------- Sessions ---------- */
async function loadSessions() {
    const sessions = await API.getSessions();
    renderSessions(sessions);
}

function renderSessions(sessions) {
    if (sessions.length === 0) {
        sessionListEl.innerHTML = `
            <div class="empty-sessions">
                <span>💬</span>
                <p>No conversations yet.<br>Start a new chat!</p>
            </div>`;
        return;
    }

    sessionListEl.innerHTML = sessions
        .map(
            (s) => `
        <div class="session-item ${s.id === currentSessionId ? "active" : ""}" 
             data-id="${s.id}" onclick="selectSession('${s.id}')">
            <span class="session-title">${escapeHtml(s.title)}</span>
            <button class="session-delete" onclick="event.stopPropagation(); deleteSession('${s.id}')" title="Delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button>
        </div>`
        )
        .join("");
}

async function createNewSession() {
    const session = await API.createSession("New Chat");
    currentSessionId = session.id;
    await loadSessions();
    showChatView();
    messagesEl.innerHTML = "";
    messageInput.focus();
    closeSidebarMobile();
}

async function selectSession(id) {
    currentSessionId = id;
    await loadSessions();
    showChatView();

    const messages = await API.getMessages(id);
    renderMessages(messages);
    scrollToBottom();
    closeSidebarMobile();
}

// Make it globally available for inline onclick
window.selectSession = selectSession;

async function deleteSession(id) {
    await API.deleteSession(id);
    if (currentSessionId === id) {
        currentSessionId = null;
        showWelcomeView();
    }
    await loadSessions();
}

window.deleteSession = deleteSession;

/* ---------- Views ---------- */
function showChatView() {
    welcomeScreenEl.style.display = "none";
    messagesContainerEl.style.display = "flex";
}

function showWelcomeView() {
    welcomeScreenEl.style.display = "flex";
    messagesContainerEl.style.display = "none";
    messagesEl.innerHTML = "";
}

/* ---------- Messages ---------- */
function renderMessages(messages) {
    messagesEl.innerHTML = messages
        .map((m) => createMessageHTML(m.role, m.content))
        .join("");
}

function createMessageHTML(role, content) {
    const avatar = role === "user" ? "👤" : "🩺";
    const rendered = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);
    return `
        <div class="message ${role}">
            <div class="message-avatar">${avatar}</div>
            <div class="message-bubble">${rendered}</div>
        </div>`;
}

function appendMessage(role, content) {
    messagesEl.insertAdjacentHTML("beforeend", createMessageHTML(role, content));
    scrollToBottom();
}

function appendStreamingMessage() {
    const html = `
        <div class="message assistant" id="streaming-msg">
            <div class="message-avatar">🩺</div>
            <div class="message-bubble">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>`;
    messagesEl.insertAdjacentHTML("beforeend", html);
    scrollToBottom();
}

function updateStreamingMessage(text) {
    const msg = document.getElementById("streaming-msg");
    if (!msg) return;
    const bubble = msg.querySelector(".message-bubble");
    bubble.innerHTML = renderMarkdown(text);
    scrollToBottom();
}

function finalizeStreamingMessage() {
    const msg = document.getElementById("streaming-msg");
    if (msg) msg.removeAttribute("id");
}

/* ---------- Chat / Streaming ---------- */
async function handleSend() {
    const text = messageInput.value.trim();
    if (!text || isStreaming) return;

    if (!currentSessionId) {
        await createNewSession();
    }

    // Show user message
    appendMessage("user", text);
    messageInput.value = "";
    messageInput.style.height = "auto";

    // Disable input
    isStreaming = true;
    sendBtn.disabled = true;

    // Show typing indicator
    appendStreamingMessage();

    try {
        const response = await API.chat(currentSessionId, text);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n");

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const data = line.slice(6).trim();

                if (data === "[DONE]") {
                    finalizeStreamingMessage();
                    continue;
                }

                try {
                    const parsed = JSON.parse(data);

                    if (parsed.error) {
                        updateStreamingMessage(`⚠️ Error: ${parsed.error}`);
                        finalizeStreamingMessage();
                        break;
                    }

                    if (parsed.text) {
                        fullText += parsed.text;
                        updateStreamingMessage(fullText);
                    }

                    if (parsed.title_update) {
                        await loadSessions();
                    }
                } catch {
                    // Skip malformed JSON
                }
            }
        }
    } catch (err) {
        updateStreamingMessage(`⚠️ Connection error: ${err.message}`);
        finalizeStreamingMessage();
    }

    isStreaming = false;
    sendBtn.disabled = false;
    messageInput.focus();
}

/* ---------- Markdown Renderer (lightweight) ---------- */
function renderMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Code blocks (```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Blockquote
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

    // Unordered list
    html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/((<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

    // Ordered list
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

    // Line breaks → paragraphs
    html = html
        .split(/\n\n+/)
        .map((block) => {
            block = block.trim();
            if (!block) return "";
            if (block.startsWith("<h") || block.startsWith("<ul") || block.startsWith("<ol") || block.startsWith("<pre") || block.startsWith("<blockquote")) {
                return block;
            }
            return `<p>${block.replace(/\n/g, "<br>")}</p>`;
        })
        .join("");

    return html;
}

/* ---------- Helpers ---------- */
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function scrollToBottom() {
    messagesContainerEl.scrollTo({
        top: messagesContainerEl.scrollHeight,
        behavior: "smooth",
    });
}

function toggleSidebar() {
    sidebar.classList.toggle("open");
    let overlay = document.querySelector(".sidebar-overlay");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.className = "sidebar-overlay";
        overlay.addEventListener("click", closeSidebarMobile);
        document.body.appendChild(overlay);
    }
    overlay.classList.toggle("active", sidebar.classList.contains("open"));
}

function closeSidebarMobile() {
    sidebar.classList.remove("open");
    const overlay = document.querySelector(".sidebar-overlay");
    if (overlay) overlay.classList.remove("active");
}
