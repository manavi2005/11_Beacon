/* Setup: about you -> roles that fit -> blueprint (levels pre-estimated) -> date -> plan. */
(function () {
  "use strict";
  const B = window.BEACON;
  const root = document.querySelector("[data-wizard]");
  if (!root) return;
  const $ = (s) => root.querySelector(s);
  const esc = B.esc;
  let blueprint = null;
  let background = $("[data-about]").value.trim();
  const LEVELS = [[0, "New to it"], [30, "Some exposure"], [50, "Comfortable"], [70, "Strong"], [85, "Could teach it"]];
  const describe = (v) => LEVELS.filter(([floor]) => v >= floor).pop()[1];

  function show(step) {
    root.querySelectorAll("[data-step]").forEach((s) => (s.hidden = s.dataset.step !== String(step)));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  root.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => show(b.dataset.back)));

  // --- Step 1: about you -------------------------------------------------
  const file = $("[data-file]");
  const drop = $("[data-drop]");
  file.addEventListener("change", () => {
    if (file.files[0]) $("[data-file-label]").innerHTML = `<strong>${esc(file.files[0].name)}</strong><br><span class="small muted">Ready. It's read once and never stored.</span>`;
  });
  ["dragover", "dragenter"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((e) => drop.addEventListener(e, () => drop.classList.remove("is-over")));
  drop.addEventListener("drop", (ev) => {
    ev.preventDefault();
    if (ev.dataTransfer.files.length) { file.files = ev.dataTransfer.files; file.dispatchEvent(new Event("change")); }
  });

  $("[data-read]").addEventListener("click", async (e) => {
    const text = $("[data-about]").value.trim();
    if (!file.files[0] && !text) return B.toast("Upload a resume or write a few sentences about you.");
    const btn = e.currentTarget;
    btn.disabled = true; btn.textContent = "Reading…";
    const form = new FormData();
    if (file.files[0]) form.append("resume", file.files[0]);
    form.append("text", text);
    try {
      const data = await B.post("/start/about/", form);
      background = data.summary || text;
      if (data.stage) $("[data-level]").value = data.stage;
      $("[data-summary]").textContent = data.summary || "";
      $("[data-about-eyebrow]").textContent = data.roles.length ? "Roles that fit you" : "Your goal";
      $("[data-ideas]").innerHTML = data.roles.map((r) =>
        `<button type="button" class="idea" data-title="${esc(r.title)}">${esc(r.title)}<small>${esc(r.why)}</small></button>`).join("");
      $("[data-ideas]").querySelectorAll("[data-title]").forEach((b) => b.addEventListener("click", () => {
        $("[data-role]").value = b.dataset.title; build();
      }));
      show(2);
    } catch (err) { B.toast(err.message); }
    btn.disabled = false; btn.textContent = "Continue →";
  });
  $("[data-skip-to-role]").addEventListener("click", () => {
    background = $("[data-about]").value.trim();
    $("[data-summary]").textContent = "";
    $("[data-ideas]").innerHTML = "";
    show(2);
    $("[data-role]").focus();
  });

  // --- Step 2 -> 3: the blueprint ----------------------------------------
  async function build() {
    const role = $("[data-role]").value.trim();
    if (!role) { $("[data-role]").focus(); return B.toast("Pick a suggestion or type a job title."); }
    const btn = $("[data-build]");
    btn.disabled = true; btn.textContent = "Reading what this role needs…";
    try {
      blueprint = await B.post("/start/blueprint/", {
        role, background, experience: $("[data-level]").selectedOptions[0].text,
      });
      renderBlueprint();
      show(3);
    } catch (e) { B.toast(e.message); }
    btn.disabled = false; btn.textContent = "Build my blueprint →";
  }
  $("[data-build]").addEventListener("click", build);
  $("[data-role]").addEventListener("keydown", (e) => e.key === "Enter" && build());

  function renderBlueprint() {
    const levels = blueprint.levels || {};
    const estimated = Object.keys(levels).length > 0;
    $("[data-bp-title]").innerHTML = `Interview-ready for <em>${esc(blueprint.title)}</em>`;
    $("[data-bp-summary]").textContent = blueprint.summary || "";
    $("[data-bp-source]").textContent = blueprint.source === "AI" ? "Blueprint written for this role" : "Starter blueprint (AI offline)";
    $("[data-rate-note]").textContent = estimated
      ? "Here's what interviewers for this role test. Beacon estimated where you are from what you shared. Adjust anything that's off."
      : "Here's what interviewers for this role test. Be honest about where you are today: your first session checks it anyway.";
    $("[data-rates]").innerHTML = blueprint.skills.map((s, i) => {
      const v = levels[s.name] != null ? levels[s.name] : 40;
      return `<div class="rate" style="animation-delay:${i * 70}ms">
        <div><div class="h3">${esc(s.name)} <span class="chip" style="margin-left:6px">bar ${s.required}</span></div>
          <div class="rate__why">${esc(s.why || "")}</div></div>
        <div><input type="range" min="0" max="100" step="5" value="${v}" data-skill="${esc(s.name)}" aria-label="Your level in ${esc(s.name)}">
          <div class="rate__val">${describe(v)}</div></div>
      </div>`;
    }).join("");
    $("[data-rates]").querySelectorAll("input[type=range]").forEach((r) =>
      r.addEventListener("input", () => (r.nextElementSibling.textContent = describe(Number(r.value)))));
  }
  $("[data-to4]").addEventListener("click", () => show(4));

  // --- Step 4: finish ----------------------------------------------------
  $("[data-finish]").addEventListener("click", async () => {
    const ratings = {};
    root.querySelectorAll("[data-skill]").forEach((r) => (ratings[r.dataset.skill] = Number(r.value)));
    show(5);
    try {
      const data = await B.post("/start/", {
        role: blueprint.title, blueprint: blueprint.slug, ratings, date: $("[data-date]").value,
        company: $("[data-company]").value, experience_level: $("[data-level]").value, background,
      });
      window.location.href = data.next;
    } catch (e) { B.toast(e.message); show(4); }
  });
})();
