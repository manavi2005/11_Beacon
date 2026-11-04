/* Mock interview room: the interviewer speaks, you answer by voice or text. */
(function () {
  "use strict";
  const B = window.BEACON;
  const root = document.querySelector("[data-interview]");
  if (!root) return;
  const $ = (sel) => root.querySelector(sel);
  const setup = $("[data-setup]"), room = $("[data-room]");
  const orb = $("[data-orb]"), say = $("[data-say]"), live = $("[data-live]"), typed = $("[data-typed]");
  const talk = $("[data-talk]"), send = $("[data-send]"), switchBtn = $("[data-switch]");
  const counter = $("[data-counter]"), log = $("[data-transcript]");
  let session = null, voice = !!B.Speech, answer = "", busy = false;

  function seg(name) {
    const group = $(`[data-${name}]`);
    group.addEventListener("click", (e) => {
      const btn = e.target.closest("button"); if (!btn) return;
      group.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
    });
    return () => group.querySelector('[aria-pressed="true"]').dataset.value;
  }
  const mode = seg("mode"), length = seg("length"), input = seg("input");
  if (!B.Speech) {
    $('[data-input] [data-value="voice"]').disabled = true;
    $('[data-input] [data-value="type"]').click();
  }

  function addLine(who, text) {
    const p = document.createElement("p");
    p.className = who === "you" ? "you" : "";
    p.textContent = (who === "you" ? "You: " : "Interviewer: ") + text;
    log.appendChild(p);
  }

  function setOrb(state) {
    orb.classList.remove("is-speaking", "is-listening", "is-thinking");
    if (state) orb.classList.add(state);
  }

  function interviewerSays(text, q, total) {
    counter.textContent = `Question ${q} of ${total}`;
    say.textContent = text;
    addLine("interviewer", text);
    setOrb("is-speaking");
    B.speak(text, () => { setOrb(null); readyToAnswer(); });
  }

  function readyToAnswer() {
    answer = ""; live.textContent = ""; typed.value = "";
    busy = false;
    if (voice) {
      live.hidden = false; typed.hidden = true;
      talk.hidden = false; send.hidden = true;
      switchBtn.textContent = "Type instead";
    } else {
      live.hidden = true; typed.hidden = false; typed.focus();
      talk.hidden = true; send.hidden = false;
      switchBtn.textContent = B.Speech ? "Speak instead" : "";
      switchBtn.hidden = !B.Speech;
    }
  }

  talk.addEventListener("click", () => {
    talk.hidden = true; send.hidden = false;
    setOrb("is-listening");
    B.Speech.listen({
      onText: (t) => { answer = t; live.textContent = t; },
      onEnd: (t) => { if (t) answer = t; },
    });
  });

  switchBtn.addEventListener("click", () => {
    if (B.Speech) B.Speech.stop();
    voice = !voice;
    const keep = voice ? typed.value : answer;
    readyToAnswer();
    if (voice) { answer = keep; live.textContent = keep; } else { typed.value = keep; }
  });

  send.addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    if (B.Speech && B.Speech.live) {
      B.Speech.stop();
      await new Promise((r) => setTimeout(r, 600));   // let the last words land
    }
    const text = (voice ? answer : typed.value).trim();
    if (!text) { busy = false; B.toast("Say or type something first. Even a rough start is fine."); return; }
    addLine("you", text);
    send.hidden = true; talk.hidden = true;
    setOrb("is-thinking");
    say.textContent = "…";
    try {
      const data = await B.post(`/interview/${session}/reply/`, { answer: text });
      if (data.done) return finish();
      interviewerSays(data.say, data.question, data.total);
    } catch (e) { B.toast(e.message); busy = false; send.hidden = false; setOrb(null); }
  });

  async function finish() {
    if (B.Speech) B.Speech.stop();
    window.speechSynthesis && window.speechSynthesis.cancel();
    setOrb("is-thinking");
    say.textContent = "Thank you, that's everything. Putting your feedback together…";
    live.hidden = typed.hidden = talk.hidden = send.hidden = true;
    try {
      const data = await B.post(`/interview/${session}/finish/`, {});
      window.location.href = data.url;
    } catch (e) { B.toast(e.message); }
  }
  $("[data-end]").addEventListener("click", () => {
    if (!session) return;
    if (log.querySelectorAll(".you").length === 0 && !confirm("You haven't answered anything yet. End anyway?")) return;
    finish();
  });

  $("[data-mute]").addEventListener("click", (e) => {
    B.muted = !B.muted;
    e.target.textContent = B.muted ? "🔇 Voice off" : "🔈 Voice on";
    if (B.muted) window.speechSynthesis && window.speechSynthesis.cancel();
  });

  $("[data-begin]").addEventListener("click", async (e) => {
    e.target.disabled = true;
    voice = input() === "voice" && !!B.Speech;
    // Unlock speech on this user gesture (iOS needs it).
    if ("speechSynthesis" in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance(""));
    try {
      const data = await B.post("/interview/start/", { mode: mode(), questions: Number(length()) });
      session = data.id;
      setup.hidden = true; room.hidden = false;
      document.querySelector(".rail") && (document.querySelector(".rail").style.opacity = ".35");
      interviewerSays(data.say, data.question, data.total);
    } catch (err) { B.toast(err.message); e.target.disabled = false; }
  });

  if ("speechSynthesis" in window) window.speechSynthesis.getVoices();
})();
