// app.js — navegação da sidebar (troca de tela) + toast genérico.

function mostrarTela(chave) {
  document.querySelectorAll(".item").forEach(el => el.classList.toggle("active", el.dataset.screen === chave));
  document.querySelectorAll(".screen").forEach(el => el.classList.toggle("active", el.id === `screen-${chave}`));
}

document.querySelectorAll(".item").forEach(el => {
  el.addEventListener("click", () => mostrarTela(el.dataset.screen));
});

let _toastTimer = null;
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.style.display = "flex";
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.style.display = "none"; }, 2800);
}

// ── WebSocket compartilhado: um único /ws, várias telas assinam por "type" ──
const _wsHandlers = {};
function onWS(type, handler) {
  (_wsHandlers[type] = _wsHandlers[type] || []).push(handler);
}

function conectarWS() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    (_wsHandlers[msg.type] || []).forEach(fn => fn(msg));
  };
  ws.onclose = () => setTimeout(conectarWS, 1500);
}
conectarWS();
