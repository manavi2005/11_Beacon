/* ===========================================================================
   Beacon front-end behaviour (Assignment 5 polish).

   Plain JavaScript, no framework and no build step, loaded with `defer` from
   base.html. Every feature here is progressive: the page works without it.

     1. Count-up numbers       [data-count]
     2. Reveal-on-load         .js-reveal -> .is-ready (bars, rings)
     3. Command palette        Ctrl/Cmd+K, or any [data-palette-open]
     4. Interactive lighthouse beam follows the mouse
     5. Onboarding stepper     live sliders and projected readiness
     6. Task checkboxes        tick off without a reload

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

  /* -------------------------------------------------------------------------
     4. Interactive lighthouse. While the mouse is over a [data-lighthouse]
        drawing, the beam turns to point at it; when the mouse leaves, the
        beam eases back into its automatic sweep. The lamp sits at (300, 120)
        in the drawing's own 400x300 coordinates, and the beam is drawn
        pointing left, so the turn needed is the pointer's angle minus 180.
     ------------------------------------------------------------------------- */
  function lighthouse(svg) {
    var beam = svg.querySelector(".lighthouse__beam");
    var host = svg.parentElement;
    if (!beam || !host || reduceMotion || !svg.getScreenCTM) return;
    var raf = null, pending = null;

    function aim() {
      raf = null;
      var ctm = svg.getScreenCTM();
      if (!ctm || !pending) return;
      var pt = svg.createSVGPoint();
      pt.x = pending.x; pt.y = pending.y;
      var p = pt.matrixTransform(ctm.inverse());
      var angle = Math.atan2(p.y - 120, p.x - 300) * 180 / Math.PI;  // -180..180
      var turn = angle < 0 ? angle + 180 : angle - 180;                // relative to pointing left
      turn = Math.max(-55, Math.min(55, turn));
      beam.style.transform = "rotate(" + turn.toFixed(1) + "deg)";
    }

    host.addEventListener("pointermove", function (e) {
      pending = { x: e.clientX, y: e.clientY };
      if (!svg.classList.contains("is-tracking")) svg.classList.add("is-tracking");
      if (!raf) raf = requestAnimationFrame(aim);
    });
    host.addEventListener("pointerleave", function () {
      pending = null;
      beam.style.transform = "";
      svg.classList.remove("is-tracking");
    });
  }

  /* -------------------------------------------------------------------------
     5. Onboarding: one step at a time, sliders with live values and role
        targets, and a projected-readiness ring using the same formula as
        CandidateProfile.readiness_percent: mean of min(rating/required, 1).
     ------------------------------------------------------------------------- */
  function onboarding(form) {
    var steps = form.querySelectorAll("[data-step]");
    var dots = form.querySelectorAll("[data-step-dot]");
    var role = form.querySelector("[name=target_role]");
    var sliders = form.querySelectorAll("input[type=range]");
    var ring = document.querySelector("[data-onb-ring]");
    var ringNumber = document.querySelector("[data-onb-readiness]");
    var defaultRequired = parseInt(form.getAttribute("data-default-required"), 10) || 65;
    var requirements = {}, names = {};
    try {
      requirements = JSON.parse(document.getElementById("role-requirements").textContent);
      names = JSON.parse(document.getElementById("skill-names").textContent);
    } catch (e) { /* no live targets; the form still submits */ }

    function show(n) {
      steps.forEach(function (s) { s.hidden = s.getAttribute("data-step") !== String(n); });
      dots.forEach(function (d) {
        var k = parseInt(d.getAttribute("data-step-dot"), 10);
        d.classList.toggle("is-current", k === n);
        d.classList.toggle("is-done", k < n);
      });
      window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    }

    function required(id) {
      var table = requirements[role ? role.value : ""] || {};
      return table[names[id]] || defaultRequired;
    }

    function update() {
      var total = 0, n = 0;
      sliders.forEach(function (s) {
        var value = parseInt(s.value, 10);
        var req = required(s.id);
        var out = form.querySelector('output[for="' + s.id + '"]');
        if (out) {
          out.textContent = value;
          out.classList.toggle("is-below", value < req);
        }
        var mark = form.querySelector('[data-target-for="' + s.id + '"]');
        if (mark) {
          mark.hidden = false;
          mark.style.left = req + "%";
          mark.title = "Your role expects " + req;
        }
        s.style.setProperty("--fill", value + "%");
        total += Math.min(value / req, 1);
        n += 1;
      });
      if (ring && n) {
        var pct = Math.round(total / n * 100);
        ring.style.setProperty("--p", pct);
        ring.classList.toggle("ring--good", pct >= 75);
        ring.classList.toggle("ring--mid", pct >= 50 && pct < 75);
        ring.classList.toggle("ring--low", pct < 50);
        ringNumber.textContent = pct + "%";
      }
    }

    form.querySelectorAll("[data-step-go]").forEach(function (b) {
      b.addEventListener("click", function () {
        var target = parseInt(b.getAttribute("data-step-go"), 10);
        if (target === 2) {
          var date = form.querySelector("[name=target_interview_date]");
          if (date && !date.reportValidity()) return;
        }
        show(target);
      });
    });
    sliders.forEach(function (s) { s.addEventListener("input", update); });
    if (role) role.addEventListener("change", update);

    // After a failed submit, open the step that holds the first error.
    var firstError = form.querySelector(".field--error");
    var errorStep = firstError ? firstError.closest("[data-step]") : null;
    show(errorStep ? parseInt(errorStep.getAttribute("data-step"), 10) : 1);
    update();
  }

  /* -------------------------------------------------------------------------
     6. Tick a task off without a page reload. The form still works on its
        own; this only sends the same POST with fetch and updates in place.
     ------------------------------------------------------------------------- */
  function taskToggle(form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var item = form.closest(".task");
      var button = form.querySelector(".task__check");
      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "Accept": "application/json" },
        credentials: "same-origin",
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (data) {
          item.classList.toggle("task--done", data.done);
          button.setAttribute("aria-checked", data.done ? "true" : "false");
          var bar = document.querySelector("[data-plan-progress]");
          var label = document.querySelector("[data-plan-percent]");
          if (bar) bar.style.setProperty("--w", data.completion_percent + "%");
          if (label) label.textContent = data.completion_percent;
          var week = item.closest(".week");
          if (week) {
            week.classList.toggle("week--done",
              week.querySelectorAll(".task").length === week.querySelectorAll(".task--done").length);
          }
        })
        .catch(function () { form.submit(); });  // fall back to a normal POST
    });
  }

  document.querySelectorAll("[data-lighthouse]").forEach(lighthouse);
  document.querySelectorAll("[data-onboarding]").forEach(onboarding);
  document.querySelectorAll("[data-task-toggle]").forEach(taskToggle);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", reveal);
  } else {
    reveal();
  }
})();
