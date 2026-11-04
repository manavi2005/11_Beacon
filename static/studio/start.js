/* Setup wizard: role (any field) -> blueprint + self-rating -> date -> plan. */
(function () {
  "use strict";
  const B = window.BEACON;
  const root = document.querySelector("[data-wizard]");
  if (!root) return;
  const $ = (s) => root.querySelector(s);
  const esc = B.esc;
  let blueprint = null;
  const LEVELS = [[0, "New to it"], [30, "Some exposure"], [50, "Comfortable"], [70, "Strong"], [85, "Could teach it"]];
  const describe = (v) => LEVELS.filter(([floor]) => v >= floor).pop()[1];

  function show(step) {
    root.querySelectorAll("[data-step]").forEach((s) => (s.hidden = s.dataset.step !== String(step)));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  root.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => show(b.dataset.back)));

  async function build() {
    const role = $("[data-role]").value.trim();
    if (!role) { $("[data-role]").focus(); return B.toast("Type the role you're working toward."); }
    const btn = $("[data-build]");
    btn.disabled = true; btn.textContent = "Reading what this role needs…";
    try {
      blueprint = await B.post("/start/blueprint/", { role, experience: $("[data-level]").selectedOptions[0].text });
      renderBlueprint();
      show(2);
    } catch (e) { B.toast(e.message); }
    btn.disabled = false; btn.textContent = "Build my blueprint →";
  }
  $("[data-build]").addEventListener("click", build);
  $("[data-role]").addEventListener("keydown", (e) => e.key === "Enter" && build());

  function renderBlueprint() {
    $("[data-bp-title]").innerHTML = `Interview-ready for <em>${esc(blueprint.title)}</em>`;
    $("[data-bp-summary]").textContent = blueprint.summary || "";
    $("[data-bp-source]").textContent = blueprint.source === "AI" ? "Blueprint written for this role" : "Starter blueprint (AI offline)";
    $("[data-rates]").innerHTML = blueprint.skills.map((s, i) => `
      <div class="rate" style="animation-delay:${i * 70}ms">
        <div><div class="h3">${esc(s.name)} <span class="chip" style="margin-left:6px">bar ${s.required}</span></div>
          <div class="rate__why">${esc(s.why || "")}</div></div>
        <div><input type="range" min="0" max="100" step="5" value="40" data-skill="${esc(s.name)}" aria-label="Your level in ${esc(s.name)}">
          <div class="rate__val" data-val>${describe(40)}</div></div>
      </div>`).join("");
    $("[data-rates]").querySelectorAll("input[type=range]").forEach((r) =>
      r.addEventListener("input", () => (r.nextElementSibling.textContent = describe(Number(r.value)))));
  }
  $("[data-to3]").addEventListener("click", () => show(3));

  $("[data-suggest]").addEventListener("click", async (e) => {
    const background = $("[data-background]").value.trim();
    if (!background) return B.toast("Tell Beacon a little about you first.");
    e.target.disabled = true;
    const ideas = $("[data-ideas]");
    ideas.innerHTML = '<span class="muted small">Thinking about what fits you…</span>';
    try {
      const { roles } = await B.post("/start/suggest/", { background });
      ideas.innerHTML = roles.length ? roles.map((r) => `<button type="button" class="idea" data-title="${esc(r.title)}">${esc(r.title)}<small>${esc(r.why)}</small></button>`).join("")
        : '<span class="muted small">Suggestions need the AI coach. Type any role above and Beacon will still build a plan for it.</span>';
      ideas.querySelectorAll("[data-title]").forEach((b) => b.addEventListener("click", () => {
        $("[data-role]").value = b.dataset.title; build();
      }));
    } catch (err) { ideas.innerHTML = ""; B.toast(err.message); }
    e.target.disabled = false;
  });

  $("[data-finish]").addEventListener("click", async () => {
    const ratings = {};
    root.querySelectorAll("[data-skill]").forEach((r) => (ratings[r.dataset.skill] = Number(r.value)));
    show(4);
    try {
      const data = await B.post("/start/", {
        role: blueprint.title, blueprint: blueprint.slug, ratings, date: $("[data-date]").value,
        company: $("[data-company]").value, experience_level: $("[data-level]").value,
        background: $("[data-background]").value,
      });
      window.location.href = data.next;
    } catch (e) { B.toast(e.message); show(3); }
  });
})();
