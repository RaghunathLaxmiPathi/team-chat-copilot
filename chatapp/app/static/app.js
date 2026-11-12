/* Team Chat web client. Plain JavaScript, no build step.
 * Message text is always set through ChatRender (escape first) or textContent, never raw HTML. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const render = window.ChatRender;

  const state = {
    token: sessionStorage.getItem("chat.token"),
    user: null,
    users: new Map(),
    convs: new Map(),
    activeId: null,
    msgs: new Map(), // conversation id -> confirmed messages in order
    hasEarlier: new Map(),
    hasLater: new Map(),
    pending: new Map(), // conversation id -> messages being sent
    drafts: JSON.parse(sessionStorage.getItem("chat.drafts") || "{}"),
    attachments: [],
    ws: null,
    backoff: 1000,
    lastSync: null,
    manualClose: false,
    pingTimer: null,
    reconnectTimer: null,
    readTimer: null,
    panel: null,
    panelOpener: null,
    threadRoot: null,
    notifCount: 0,
  };

  // ---------- helpers ----------
  function announce(text) {
    const live = $("live");
    live.textContent = "";
    setTimeout(() => { live.textContent = text; }, 50);
  }

  function showError(text) {
    const el = $("alert");
    el.textContent = "";
    setTimeout(() => { el.textContent = text; }, 50);
    announce(text);
  }

  function el(tag, props, children) {
    const node = document.createElement(tag);
    Object.entries(props || {}).forEach(([k, v]) => {
      if (k === "text") node.textContent = v;
      else if (k === "class") node.className = v;
      else if (k === "on") Object.entries(v).forEach(([ev, fn]) => node.addEventListener(ev, fn));
      else if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
    });
    (children || []).forEach((c) => node.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return node;
  }

  function fmtTime(iso) {
    return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  }

  function fmtSize(n) {
    return n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";
  }

  function userName(id) {
    const u = state.users.get(id);
    return u ? u.display_name : "Someone";
  }

  function newClientId() {
    return (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(16) + Math.random().toString(16).slice(2)).replace(/-/g, "");
  }

  async function api(method, path, body) {
    const headers = {};
    if (state.token) headers.Authorization = "Bearer " + state.token;
    const init = { method, headers };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    const res = await fetch(path, init);
    if (res.status === 204) return null;
    let data = null;
    try { data = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      const info = (data && data.error) || {};
      const err = new Error(info.message || "Request failed (" + res.status + ")");
      err.status = res.status;
      err.code = info.code;
      err.requestId = info.request_id;
      err.retryAfter = res.headers.get("Retry-After");
      if (res.status === 401 && state.token && !path.endsWith("/dev-login")) endSession("Your session has expired. Sign in again.", true);
      throw err;
    }
    return data;
  }

  function reportError(err) {
    showError(err.message + (err.requestId ? " (reference " + err.requestId + ")" : ""));
  }

  // ---------- sign in / out ----------
  $("login-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    $("login-error").hidden = true;
    try {
      const data = await api("POST", "/api/v1/auth/dev-login", { username: $("login-username").value });
      state.token = data.token;
      state.user = data.user;
      sessionStorage.setItem("chat.token", data.token);
      await startApp();
    } catch (err) {
      $("login-error").textContent = err.message;
      $("login-error").hidden = false;
    }
  });

  function endSession(message, keepDrafts) {
    state.manualClose = true;
    if (state.ws) { try { state.ws.close(); } catch (e) { /* closed */ } }
    clearInterval(state.pingTimer);
    clearTimeout(state.reconnectTimer);
    state.token = null;
    sessionStorage.removeItem("chat.token");
    if (!keepDrafts) { state.drafts = {}; sessionStorage.removeItem("chat.drafts"); }
    ["msgs", "hasEarlier", "hasLater", "pending", "convs", "users"].forEach((k) => state[k].clear());
    state.activeId = null;
    state.lastSync = null;
    $("app-view").hidden = true;
    $("login-view").hidden = false;
    $("login-error").textContent = message || "";
    $("login-error").hidden = !message;
    $("login-username").focus();
  }

  $("signout-button").addEventListener("click", () => endSession("", false));

  $("copilot-toggle").addEventListener("change", async (ev) => {
    try {
      state.user = await api("PATCH", "/api/v1/me", { copilot_auto: ev.target.checked });
      announce(state.user.copilot_auto ? "Copilot will reply to everything you write." : "Copilot will only reply when you mention it.");
    } catch (err) {
      ev.target.checked = !ev.target.checked;
      reportError(err);
    }
  });

  $("history-toggle").addEventListener("change", async (ev) => {
    try {
      state.user = await api("PATCH", "/api/v1/me", { copilot_history: ev.target.checked });
      announce(state.user.copilot_history ? "Copilot may use your history in your private chat." : "Copilot will not use your history.");
    } catch (err) {
      ev.target.checked = !ev.target.checked;
      reportError(err);
    }
  });

  async function startApp() {
    $("login-view").hidden = true;
    $("app-view").hidden = false;
    $("whoami").textContent = "Signed in as " + state.user.display_name;
    $("copilot-toggle").checked = !!state.user.copilot_auto;
    $("history-toggle").checked = !!state.user.copilot_history;
    $("admin-button").hidden = !state.user.is_admin;
    $("channel-option").hidden = !state.user.is_admin;
    state.manualClose = false;
    await Promise.all([loadUsers(), loadConversations()]);
    refreshNotifCount();
    connect();
    $("conv-title").focus && $("messages-region").focus();
  }

  async function loadUsers() {
    const data = await api("GET", "/api/v1/users");
    state.users = new Map(data.users.map((u) => [u.id, u]));
  }

  async function loadConversations() {
    const data = await api("GET", "/api/v1/conversations");
    state.convs = new Map(data.conversations.map((c) => [c.id, c]));
    if (state.activeId && !state.convs.has(state.activeId)) clearActive();
    renderConversations();
  }

  // ---------- conversations ----------
  function convName(c) {
    if (c.type !== "dm") return c.name;
    const other = c.members.find((m) => m.id !== state.user.id) || c.members[0];
    return other ? other.display_name : "Direct message";
  }

  const KIND = { dm: "Direct message", group: "Group chat", channel: "Channel" };

  function renderConversations() {
    const list = $("conversation-list");
    list.textContent = "";
    const order = { channel: 0, group: 1, dm: 2 };
    Array.from(state.convs.values())
      .sort((a, b) => order[a.type] - order[b.type] || convName(a).localeCompare(convName(b)))
      .forEach((c) => {
        const label = convName(c) + ", " + KIND[c.type] + (c.unread_count ? ", " + c.unread_count + " unread" : "");
        const btn = el("button", {
          type: "button", "aria-label": label, "aria-current": c.id === state.activeId ? "true" : "false",
          on: { click: () => openConversation(c.id) },
        }, [
          el("span", { text: convName(c) }),
          el("span", {}, [
            el("span", { class: "conv-kind", text: KIND[c.type] + " " }),
            c.unread_count ? el("span", { class: "badge", text: String(c.unread_count), "aria-hidden": "true" }) : "",
          ]),
        ]);
        list.appendChild(el("li", {}, [btn]));
      });
  }

  function clearActive() {
    state.activeId = null;
    $("conv-title").textContent = "Select a conversation";
    $("conv-sub").textContent = "";
    $("composer").hidden = true;
    $("members-button").hidden = true;
    $("leave-button").hidden = true;
    $("message-list").textContent = "";
    $("load-earlier").hidden = true;
    $("load-later").hidden = true;
  }

  async function openConversation(cid, aroundSeq) {
    const conv = state.convs.get(cid);
    if (!conv) return;
    saveDraft();
    state.activeId = cid;
    state.attachments = [];
    renderChips();
    $("conv-title").textContent = convName(conv);
    $("conv-sub").textContent = KIND[conv.type] + ", " + conv.members.length + (conv.members.length === 1 ? " member" : " members");
    $("composer").hidden = false;
    $("composer-text").value = state.drafts[cid] || "";
    const hasBot = conv.members.some((m) => (state.users.get(m.id) || {}).is_bot);
    $("composer-text").placeholder = hasBot
      ? "Copilot is here. Ask: summarize, search, actions, members, or just chat. Enter sends."
      : "Write a message. Enter sends, Shift+Enter adds a line.";
    $("members-button").hidden = conv.type === "dm";
    $("leave-button").hidden = conv.type === "dm";
    renderConversations();
    try {
      const q = aroundSeq != null ? "?around_seq=" + aroundSeq : "";
      const page = await api("GET", "/api/v1/conversations/" + cid + "/messages" + q);
      state.msgs.set(cid, page.messages);
      state.hasEarlier.set(cid, page.has_more_before);
      state.hasLater.set(cid, page.has_more_after);
      renderMessages({ toBottom: aroundSeq == null, focusSeq: aroundSeq });
      if (aroundSeq == null) markRead(cid);
    } catch (err) {
      if (err.status === 404) { await loadConversations(); }
      reportError(err);
    }
  }

  function saveDraft() {
    if (!state.activeId) return;
    const text = $("composer-text").value;
    if (text) state.drafts[state.activeId] = text; else delete state.drafts[state.activeId];
    sessionStorage.setItem("chat.drafts", JSON.stringify(state.drafts));
  }
  $("composer-text").addEventListener("input", saveDraft);

  function mentionNames(cid) {
    const c = state.convs.get(cid);
    const names = new Set();
    if (c) c.members.forEach((m) => { const u = state.users.get(m.id); if (u) names.add(u.username); });
    return names;
  }

  // ---------- messages ----------
  function messageEl(msg, cid, readOnly) {
    const mine = msg.sender_id === state.user.id;
    const li = el("li", { class: "msg" + (mine ? " mine" : "") + (msg.deleted ? " deleted" : ""), id: "m-" + msg.id, tabindex: "-1" });
    const botTag = (state.users.get(msg.sender_id) || {}).is_bot ? " (assistant)" : "";
    const head = el("div", { class: "msg-head" }, [
      el("strong", { text: msg.sender_name + botTag + (msg.sender_status === "deactivated" ? " (former member)" : "") }),
      el("time", { datetime: msg.created_at, text: fmtTime(msg.created_at) }),
    ]);
    if (msg.reply_to_id && !readOnly) head.appendChild(el("span", { class: "replying", text: "Reply in thread" }));
    li.appendChild(head);
    const body = el("div", { class: "msg-body" });
    if (msg.deleted) body.textContent = "Message deleted";
    else body.innerHTML = render.renderMarkdown(msg.body, mentionNames(cid));
    li.appendChild(body);
    (msg.attachments || []).forEach((a) => {
      li.appendChild(el("button", {
        type: "button", class: "attach", text: "Download " + a.filename + " (" + fmtSize(a.size_bytes) + ")",
        on: { click: () => downloadAttachment(a) },
      }));
    });
    if (!msg.deleted && !readOnly) {
      const actions = el("div", { class: "msg-actions" });
      actions.appendChild(el("button", {
        type: "button", text: "Reply", "aria-label": "Reply to message from " + msg.sender_name,
        on: { click: (ev) => openThread(msg.id, ev.currentTarget) },
      }));
      if (mine) {
        actions.appendChild(el("button", {
          type: "button", text: "Delete", "aria-label": "Delete your message from " + fmtTime(msg.created_at),
          on: { click: () => deleteMessage(msg) },
        }));
      }
      li.appendChild(actions);
    }
    return li;
  }

  function pendingEl(p) {
    const li = el("li", { class: "msg mine" });
    li.appendChild(el("div", { class: "msg-head" }, [el("strong", { text: "You" })]));
    li.appendChild(el("div", { class: "msg-body", text: p.body }));
    const status = { sending: "Sending...", retrying: "Failed to send, retrying...", failed: "Not sent", rejected: "Not sent: " + (p.error || "") }[p.status];
    const row = el("div", { class: "msg-actions" }, [el("span", { class: p.status === "sending" ? "" : "status-failed", text: status })]);
    if (p.status === "failed" || p.status === "rejected") {
      if (p.status === "failed") row.appendChild(el("button", { type: "button", text: "Retry", on: { click: () => { p.attempts = 0; attempt(p); } } }));
      row.appendChild(el("button", { type: "button", text: "Remove", on: { click: () => { removePending(p); renderMessages(); } } }));
    }
    li.appendChild(row);
    return li;
  }

  function renderMessages(opts) {
    opts = opts || {};
    const cid = state.activeId;
    if (!cid) return;
    const wrap = document.querySelector(".list-wrap");
    const nearBottom = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight < 80;
    const before = wrap.scrollHeight;
    const list = $("message-list");
    list.textContent = "";
    (state.msgs.get(cid) || []).forEach((m) => list.appendChild(messageEl(m, cid, false)));
    (state.pending.get(cid) || []).forEach((p) => list.appendChild(pendingEl(p)));
    $("load-earlier").hidden = !state.hasEarlier.get(cid);
    $("load-later").hidden = !state.hasLater.get(cid);
    if (opts.focusSeq != null) {
      const target = (state.msgs.get(cid) || []).find((m) => m.seq === opts.focusSeq);
      const node = target && document.getElementById("m-" + target.id);
      if (node) { node.scrollIntoView({ block: "center" }); node.focus(); return; }
    }
    if (opts.toBottom || (nearBottom && !opts.keepPosition)) wrap.scrollTop = wrap.scrollHeight;
    else if (opts.keepPosition) wrap.scrollTop += wrap.scrollHeight - before;
  }

  function addMessages(cid, messages) {
    const arr = state.msgs.get(cid) || [];
    if (state.hasLater.get(cid)) return arr; // viewing older history: do not splice live messages in
    const known = new Set(arr.map((m) => m.id));
    messages.forEach((m) => { if (!known.has(m.id)) arr.push(m); });
    arr.sort((a, b) => a.seq - b.seq);
    state.msgs.set(cid, arr);
    return arr;
  }

  $("load-earlier").addEventListener("click", async () => {
    const cid = state.activeId;
    const first = (state.msgs.get(cid) || [])[0];
    if (!first) return;
    try {
      const page = await api("GET", "/api/v1/conversations/" + cid + "/messages?before_seq=" + first.seq);
      state.msgs.set(cid, page.messages.concat(state.msgs.get(cid)));
      state.hasEarlier.set(cid, page.has_more_before);
      renderMessages({ keepPosition: true });
    } catch (err) { reportError(err); }
  });

  $("load-later").addEventListener("click", async () => {
    const cid = state.activeId;
    const arr = state.msgs.get(cid) || [];
    const last = arr[arr.length - 1];
    if (!last) return;
    try {
      const page = await api("GET", "/api/v1/conversations/" + cid + "/messages?after_seq=" + last.seq);
      state.msgs.set(cid, arr.concat(page.messages));
      state.hasLater.set(cid, page.has_more_after);
      renderMessages();
    } catch (err) { reportError(err); }
  });

  // ---------- sending ----------
  function removePending(p) {
    state.pending.set(p.cid, (state.pending.get(p.cid) || []).filter((x) => x !== p));
  }

  function submitMessage(cid, body, replyTo, attachments, onSent) {
    const p = { clientId: newClientId(), cid, body, replyTo, attachments: attachments.slice(), status: "sending", attempts: 0, onSent };
    state.pending.set(cid, (state.pending.get(cid) || []).concat([p]));
    if (cid === state.activeId) renderMessages({ toBottom: true });
    attempt(p);
  }

  async function attempt(p) {
    p.attempts += 1;
    p.status = p.attempts > 1 ? "retrying" : "sending";
    if (p.cid === state.activeId) renderMessages();
    try {
      const res = await api("POST", "/api/v1/conversations/" + p.cid + "/messages", {
        client_msg_id: p.clientId, body: p.body, reply_to_id: p.replyTo || undefined, attachment_ids: p.attachments,
      });
      removePending(p);
      addMessages(p.cid, [res.message]);
      if (p.cid === state.activeId) renderMessages({ toBottom: true });
      if (p.onSent) p.onSent();
    } catch (err) {
      const clientError = err.status && err.status >= 400 && err.status < 500 && err.status !== 429 && err.status !== 408;
      if (err.status === 401) return;
      if (clientError) { p.status = "rejected"; p.error = err.message; renderMessages(); return; }
      if (p.attempts >= 5) { p.status = "failed"; renderMessages(); return; }
      p.status = "retrying";
      renderMessages();
      const wait = err.status === 429 ? (Number(err.retryAfter) || 2) * 1000 : 1000 * Math.pow(2, p.attempts - 1);
      setTimeout(() => attempt(p), wait);
    }
  }

  $("composer").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const text = $("composer-text").value.trim();
    if (!text || !state.activeId) return;
    submitMessage(state.activeId, text, null, state.attachments.map((a) => a.id));
    $("composer-text").value = "";
    state.attachments = [];
    renderChips();
    saveDraft();
  });

  $("composer-text").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); $("composer").requestSubmit(); }
  });

  async function deleteMessage(msg) {
    if (!confirm("Delete this message? This cannot be undone.")) return;
    try {
      await api("DELETE", "/api/v1/messages/" + msg.id);
      markDeleted(msg.conversation_id, msg.id);
      announce("Message deleted");
    } catch (err) { reportError(err); }
  }

  function markDeleted(cid, id) {
    const m = (state.msgs.get(cid) || []).find((x) => x.id === id);
    if (m) { m.deleted = true; m.body = null; m.attachments = []; }
    if (cid === state.activeId) renderMessages();
    if (state.panel === "thread") refreshThread();
  }

  // ---------- attachments ----------
  $("file-input").addEventListener("change", async (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (!file || !state.activeId) return;
    if (state.attachments.length >= 5) { showError("A message can have at most 5 attachments."); return; }
    const form = new FormData();
    form.append("conversation_id", state.activeId);
    form.append("file", file);
    try {
      const a = await api("POST", "/api/v1/attachments", form);
      state.attachments.push(a);
      renderChips();
      announce("Attached " + a.filename);
    } catch (err) { reportError(err); }
  });

  function renderChips() {
    const list = $("chips");
    list.textContent = "";
    state.attachments.forEach((a) => {
      list.appendChild(el("li", {}, [
        el("span", { text: a.filename + " (" + fmtSize(a.size_bytes) + ") " }),
        el("button", { type: "button", text: "Remove", "aria-label": "Remove attachment " + a.filename, on: { click: () => { state.attachments = state.attachments.filter((x) => x !== a); renderChips(); } } }),
      ]));
    });
  }

  async function downloadAttachment(a) {
    try {
      const res = await fetch("/api/v1/attachments/" + a.id, { headers: { Authorization: "Bearer " + state.token } });
      if (!res.ok) throw new Error("Could not download the file.");
      const url = URL.createObjectURL(await res.blob());
      const link = el("a", { href: url, download: a.filename });
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (err) { showError(err.message); }
  }

  // ---------- read position ----------
  function markRead(cid) {
    const arr = state.msgs.get(cid) || [];
    const last = arr[arr.length - 1];
    const conv = state.convs.get(cid);
    if (!last || !conv) return;
    conv.unread_count = 0;
    renderConversations();
    clearTimeout(state.readTimer);
    state.readTimer = setTimeout(() => api("POST", "/api/v1/conversations/" + cid + "/read", { seq: last.seq }).catch(() => {}), 300);
  }

  // ---------- side panel ----------
  function openPanel(kind, title, opener) {
    state.panel = kind;
    state.panelOpener = opener || document.activeElement;
    $("panel-title").textContent = title;
    $("panel-body").textContent = "";
    $("side-panel").hidden = false;
    document.querySelector(".app").classList.add("with-panel");
    return $("panel-body");
  }

  function focusPanel() { $("side-panel").focus(); }

  function closePanel() {
    state.panel = null;
    state.threadRoot = null;
    $("side-panel").hidden = true;
    document.querySelector(".app").classList.remove("with-panel");
    if (state.panelOpener && document.contains(state.panelOpener)) state.panelOpener.focus();
  }
  $("panel-close").addEventListener("click", closePanel);

  // ---------- threads ----------
  async function openThread(messageId, opener) {
    try {
      const data = await api("GET", "/api/v1/messages/" + messageId + "/thread");
      state.threadRoot = data.root.id;
      buildThread(data, opener);
      focusPanel();
    } catch (err) { reportError(err); }
  }

  async function refreshThread() {
    if (!state.threadRoot) return;
    try { buildThread(await api("GET", "/api/v1/messages/" + state.threadRoot + "/thread")); } catch (err) { /* panel may have closed */ }
  }

  function buildThread(data, opener) {
    const body = state.panel === "thread" && !opener ? ($("panel-body").textContent = "", $("panel-body")) : openPanel("thread", "Thread", opener);
    const cid = data.root.conversation_id;
    const list = el("ul", { "aria-label": "Messages in this thread" });
    list.appendChild(messageEl(data.root, cid, true));
    data.replies.forEach((r) => list.appendChild(messageEl(r, cid, true)));
    body.appendChild(list);
    const form = el("form", {}, [
      el("label", { for: "thread-text", text: "Reply" }),
      el("textarea", { id: "thread-text", rows: "3", maxlength: "4000" }),
      el("button", { type: "submit", text: "Send reply" }),
    ]);
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const text = $("thread-text").value.trim();
      if (!text) return;
      submitMessage(cid, text, data.root.id, [], refreshThread);
      $("thread-text").value = "";
    });
    body.appendChild(form);
  }

  // ---------- search ----------
  $("search-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const q = $("search-input").value.trim();
    if (q.length < 2) { showError("Type at least 2 characters to search."); return; }
    try {
      const data = await api("GET", "/api/v1/search?q=" + encodeURIComponent(q));
      const body = openPanel("search", "Search results", $("search-input"));
      if (!data.results.length) body.appendChild(el("p", { text: "No messages found." }));
      const list = el("ul");
      data.results.forEach((r) => {
        list.appendChild(el("li", {}, [el("button", {
          type: "button",
          on: { click: () => { closePanel(); openConversation(r.message.conversation_id, r.message.seq); } },
        }, [el("strong", { text: r.conversation_name + ": " }), el("span", { text: r.message.sender_name + " - " + r.excerpt })])]));
      });
      body.appendChild(list);
      announce(data.results.length + " results");
      focusPanel();
    } catch (err) { reportError(err); }
  });

  // ---------- notifications ----------
  async function refreshNotifCount() {
    try {
      const data = await api("GET", "/api/v1/notifications?unread_only=true");
      setNotifCount(data.unread_count);
    } catch (err) { /* ignore */ }
  }

  function setNotifCount(n) {
    state.notifCount = n;
    $("notif-count").textContent = String(n);
    $("notif-count").hidden = n === 0;
  }

  $("notif-button").addEventListener("click", async (ev) => {
    try {
      const data = await api("GET", "/api/v1/notifications");
      setNotifCount(data.unread_count);
      const body = openPanel("notifications", "Notifications", ev.currentTarget);
      if (!data.notifications.length) body.appendChild(el("p", { text: "No notifications." }));
      const list = el("ul");
      data.notifications.forEach((n) => {
        const text = n.type === "mention" ? n.actor_name + " mentioned you in " + n.conversation_name : n.actor_name + " added you to " + n.conversation_name;
        list.appendChild(el("li", {}, [el("button", {
          type: "button", text: text + (n.read ? "" : " (unread)"),
          on: { click: async () => {
            await api("POST", "/api/v1/notifications/" + n.id + "/read").catch(() => {});
            refreshNotifCount();
            closePanel();
            if (state.convs.has(n.conversation_id)) openConversation(n.conversation_id);
          } },
        })]));
      });
      body.appendChild(list);
      focusPanel();
    } catch (err) { reportError(err); }
  });

  // ---------- members ----------
  $("members-button").addEventListener("click", (ev) => showMembers(ev.currentTarget));

  function showMembers(opener) {
    const conv = state.convs.get(state.activeId);
    if (!conv) return;
    const body = openPanel("members", "Members of " + convName(conv), opener);
    const canManage = conv.type === "group" || (conv.type === "channel" && state.user.is_admin);
    const list = el("ul");
    conv.members.forEach((m) => {
      const li = el("li", {}, [el("span", { text: m.display_name + (m.id === state.user.id ? " (you)" : "") + " " })]);
      if (conv.type === "channel" && state.user.is_admin && m.id !== state.user.id) {
        li.appendChild(el("button", { type: "button", text: "Remove", "aria-label": "Remove " + m.display_name, on: { click: async () => {
          try { await api("DELETE", "/api/v1/conversations/" + conv.id + "/members/" + m.id); await loadConversations(); showMembers(opener); } catch (err) { reportError(err); }
        } } }));
      }
      list.appendChild(li);
    });
    body.appendChild(list);
    if (canManage) {
      const current = new Set(conv.members.map((m) => m.id));
      const options = Array.from(state.users.values()).filter((u) => u.status === "active" && !current.has(u.id));
      if (options.length) {
        const select = el("select", { id: "add-member-select" }, options.map((u) => el("option", { value: u.id, text: u.display_name })));
        const form = el("form", {}, [el("label", { for: "add-member-select", text: "Add a member" }), select, el("button", { type: "submit", text: "Add" })]);
        form.addEventListener("submit", async (ev) => {
          ev.preventDefault();
          try { await api("POST", "/api/v1/conversations/" + conv.id + "/members", { user_id: select.value }); await loadConversations(); showMembers(opener); announce("Member added"); } catch (err) { reportError(err); }
        });
        body.appendChild(form);
      }
    }
    focusPanel();
  }

  $("leave-button").addEventListener("click", async () => {
    const conv = state.convs.get(state.activeId);
    if (!conv || !confirm("Leave " + convName(conv) + "?")) return;
    try {
      await api("DELETE", "/api/v1/conversations/" + conv.id + "/members/" + state.user.id);
      state.convs.delete(conv.id);
      clearActive();
      renderConversations();
      announce("You left " + convName(conv));
    } catch (err) { reportError(err); }
  });

  // ---------- new conversation ----------
  const dialog = $("new-dialog");
  $("new-button").addEventListener("click", () => {
    $("new-error").hidden = true;
    $("new-name").value = "";
    const box = $("member-choices");
    box.textContent = "";
    Array.from(state.users.values()).filter((u) => u.status === "active" && u.id !== state.user.id).forEach((u) => {
      box.appendChild(el("label", {}, [el("input", { type: "checkbox", name: "member", value: u.id }), " " + u.display_name + (u.is_bot ? " (assistant)" : "")]));
    });
    syncNewType();
    dialog.showModal();
  });
  function syncNewType() {
    const type = document.querySelector('input[name="ctype"]:checked').value;
    $("name-row").hidden = $("new-name").hidden = type === "dm";
  }
  document.querySelectorAll('input[name="ctype"]').forEach((r) => r.addEventListener("change", syncNewType));
  $("new-cancel").addEventListener("click", () => dialog.close());
  $("new-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const type = document.querySelector('input[name="ctype"]:checked').value;
    const ids = Array.from(document.querySelectorAll('input[name="member"]:checked')).map((i) => i.value);
    try {
      const conv = await api("POST", "/api/v1/conversations", { type, name: type === "dm" ? undefined : $("new-name").value, member_ids: ids });
      dialog.close();
      await loadConversations();
      openConversation(conv.id);
    } catch (err) {
      $("new-error").textContent = err.message;
      $("new-error").hidden = false;
    }
  });

  // ---------- administration ----------
  $("admin-button").addEventListener("click", (ev) => showAdmin(ev.currentTarget));

  async function showAdmin(opener) {
    try {
      await loadUsers();
      const body = openPanel("admin", "Administration", opener);
      const form = el("form", {}, [
        el("label", { for: "new-username", text: "User name" }), el("input", { id: "new-username", required: true }),
        el("label", { for: "new-display", text: "Display name" }), el("input", { id: "new-display", required: true }),
        el("label", {}, [el("input", { type: "checkbox", id: "new-admin" }), " Administrator"]),
        el("button", { type: "submit", text: "Add user" }),
      ]);
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        try {
          await api("POST", "/api/v1/users", { username: $("new-username").value, display_name: $("new-display").value, is_admin: $("new-admin").checked });
          announce("User added");
          showAdmin(opener);
        } catch (err) { reportError(err); }
      });
      body.appendChild(form);
      const list = el("ul", { "aria-label": "Users" });
      state.users.forEach((u) => {
        const li = el("li", {}, [el("span", { text: u.display_name + " (" + u.username + ")" + (u.is_admin ? " administrator" : "") + (u.status === "deactivated" ? " deactivated" : "") + " " })]);
        if (u.status === "active" && u.id !== state.user.id) {
          li.appendChild(el("button", { type: "button", text: u.is_admin ? "Remove admin" : "Make admin", on: { click: async () => {
            try { await api("PATCH", "/api/v1/users/" + u.id, { is_admin: !u.is_admin }); showAdmin(opener); } catch (err) { reportError(err); }
          } } }));
          li.appendChild(el("button", { type: "button", text: "Deactivate", "aria-label": "Deactivate " + u.display_name, on: { click: async () => {
            if (!confirm("Deactivate " + u.display_name + "? They lose access immediately.")) return;
            try { await api("POST", "/api/v1/users/" + u.id + "/deactivate"); showAdmin(opener); } catch (err) { reportError(err); }
          } } }));
        }
        list.appendChild(li);
      });
      body.appendChild(list);
      await addSlo(body);
      focusPanel();
    } catch (err) { reportError(err); }
  }

  async function addSlo(body) {
    const slo = await api("GET", "/api/v1/slo");
    body.appendChild(el("h3", { text: "Service objectives" }));
    const rows = [["Window", "Success", "P50", "P75", "P90", "P95", "P99"]];
    Object.entries(slo.windows).forEach(([name, w]) => {
      const cell = (x) => x.status === "insufficient_data" ? "no data" : (x.value_ms == null ? "over" : x.value_ms + " ms") + " " + x.status;
      const s = w.success_rate;
      rows.push([name, s.status === "insufficient_data" ? "no data" : (s.value * 100).toFixed(2) + "% " + s.status]
        .concat(["p50", "p75", "p90", "p95", "p99"].map((k) => cell(w.latency_ms[k]))));
    });
    const table = el("table", { class: "slo-table" });
    rows.forEach((r, i) => table.appendChild(el("tr", {}, r.map((c) => el(i === 0 ? "th" : "td", { text: c })))));
    body.appendChild(table);
    if (slo.burn_rate_warning) body.appendChild(el("p", { class: "error", text: "Warning: the success rate is burning through its budget." }));
  }

  // ---------- real-time ----------
  function connect() {
    if (!state.token) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(proto + "://" + location.host + "/ws?token=" + encodeURIComponent(state.token));
    state.ws = ws;
    ws.onmessage = (ev) => handleFrame(JSON.parse(ev.data));
    ws.onclose = (ev) => {
      clearInterval(state.pingTimer);
      if (state.manualClose || ws !== state.ws) return;
      if (ev.code === 4401) { endSession("Your session has expired. Sign in again.", true); return; }
      if (ev.code === 4403) { endSession("Your access was removed.", true); return; }
      $("connection-banner").hidden = false;
      announce("Connection lost. Reconnecting.");
      const wait = Math.min(state.backoff, 30000) * (0.7 + Math.random() * 0.6);
      state.backoff = Math.min(state.backoff * 2, 30000);
      state.reconnectTimer = setTimeout(connect, wait);
    };
  }

  function send(frame) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify(frame));
  }

  function handleFrame(f) {
    switch (f.type) {
      case "hello": onHello(); break;
      case "message": onMessage(f.message); break;
      case "message_deleted": markDeleted(f.conversation_id, f.message_id); break;
      case "conversation_added": loadConversations().then(() => announce("You were added to " + convName(f.conversation))); break;
      case "conversation_removed":
        state.convs.delete(f.conversation_id);
        if (state.activeId === f.conversation_id) clearActive();
        renderConversations();
        announce("You were removed from a conversation");
        break;
      case "notification":
        setNotifCount(state.notifCount + 1);
        announce(f.notification.type === "mention" ? f.notification.actor_name + " mentioned you in " + f.notification.conversation_name : f.notification.actor_name + " added you to " + f.notification.conversation_name);
        break;
      case "resume_page": onResumePage(f); break;
      case "resume_done": onResumeDone(f); break;
      case "error": showError(f.message); break;
      default: break;
    }
  }

  async function onHello() {
    $("connection-banner").hidden = true;
    state.backoff = 1000;
    clearInterval(state.pingTimer);
    state.pingTimer = setInterval(() => send({ type: "ping" }), 25000);
    // Reload the list first: it picks up conversations added or removed while offline.
    try { await loadConversations(); } catch (err) { return; }
    const cursors = {};
    state.convs.forEach((c, cid) => {
      const arr = state.msgs.get(cid);
      if (arr && arr.length && !state.hasLater.get(cid)) cursors[cid] = arr[arr.length - 1].seq;
    });
    send({ type: "resume", cursors, since: state.lastSync });
  }

  function onMessage(msg) {
    send({ type: "ack", message_id: msg.id });
    const cid = msg.conversation_id;
    const conv = state.convs.get(cid);
    const fromMe = msg.sender_id === state.user.id;
    if (!conv) { loadConversations(); return; }
    conv.last_seq = Math.max(conv.last_seq, msg.seq);
    (state.pending.get(cid) || []).filter((p) => p.clientId === msg.client_msg_id).forEach(removePending);
    if (state.msgs.has(cid)) addMessages(cid, [msg]);
    if (cid === state.activeId) {
      renderMessages();
      if (!fromMe) { announce("New message from " + msg.sender_name); markRead(cid); }
    } else if (!fromMe) {
      conv.unread_count += 1;
      renderConversations();
      announce("New message from " + msg.sender_name + " in " + convName(conv));
    }
    if (state.panel === "thread" && state.threadRoot && (msg.reply_to_id === state.threadRoot || msg.id === state.threadRoot)) refreshThread();
  }

  async function catchUp(cid, afterSeq) {
    let cursor = afterSeq;
    for (;;) {
      const page = await api("GET", "/api/v1/conversations/" + cid + "/messages?after_seq=" + cursor);
      if (!page.messages.length) break;
      addMessages(cid, page.messages);
      cursor = page.messages[page.messages.length - 1].seq;
      if (!page.has_more_after) break;
    }
    if (cid === state.activeId) renderMessages();
  }

  function onResumePage(f) {
    addMessages(f.conversation_id, f.messages);
    const last = f.messages[f.messages.length - 1];
    const conv = state.convs.get(f.conversation_id);
    if (conv && last && f.conversation_id !== state.activeId) conv.unread_count += f.messages.filter((m) => m.sender_id !== state.user.id).length;
    if (f.has_more && last) catchUp(f.conversation_id, last.seq).catch(reportError);
    if (f.conversation_id === state.activeId) { renderMessages(); markRead(f.conversation_id); }
    renderConversations();
  }

  function onResumeDone(f) {
    (f.deleted || []).forEach((d) => markDeleted(d.conversation_id, d.message_id));
    state.lastSync = f.server_time;
  }

  // ---------- start ----------
  async function init() {
    if (state.token) {
      try {
        state.user = await api("GET", "/api/v1/me");
        await startApp();
        return;
      } catch (err) { /* fall through to the sign-in page */ }
    }
    $("login-view").hidden = false;
    $("login-username").focus();
  }
  init();
})();
