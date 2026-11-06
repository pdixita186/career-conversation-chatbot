(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const views = { welcome: $("#view-welcome"), chat: $("#view-chat") };
  const chatView = $("#view-chat");
  const messages = $("#messages");
  const mobile = () => window.matchMedia("(max-width: 960px)").matches;

  let profile = null;
  let started = false;
  let contactShown = false;
  let pending = false;
  const sessionId = getSessionId();

  // ---------- Helpers ----------
  function getSessionId() {
    const make = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + "-" + Math.random().toString(36).slice(2, 10));
    try {
      let id = sessionStorage.getItem("career-chat-session");
      if (!id) { id = make(); sessionStorage.setItem("career-chat-session", id); }
      return id;
    } catch (e) { return make(); }
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  // Renders the small markdown subset the assistant is told to use: paragraphs, "- " lists, **bold**.
  function renderText(text) {
    const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    return text.trim().split(/\n{2,}/).map((block) => {
      const lines = block.split("\n");
      if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
        return "<ul>" + lines.map((l) => "<li>" + inline(l.replace(/^\s*[-*]\s+/, "")) + "</li>").join("") + "</ul>";
      }
      return "<p>" + lines.map(inline).join("<br>") + "</p>";
    }).join("");
  }
  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  // ---------- Profile rendering ----------
  function renderProfile(p) {
    document.title = p.first_name + "'s career chat";
    document.querySelectorAll("[data-bind]").forEach((n) => { n.textContent = p[n.dataset.bind] || ""; });
    $("#role-line").textContent = [p.name, p.role, p.location].filter(Boolean).join(" · ");
    $("#how").textContent = "Answers come only from " + p.first_name + "'s resume and project notes. If the assistant doesn't know something, it says so and passes the question to " + p.first_name + ".";
    $("#assistant-name").textContent = p.first_name + "'s career assistant";
    $("#status-line").textContent = "Answers from " + p.first_name + "'s resume";
    $("#contact-label").textContent = "Contact " + p.first_name;
    $("#composer-note").textContent = p.mode === "demo"
      ? "Demo mode: replies are scripted until an API key is configured."
      : "AI assistant. It can make mistakes, so confirm important details with " + p.first_name + ".";

    const flags = [];
    if (p.is_sample) flags.push("Sample content");
    if (p.mode === "demo") flags.push("Demo mode");
    if (flags.length) { $("#flag").textContent = flags.join(" · "); $("#flag").hidden = false; }

    const qs = p.suggested_questions || [];
    $("#ask-list").innerHTML = qs.slice(0, 4).map((q) =>
      '<li><button type="button" data-ask="' + esc(q.question) + '"><span>' + esc(q.question) + '</span><span aria-hidden="true">→</span></button></li>').join("");
    $("#chips").innerHTML = qs.map((q) =>
      '<button class="chip" type="button" data-ask="' + esc(q.question) + '">' + esc(q.label) + "</button>").join("");
    $("#facts").innerHTML = (p.facts || []).map((f) =>
      '<div class="fact"><b>' + esc(f.value) + "</b><span>" + esc(f.label) + "</span></div>").join("");
    $("#facts").hidden = !(p.facts || []).length;
    $("#timeline").innerHTML = (p.experience || []).map((x) =>
      '<li><span class="dates">' + esc(x.dates) + "</span><b>" + esc(x.title) + "</b><span>" + esc(x.detail || "") + "</span></li>").join("");
    $("#skills").innerHTML = (p.skills || []).map((s) => '<span class="skill">' + esc(s) + "</span>").join("");
    if (p.resume_url) { $("#resume-link").href = p.resume_url; $("#resume-link").hidden = false; }
    if (p.linkedin) { $("#linkedin-link").href = p.linkedin; $("#linkedin-link").hidden = false; }
  }

  // ---------- Routing (#welcome, #chat, #contact, #profile) ----------
  function show(name) {
    const route = ["welcome", "chat", "contact", "profile"].includes(name) ? name : "welcome";
    const isChat = route !== "welcome";
    views.welcome.hidden = isChat;
    views.chat.hidden = !isChat;
    if (!isChat) return;
    startChat();
    if (route === "contact") showContactCard();
    if (route === "profile") setPanel(true);
    else if (mobile()) setPanel(false);
  }
  function go(name) {
    if (location.hash.slice(1) === name) show(name);
    else location.hash = name;
  }
  window.addEventListener("hashchange", () => show(location.hash.slice(1)));

  // ---------- Panel ----------
  function setPanel(open) {
    if (mobile()) {
      chatView.classList.remove("panel-closed");
      chatView.classList.toggle("drawer-open", open);
    } else {
      chatView.classList.remove("drawer-open");
      chatView.classList.toggle("panel-closed", !open);
    }
    $("#btn-panel").setAttribute("aria-expanded", String(open));
  }
  const panelOpen = () => mobile() ? chatView.classList.contains("drawer-open") : !chatView.classList.contains("panel-closed");
  $("#btn-panel").addEventListener("click", () => setPanel(!panelOpen()));
  $("#btn-close-panel").addEventListener("click", () => setPanel(false));
  $("#scrim").addEventListener("click", () => setPanel(false));

  // ---------- Messages ----------
  const scrollDown = () => { messages.scrollTop = messages.scrollHeight; };
  function avatar() { return '<div class="avatar" aria-hidden="true">' + esc(profile ? profile.initials : "") + "</div>"; }
  function addUser(text) {
    const row = el("div", "msg user");
    const b = el("div", "bubble");
    b.textContent = text;
    row.appendChild(b);
    messages.appendChild(row);
    scrollDown();
  }
  function addBot(html, opts) {
    opts = opts || {};
    const row = el("div", "msg bot", avatar() + '<div class="bubble' + (opts.cls ? " " + opts.cls : "") + '">' + html + "</div>");
    if (opts.node) row.querySelector(".bubble").appendChild(opts.node);
    messages.appendChild(row);
    scrollDown();
    return row;
  }
  function typing() {
    const row = el("div", "msg bot", avatar() + '<div class="bubble typing" aria-label="Typing"><i></i><i></i><i></i></div>');
    messages.appendChild(row);
    scrollDown();
    return row;
  }
  function startChat() {
    if (started || !profile) return;
    started = true;
    addBot("<p>Hi, I'm " + esc(profile.first_name) + "'s career assistant. I can answer questions about " + esc(profile.first_name) +
      "'s experience, skills, projects and what they're looking for next.</p><p>Pick a topic below or type your own question.</p>");
  }
  function setPending(on) {
    pending = on;
    $("#send").disabled = on;
  }

  async function ask(text) {
    text = (text || "").trim();
    if (!text || pending) return;
    if (views.chat.hidden) go("chat");
    addUser(text);
    setPending(true);
    const t = typing();
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      const data = await res.json().catch(() => ({}));
      t.remove();
      if (!res.ok) {
        const msg = typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
        addBot("<p>" + esc(msg) + "</p>", { cls: "error" });
        return;
      }
      showReply(data);
    } catch (e) {
      t.remove();
      addBot("<p>Couldn't reach the assistant. Check your connection and try again.</p>", { cls: "error" });
    } finally {
      setPending(false);
    }
  }

  function showReply(data) {
    let html = renderText(data.reply);
    if (data.sources && data.sources.length) html += '<span class="source">Source: ' + esc(data.sources.join(", ")) + "</span>";
    const extra = el("div");
    if (data.question_logged) extra.appendChild(el("span", "logged", "● Question saved for " + esc(profile.first_name)));
    if (data.contact_saved) {
      contactShown = true;
      extra.appendChild(el("span", "logged", "● Contact details saved"));
    } else if (data.question_logged && !contactShown) {
      const btn = el("button", "btn btn-ghost inline-action");
      btn.type = "button";
      btn.textContent = "Leave your email for a reply";
      btn.addEventListener("click", () => { btn.remove(); showContactCard(); });
      extra.appendChild(document.createElement("br"));
      extra.appendChild(btn);
    }
    addBot(html, { node: extra.childNodes.length ? extra : null });
    // When the assistant invites the visitor to leave details, open the form right away.
    if (!contactShown && !data.question_logged && !data.contact_saved && /leave (your|their) (contact )?details/i.test(data.reply)) {
      showContactCard();
    }
  }

  // ---------- Contact capture ----------
  function showContactCard() {
    const existing = document.getElementById("contact-card");
    if (existing) {
      existing.scrollIntoView({ block: "center" });
      const f = existing.querySelector("input");
      if (f) f.focus();
      return;
    }
    if (contactShown) { toast("Your details are already saved."); return; }
    const first = profile.first_name;
    const card = el("form", "contact-card");
    card.id = "contact-card";
    card.noValidate = true;
    card.innerHTML =
      "<h3>Get in touch with " + esc(first) + "</h3>" +
      '<p class="lead">' + esc(first) + " usually replies within 2 business days.</p>" +
      '<div class="field" id="f-name"><label for="c-name">Your name</label><input id="c-name" name="name" autocomplete="name" maxlength="120"><span class="err" hidden>Enter your name.</span></div>' +
      '<div class="field" id="f-email"><label for="c-email">Work email</label><input id="c-email" name="email" type="email" autocomplete="email" placeholder="you@company.com" maxlength="200"><span class="err" hidden>Enter a valid email, like you@company.com.</span></div>' +
      '<div class="field"><label for="c-company">Company <span class="opt">(optional)</span></label><input id="c-company" name="company" autocomplete="organization" maxlength="120"></div>' +
      '<div class="field"><label for="c-reason">Reason</label><select id="c-reason" name="reason"><option>A role I\'m hiring for</option><option>Schedule an interview</option><option>Freelance or consulting</option><option>Something else</option></select></div>' +
      '<p class="form-error" hidden></p>' +
      '<div class="form-foot"><small>Only ' + esc(first) + ' sees these details.</small><button class="btn btn-primary" type="submit">Send to ' + esc(first) + "</button></div>";
    card.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = card.querySelector("#c-name");
      const email = card.querySelector("#c-email");
      const okName = name.value.trim().length > 0;
      const okEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());
      setErr("f-name", !okName);
      setErr("f-email", !okEmail);
      if (!okName) { name.focus(); return; }
      if (!okEmail) { email.focus(); return; }
      const submit = card.querySelector("button[type=submit]");
      const formErr = card.querySelector(".form-error");
      submit.disabled = true;
      formErr.hidden = true;
      try {
        const res = await fetch("/api/contact", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name.value.trim(), email: email.value.trim(),
            company: card.querySelector("#c-company").value.trim(),
            reason: card.querySelector("#c-reason").value, session_id: sessionId,
          }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(typeof data.detail === "string" ? data.detail : "Couldn't save your details. Try again.");
        }
        contactShown = true;
        const firstName = name.value.trim().split(/\s+/)[0];
        card.innerHTML = '<div class="done"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="m5 12 5 5 9-10"/></svg>' +
          "<div><b>Sent to " + esc(first) + ".</b><br><span>" + esc(first) + " will reply to " + esc(email.value.trim()) + ".</span></div></div>";
        addBot("<p>Thanks, " + esc(firstName) + ". Is there anything else you'd like to know in the meantime?</p>");
      } catch (err) {
        formErr.textContent = err.message || "Couldn't save your details. Try again.";
        formErr.hidden = false;
        submit.disabled = false;
      }
    });
    addBot("", { cls: "form-wrap", node: card });
    setTimeout(() => card.querySelector("#c-name").focus({ preventScroll: true }), 50);
  }
  function setErr(id, bad) {
    const f = document.getElementById(id);
    f.classList.toggle("invalid", bad);
    f.querySelector(".err").hidden = !bad;
  }

  // ---------- Toast & misc ----------
  let toastTimer;
  function toast(msg) {
    const n = $("#toast");
    n.textContent = msg;
    n.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => n.classList.remove("show"), 2600);
  }
  $("#btn-copy").addEventListener("click", () => {
    const text = $("#email-text").textContent;
    const fallback = () => {
      const r = document.createRange();
      r.selectNodeContents($("#email-text"));
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
      toast("Email selected. Press Ctrl+C or ⌘C to copy.");
    };
    try { navigator.clipboard.writeText(text).then(() => toast("Email copied."), fallback); } catch (e) { fallback(); }
  });
  $("#btn-contact").addEventListener("click", () => {
    if (mobile()) setPanel(false);
    showContactCard();
  });
  document.addEventListener("click", (e) => {
    const goBtn = e.target.closest("[data-go]");
    if (goBtn) { go(goBtn.dataset.go); return; }
    const askBtn = e.target.closest("[data-ask]");
    if (askBtn) ask(askBtn.dataset.ask);
  });
  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#q");
    const v = input.value;
    if (pending) return;
    input.value = "";
    ask(v);
  });

  // ---------- Boot ----------
  fetch("/api/profile")
    .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
    .then((p) => { profile = p; renderProfile(p); show(location.hash.slice(1)); })
    .catch(() => {
      document.getElementById("app").innerHTML = '<p style="padding:24px">Couldn\'t load the profile. Refresh the page to try again.</p>';
    });
})();
