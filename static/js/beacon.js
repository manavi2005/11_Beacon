/* ===========================================================================
   Beacon front-end behaviour (Assignment 5 polish).

   Plain JavaScript, no framework and no build step, loaded with `defer` from
   base.html. Every feature here is progressive: the page works without it.

     1. Count-up numbers       [data-count]
     2. Reveal-on-load         .js-reveal -> .is-ready (bars, rings)
     3. Command palette        Ctrl/Cmd+K, or any [data-palette-open]

   Motion is skipped entirely for readers who ask their OS for less of it.
   =========================================================================== */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* -------------------------------------------------------------------------
     1. Count-up numbers. The real value is already in the HTML, so a reader
        without JavaScript, or a screen reader, gets it straight away.
     ------------------------------------------------------------------------- */
  function countUp(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    if (isNaN(target) || reduceMotion) return;
    var decimals = (el.getAttribute("data-count").split(".")[1] || "").length;
    var suffix = el.getAttribute("data-suffix") || "";
    var duration = 900;
    var start = null;
    function frame(now) {
      if (start === null) start = now;
      var t = Math.min((now - start) / duration, 1);
      var eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (t < 1) requestAnimationFrame(frame);
    }
    el.textContent = (0).toFixed(decimals) + suffix;
    requestAnimationFrame(frame);
  }

  /* -------------------------------------------------------------------------
     2. Reveal. Bars and rings are drawn at their final size by the CSS; the
        .is-ready class is what lets them grow in from zero once, on load.
     ------------------------------------------------------------------------- */
  function reveal() {
    document.querySelectorAll("[data-count]").forEach(countUp);
    // Two frames, so the browser paints the zero state before transitioning.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        document.documentElement.classList.add("is-ready");
      });
    });
  }

  /* -------------------------------------------------------------------------
     3. Command palette
     ------------------------------------------------------------------------- */
  var palette = document.querySelector("[data-palette]");
  var input, list, items = null, shown = [], active = 0, lastFocus = null;

  // Subsequence match with a score: consecutive letters and word starts
  // score higher, so "sql" ranks "SQL & relational modeling" above
  // "System design basics".
  function score(query, text) {
    if (!query) return 1;
    query = query.toLowerCase();
    text = text.toLowerCase();
    var qi = 0, s = 0, run = 0;
    for (var ti = 0; ti < text.length && qi < query.length; ti++) {
      if (text[ti] === query[qi]) {
        run += 1;
        s += 1 + run + (ti === 0 || text[ti - 1] === " " ? 3 : 0);
        qi += 1;
      } else {
        run = 0;
      }
    }
    return qi === query.length ? s : 0;
  }

  function render() {
    var q = input.value.trim();
    shown = (items || [])
      .map(function (it) {
        return { it: it, s: Math.max(score(q, it.label), score(q, it.hint || "") * 0.5) };
      })
      .filter(function (r) { return r.s > 0; })
      .sort(function (a, b) { return b.s - a.s; })
      .slice(0, 12)
      .map(function (r) { return r.it; });
    active = Math.min(active, Math.max(shown.length - 1, 0));
    list.innerHTML = "";
    if (!shown.length) {
      var empty = document.createElement("li");
      empty.className = "palette__empty";
      empty.textContent = items ? "Nothing matches “" + q + "”" : "Loading…";
      list.appendChild(empty);
      return;
    }
    shown.forEach(function (it, i) {
      var li = document.createElement("li");
      li.className = "palette__item" + (i === active ? " is-active" : "");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", i === active ? "true" : "false");
      var group = document.createElement("span");
      group.className = "palette__group palette__group--" + it.group.toLowerCase();
      group.textContent = it.group;
      var label = document.createElement("span");
      label.className = "palette__label";
      label.textContent = it.label;
      var hint = document.createElement("span");
      hint.className = "palette__hint-text";
      hint.textContent = it.hint || "";
      li.appendChild(group);
      li.appendChild(label);
      li.appendChild(hint);
      li.addEventListener("mousemove", function () {
        if (active !== i) { active = i; render(); }
      });
      li.addEventListener("click", function () { go(it); });
      list.appendChild(li);
    });
  }

  function go(it) { if (it) window.location.href = it.url; }

  function load() {
    if (items) return;
    fetch(palette.getAttribute("data-source"), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : { items: [] }; })
      .then(function (data) { items = data.items || []; render(); })
      .catch(function () { items = []; render(); });
  }

  function open() {
    if (!palette || !palette.hidden) return;
    lastFocus = document.activeElement;
    palette.hidden = false;
    document.documentElement.classList.add("palette-open");
    input.value = "";
    active = 0;
    render();
    load();
    input.focus();
  }

  function close() {
    if (!palette || palette.hidden) return;
    palette.hidden = true;
    document.documentElement.classList.remove("palette-open");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  if (palette) {
    input = palette.querySelector(".palette__input");
    list = palette.querySelector(".palette__results");

    input.addEventListener("input", function () { active = 0; render(); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { active = Math.min(active + 1, shown.length - 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); render(); e.preventDefault(); }
      else if (e.key === "Enter") { go(shown[active]); e.preventDefault(); }
    });
    palette.querySelectorAll("[data-palette-close]").forEach(function (el) {
      el.addEventListener("click", close);
    });
    document.querySelectorAll("[data-palette-open]").forEach(function (el) {
      el.addEventListener("click", open);
    });
    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        palette.hidden ? open() : close();
      } else if (e.key === "Escape") {
        close();
      }
    });
    // Show the right shortcut: the nav says ⌘K on a Mac, Ctrl K elsewhere.
    if (!/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) {
      document.querySelectorAll(".nav-palette kbd").forEach(function (k) {
        k.textContent = "Ctrl K";
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", reveal);
  } else {
    reveal();
  }
})();
