let token = null;

const loginForm = document.querySelector("#login-form");
const signupForm = document.querySelector("#signup-form");
const dashboard = document.querySelector("#dashboard");
const authSection = document.querySelector("#auth-section");
const summaryBox = document.querySelector("#summary");
const historyBox = document.querySelector("#history");
const clientEditor = document.querySelector("#client-editor");
const saveBtn = document.querySelector("#save-client");
const saveStatus = document.querySelector("#save-status");
const userInfo = document.querySelector("#user-info");

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (token) headers["Authorization"] = token;
  headers["Content-Type"] = "application/json";
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg || res.statusText);
  }
  return res.json();
}

loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(loginForm).entries());
  try {
    const res = await api("/api/login", { method: "POST", body: JSON.stringify(data) });
    token = res.token;
    await loadMe();
    await loadClient();
    await loadHistory();
    authSection.classList.add("hidden");
    dashboard.classList.remove("hidden");
  } catch (err) {
    alert("Connexion échouée: " + err.message);
  }
});

signupForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(signupForm);
  const payload = {
    activation_key: form.get("activation_key"),
    name: form.get("name"),
    email: form.get("email"),
    password: form.get("password"),
    client: JSON.parse(form.get("client_json")),
  };
  try {
    const res = await api("/api/signup", { method: "POST", body: JSON.stringify(payload) });
    token = res.token;
    await loadMe();
    await loadClient();
    await loadHistory();
    authSection.classList.add("hidden");
    dashboard.classList.remove("hidden");
  } catch (err) {
    alert("Inscription échouée: " + err.message);
  }
});

async function loadMe() {
  const me = await api("/api/me");
  userInfo.textContent = `${me.name} (${me.email})`;
}

async function loadClient() {
  const res = await api("/api/client");
  clientEditor.value = JSON.stringify(res, null, 2);
  summaryBox.innerHTML = `
    <div><strong>Client ID:</strong> ${res.client_id}</div>
    <div><strong>Mode:</strong> ${res.engine.features?.mode}</div>
    <div><strong>Prix:</strong> ${res.engine.prices?.mode}</div>
  `;
}

saveBtn?.addEventListener("click", async () => {
  saveStatus.textContent = "";
  try {
    const json = JSON.parse(clientEditor.value);
    await api("/api/client", { method: "POST", body: JSON.stringify({ client: json }) });
    saveStatus.textContent = "Sauvegardé";
    saveStatus.className = "status-ok";
  } catch (err) {
    saveStatus.textContent = err.message;
    saveStatus.className = "status-error";
  }
});

async function loadHistory() {
  const res = await api("/api/history");
  const fmt = (arr) => arr.slice(-5).map((x) => `${x.timestamp || x.time}: ${x.temperature || x.production || x.decision}`).join("<br>");
  historyBox.innerHTML = `
    <strong>Températures (5 derniers):</strong><br>${fmt(res.temperatures)}<br><br>
    <strong>Production mesurée:</strong><br>${fmt(res.production_measured)}<br><br>
    <strong>Décisions:</strong><br>${fmt(res.decisions)}<br><br>
    <strong>Production prévue:</strong><br>${fmt(res.production_forecast)}
  `;
}
