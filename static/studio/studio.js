/* Beacon v2: shared behaviour. Page-specific code lives in its own file. */
(function () {
  "use strict";

  const B = (window.BEACON = window.BEACON || {});
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  B.post = async function (url, data) {
    const isForm = data instanceof FormData;
    const res = await fetch(url, {
      method: "POST",
      headers: Object.assign({ "X-CSRFToken": B.csrf }, isForm ? {} : { "Content-Type": "application/json" }),
      body: isForm ? data : JSON.stringify(data || {}),
      credentials: "same-origin",
    });
    let body = {};
    try { body = await res.json(); } catch (e) { /* non-JSON error page */ }
    if (!res.ok) throw new Error(body.error || "Something went wrong. Please try again.");
    return body;
  };

  B.toast = function (message) {
    const el = document.querySelector(".toast");
    if (!el) return;
    el.textContent = message;
    el.hidden = false;
    clearTimeout(B._toastTimer);
    B._toastTimer = setTimeout(() => (el.hidden = true), 3600);
  };

  B.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  };

  B.countUp = function (el, to, ms) {
    const small = el.querySelector("small");
    const suffix = small ? small.outerHTML : "";
    if (reduced) { el.innerHTML = to + suffix; return; }
    const start = performance.now();
    const from = 0;
    (function frame(now) {
      const t = Math.min((now - start) / (ms || 1400), 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.innerHTML = Math.round(from + (to - from) * eased) + suffix;
      if (t < 1) requestAnimationFrame(frame);
    })(start);
  };

  B.animateRings = function (root) {
    (root || document).querySelectorAll("[data-ring]").forEach((ring) => {
      const value = Math.max(0, Math.min(100, Number(ring.dataset.ring) || 0));
      const arc = ring.querySelector(".ring__value");
      const fc = ring.querySelector(".ring__forecast");
      if (fc) {
        const f = Math.max(value, Math.min(100, Number(ring.dataset.forecast) || 0));
        fc.setAttribute("stroke-dasharray", `0 ${value} ${f - value} 100`);
      }
      requestAnimationFrame(() => arc && arc.setAttribute("stroke-dashoffset", String(100 - value)));
      const num = ring.querySelector("[data-count]");
      if (num) B.countUp(num, value);
    });
  };

  /* Readiness over time: one series, so no legend; the bar line is labelled. */
  B.trend = function (el) {
    let points = [];
    try { points = JSON.parse(el.dataset.trend || "[]"); } catch (e) { points = []; }
    if (points.length < 2) {
      el.innerHTML = '<p class="trend__empty">Your line starts here. Come back tomorrow to see it grow.</p>';
      return;
    }
    const W = el.clientWidth || 400, H = el.clientHeight || 160, pad = { l: 30, r: 10, t: 12, b: 22 };
    const target = Number(el.dataset.target || 80);
    const x = (i) => pad.l + (i / (points.length - 1)) * (W - pad.l - pad.r);
    const y = (v) => pad.t + (1 - v / 100) * (H - pad.t - pad.b);
    const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    const area = `${line}L${x(points.length - 1)},${y(0)}L${x(0)},${y(0)}Z`;
    const fmt = (d) => new Date(d + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
    el.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Readiness over the last ${points.length} active days, from ${points[0].v}% to ${points[points.length - 1].v}%">
        <defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#ffb06b" stop-opacity=".35"/><stop offset="1" stop-color="#ffb06b" stop-opacity="0"/></linearGradient></defs>
        ${[0, 50, 100].map((v) => `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" stroke="rgba(255,255,255,.06)"/>
          <text x="${pad.l - 8}" y="${y(v) + 4}" text-anchor="end" font-size="10" fill="#8d8aa6">${v}</text>`).join("")}
        <line x1="${pad.l}" x2="${W - pad.r}" y1="${y(target)}" y2="${y(target)}" stroke="#a99bff" stroke-dasharray="3 5" stroke-width="1.5"/>
        <text x="${W - pad.r}" y="${y(target) - 6}" text-anchor="end" font-size="10.5" fill="#d8d0ff">Interview-ready ${target}%</text>
        <path d="${area}" fill="url(#trendFill)"/>
        <path d="${line}" fill="none" stroke="#ffb06b" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle class="trend__dot" r="5" fill="#ffc46b" stroke="#0b0d1a" stroke-width="2" cx="${x(points.length - 1)}" cy="${y(points[points.length - 1].v)}"/>
        <text x="${pad.l}" y="${H - 4}" font-size="10" fill="#8d8aa6">${fmt(points[0].d)}</text>
        <text x="${W - pad.r}" y="${H - 4}" font-size="10" fill="#8d8aa6" text-anchor="end">${fmt(points[points.length - 1].d)}</text>
        <rect x="${pad.l}" y="0" width="${W - pad.l - pad.r}" height="${H}" fill="transparent" class="trend__hit"/>
      </svg><div class="trend__tip" hidden></div>`;
    const svg = el.querySelector("svg"), dot = el.querySelector(".trend__dot"), tip = el.querySelector(".trend__tip");
    const hit = el.querySelector(".trend__hit");
    const show = (evt) => {
      const r = svg.getBoundingClientRect();
      const px = ((evt.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(points.length - 1, Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (points.length - 1))));
      dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(points[i].v));
      tip.hidden = false;
      tip.style.left = (x(i) / W) * 100 + "%";
      tip.style.top = (y(points[i].v) / H) * 100 + "%";
      tip.textContent = `${fmt(points[i].d)} · ${points[i].v}% ready`;
    };
    hit.addEventListener("pointermove", show);
    hit.addEventListener("pointerleave", () => {
      tip.hidden = true;
      dot.setAttribute("cx", x(points.length - 1)); dot.setAttribute("cy", y(points[points.length - 1].v));
    });
  };

  /* Speech: the browser's own recognition where it exists (Chrome, Edge,
     Safari); otherwise record and send to /interview/transcribe (Lumen's
     free speech model). Audio is never stored. */
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canRecord = !!(navigator.mediaDevices && window.MediaRecorder);
  if (Recognition || canRecord) {
    B.Speech = {
      native: !!Recognition,
      _rec: null, _media: null,
      /* listen({onText(fullText, isFinal), onEnd}) */
      listen(opts) {
        this.stop();
        if (Recognition) {
          const rec = new Recognition();
          rec.continuous = true; rec.interimResults = true; rec.lang = navigator.language || "en-US";
          let finalText = "";
          rec.onresult = (e) => {
            let interim = "";
            for (let i = e.resultIndex; i < e.results.length; i++) {
              if (e.results[i].isFinal) finalText += e.results[i][0].transcript + " ";
              else interim += e.results[i][0].transcript;
            }
            opts.onText((finalText + interim).trim(), !interim);
          };
          rec.onerror = (e) => { if (e.error === "not-allowed") B.toast("Microphone access is blocked. You can type instead."); };
          rec.onend = () => { this._rec = null; opts.onEnd && opts.onEnd(finalText.trim()); };
          rec.start();
          this._rec = rec;
          return Promise.resolve();
        }
        return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
          const chunks = [];
          const media = new MediaRecorder(stream);
          media.ondataavailable = (e) => e.data.size && chunks.push(e.data);
          media.onstop = async () => {
            stream.getTracks().forEach((t) => t.stop());
            this._media = null;
            const form = new FormData();
            form.append("audio", new Blob(chunks, { type: media.mimeType }), "answer.webm");
            opts.onText("Transcribing…", false);
            try {
              const { text } = await B.post("/interview/transcribe/", form);
              opts.onText(text, true); opts.onEnd && opts.onEnd(text);
            } catch (err) { B.toast(err.message); opts.onText("", true); opts.onEnd && opts.onEnd(""); }
          };
          media.start();
          this._media = media;
        }).catch(() => B.toast("Microphone access is blocked. You can type instead."));
      },
      stop() {
        if (this._rec) this._rec.stop();
        if (this._media && this._media.state !== "inactive") this._media.stop();
      },
      get live() { return !!(this._rec || this._media); },
      /* Dictation into a textarea, toggled by a button. */
      attach(button, area) {
        let base = "";
        button.addEventListener("click", () => {
          if (this.live) { this.stop(); return; }
          base = area.value ? area.value.trim() + " " : "";
          button.classList.add("is-live");
          this.listen({
            onText: (t) => { area.value = base + t; area.dispatchEvent(new Event("input")); },
            onEnd: () => button.classList.remove("is-live"),
          });
        });
      },
    };
  }

  B.speak = function (text, onEnd) {
    if (!("speechSynthesis" in window) || B.muted) { onEnd && onEnd(); return; }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const lang = (navigator.language || "en").slice(0, 2);
    const preferred = voices.find((v) => v.lang.startsWith(lang) && /natural|premium|enhanced|samantha|google/i.test(v.name))
      || voices.find((v) => v.lang.startsWith(lang));
    if (preferred) u.voice = preferred;
    u.rate = 1.0; u.pitch = 1.0;
    u.onend = () => onEnd && onEnd();
    u.onerror = () => onEnd && onEnd();
    window.speechSynthesis.speak(u);
  };

  function moodPicker(root) {
    root.addEventListener("click", async (evt) => {
      const btn = evt.target.closest("[data-mood]");
      if (!btn) return;
      try {
        await B.post("/today/mood/", { mood: btn.dataset.mood });
        window.location.reload();
      } catch (e) { B.toast(e.message); }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    B.animateRings();
    document.querySelectorAll("[data-trend]").forEach(B.trend);
    document.querySelectorAll("[data-mood-picker]").forEach(moodPicker);
    document.querySelectorAll(".skill__fill, .bar > span").forEach((bar) => {
      if (reduced) return;
      const w = bar.style.width;
      bar.style.width = "0";
      requestAnimationFrame(() => requestAnimationFrame(() => {
        bar.style.transition = "width 1.2s cubic-bezier(.2,.8,.2,1)";
        bar.style.width = w;
      }));
    });
  });
})();
