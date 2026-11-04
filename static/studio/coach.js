/* Coach chat: send, show a typing indicator, append the reply. */
(function () {
  "use strict";
  const B = window.BEACON;
  const root = document.querySelector("[data-chat]");
  if (!root) return;
  const log = root.querySelector("[data-log]");
  const form = root.querySelector("[data-composer]");
  const input = root.querySelector("[data-input]");
  const mic = root.querySelector("[data-mic]");

  function bubble(text, who) {
    const div = document.createElement("div");
    div.className = `bubble bubble--${who}`;
    div.textContent = text;
    log.appendChild(div);
    div.scrollIntoView({ behavior: "smooth", block: "end" });
    return div;
  }

  async function send(text) {
    text = text.trim();
    if (!text) return;
    const starters = root.querySelector("[data-starters]");
    if (starters) starters.remove();
    bubble(text, "you");
    input.value = ""; input.style.height = "";
    const typing = bubble("", "coach");
    typing.classList.add("bubble--typing");
    typing.innerHTML = "<span></span><span></span><span></span>";
    form.querySelector("[type=submit]").disabled = true;
    try {
      const { html } = await B.post("/coach/send/", { message: text });
      typing.classList.remove("bubble--typing");
      typing.innerHTML = html;   // escaped and formatted on the server
    } catch (e) {
      typing.remove();
      B.toast(e.message);
    }
    form.querySelector("[type=submit]").disabled = false;
    input.focus();
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 180) + "px"; });
  root.querySelectorAll("[data-starter]").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
  if (mic && B.Speech) { mic.hidden = false; B.Speech.attach(mic, input); }
  log.lastElementChild && log.lastElementChild.scrollIntoView({ block: "end" });
})();
