// modulos.js — tela Módulos: lista + formulário + gravador de teclas/cliques.

const MOD = { modulos: [], sel: null, confirmDel: null, gravando: false };

async function carregarModulos() {
  const r = await fetch("/api/modulos");
  const data = await r.json();
  MOD.modulos = data.modulos;
  MOD.gravando = data.gravando;
  renderModLista();
}

function renderModLista() {
  const wrap = document.getElementById("mod-list");
  wrap.innerHTML = "";
  MOD.modulos.forEach(m => {
    const row = document.createElement("div");
    row.className = "list-row" + (m.name === MOD.sel ? " active" : "");

    if (MOD.confirmDel === m.name) {
      row.innerHTML = `
        <div class="confirm-row" style="width:100%;">
          <div class="msg">Excluir <span style="font-family:var(--font-mono);">${m.name}</span>?
            <span class="sub">Remove a entrada de modulos.json — não afeta os testes já escritos.</span>
          </div>
          <button class="btn subtle" data-cancel="${m.name}" style="height:34px;background:var(--bg-panel-2);">Cancelar</button>
          <button class="btn subtle" data-confirm="${m.name}" style="height:34px;background:var(--red-tint);color:var(--red-soft);">Excluir</button>
        </div>`;
      row.querySelector(`[data-cancel]`).addEventListener("click", (e) => { e.stopPropagation(); MOD.confirmDel = null; renderModLista(); });
      row.querySelector(`[data-confirm]`).addEventListener("click", async (e) => {
        e.stopPropagation();
        await fetch(`/api/modulos/${encodeURIComponent(m.name)}`, { method: "DELETE" });
        MOD.confirmDel = null;
        if (MOD.sel === m.name) modNovo();
        toast(`Módulo ${m.name} removido`);
        carregarModulos();
      });
    } else {
      row.innerHTML = `
        <div style="flex:1;min-width:0;">
          <div class="name">${m.name}</div>
          <div class="meta">${m.exe}</div>
        </div>
        <div class="steps">${(m.menu || []).map(s => `<span class="step-chip">${s}</span>`).join("")}</div>
        <button class="icon-btn danger" data-del="${m.name}">🗑</button>`;
      row.addEventListener("click", () => selecionarModulo(m.name));
      row.querySelector(`[data-del]`).addEventListener("click", (e) => {
        e.stopPropagation();
        MOD.confirmDel = m.name;
        renderModLista();
      });
    }
    wrap.appendChild(row);
  });
}

function selecionarModulo(nome) {
  MOD.sel = nome;
  const m = MOD.modulos.find(x => x.name === nome);
  document.getElementById("mod-nome").value = m.name;
  document.getElementById("mod-exe").value = m.exe;
  document.getElementById("mod-steps").value = (m.menu || []).join("\n");
  document.getElementById("mod-status").textContent = "";
  renderModLista();
  renderModJson();
}

function modNovo() {
  MOD.sel = null;
  document.getElementById("mod-nome").value = "";
  document.getElementById("mod-exe").value = "";
  document.getElementById("mod-steps").value = "";
  document.getElementById("mod-status").textContent = "Novo módulo — preencha e salve.";
  renderModLista();
  renderModJson();
}

function modFormState() {
  const nome = document.getElementById("mod-nome").value.trim();
  const exe = document.getElementById("mod-exe").value.trim();
  const menu = document.getElementById("mod-steps").value.split("\n").map(s => s.trim()).filter(Boolean);
  return { nome, exe, menu };
}

function renderModJson() {
  const { nome, exe, menu } = modFormState();
  if (!nome) { document.getElementById("mod-json").textContent = ""; return; }
  document.getElementById("mod-json").textContent = JSON.stringify({ [nome]: { exe, menu } }, null, 2);
}

async function salvarModulo() {
  const { nome, exe, menu } = modFormState();
  if (!nome || !exe) { document.getElementById("mod-status").textContent = "Informe nome e executável."; return; }
  const r = await fetch("/api/modulos", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome, exe, menu }),
  });
  const data = await r.json();
  if (data.status === "ok") {
    document.getElementById("mod-status").textContent = `✓ '${nome}' salvo em modulos.json`;
    MOD.sel = nome;
    await carregarModulos();
    renderModJson();
  } else {
    document.getElementById("mod-status").textContent = data.message || "Erro ao salvar.";
  }
}

async function removerAtual() {
  const { nome } = modFormState();
  if (!nome) return;
  MOD.confirmDel = nome;
  renderModLista();
}

async function testarModulo() {
  const { nome } = modFormState();
  if (!nome) { document.getElementById("mod-status").textContent = "Selecione/preencha um módulo."; return; }
  document.getElementById("mod-status").textContent = "Abrindo módulo (login + navegação)...";
  await fetch("/api/modulos/testar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome }),
  });
}

async function toggleGravarModulo() {
  const btn = document.getElementById("btn-mod-gravar");
  if (!MOD.gravando) {
    await fetch("/api/modulos/gravar/start", { method: "POST" });
    MOD.gravando = true;
    btn.textContent = "■ Parar gravação";
    document.getElementById("mod-status").textContent = "Gravando — foque a janela do Formula Certa e clique no item do menu.";
  } else {
    await fetch("/api/modulos/gravar/stop", { method: "POST" });
    MOD.gravando = false;
    btn.textContent = "🎯 Gravar teclas/cliques";
    document.getElementById("mod-status").textContent = "Gravação encerrada. Revise os passos e salve.";
  }
}

onWS("modulo_token", (msg) => {
  const ta = document.getElementById("mod-steps");
  ta.value = ta.value.trim() ? ta.value.trim() + "\n" + msg.token : msg.token;
  renderModJson();
});

onWS("modulo_teste", (msg) => {
  const el = document.getElementById("mod-status");
  if (msg.ok) el.textContent = `✓ Módulo '${msg.nome}' abriu com sucesso.`;
  else el.textContent = `⚠ falhou: ${(msg.erro || "").slice(0, 120)}`;
});

document.getElementById("btn-mod-novo").addEventListener("click", modNovo);
document.getElementById("btn-mod-salvar").addEventListener("click", salvarModulo);
document.getElementById("btn-mod-testar").addEventListener("click", testarModulo);
document.getElementById("btn-mod-remover").addEventListener("click", removerAtual);
document.getElementById("btn-mod-gravar").addEventListener("click", toggleGravarModulo);
["mod-nome", "mod-exe", "mod-steps"].forEach(id =>
  document.getElementById(id).addEventListener("input", renderModJson));

carregarModulos();
