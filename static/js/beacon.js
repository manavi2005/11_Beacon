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
     7. Menus                  one open at a time, close on outside click
     8. Developer notes        "Show how pages are built" switch
     9. AI coach               advice swap-in and the question box

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
     5. Onboarding: three steps, one at a time.
        - Interests mark matching roles "Suggested for you", and pre-select
          the best match if no role has been picked yet.
        - Up to three roles; "General interview readiness" is exclusive.
        - "Interview booked?" swaps the date field for a plan length.
        - Each slider shows the bar the chosen roles set (the highest among
          them), and the ring projects readiness with the same formula as
          CandidateProfile.readiness_percent: mean of min(rating/required, 1).
     ------------------------------------------------------------------------- */
  function onboarding(form) {
    var GENERAL = "General interview readiness";
    var MAX_ROLES = 3;
    var steps = form.querySelectorAll("[data-step]");
    var dots = form.querySelectorAll("[data-step-dot]");
    var roleBoxes = form.querySelectorAll("[name=target_roles]");
    var interestBoxes = form.querySelectorAll("[name=interests]");
    var timeline = form.querySelectorAll("[name=has_interview]");
    var sliders = form.querySelectorAll("input[type=range]");
    var ring = document.querySelector("[data-onb-ring]");
    var ringNumber = document.querySelector("[data-onb-readiness]");
    var defaultRequired = parseInt(form.getAttribute("data-default-required"), 10) || 65;
    var requirements = {}, names = {}, interestRoles = {};
    try {
      requirements = JSON.parse(document.getElementById("role-requirements").textContent);
      names = JSON.parse(document.getElementById("skill-names").textContent);
      interestRoles = JSON.parse(document.getElementById("interest-roles").textContent);
    } catch (e) { /* no live hints; the form still submits */ }

    function checkedValues(boxes) {
      return Array.prototype.filter.call(boxes, function (b) { return b.checked; })
        .map(function (b) { return b.value; });
    }

    function show(n) {
      steps.forEach(function (s) { s.hidden = s.getAttribute("data-step") !== String(n); });
      dots.forEach(function (d) {
        var k = parseInt(d.getAttribute("data-step-dot"), 10);
        d.classList.toggle("is-current", k === n);
        d.classList.toggle("is-done", k < n);
      });
      window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    }

    // --- interests -> suggested roles -------------------------------------
    function suggestions() {
      var score = {};
      checkedValues(interestBoxes).forEach(function (key) {
        (interestRoles[key] || []).forEach(function (role, rank) {
          score[role] = (score[role] || 0) + (2 - rank);
        });
      });
      return Object.keys(score).sort(function (a, b) { return score[b] - score[a]; });
    }

    function markSuggestions() {
      var suggested = suggestions();
      form.querySelectorAll("[data-role]").forEach(function (chip) {
        var on = suggested.indexOf(chip.getAttribute("data-role")) !== -1;
        chip.classList.toggle("is-suggested", on);
        chip.querySelector(".chip__badge").hidden = !on;
      });
      return suggested;
    }

    // --- roles: max three, General is exclusive ------------------------------
    function onRoleChange(e) {
      var box = e.target;
      if (box.checked && box.value === GENERAL) {
        roleBoxes.forEach(function (b) { if (b !== box) b.checked = false; });
      } else if (box.checked) {
        roleBoxes.forEach(function (b) { if (b.value === GENERAL) b.checked = false; });
        if (checkedValues(roleBoxes).length > MAX_ROLES) box.checked = false;
      }
      form.querySelector("[data-roles-error]").hidden = true;
      syncChips();
      update();
    }

    function syncChips() {
      form.querySelectorAll(".chip").forEach(function (chip) {
        var input = chip.querySelector("input");
        if (input) chip.classList.toggle("is-checked", input.checked);
      });
    }

    // --- timeline: date or plan length ---------------------------------------
    function syncTimeline() {
      var booked = checkedValues(timeline)[0] === "yes";
      form.querySelectorAll("[data-when]").forEach(function (el) {
        el.hidden = el.getAttribute("data-when") !== (booked ? "yes" : "no");
      });
      syncChips();
    }

    // --- sliders and projected readiness ------------------------------------
    function required(id) {
      var roles = checkedValues(roleBoxes);
      if (!roles.length) roles = [GENERAL];
      return Math.max.apply(null, roles.map(function (r) {
        var table = requirements[r] || {};
        return table[names[id]] || defaultRequired;
      }));
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
          mark.title = "Your target expects " + req;
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

    // --- step navigation with light validation -------------------------------
    form.querySelectorAll("[data-step-go]").forEach(function (b) {
      b.addEventListener("click", function () {
        var target = parseInt(b.getAttribute("data-step-go"), 10);
        if (target === 2) {
          // Arriving at the goal step: pre-select the best-matching role if
          // the user has not chosen any yet.
          var suggested = markSuggestions();
          if (!checkedValues(roleBoxes).length && suggested.length) {
            roleBoxes.forEach(function (box) { box.checked = box.value === suggested[0]; });
            syncChips();
            update();
          }
        }
        if (target === 3) {
          if (!checkedValues(roleBoxes).length) {
            form.querySelector("[data-roles-error]").hidden = false;
            return;
          }
          if (checkedValues(timeline)[0] === "yes") {
            var date = form.querySelector("[name=target_interview_date]");
            if (!date.value) { date.focus(); return; }
          }
        }
        show(target);
      });
    });

    roleBoxes.forEach(function (b) { b.addEventListener("change", onRoleChange); });
    interestBoxes.forEach(function (b) {
      b.addEventListener("change", function () { syncChips(); markSuggestions(); });
    });
    timeline.forEach(function (b) { b.addEventListener("change", syncTimeline); });
    sliders.forEach(function (s) { s.addEventListener("input", update); });

    // --- resume / LinkedIn PDF import --------------------------------------
    var importer = form.querySelector("[data-resume-import]");
    if (importer) {
      var fileInput = importer.querySelector("[data-resume-file]");
      var pasteInput = importer.querySelector("[data-resume-text]");
      var status = importer.querySelector("[data-resume-status]");
      var result = importer.querySelector("[data-resume-result]");
      var drop = importer.querySelector("[data-drop]");
      var dropLabel = importer.querySelector("[data-drop-label]");

      fileInput.addEventListener("change", function () {
        if (fileInput.files[0]) dropLabel.textContent = fileInput.files[0].name;
      });
      ["dragenter", "dragover"].forEach(function (t) {
        drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("is-over"); });
      });
      ["dragleave", "drop"].forEach(function (t) {
        drop.addEventListener(t, function () { drop.classList.remove("is-over"); });
      });
      drop.addEventListener("drop", function (e) {
        e.preventDefault();
        if (e.dataTransfer.files.length) {
          fileInput.files = e.dataTransfer.files;
          dropLabel.textContent = e.dataTransfer.files[0].name;
        }
      });

      var sample = importer.querySelector("[data-resume-sample]");
      if (sample) {
        sample.addEventListener("click", function () {
          fetch(sample.getAttribute("data-resume-sample"))
            .then(function (r) { return r.blob(); })
            .then(function (blob) {
              var dt = new DataTransfer();
              dt.items.add(new File([blob], "sample_resume_maya.pdf", { type: "application/pdf" }));
              fileInput.files = dt.files;
              dropLabel.textContent = "sample_resume_maya.pdf";
              importer.querySelector("[data-resume-go]").click();
            });
        });
      }

      importer.querySelector("[data-resume-go]").addEventListener("click", function () {
        var body = new FormData();
        body.append("csrfmiddlewaretoken", form.querySelector("[name=csrfmiddlewaretoken]").value);
        if (fileInput.files[0]) body.append("resume", fileInput.files[0]);
        else body.append("text", pasteInput.value);
        status.textContent = "Reading\u2026";
        status.className = "importer__status";
        fetch(importer.getAttribute("data-url"), { method: "POST", body: body, credentials: "same-origin" })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
          .then(function (res) {
            if (!res.ok) throw new Error(res.data.error || "Could not read that.");
            applyResume(res.data);
          })
          .catch(function (err) {
            status.textContent = err.message;
            status.className = "importer__status is-error";
          });
      });

      function applyResume(data) {
        // Interests: tick any the resume points to (never untick the user's).
        interestBoxes.forEach(function (b) {
          if (data.interests.indexOf(b.value) !== -1) b.checked = true;
        });
        markSuggestions();
        // Roles: only pre-select when the user has not chosen any.
        if (!checkedValues(roleBoxes).length && data.suggested_roles.length) {
          roleBoxes.forEach(function (b) { b.checked = b.value === data.suggested_roles[0]; });
        }
        // Skills: start each slider with evidence at the suggested rating.
        data.skills.forEach(function (s) {
          var slider = document.getElementById(s.field);
          if (!slider) return;
          slider.value = s.rating;
          var tag = form.querySelector('[data-from-resume="' + s.field + '"]');
          if (tag) { tag.hidden = false; tag.title = s.evidence; }
        });
        syncChips();
        update();

        var source = data.source === "linkedin" ? "LinkedIn profile" : "resume";
        status.textContent = "Read your " + source + ": found " + data.skills.length +
          " skill" + (data.skills.length === 1 ? "" : "s") + ".";
        status.className = "importer__status is-ok";
        result.innerHTML = "";
        var list = document.createElement("ul");
        list.className = "importer__skills";
        data.skills.slice(0, 8).forEach(function (s) {
          var li = document.createElement("li");
          var name = document.createElement("strong");
          name.textContent = s.name;
          var meta = document.createElement("span");
          meta.textContent = " \u00b7 " + s.mentions + " mention" + (s.mentions === 1 ? "" : "s") +
            " \u00b7 starts at " + s.rating;
          var quote = document.createElement("q");
          quote.textContent = s.evidence;
          li.appendChild(name); li.appendChild(meta); li.appendChild(quote);
          list.appendChild(li);
        });
        var note = document.createElement("p");
        note.className = "muted";
        note.textContent = data.skills.length
          ? "These are starting points: a resume shows you used a skill, not how strong you are. You'll confirm every rating in step 3."
          : "No catalog skills were mentioned, so your ratings start at 50.";
        if (data.interests.length) {
          var interestNote = document.createElement("p");
          interestNote.className = "muted";
          interestNote.textContent = "Interests ticked from your " + source + ". Suggested roles: " +
            (data.suggested_roles.join(", ") || "none yet") + ".";
          result.appendChild(interestNote);
        }
        result.appendChild(list);
        result.appendChild(note);
        result.hidden = false;
      }
    }

    // After a failed submit, open the step that holds the first error.
    var firstError = form.querySelector(".field--error, .field__error:not([hidden])");
    var errorStep = firstError ? firstError.closest("[data-step]") : null;
    markSuggestions();
    syncTimeline();
    syncChips();
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

  /* -------------------------------------------------------------------------
     7. Menus. They are <details>, so they work with no JavaScript; this only
        keeps one open at a time and closes it on an outside click or Esc.
     ------------------------------------------------------------------------- */
  var menus = document.querySelectorAll(".nav details.menu");
  menus.forEach(function (menu) {
    menu.addEventListener("toggle", function () {
      if (menu.open) menus.forEach(function (m) { if (m !== menu) m.open = false; });
    });
  });
  document.addEventListener("click", function (e) {
    menus.forEach(function (m) { if (m.open && !m.contains(e.target)) m.open = false; });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") menus.forEach(function (m) { m.open = false; });
  });

  /* -------------------------------------------------------------------------
     8. "Show how pages are built": reveals the .devnote course notes.
     ------------------------------------------------------------------------- */
  document.querySelectorAll("[data-dev-toggle]").forEach(function (btn) {
    var root = document.documentElement;
    btn.setAttribute("aria-pressed", root.classList.contains("show-dev") ? "true" : "false");
    btn.addEventListener("click", function () {
      var on = root.classList.toggle("show-dev");
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      try { localStorage.setItem("beacon-dev-notes", on ? "1" : "0"); } catch (e) { /* private mode */ }
    });
  });

  /* -------------------------------------------------------------------------
     9. AI coach on My plan. The panel is rendered with the rule-based advice;
        this fetches the AI version and swaps it in, and runs the question
        box. Model text goes through textContent, except chat answers, which
        are HTML-escaped first and then given a few safe Markdown tags.
     ------------------------------------------------------------------------- */
  function coachPanel(panel) {
    var ai = panel.getAttribute("data-ai") === "1";
    var body = panel.querySelector("[data-coach-body]");
    var engine = panel.querySelector("[data-coach-engine]");
    var note = panel.querySelector("[data-coach-note]");
    var thread = panel.querySelector("[data-coach-thread]");
    var form = panel.querySelector("[data-coach-ask]");
    var input = panel.querySelector("[data-coach-input]");
    var csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;

    function render(result) {
      var a = result.advice;
      ["headline", "why", "practice_question", "encouragement"].forEach(function (k) {
        var el = panel.querySelector('[data-coach-field="' + k + '"]');
        if (el && a[k]) el.textContent = a[k];
      });
      var list = panel.querySelector("[data-coach-actions]");
      list.innerHTML = "";
      (a.actions || []).forEach(function (t) {
        var li = document.createElement("li");
        li.textContent = t;
        list.appendChild(li);
      });
      engine.textContent = result.engine;
      engine.classList.toggle("is-ai", result.source === "llm");
      note.hidden = !result.note;
      note.textContent = result.note || "";
    }

    function load(refresh) {
      if (!ai) return;
      body.classList.add("is-thinking");
      engine.textContent = "Thinking…";
      fetch(panel.getAttribute("data-advice-url") + (refresh ? "?refresh=1" : ""),
            { credentials: "same-origin", headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json(); })
        .then(render)
        .catch(function () { engine.textContent = "Beacon rules (AI unavailable)"; })
        .then(function () { body.classList.remove("is-thinking"); });
    }

    // Models answer in light Markdown. Escape everything first, then turn
    // only **bold**, *italic* and "- " bullet lines into tags, so nothing the
    // model writes can become live HTML.
    function miniMarkdown(text) {
      var escaped = String(text)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
      var html = [], inList = false;
      escaped.split(/\n/).forEach(function (line) {
        var bullet = /^\s*(?:[-*\u2022]|\d+[.)])\s+(.*)$/.exec(line);
        if (bullet && !inList) { html.push("<ul>"); inList = true; }
        if (!bullet && inList) { html.push("</ul>"); inList = false; }
        var body = (bullet ? bullet[1] : line)
          .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
          .replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, "$1<em>$2</em>");
        if (bullet) html.push("<li>" + body + "</li>");
        else if (body.trim()) html.push("<p>" + body + "</p>");
      });
      if (inList) html.push("</ul>");
      return html.join("");
    }

    function bubble(text, who) {
      var li = document.createElement("li");
      li.className = "coach__msg coach__msg--" + who;
      li.textContent = text;
      thread.appendChild(li);
      li.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
      return li;
    }

    function send(question) {
      question = (question || "").trim();
      if (!question) return;
      bubble(question, "me");
      input.value = "";
      var pending = bubble("…", "coach");
      pending.classList.add("is-typing");
      fetch(panel.getAttribute("data-ask-url"), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ question: question }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          pending.classList.add("coach__msg--rich");
          pending.innerHTML = miniMarkdown(d.answer || d.error || "No answer.");
        })
        .catch(function () { pending.textContent = "The coach could not be reached. Try again."; })
        .then(function () { pending.classList.remove("is-typing"); });
    }

    form.addEventListener("submit", function (e) { e.preventDefault(); send(input.value); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
    });
    panel.querySelectorAll("[data-coach-suggest]").forEach(function (b) {
      b.addEventListener("click", function () { send(b.getAttribute("data-coach-suggest")); });
    });
    panel.querySelector("[data-coach-practice]").addEventListener("click", function () {
      var q = panel.querySelector('[data-coach-field="practice_question"]').textContent;
      input.value = 'Feedback on my answer to "' + q + '":\n';
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    });
    var refresh = panel.querySelector("[data-coach-refresh]");
    if (refresh) refresh.addEventListener("click", function () { load(true); });
    load(false);
  }
  document.querySelectorAll("[data-coach]").forEach(coachPanel);

  document.querySelectorAll("[data-lighthouse]").forEach(lighthouse);
  document.querySelectorAll("[data-onboarding]").forEach(onboarding);
  document.querySelectorAll("[data-task-toggle]").forEach(taskToggle);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", reveal);
  } else {
    reveal();
  }
})();
