/* Focus session: one card at a time, instant feedback, a summary at the end. */
(function () {
  "use strict";
  const B = window.BEACON;
  const root = document.querySelector("[data-session]");
  if (!root) return;
  const stage = root.querySelector("[data-stage]");
  const pips = Array.from(root.querySelectorAll(".focus__progress span"));
  const xpEl = root.querySelector("[data-xp]");
  let xp = 0;
  const esc = B.esc;

  const THINKING = (text) => `<div class="thinking"><div class="thinking__beam" aria-hidden="true"></div><p>${text}</p></div>`;
  const LOADING_LINES = ["Writing a fresh question…", "Picking a new angle on this skill…", "Tailoring it to your role…"];
  const GRADING_LINES = ["Reading your answer carefully…", "Comparing it with what interviewers look for…"];
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

  function progress(position) {
    pips.forEach((p, i) => {
      p.classList.toggle("is-done", i < position - 1);
      p.classList.toggle("is-now", i === position - 1);
    });
  }

  // The next question is written in the background while you answer this
  // one, so "Continue" is instant instead of an 8-second wait.
  let prefetched = null;
  const fetchNext = () => B.post("/session/next/", {});

  async function next() {
    window.scrollTo({ top: 0, behavior: "smooth" });
    const ready = prefetched;
    prefetched = null;
    stage.innerHTML = THINKING(pick(LOADING_LINES));
    stage.style.animation = "none"; void stage.offsetWidth; stage.style.animation = "";
    try {
      let data = (ready && (await ready)) || (await fetchNext());
      // A prefetched "done" was computed before the last answer was graded;
      // ask again so the summary includes it.
      if (data.done && ready) data = await fetchNext();
      if (data.done) return summary(data.summary);
      if (data.position < data.total) prefetched = fetchNext().catch(() => null);
      progress(data.position);
      render(data.card);
    } catch (e) {
      stage.innerHTML = `<div class="thinking"><p>${esc(e.message)}</p><a class="btn" href="/today/">Back to Today</a></div>`;
    }
  }

  function header(card) {
    return `<div class="qcard__meta">
      <span class="chip chip--beam">${esc(card.skill)}</span>
      ${card.is_review ? '<span class="chip chip--memory"><span class="dot"></span>Spaced review</span>' : ""}
      <span class="chip">${esc(card.kind_label)}</span>
    </div>
    <h1 class="qcard__prompt">${esc(card.prompt)}</h1>`;
  }

  function render(card) {
    if (card.kind === "CHOICE") {
      stage.innerHTML = header(card) + `<div class="options" role="group" aria-label="Answer options">
        ${card.options.map((o, i) => `<button class="option" data-pick="${i}"><span class="option__key">${"ABCD"[i]}</span><span>${esc(o)}</span></button>`).join("")}
      </div><div data-feedback></div>`;
      stage.querySelectorAll("[data-pick]").forEach((btn) =>
        btn.addEventListener("click", () => answerChoice(card, Number(btn.dataset.pick))));
      const keyHandler = (e) => {
        const i = "abcd".indexOf(e.key.toLowerCase());
        if (i >= 0 && stage.querySelector(`[data-pick="${i}"]:not([disabled])`)) {
          document.removeEventListener("keydown", keyHandler);
          answerChoice(card, i);
        }
      };
      document.addEventListener("keydown", keyHandler);
      return;
    }
    const hint = card.kind === "STORY" ? "Situation → Task → Action → Result. First person, a real example, and end with what changed."
      : "A few clear sentences. Say it the way you would in the room.";
    stage.innerHTML = header(card) + `
      <label class="sr-only" for="answer">Your answer</label>
      <textarea class="answer" id="answer" placeholder="${esc(hint)}"></textarea>
      <div class="answer-bar">
        <div class="row">
          ${B.Speech ? '<button type="button" class="mic-btn" data-mic aria-label="Speak your answer"><svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></button>' : ""}
          <span class="small muted" data-words>0 words</span>
        </div>
        <div class="row">
          <button type="button" class="btn btn--ghost" data-skip>Skip</button>
          <button type="button" class="btn btn--beam" data-submit>Check my answer</button>
        </div>
      </div><div data-feedback></div>`;
    const area = stage.querySelector("#answer");
    const words = stage.querySelector("[data-words]");
    area.focus();
    area.addEventListener("input", () => {
      const n = area.value.trim() ? area.value.trim().split(/\s+/).length : 0;
      words.textContent = `${n} word${n === 1 ? "" : "s"}`;
    });
    area.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit(); });
    const mic = stage.querySelector("[data-mic]");
    if (mic) B.Speech.attach(mic, area);
    const submit = () => answerWritten(card, area.value);
    stage.querySelector("[data-submit]").addEventListener("click", submit);
    stage.querySelector("[data-skip]").addEventListener("click", () => answerWritten(card, "", true));
  }

  async function answerChoice(card, i) {
    stage.querySelectorAll("[data-pick]").forEach((b) => (b.disabled = true));
    const result = await B.post(`/cards/${card.id}/answer/`, { pick: i }).catch((e) => B.toast(e.message));
    if (!result) return;
    const right = result.feedback.correct;
    stage.querySelector(`[data-pick="${right}"]`).classList.add("is-right");
    if (i !== right) stage.querySelector(`[data-pick="${i}"]`).classList.add("is-wrong");
    showFeedback(result, `<p class="mt-8" style="color:var(--text-2)">${esc(result.feedback.why)}</p>`);
  }

  async function answerWritten(card, text, skipped) {
    const fb = stage.querySelector("[data-feedback]");
    stage.querySelectorAll("button, textarea").forEach((el) => (el.disabled = true));
    if (B.Speech) B.Speech.stop();
    fb.innerHTML = THINKING(pick(GRADING_LINES));
    try {
      const result = await B.post(`/cards/${card.id}/answer/`, { answer: skipped ? "" : text });
      const f = result.feedback;
      let body = "";
      if (f.strengths && f.strengths.length) body += `<h3 class="h3 mt-16">What worked</h3><ul class="fb-list">${f.strengths.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>`;
      if (f.improve && f.improve.length) body += `<h3 class="h3 mt-16">Make it stronger</h3><ul class="fb-list fb-list--improve">${f.improve.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>`;
      if (f.star) body += `<div class="star-bars">${["situation", "task", "action", "result"].map((k) =>
        `<div><span>${k[0].toUpperCase() + k.slice(1)} · ${f.star[k]}</span><div class="bar"><span style="width:${f.star[k]}%"></span></div></div>`).join("")}</div>`;
      if (f.model_answer) body += `<details class="model-answer"><summary>See a stronger version</summary><p>${esc(f.model_answer)}</p></details>`;
      fb.innerHTML = "";
      showFeedback(result, body);
    } catch (e) {
      fb.innerHTML = `<p class="care-note">${esc(e.message)}</p>`;
      stage.querySelectorAll("button, textarea").forEach((el) => (el.disabled = false));
    }
  }

  function showFeedback(result, body) {
    xp += result.xp;
    xpEl.textContent = xp;
    const f = result.feedback;
    const delta = result.after - result.before;
    const days = result.next_review_days;
    const when = days < 1 ? "later today" : days < 1.5 ? "tomorrow" : `in ${Math.round(days)} days`;
    const html = `<section class="card feedback" aria-live="polite">
      <div class="feedback__top">
        <div class="score-pill tnum">${result.score}<small>/100</small></div>
        <div>
          <p style="font-weight:600">${esc(f.headline || "")}</p>
          <p class="small muted mt-8"><span class="xp-pop">+${result.xp} XP</span> · ${esc(result.level)} · next review ${when}</p>
        </div>
      </div>
      ${body}
      <div class="grow">
        <div class="spread small"><span>Skill level</span><span class="tnum">${result.before} → <strong>${result.after}</strong> ${delta > 0 ? `<span style="color:var(--good)">▲ ${delta}</span>` : ""}</span></div>
        <div class="bar mt-8"><span style="width:${result.before}%" data-grow="${result.after}"></span></div>
      </div>
      <div class="row mt-24" style="justify-content:flex-end"><button class="btn btn--beam" data-next>Continue <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></div>
    </section>`;
    (stage.querySelector("[data-feedback]") || stage).insertAdjacentHTML("beforeend", html);
    const grow = stage.querySelector("[data-grow]");
    setTimeout(() => (grow.style.width = grow.dataset.grow + "%"), 350);
    const nextBtn = stage.querySelector("[data-next]");
    nextBtn.focus({ preventScroll: true });
    nextBtn.scrollIntoView({ behavior: "smooth", block: "nearest" });
    nextBtn.addEventListener("click", next);
  }

  function summary(s) {
    pips.forEach((p) => { p.classList.add("is-done"); p.classList.remove("is-now"); });
    const gained = s.readiness_after - s.readiness_before;
    stage.innerHTML = `<div class="summary">
      <div class="eyebrow">Session complete</div>
      <h1 class="display mt-8">${s.cards >= 3 ? "That was <em>real</em> progress." : "Every rep <em>counts</em>."}</h1>
      <div class="summary__stats">
        <div class="stat"><div class="stat__n tnum">${s.cards}</div><div class="stat__l">questions</div></div>
        <div class="stat"><div class="stat__n tnum">+${s.xp}</div><div class="stat__l">XP earned</div></div>
        <div class="stat"><div class="stat__n tnum">${s.streak}</div><div class="stat__l">day streak</div></div>
      </div>
      <p class="lede" style="margin:0 auto">Readiness ${s.readiness_before}% → <strong>${s.readiness_after}%</strong>${gained > 0 ? ` <span style="color:var(--good)">▲ ${gained}</span>` : ""}. Beacon has scheduled each skill's next review for just before you'd start to forget it.</p>
      <div class="row mt-32" style="justify-content:center">
        <a class="btn btn--beam btn--big" href="/today/">Back to Today</a>
        <a class="btn" href="/interview/">Try a mock interview</a>
      </div></div>`;
    if (s.cards) confetti();
  }

  function confetti() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const c = document.createElement("canvas");
    c.className = "confetti"; document.body.appendChild(c);
    const ctx = c.getContext("2d");
    c.width = innerWidth; c.height = innerHeight;
    const colors = ["#ffc46b", "#ff8a5c", "#a99bff", "#6fe3b0", "#fff3dc"];
    const parts = Array.from({ length: 140 }, () => ({
      x: innerWidth / 2, y: innerHeight / 3, vx: (Math.random() - .5) * 14, vy: Math.random() * -14 - 4,
      r: Math.random() * 5 + 3, c: colors[Math.floor(Math.random() * colors.length)], a: Math.random() * 6,
    }));
    let frames = 0;
    (function tick() {
      ctx.clearRect(0, 0, c.width, c.height);
      parts.forEach((p) => {
        p.vy += .35; p.x += p.vx; p.y += p.vy; p.a += .1;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.a); ctx.fillStyle = p.c;
        ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * .6); ctx.restore();
      });
      if (++frames < 160) requestAnimationFrame(tick); else c.remove();
    })();
  }

  next();
})();
