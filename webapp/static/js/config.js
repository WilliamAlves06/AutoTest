// config.js — tela Configurações: 3 cards (Aplicação/Credenciais/Testes).

async function carregarConfig() {
  const r = await fetch("/api/config");
  const cfg = await r.json();
  document.getElementById("cfg-exe-path").value = cfg.exe_path || "";
  document.getElementById("cfg-login").value = cfg.login || "";
  document.getElementById("cfg-senha").value = cfg.senha || "";
  document.getElementById("cfg-base").value = cfg.base || "";
  document.getElementById("cfg-recorder-dir").value = cfg.recorder_output_dir || "";
}

async function salvarConfig() {
  const payload = {
    exe_path: document.getElementById("cfg-exe-path").value,
    login: document.getElementById("cfg-login").value,
    senha: document.getElementById("cfg-senha").value,
    base: document.getElementById("cfg-base").value,
    recorder_output_dir: document.getElementById("cfg-recorder-dir").value,
  };
  const r = await fetch("/api/config", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (r.ok) toast("✓ Configurações salvas");
}

document.getElementById("btn-cfg-save").addEventListener("click", salvarConfig);
document.getElementById("btn-toggle-senha").addEventListener("click", () => {
  const el = document.getElementById("cfg-senha");
  el.type = el.type === "password" ? "text" : "password";
});

carregarConfig();
