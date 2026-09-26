const $ = s => document.querySelector(s);
const pct = x => x == null ? "—" : Math.round(x * 100) + "%";
const P = new URLSearchParams(location.search);
let Q, idx = 0, name = "", picks = {}, timeouts = [], tick = null, left = 0, preload = [];

fetch("/api/quiz").then(r => r.json()).then(d => {
  Q = d; preload = d.items.map(it => { const i = new Image(); i.src = it.image; return i; });
  if (P.get("name")) { name = P.get("name"); start(); }
});

$("#name").value = localStorage.getItem("spot-name") || "";
$("#f-start").onsubmit = e => {
  e.preventDefault(); name = $("#name").value.trim(); if (!name || !Q) return;
  localStorage.setItem("spot-name", name); start();
};

function start() { $("#s-start").classList.add("hide"); $("#s-quiz").classList.remove("hide"); idx = 0; show(); }

function show() {
  const it = Q.items[idx]; picks[it.id] = [];
  $("#q-n").textContent = `${idx + 1} / ${Q.items.length}`;
  $("#q-room").textContent = it.room;
  $("#q-img").src = it.image;
  const box = $("#q-chips"); box.innerHTML = "";
  const safe = mk("Looks safe", "safe");
  it.chips.forEach(c => {
    const b = mk(c.label); b.onclick = () => {
      b.classList.toggle("on"); safe.classList.remove("on");
      picks[it.id] = [...box.querySelectorAll(".chip.on[data-id]")].map(x => x.dataset.id);
    }; b.dataset.id = c.id; box.appendChild(b);
  });
  safe.onclick = () => { box.querySelectorAll(".chip[data-id]").forEach(x => x.classList.remove("on")); safe.classList.add("on"); picks[it.id] = []; };
  box.appendChild(safe);
  $("#q-next").textContent = idx === Q.items.length - 1 ? "Finish →" : "Next →";
  left = Q.seconds; render(); clearInterval(tick);
  if (P.get("freeze")) { left = 9; render(); return; }
  const t0 = Date.now();
  tick = setInterval(() => {
    left = Math.max(0, Q.seconds - (Date.now() - t0) / 1000); render();
    if (left <= 0) { timeouts.push(it.id); next(); }
  }, 200);
}
function mk(label, cls) { const b = document.createElement("button"); b.type = "button"; b.className = "chip " + (cls || ""); b.textContent = label; return b; }
function render() {
  $("#q-t").textContent = Math.ceil(left);
  const low = left <= 5; $("#q-t").classList.toggle("low", low); $(".bar").classList.toggle("low", low);
  $("#q-bar").style.transform = `scaleX(${left / Q.seconds})`;
}
function next() {
  clearInterval(tick);
  if (++idx < Q.items.length) return show();
  submit();
}
$("#q-next").onclick = next;

async function submit() {
  $("#s-quiz").classList.add("hide");
  const r = await fetch("/api/submit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, picks, timeouts }) }).then(r => r.json());
  done(r);
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
  $("#d-per").innerHTML = r.items.map(it => {
    const p = g.per_scene[it.id]; const cls = it.clean ? (p.false_alarms ? "fa" : "ok") : (p.hit ? (p.false_alarms ? "fa" : "ok") : "bad");
    return `<div class="t ${cls}"><img src="${it.image}"><span>${it.clean ? "clean room" : it.answer_label[0]}</span></div>`;
  }).join("");
  lb(s.leaderboard, r.id);
}
function lb(board, me) {
  $("#d-lb").innerHTML = `<tr class="hd"><td></td><td>Name</td><td class="r">Caught</td><td class="r">Score</td></tr>` + board.map((b, i) => `<tr class="${b.id === me ? "me" : b.kind === "human" ? "h" : ""}"><td class="n">${i + 1}</td><td>${esc(b.name)}<span class="tag ${b.kind[0]}">${b.kind}</span></td><td class="r">${pct(b.recall)}</td><td class="r">${pct(b.score)}</td></tr>`).join("");
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
