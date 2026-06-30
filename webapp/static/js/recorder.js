// recorder.js — tela Recorder: grava cliques/digitação e gera o teste em DSL fc ao vivo.

const REC = { recording: false };

// Highlighter leve (sem dependência): comentários/keywords em verde-acinzentado,
// "fc" em azul-claro, strings em âmbar — mesma paleta do mockup.
const _FC_PATTERN = /(#.*$)|("(?:[^"\\]|\\.)*")|\b(def|import|from|try|except|return|class|if|elif|else|for|while|in|not|is|None|True|False|pass|with|as|yield|raise)\b|\bfc\b/gm;

function highlightFc(code) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc(code).replace(_FC_PATTERN, (m, comment, str, kw) => {
    if (comment) return `<span class="kw">${m}</span>`;
    if (str) return `<span class="str">${m}</span>`;
    if (kw) return `<span class="kw">${m}</span>`;
    return `<span class="fc">${m}</span>`;
  });
}

async function carregarRecorderState() {
  const r = await fetch("/api/recorder/state");
  const data = await r.json();
  aplicarEstadoRecorder(data);
}

function aplicarEstadoRecorder(data) {
  REC.recording = data.recording;
  document.getElementById("code-view").innerHTML = highlightFc(data.code || "");
  document.getElementById("rec-count").textContent = `${data.count} ação${data.count !== 1 ? "ões" : ""}`;
  document.getElementById("rec-process").textContent = data.process || "—";
  renderRecFeed(data.feed || []);

  const btn = document.getElementById("btn-rec-toggle");
  const lbl = document.getElementById("rec-btn-label");
  btn.classList.toggle("recording", data.recording);
  lbl.textContent = data.recording ? "Parar" : "Iniciar";
}

function renderRecFeed(feed) {
  const wrap = document.getElementById("rec-feed");
  wrap.innerHTML = "";
  if (!feed.length) {
    wrap.innerHTML = `<div class="feed-empty">Clique em Iniciar para gravar. Clique na janela do Fcerta antes de Alt+A, setas e Enter.</div>`;
    return;
  }
  feed.forEach(item => {
    const row = document.createElement("div");
    row.className = "feed-mini";
    row.innerHTML = `<span class="bullet"></span><div><div class="code">${item.code}</div><div class="sub">${item.sub}</div></div>`;
    wrap.appendChild(row);
  });
  wrap.scrollTop = wrap.scrollHeight;
}

async function toggleRecording() {
  if (!REC.recording) {
    const test_name = document.getElementById("rec-test-name").value.trim() || "Teste_Gravado";
    const r = await fetch("/api/recorder/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ test_name }),
    });
    const data = await r.json();
    if (data.status === "error") toast(data.message);
  } else {
    await fetch("/api/recorder/stop", { method: "POST" });
  }
}

async function armarAssert(kind, chipEl) {
  const r = await fetch("/api/recorder/assert", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind }),
  });
  const data = await r.json();
  if (data.status === "error") { toast(data.message); return; }
  document.querySelectorAll(".assert-chip").forEach(c => c.classList.remove("armed"));
  chipEl.classList.add("armed");
  toast("🎯 agora CLIQUE no elemento para verificar...");
  setTimeout(() => chipEl.classList.remove("armed"), 4000);
}

async function salvarGravacao() {
  const test_name = document.getElementById("rec-test-name").value.trim() || "Teste_Gravado";
  const r = await fetch("/api/recorder/save", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ test_name }),
  });
  const data = await r.json();
  if (data.status === "ok") {
    const novos = Object.entries(data.novos_aliases || {});
    let extra = "";
    if (novos.length) extra = " · novos aliases: " + novos.map(([m, els]) => `${m}(${els.length})`).join(", ");
    toast(`💾 Salvo em ${data.path}${extra}`);
  } else {
    toast(data.message || "Erro ao salvar.");
  }
}

async function limparGravacao() {
  if (!confirm("Limpar todo o teste capturado?")) return;
  await fetch("/api/recorder/clear", { method: "POST" });
  // O WebSocket recorder_update atualiza feed/código/contagem.
}

async function desfazerUltima() {
  const r = await fetch("/api/recorder/undo", { method: "POST" });
  if (!r.ok) { toast("Desfazer indisponível — reinicie o servidor (run_web.py)."); return; }
  const data = await r.json();
  if (data.status === "empty") toast("Nada para desfazer.");
}

onWS("recorder_update", aplicarEstadoRecorder);

document.getElementById("btn-rec-toggle").addEventListener("click", toggleRecording);
document.getElementById("btn-rec-save").addEventListener("click", salvarGravacao);
document.getElementById("btn-rec-undo").addEventListener("click", desfazerUltima);
document.getElementById("btn-rec-clear").addEventListener("click", limparGravacao);
document.querySelectorAll(".assert-chip").forEach(chip =>
  chip.addEventListener("click", () => armarAssert(chip.dataset.assert, chip)));

carregarRecorderState();
