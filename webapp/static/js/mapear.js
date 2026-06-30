// mapear.js — tela Mapear: varredura de janela + editor de aliases.

const MAP = { targets: [], modulo: null, janela: null, elements: [], confirmDel: null, capturando: false, scanning: false };

async function carregarTargets() {
  const r = await fetch("/api/mapear/targets");
  const data = await r.json();
  MAP.targets = data.targets;
  renderMapTargets();
}

function renderMapTargets() {
  const wrap = document.getElementById("map-targets");
  wrap.innerHTML = "";
  MAP.targets.forEach(nome => {
    const chip = document.createElement("div");
    chip.className = "chip" + (nome === MAP.modulo ? " active" : "");
    chip.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 21h8M12 18v3"/></svg><span class="name">${nome}</span>`;
    chip.addEventListener("click", () => {
      MAP.modulo = nome;
      document.getElementById("map-modulo").textContent = nome;
      renderMapTargets();
      carregarMapaExistente(nome);
    });
    wrap.appendChild(chip);
  });
}

function janelaDeModulo(modulo) {
  return modulo.toUpperCase().startsWith("FC") ? modulo.slice(2) : modulo;
}

async function carregarMapaExistente(modulo) {
  const janela = janelaDeModulo(modulo);
  document.getElementById("scan-log").style.display = "none";
  document.getElementById("scan-log").textContent = "";
  try {
    const r = await fetch(`/api/mapear/map?modulo=${encodeURIComponent(modulo)}&janela=${encodeURIComponent(janela)}`);
    const data = await r.json();
    MAP.janela = janela;
    MAP.elements = data.elements || [];
  } catch {
    MAP.janela = janela;
    MAP.elements = [];
  }
  document.getElementById("map-info-modulo").textContent = modulo;
  document.getElementById("map-info-janela").textContent = janela;
  renderAliasRows();
}

function scanLog(linha) {
  const el = document.getElementById("scan-log");
  el.style.display = "block";
  el.textContent += linha + "\n";
  el.scrollTop = el.scrollHeight;
}

async function escanear(merge) {
  if (!MAP.modulo) { toast("Escolha um módulo primeiro"); return; }
  if (MAP.scanning) return;
  MAP.scanning = true;
  document.getElementById("scan-log").textContent = "";
  scanLog(`--- ${merge ? "re-mapeando (mesclar)" : "mapeando"}: ${MAP.modulo} ---`);
  const r = await fetch("/api/mapear/scan", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modulo: MAP.modulo, existing: merge ? MAP.elements : null }),
  });
  const data = await r.json();
  if (data.status === "error") { scanLog("ERRO: " + data.message); MAP.scanning = false; }
}

onWS("scan_started", () => {});
onWS("scan_progress", (msg) => scanLog(msg.msg));
onWS("scan_done", (msg) => {
  MAP.scanning = false;
  MAP.janela = msg.janela;
  MAP.elements = msg.elements;
  scanLog(`OK — ${msg.total} elementos`);
  document.getElementById("map-info-modulo").textContent = msg.modulo;
  document.getElementById("map-info-janela").textContent = msg.janela;
  renderAliasRows();
});
onWS("scan_error", (msg) => {
  MAP.scanning = false;
  scanLog("ERRO: " + msg.message);
  toast("Falha no mapeamento: " + msg.message.slice(0, 100));
});

function kindOf(el) {
  const cls = (el.class_name || "").toLowerCase();
  const ct = (el.control_type || "").toLowerCase();
  if (cls.includes("grid")) return "grid";
  if (cls.includes("combo")) return "combo";
  if (cls.includes("check")) return "check";
  if (cls.includes("button") || cls.includes("btn") || ct === "button") return "botão";
  return "campo";
}

function locOf(el) {
  if (el.automation_id) return `automation_id ${el.automation_id} · idx ${el.found_index}`;
  if (el.title) return `title "${el.title}" · idx ${el.found_index}`;
  return `class ${el.class_name || "?"} · idx ${el.found_index}`;
}

function renderAliasRows() {
  const wrap = document.getElementById("alias-rows");
  wrap.innerHTML = "";
  const nomeados = MAP.elements.filter(e => (e.alias || "").trim()).length;
  document.getElementById("map-info-count").textContent = `${nomeados} nomeados`;
  document.getElementById("add-alias-hint").style.display = MAP.elements.length ? "none" : "block";

  MAP.elements.forEach((el, idx) => {
    const row = document.createElement("div");
    row.className = "alias-row";

    if (MAP.confirmDel === idx) {
      row.innerHTML = `
        <div class="confirm-row">
          <div class="msg">Remover alias <span style="font-family:var(--font-mono);">${el.alias || "(sem nome)"}</span>?
            <span class="sub">O localizador errado sai do alias-map desta janela.</span>
          </div>
          <button class="btn subtle" data-cancel style="height:34px;background:var(--bg-panel-2);">Cancelar</button>
          <button class="btn subtle" data-confirm style="height:34px;background:var(--red-tint);color:var(--red-soft);">Remover</button>
        </div>`;
      row.querySelector("[data-cancel]").addEventListener("click", () => { MAP.confirmDel = null; renderAliasRows(); });
      row.querySelector("[data-confirm]").addEventListener("click", () => {
        MAP.elements.splice(idx, 1);
        MAP.confirmDel = null;
        renderAliasRows();
      });
    } else {
      row.innerHTML = `
        <div class="row-grid">
          <input class="alias-input" data-idx="${idx}" value="${el.alias || ""}" placeholder="nome_do_alias">
          <div><span class="kind-badge">${kindOf(el)}</span></div>
          <div class="loc">${locOf(el)}</div>
          <div class="row-actions">
            <button class="icon-btn" data-eye="${idx}">👁</button>
            <button class="icon-btn danger" data-del="${idx}">🗑</button>
          </div>
        </div>`;
      row.querySelector("[data-eye]").addEventListener("click", () => realcar(el));
      row.querySelector("[data-del]").addEventListener("click", () => { MAP.confirmDel = idx; renderAliasRows(); });
      row.querySelector(".alias-input").addEventListener("input", (e) => { el.alias = e.target.value; });
    }
    wrap.appendChild(row);
  });
}

async function realcar(el) {
  if (!MAP.modulo) return;
  await fetch("/api/mapear/highlight", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modulo: MAP.modulo, element: el }),
  });
}

async function salvarMapa() {
  if (!MAP.modulo || !MAP.janela) { toast("Mapeie um módulo primeiro"); return; }
  const r = await fetch("/api/mapear/save", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modulo: MAP.modulo, janela: MAP.janela, elements: MAP.elements }),
  });
  const data = await r.json();
  if (data.status === "ok") toast(`✓ Alias-map salvo (${data.total} elementos)`);
  else toast(data.message || "Erro ao salvar.");
}

async function toggleCaptura() {
  const btn = document.getElementById("btn-capture");
  if (!MAP.modulo) { toast("Escolha um módulo primeiro"); return; }
  if (!MAP.capturando) {
    await fetch("/api/mapear/capture/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modulo: MAP.modulo }),
    });
    MAP.capturando = true;
    btn.textContent = "■ Parar captura";
    btn.style.background = "var(--red-tint)";
    btn.style.color = "var(--red-soft)";
    toast("Captura LIGADA — clique num campo do Formula Certa.");
  } else {
    await fetch("/api/mapear/capture/stop", { method: "POST" });
    MAP.capturando = false;
    btn.textContent = "🎯 Capturar manual";
    btn.style.background = "var(--bg-panel-2)";
    btn.style.color = "var(--txt)";
  }
}

onWS("capture_candidate", (msg) => {
  const info = msg.element;
  const dup = MAP.elements.find(e => e.automation_id && e.automation_id === info.automation_id);
  const nome = window.prompt(
    (dup ? `Este campo já existe (alias '${dup.alias}'). ` : "") +
    `Campo capturado:\nclass_name: ${info.class_name || "—"}\ntitle: ${info.title || "—"}\nautomation_id: ${info.automation_id || "—"}\n\nNome do alias:`
  );
  if (!nome) return;
  info.alias = nome.trim();
  MAP.elements.push(info);
  renderAliasRows();
});

document.getElementById("btn-scan").addEventListener("click", () => escanear(false));
document.getElementById("btn-remap").addEventListener("click", () => escanear(true));
document.getElementById("btn-save-map").addEventListener("click", salvarMapa);
document.getElementById("btn-capture").addEventListener("click", toggleCaptura);

carregarTargets();
