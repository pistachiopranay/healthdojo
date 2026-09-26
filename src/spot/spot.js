const $ = s => document.querySelector(s);
const pct = x => x == null ? "-" : Math.round(x * 100) + "%";
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const P = new URLSearchParams(location.search);
let pending = false, cur = 20, Q, idx = 0, name = "", answers = {}, timeouts = [], tick = null, left = 0, preload = [];

fetch("/api/quiz").then(r => r.json()).then(d => {
  Q = d; preload = d.items.map(it => { const i = new Image(); i.src = it.image; return i; });
  if (P.get("name")) { name = P.get("name"); start(); }
});

$("#name").value = localStorage.getItem("spot-name") || "";
$("#f-start").onsubmit = async e => {
  e.preventDefault(); const n = $("#name").value.trim(); if (!n || !Q) return;
  $("#b-start").disabled = true; $("#b-start").textContent = "Checking…"; $("#name-err").classList.add("hide");
  let r; try { r = await fetch("/api/name", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: n }) }).then(r => r.json()); } catch { r = { ok: false, msg: "Network hiccup. Try again" }; }
  $("#b-start").disabled = false; $("#b-start").textContent = "Start →";
  if (!r.ok) { $("#name-err").textContent = r.msg; $("#name-err").classList.remove("hide"); return; }
  name = r.name; localStorage.setItem("spot-name", name);
  if (pending) { pending = false; $("#s-start").classList.add("hide"); return submit(); }
  start();
};

let wframe = null, wready = false;
function preloadWorld() {
  const w = Q.items.find(i => i.kind === "world"); if (!w || wframe) return;
  const box = $("#q-world"); box.classList.remove("hide"); box.classList.add("pre");
  wframe = document.createElement("iframe"); wframe.src = w.src; wframe.allow = "fullscreen; xr-spatial-tracking";
  wframe.onload = () => {
    try {
      const d = wframe.contentDocument, st = d.createElement("style");
      st.textContent = "#cap{display:none!important}.embed.touch #joy{display:block!important}.embed.touch #updn{display:flex!important}.embed #load .bar{display:block!important}";
      d.head.appendChild(st);
      const poll = setInterval(() => { const l = d.getElementById("load"); if (!l || l.classList.contains("gone")) { wready = true; clearInterval(poll); } }, 300);
    } catch { wready = true; }
  };
  box.appendChild(wframe);
  setTimeout(() => wready = true, 25000);
}

function start() { $("#s-start").classList.add("hide"); $("#s-quiz").classList.remove("hide"); idx = +(P.get("item") || 0); preloadWorld(); show(); }

function show() {
  const it = Q.items[idx];
  $("#q-n").textContent = `${idx + 1} / ${Q.items.length}`;
  const W = it.kind === "world";
  $("#q-room").textContent = W ? "3D · walk around" : it.room; $("#q-room").classList.toggle("w3d", W);
  $("#q-imgbox").classList.toggle("hide", W); $("#q-whint").classList.toggle("hide", !W);
  if (W) { $("#q-world").classList.remove("pre", "hide"); } else { $("#q-img").src = it.image; }
  $("#q-text").value = P.get("text") || "";
  $("#q-next").textContent = idx === Q.items.length - 1 ? "Finish →" : "Next →";
  const secs = it.seconds || Q.seconds; cur = secs;
  left = secs; render(); clearInterval(tick);
  if (P.get("freeze")) { left = 12; render(); return; }
  let t0 = W && !wready ? null : Date.now();
  tick = setInterval(() => {
    if (t0 === null) { if (wready) t0 = Date.now(); else { $("#q-t").textContent = "…"; return; } }
    left = Math.max(0, secs - (Date.now() - t0) / 1000); render();
    if (left <= 0) { timeouts.push(it.id); next(false); }
  }, 200);
}
function render() {
  $("#q-t").textContent = Math.ceil(left);
  const low = left <= 5; $("#q-t").classList.toggle("low", low); $(".bar").classList.toggle("low", low);
  $("#q-bar").style.transform = `scaleX(${left / cur})`;
}
function next(safe) {
  clearInterval(tick);
  const it = Q.items[idx], text = $("#q-text").value.trim();
  answers[it.id] = { text: safe ? "" : text, safe: !!safe };
  $("#q-text").blur();
  if (Q.items[idx].kind === "world") { $("#q-world").classList.add("hide"); if (wframe) wframe.src = "about:blank"; }
  if (++idx < Q.items.length) return show();
  submit();
}
$("#q-next").onclick = () => next(false);
$("#q-safe").onclick = () => next(true);

async function submit() {
  $("#s-quiz").classList.add("hide"); $("#s-wait").classList.remove("hide");
  const res = await fetch("/api/submit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, answers, timeouts }) });
  const r = await res.json();
  if (!res.ok) {  // name clash/unsafe at submit time: keep answers, ask for a new name, resubmit
    pending = true; $("#s-wait").classList.add("hide"); $("#s-start").classList.remove("hide");
    $("#name-err").textContent = (r.detail || "Please pick a different name") + ". Your answers are saved."; $("#name-err").classList.remove("hide");
    $("#b-start").textContent = "Submit answers →"; return;
  }
  $("#s-wait").classList.add("hide"); done(r);
}

function done(r) {
  $("#s-done").classList.remove("hide"); window.scrollTo(0, 0);
  const g = r.grade, s = r.summary;
  $("#d-eyebrow").textContent = `${name} · your result`;
  $("#d-score").textContent = pct(g.score);
  $("#d-rec").textContent = `${g.tp}/${g.tp + g.fn}`;
  $("#d-fa").textContent = `${g.fp}`;
  $("#d-rank").textContent = `#${r.rank}/${r.of}`;
  const bm = s.best_model;
  $("#d-verdict").innerHTML = r.models_beaten === s.n_models ? `You beat <b>all ${s.n_models} models</b>, including ${bm.name}.`
    : r.models_beaten ? `You beat <b>${r.models_beaten} of ${s.n_models}</b> models. Best model: ${bm.name} at ${pct(bm.score)}.`
    : `The models won this round. Best model: ${bm.name} at ${pct(bm.score)}.`;
  const rows = [["You", g.score, "var(--lime-active)"], ["Humans avg", s.humans.score, "var(--green)"], ["Best model", bm.score, "var(--ink)"], ["Model avg", s.models.score, "var(--text-faint)"]];
  $("#d-cmp").innerHTML = rows.map(([l, v, c]) => `<div class="row"><span>${l}</span><div class="track"><i style="width:${(v || 0) * 100}%;background:${c}"></i></div><b class="mono">${pct(v)}</b></div>`).join("");
  const w = s.world;
  $("#d-world").innerHTML = `${r.world_found ? "You <b class=\"ok\">found</b>" : "You <b class=\"no\">missed</b>"} the ${esc(w.hazard.toLowerCase())}. Found it in 3D: humans <b>${pct(w.human_rate)}</b> vs models <b>${pct(w.model_rate)}</b> <span class="sub">(${w.n_models} models walked it)</span>`;
  $("#d-per").innerHTML = r.items.map(it => {
    const a = r.answers[it.id], gr = r.graded[it.id], p = g.per_scene[it.id] || {}, neg = new Set(r.known_absent[it.id]);
    const ids = new Set(gr.ids), pills = [];
    it.answer.forEach(h => pills.push(`<span class="pill ${ids.has(h) ? "hit" : "miss"}">${ids.has(h) ? "hit" : "missed"}: ${esc(r.labels[h])}</span>`));
    gr.ids.filter(h => !it.answer.includes(h)).forEach(h => pills.push(`<span class="pill ${neg.has(h) ? "fa" : ""}">${neg.has(h) ? "false alarm" : "not scored"}: ${esc(r.labels[h])}</span>`));
    if (it.kind === "world") pills.push(`<span class="pill">3D room</span>`);
    if (it.clean && !p.false_alarms) pills.push(`<span class="pill clean">correct: clean room</span>`);
    const cls = it.kind === "world" ? (r.world_found ? "ok" : "bad") : it.clean ? (p.false_alarms ? "fa" : "ok") : (p.hit ? (p.false_alarms ? "fa" : "ok") : "bad");
    const wrote = a.safe ? "<i>Looks safe</i>" : a.text ? `&ldquo;${esc(a.text)}&rdquo;` : "<i>(nothing, time ran out)</i>";
    return `<div class="a ${cls}"><img src="${it.image}"><div><div class="w">${wrote}</div><div class="g">${pills.join("")}</div></div></div>`;
  }).join("");
  lb(s.leaderboard, r.id);
}
function lb(board, me) {
  $("#d-lb").innerHTML = `<tr class="hd"><td></td><td>Name</td><td class="r">Caught</td><td class="r">3D</td><td class="r">Score</td></tr>` + board.map((b, i) => `<tr class="${b.id === me ? "me" : b.kind === "human" ? "h" : ""}"><td class="n">${i + 1}</td><td>${esc(b.name)}<span class="tag ${b.kind[0]}">${b.kind}</span></td><td class="r">${pct(b.recall)}</td><td class="r">${b.world == null ? "–" : b.world ? "✓" : "✗"}</td><td class="r">${pct(b.score)}</td></tr>`).join("");
}
