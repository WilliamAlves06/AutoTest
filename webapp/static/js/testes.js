// testes.js — tela "Execução de Testes": chips de suíte, hero/gauge, feed de
// resultados com abas e WebSocket para progresso em tempo real.

const ST = {
  suites: {},        // nome -> [nomes de teste]
  suiteSel: null,
  selTests: new Set(),
  results: [],        // {suite, name, status, dur, log}
  tab: "resumo",
  running: false,
};

const CORES_SUITE = ["#3fbe52", "#4ea1ff", "#f5b13d", "#a855f7", "#f06363", "#06b6d4"];

function corSuite(nome) {
  const nomes = Object.keys(ST.suites);
  const i = nomes.indexOf(nome);
  return CORES_SUITE[(i >= 0 ? i : 0) % CORES_SUITE.length];
}

async function carregarSuites() {
  const r = await fetch("/api/suites");
  const data = await r.json();
  ST.suites = {};
  data.suites.forEach(s => { ST.suites[s.name] = s.tests; });
  renderChips();
  atualizarStats();
}

function renderChips() {
  const termo = (document.getElementById("busca-suite").value || "").trim().toLowerCase();
  const wrap = document.getElementById("chips");
  wrap.innerHTML = "";
  Object.keys(ST.suites).filter(n => n.toLowerCase().includes(termo)).forEach(nome => {
    const n = ST.suites[nome].length;
    const chip = document.createElement("div");
    chip.className = "chip" + (nome === ST.suiteSel ? " active" : "");
    chip.innerHTML = `<span class="dot" style="background:${corSuite(nome)}"></span>
      <span class="name">${nome}</span><span class="count">${n}</span>`;
    chip.addEventListener("click", () => selecionarSuite(nome));
    wrap.appendChild(chip);
  });
}

function selecionarSuite(nome) {
  ST.suiteSel = nome;
  ST.selTests = new Set();
  ST.results = [];
  ST.tab = "resumo";
  document.getElementById("log-view").textContent = "";
  renderChips();
  setTab("resumo");
  atualizarStats();
}

function testesPendentes() {
  if (!ST.suiteSel) return [];
  return (ST.suites[ST.suiteSel] || []).map(n => ({ suite: ST.suiteSel, name: n, status: "—", dur: null, pending: true }));
}

function toggleTeste(nome) {
  if (ST.selTests.has(nome)) ST.selTests.delete(nome); else ST.selTests.add(nome);
  atualizarBotaoRodarSuite();
  renderFeed();
}

function atualizarBotaoRodarSuite() {
  const btn = document.getElementById("btn-run-suite");
  const n = ST.selTests.size;
  if (n) btn.textContent = `▶ Rodar ${n} selecionado${n !== 1 ? "s" : ""}`;
  else if (ST.suiteSel) btn.textContent = `▶ Rodar suíte (${(ST.suites[ST.suiteSel] || []).length})`;
  else btn.textContent = "▶ Rodar suíte";
}

function setTab(tab) {
  ST.tab = tab;
  document.querySelectorAll(".tab").forEach(el => el.classList.toggle("active", el.dataset.tab === tab));
  const feed = document.getElementById("feed");
  const log = document.getElementById("log-view");
  if (tab === "log") {
    feed.style.display = "none";
    log.style.display = "block";
  } else {
    log.style.display = "none";
    feed.style.display = "block";
    renderFeed();
  }
}

function renderFeed() {
  const feed = document.getElementById("feed");
  feed.innerHTML = "";

  let linhas, pendente = false;
  if (ST.tab === "falhas") {
    linhas = ST.results.filter(r => r.status === "FAIL");
  } else if (ST.results.length) {
    linhas = ST.results;
  } else {
    linhas = testesPendentes();
    pendente = true;
  }

  if (!linhas.length) {
    const msg = ST.tab === "falhas" ? "Nenhuma falha." : "Selecione uma suíte para ver os testes.";
    feed.innerHTML = `<div class="feed-empty">${msg}</div>`;
    return;
  }

  if (pendente) {
    const hint = document.createElement("div");
    hint.className = "feed-hint";
    hint.textContent = "Clique para marcar os testes (vazio = roda todos).";
    feed.appendChild(hint);
  }

  linhas.forEach(r => {
    const marcado = pendente && ST.selTests.has(r.name);
    const status = r.status;
    const dotClass = status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "pending";
    const pillClass = status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "pending";
    const pillLabel = status === "PASS" ? "PASS" : status === "FAIL" ? "FAIL" : "pendente";
    const dur = r.dur != null ? `${r.dur.toFixed(1)}s` : "—";

    let sub;
    if (status === "FAIL") sub = r.err || "reprovado";
    else if (status === "PASS") sub = `${r.suite} · validado em banco ✔`;
    else sub = `${r.suite} · ` + (marcado ? "selecionado — clique p/ remover" : "aguardando — clique p/ marcar");

    const row = document.createElement("div");
    row.className = "feed-row" + (pendente ? " pending" : "") + (marcado ? " marked" : "");
    row.innerHTML = `
      <span class="status-dot ${dotClass}"></span>
      <div class="mid"><div class="name">${r.name}</div><div class="sub">${sub}</div></div>
      <span class="dur">${dur}</span>
      <span class="pill ${pillClass}">${pillLabel}</span>`;
    if (pendente) row.addEventListener("click", () => toggleTeste(r.name));
    feed.appendChild(row);
  });
}

function atualizarStats() {
  const totalSuite = Object.values(ST.suites).reduce((a, t) => a + t.length, 0);
  const passou = ST.results.filter(r => r.status === "PASS").length;
  const falhou = ST.results.filter(r => r.status === "FAIL").length;
  const executados = passou + falhou;
  const rate = executados ? Math.round(passou / executados * 100) : 0;
  const falhaMods = [...new Set(ST.results.filter(r => r.status === "FAIL").map(r => r.suite))].join(", ");

  document.getElementById("gauge").style.setProperty("--pct", rate);
  document.getElementById("gauge-val").textContent = `${rate}%`;
  document.getElementById("num-pass").textContent = passou;
  document.getElementById("num-total").textContent = `/ ${totalSuite}`;
  document.getElementById("tile-pass").textContent = passou;
  document.getElementById("tile-fail").textContent = falhou;
  document.getElementById("tile-fail-cap").textContent = falhaMods ? `Reprovados (${falhaMods})` : "Reprovados";

  const tabFalhas = document.querySelector('.tab[data-tab="falhas"]');
  tabFalhas.textContent = falhou ? `Falhas  ${falhou}` : "Falhas";

  atualizarBotaoRodarSuite();
}

function setRunning(running) {
  ST.running = running;
  document.getElementById("btn-run-all").disabled = running;
  document.getElementById("btn-run-all-top").disabled = running;
  document.getElementById("btn-run-suite").disabled = running;
  document.getElementById("running-flag").style.display = running ? "flex" : "none";
}

async function executarTudo() {
  if (ST.running) return;
  ST.results = [];
  const r = await fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: "all" }),
  });
  const data = await r.json();
  if (data.status === "error") toast(data.message);
}

async function executarSuite() {
  if (ST.running) return;
  if (!ST.suiteSel) { toast("Selecione uma suíte primeiro"); return; }
  ST.results = [];
  const tests = ST.selTests.size ? [...ST.selTests] : null;
  const r = await fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: "suite", suite: ST.suiteSel, tests }),
  });
  const data = await r.json();
  if (data.status === "error") toast(data.message);
}

function limparResultados() {
  ST.results = [];
  document.getElementById("log-view").textContent = "";
  renderFeed();
  atualizarStats();
}

function registrarWS() {
  onWS("started", () => setRunning(true));
  onWS("result", (msg) => {
    ST.results.push({ suite: msg.suite, name: msg.name, status: msg.status, dur: msg.dur, log: msg.log });
    const log = document.getElementById("log-view");
    log.textContent += `\n>> ${msg.suite}/${msg.name}  [${msg.status}]  ${msg.dur.toFixed(1)}s\n${msg.log}\n`;
    log.scrollTop = log.scrollHeight;
    renderFeed();
    atualizarStats();
  });
  onWS("done", () => setRunning(false));
}

document.getElementById("btn-reload").addEventListener("click", carregarSuites);
document.getElementById("busca-suite").addEventListener("input", renderChips);
document.getElementById("btn-run-all").addEventListener("click", executarTudo);
document.getElementById("btn-run-all-top").addEventListener("click", executarTudo);
document.getElementById("btn-run-suite").addEventListener("click", executarSuite);
document.getElementById("btn-clear").addEventListener("click", limparResultados);
document.querySelectorAll(".tab").forEach(el => el.addEventListener("click", () => setTab(el.dataset.tab)));

carregarSuites();
registrarWS();
