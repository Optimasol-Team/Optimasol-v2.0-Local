let token = null;
let signupToken = null;
let drivers = [];
let currentDriver = null;
let currentClient = null;
let configMode = "signup"; // signup | edit

const loginForm = document.querySelector("#login-form");
const signupForm = document.querySelector("#signup-form");
const configForm = document.querySelector("#config-form");
const passwordForm = document.querySelector("#password-form");

const authScreen = document.querySelector("#auth-screen");
const configSection = document.querySelector("#config-section");
const appScreen = document.querySelector("#app-screen");

const loginStatus = document.querySelector("#login-status");
const signupStatus = document.querySelector("#signup-status");
const configStatus = document.querySelector("#config-status");
const resumeCard = document.querySelector("#resume-card");
const resumeBtn = document.querySelector("#resume-signup");
const resumeStatus = document.querySelector("#resume-status");
const userInfo = document.querySelector("#user-info");
const summaryBox = document.querySelector("#summary");
const historyList = document.querySelector("#history-list");
const historyChart = document.querySelector("#history-chart");
const historyLoad = document.querySelector("#history-load");
const historyStart = document.querySelector("#history-start");
const historyEnd = document.querySelector("#history-end");
const pwdStatus = document.querySelector("#pwd-status");

const driverSelect = document.querySelector("#driver-select");
const driverName = document.querySelector("#driver-name");
const driverDescription = document.querySelector("#driver-description");
const driverIcon = document.querySelector("#driver-icon");
const driverFields = document.querySelector("#driver-fields");
const clientJsonField = document.querySelector("#client-json");

const priceMode = document.querySelector("#price-mode");
const priceBaseRow = document.querySelector("#price-base-row");
const priceHpHcRow = document.querySelector("#price-hp-hc-row");
const priceBase = document.querySelector("#price-base");
const priceHp = document.querySelector("#price-hp");
const priceHc = document.querySelector("#price-hc");
const priceResell = document.querySelector("#price-resell");
const backgroundNoise = document.querySelector("#background-noise");

const forbiddenList = document.querySelector("#forbidden-list");
const forbiddenAdd = document.querySelector("#forbidden-add");
const planningList = document.querySelector("#planning-list");
const planningAdd = document.querySelector("#planning-add");

const configTitle = document.querySelector("#config-title");
const configSubtitle = document.querySelector("#config-subtitle");
const configWizard = document.querySelector("#config-wizard");
const configBack = document.querySelector("#config-back");
const configSubmitBtn = document.querySelector("#config-submit");
const signupSubmitBtn = document.querySelector("#signup-form button[type=\"submit\"]");

const navItems = document.querySelectorAll(".nav-item[data-panel]");
const navSettings = document.querySelector(".nav-item[data-action=\"settings\"]");
const logoutBtn = document.querySelector("#logout-btn");
const panelHome = document.querySelector("#panel-home");
const panelHistory = document.querySelector("#panel-history");
const panelSecurity = document.querySelector("#panel-security");

function setStatus(el, message, ok = false) {
  if (!el) return;
  el.textContent = message || "";
  el.className = `form-status ${ok ? "status-ok" : "status-error"}`;
}

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

function showSection(section) {
  authScreen?.classList.add("hidden");
  configSection?.classList.add("hidden");
  appScreen?.classList.add("hidden");
  section?.classList.remove("hidden");
}

function showResumeCard(show) {
  if (!resumeCard) return;
  resumeCard.classList.toggle("hidden", !show);
}

function setActivePanel(panel) {
  panelHome?.classList.add("hidden");
  panelHistory?.classList.add("hidden");
  panelSecurity?.classList.add("hidden");
  if (panel === "history") panelHistory?.classList.remove("hidden");
  else if (panel === "security") panelSecurity?.classList.remove("hidden");
  else panelHome?.classList.remove("hidden");

  navItems.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.panel === panel);
  });
}

function showApp() {
  showSection(appScreen);
  setActivePanel("home");
  if (appScreen && typeof appScreen.scrollIntoView === "function") {
    appScreen.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function normalizeFieldValue(input) {
  if (!input) return null;
  if (input.type === "number") return Number(input.value);
  if (input.type === "checkbox") return Boolean(input.checked);
  return input.value;
}

function renderDriverFields(def, values = {}) {
  driverFields.innerHTML = "";
  if (!def || !def.form_schema) return;

  def.form_schema.forEach((field) => {
    const wrapper = document.createElement("div");
    wrapper.className = "field";

    const label = document.createElement("label");
    label.textContent = field.label || field.key;
    wrapper.appendChild(label);

    let input;
    if (field.type === "select") {
      input = document.createElement("select");
      (field.options || []).forEach((opt) => {
        const option = document.createElement("option");
        if (Array.isArray(opt)) {
          option.value = opt[0];
          option.textContent = opt[1];
        } else {
          option.value = opt;
          option.textContent = opt;
        }
        input.appendChild(option);
      });
    } else {
      input = document.createElement("input");
      input.type = field.type || "text";
    }

    input.name = field.key;
    if (field.required) input.required = true;
    if (field.default !== undefined) input.value = field.default;
    if (field.placeholder) input.placeholder = field.placeholder;
    if (values && values[field.key] !== undefined) {
      input.value = values[field.key];
    }

    wrapper.appendChild(input);

    if (field.help) {
      const help = document.createElement("div");
      help.className = "hint";
      help.textContent = field.help;
      wrapper.appendChild(help);
    }

    driverFields.appendChild(wrapper);
  });
}

function renderDriver(def, values = {}) {
  currentDriver = def;
  if (!def) return;
  driverName.textContent = def.name || def.id || "";
  driverDescription.textContent = def.description || "";
  if (def.icon_data) {
    driverIcon.src = def.icon_data;
    driverIcon.classList.remove("hidden");
  } else {
    driverIcon.removeAttribute("src");
    driverIcon.classList.add("hidden");
  }
  renderDriverFields(def, values);
}

async function loadDrivers() {
  const res = await api("/api/drivers");
  drivers = res.drivers || [];
  driverSelect.innerHTML = "";
  drivers.forEach((drv) => {
    const opt = document.createElement("option");
    opt.value = drv.id;
    opt.textContent = drv.name || drv.id;
    driverSelect.appendChild(opt);
  });
  if (drivers.length > 0) {
    renderDriver(drivers[0]);
  }
  updatePriceFields();
}

driverSelect?.addEventListener("change", () => {
  const def = drivers.find((d) => d.id === driverSelect.value);
  renderDriver(def);
});

function updatePriceFields() {
  if (!priceMode) return;
  const isHpHc = priceMode.value === "HC_HP";
  priceBaseRow?.classList.toggle("hidden", isHpHc);
  priceHpHcRow?.classList.toggle("hidden", !isHpHc);
  if (priceBase) {
    priceBase.required = !isHpHc;
    priceBase.disabled = isHpHc;
  }
  if (priceHp && priceHc) {
    priceHp.required = isHpHc;
    priceHc.required = isHpHc;
    priceHp.disabled = !isHpHc;
    priceHc.disabled = !isHpHc;
  }
}

priceMode?.addEventListener("change", updatePriceFields);

function addForbiddenRow(data = {}) {
  const row = document.createElement("div");
  row.className = "list-row two-col";

  const startWrap = document.createElement("div");
  const startLabel = document.createElement("label");
  startLabel.textContent = "Début";
  const startInput = document.createElement("input");
  startInput.type = "time";
  startInput.value = data.start || "";
  startWrap.appendChild(startLabel);
  startWrap.appendChild(startInput);

  const endWrap = document.createElement("div");
  const endLabel = document.createElement("label");
  endLabel.textContent = "Fin";
  const endInput = document.createElement("input");
  endInput.type = "time";
  endInput.value = data.end || "";
  endWrap.appendChild(endLabel);
  endWrap.appendChild(endInput);

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "ghost";
  remove.textContent = "Supprimer";
  remove.addEventListener("click", () => row.remove());

  row.appendChild(startWrap);
  row.appendChild(endWrap);
  row.appendChild(remove);
  forbiddenList?.appendChild(row);
}

function addPlanningRow(data = {}) {
  const row = document.createElement("div");
  row.className = "list-row four-col";

  const dayWrap = document.createElement("div");
  const dayLabel = document.createElement("label");
  dayLabel.textContent = "Jour";
  const daySelect = document.createElement("select");
  const days = [
    ["0", "Lundi"],
    ["1", "Mardi"],
    ["2", "Mercredi"],
    ["3", "Jeudi"],
    ["4", "Vendredi"],
    ["5", "Samedi"],
    ["6", "Dimanche"],
  ];
  days.forEach(([value, label]) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    daySelect.appendChild(opt);
  });
  daySelect.value = data.day ?? "0";
  dayWrap.appendChild(dayLabel);
  dayWrap.appendChild(daySelect);

  const timeWrap = document.createElement("div");
  const timeLabel = document.createElement("label");
  timeLabel.textContent = "Heure";
  const timeInput = document.createElement("input");
  timeInput.type = "time";
  timeInput.value = data.time || "";
  timeWrap.appendChild(timeLabel);
  timeWrap.appendChild(timeInput);

  const tempWrap = document.createElement("div");
  const tempLabel = document.createElement("label");
  tempLabel.textContent = "Temp cible (°C)";
  const tempInput = document.createElement("input");
  tempInput.type = "number";
  tempInput.step = "0.1";
  tempInput.value = data.target_temp ?? 50;
  tempWrap.appendChild(tempLabel);
  tempWrap.appendChild(tempInput);

  const volumeWrap = document.createElement("div");
  const volumeLabel = document.createElement("label");
  volumeLabel.textContent = "Volume (L)";
  const volumeInput = document.createElement("input");
  volumeInput.type = "number";
  volumeInput.step = "1";
  volumeInput.value = data.volume ?? 30;
  volumeWrap.appendChild(volumeLabel);
  volumeWrap.appendChild(volumeInput);

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "ghost";
  remove.textContent = "Supprimer";
  remove.addEventListener("click", () => row.remove());

  row.appendChild(dayWrap);
  row.appendChild(timeWrap);
  row.appendChild(tempWrap);
  row.appendChild(volumeWrap);
  row.appendChild(remove);
  planningList?.appendChild(row);
}

forbiddenAdd?.addEventListener("click", () => addForbiddenRow());
planningAdd?.addEventListener("click", () => addPlanningRow());

function clearDynamicLists() {
  forbiddenList.innerHTML = "";
  planningList.innerHTML = "";
}

function buildAssistantFromForm() {
  const driverConfig = {};
  driverFields.querySelectorAll("input, select, textarea").forEach((input) => {
    driverConfig[input.name] = normalizeFieldValue(input);
  });

  const priceModeValue = priceMode?.value || "BASE";
  const prices = { mode: priceModeValue, resell_price: Number(priceResell.value) };
  if (priceModeValue === "HC_HP") {
    prices.hp_price = Number(priceHp.value);
    prices.hc_price = Number(priceHc.value);
  } else {
    prices.base_price = Number(priceBase.value);
  }

  const forbidden = Array.from(forbiddenList?.querySelectorAll(".list-row") || [])
    .map((row) => {
      const inputs = row.querySelectorAll("input");
      const start = inputs[0]?.value || "";
      const end = inputs[1]?.value || "";
      if (!start || !end) return null;
      return { start, end };
    })
    .filter(Boolean);

  const planning = Array.from(planningList?.querySelectorAll(".list-row") || [])
    .map((row) => {
      const selects = row.querySelectorAll("select");
      const inputs = row.querySelectorAll("input");
      const day = selects[0]?.value ?? "0";
      const time = inputs[0]?.value || "";
      const target = inputs[1]?.value || "";
      const volume = inputs[2]?.value || "";
      if (!time) return null;
      return {
        day: Number(day),
        time,
        target_temp: Number(target),
        volume: Number(volume),
      };
    })
    .filter(Boolean);

  return {
    driver: {
      type: currentDriver?.id || "",
      config: driverConfig,
    },
    engine: {
      water_heater: {
        volume: Number(document.querySelector("#wh-volume").value),
        power: Number(document.querySelector("#wh-power").value),
        insulation_coeff: Number(document.querySelector("#wh-insulation").value),
        temp_cold_water: Number(document.querySelector("#wh-cold").value),
      },
      prices,
      features: {
        mode: document.querySelector("#mode-optim").value,
        gradation: Boolean(document.querySelector("#feature-gradation").checked),
      },
      constraints: {
        min_temp: Number(document.querySelector("#min-temp").value),
        forbidden_slots: forbidden,
        background_noise: Number(backgroundNoise?.value || 250.0),
      },
      planning,
    },
    weather: {
      position: {
        latitude: Number(document.querySelector("#loc-lat").value),
        longitude: Number(document.querySelector("#loc-lon").value),
        altitude: Number(document.querySelector("#loc-alt").value),
      },
      installation: {
        rendement_global: Number(document.querySelector("#pv-rendement").value),
        liste_panneaux: [
          {
            azimuth: Number(document.querySelector("#pv-azimuth").value),
            tilt: Number(document.querySelector("#pv-tilt").value),
            surface_panneau: Number(document.querySelector("#pv-surface").value),
            puissance_nominale: Number(document.querySelector("#pv-power").value),
          },
        ],
      },
    },
  };
}

function fillFormFromClient(client) {
  if (!client) return;
  const engine = client.engine || {};
  const weather = client.weather || {};
  const driver = client.driver || {};

  document.querySelector("#wh-volume").value = engine.water_heater?.volume ?? 200;
  document.querySelector("#wh-power").value = engine.water_heater?.power ?? 2400;
  document.querySelector("#wh-insulation").value = engine.water_heater?.insulation_coeff ?? 0.8;
  document.querySelector("#wh-cold").value = engine.water_heater?.temp_cold_water ?? 15;

  document.querySelector("#loc-lat").value = weather.position?.latitude ?? 0;
  document.querySelector("#loc-lon").value = weather.position?.longitude ?? 0;
  document.querySelector("#loc-alt").value = weather.position?.altitude ?? 0;

  document.querySelector("#pv-azimuth").value = weather.installation?.liste_panneaux?.[0]?.azimuth ?? 180;
  document.querySelector("#pv-tilt").value = weather.installation?.liste_panneaux?.[0]?.tilt ?? 30;
  document.querySelector("#pv-surface").value = weather.installation?.liste_panneaux?.[0]?.surface_panneau ?? 1.8;
  document.querySelector("#pv-power").value = weather.installation?.liste_panneaux?.[0]?.puissance_nominale ?? 350;
  document.querySelector("#pv-rendement").value = weather.installation?.rendement_global ?? 0.18;

  const prices = engine.prices || {};
  priceMode.value = prices.mode || "BASE";
  priceBase.value = prices.base_price ?? 0.18;
  priceHp.value = prices.hp_price ?? 0.22;
  priceHc.value = prices.hc_price ?? 0.14;
  priceResell.value = prices.resell_price ?? 0.06;
  updatePriceFields();

  document.querySelector("#mode-optim").value = engine.features?.mode || "cost";
  document.querySelector("#feature-gradation").checked = Boolean(engine.features?.gradation ?? true);

  document.querySelector("#min-temp").value = engine.constraints?.min_temp ?? 45;
  document.querySelector("#background-noise").value = engine.constraints?.background_noise ?? 250;

  clearDynamicLists();
  (engine.constraints?.forbidden_slots || []).forEach(addForbiddenRow);
  (engine.planning || []).forEach(addPlanningRow);

  const def = drivers.find((d) => d.id === driver.type) || drivers[0];
  if (def) {
    driverSelect.value = def.id;
    renderDriver(def, driver.config || {});
  }
}

function openConfigForSignup() {
  configMode = "signup";
  configTitle.textContent = "Configuration du client";
  configSubtitle.textContent = "Complétez les informations pour finaliser l'inscription.";
  configWizard.classList.remove("hidden");
  configBack.classList.add("hidden");
  configSubmitBtn.textContent = "Finaliser l'inscription";
  clientJsonField.value = "";
  showSection(configSection);
}

function openConfigForEdit() {
  configMode = "edit";
  configTitle.textContent = "Paramètres client";
  configSubtitle.textContent = "Modifiez vos paramètres via l'assistant.";
  configWizard.classList.add("hidden");
  configBack.classList.remove("hidden");
  configSubmitBtn.textContent = "Mettre à jour";
  clientJsonField.value = "";
  showSection(configSection);
  if (currentClient) {
    fillFormFromClient(currentClient);
  }
}

function logout() {
  token = null;
  signupToken = null;
  currentClient = null;
  localStorage.removeItem("optimasol_token");
  localStorage.removeItem("optimasol_signup");
  userInfo.textContent = "";
  showSection(authScreen);
}

loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus(loginStatus, "");
  const data = Object.fromEntries(new FormData(loginForm).entries());
  try {
    const res = await api("/api/login", { method: "POST", body: JSON.stringify(data) });
    token = res.token;
    localStorage.setItem("optimasol_token", token);
    showResumeCard(false);
    await loadDashboard();
  } catch (err) {
    setStatus(loginStatus, "Connexion échouée: " + err.message);
  }
});

signupForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus(signupStatus, "");
  if (signupSubmitBtn) signupSubmitBtn.disabled = true;
  const form = new FormData(signupForm);
  const payload = {
    name: form.get("name"),
    admin_identifier: form.get("admin_identifier"),
    email: form.get("email"),
    password: form.get("password"),
    password_confirm: form.get("password_confirm"),
    activation_key: form.get("activation_key"),
  };
  if (payload.password !== payload.password_confirm) {
    setStatus(signupStatus, "Les mots de passe ne correspondent pas.");
    if (signupSubmitBtn) signupSubmitBtn.disabled = false;
    return;
  }
  try {
    const res = await api("/api/signup/start", { method: "POST", body: JSON.stringify(payload) });
    signupToken = res.signup_token;
    localStorage.setItem("optimasol_signup", signupToken);
    await loadDrivers();
    openConfigForSignup();
    updatePriceFields();
    showResumeCard(false);
  } catch (err) {
    setStatus(signupStatus, "Inscription échouée: " + err.message);
  } finally {
    if (signupSubmitBtn) signupSubmitBtn.disabled = false;
  }
});

configBack?.addEventListener("click", () => {
  showApp();
});

configForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus(configStatus, "");
  if (!configForm.checkValidity()) {
    configForm.reportValidity();
    return;
  }

  if (configMode === "edit") {
    if (!currentClient) {
      setStatus(configStatus, "Client introuvable. Rechargez la page.");
      return;
    }
    const advancedJson = clientJsonField?.value?.trim();
    let updated = JSON.parse(JSON.stringify(currentClient));

    if (advancedJson) {
      try {
        updated = JSON.parse(advancedJson);
      } catch (err) {
        setStatus(configStatus, "JSON invalide: " + err.message);
        return;
      }
    } else {
      const assistant = buildAssistantFromForm();
      updated.engine = { ...updated.engine, ...assistant.engine };
      updated.weather = { ...updated.weather, ...assistant.weather };
      updated.driver = assistant.driver;
    }

    try {
      await api("/api/client", { method: "POST", body: JSON.stringify({ client: updated }) });
      setStatus(configStatus, "Paramètres mis à jour.", true);
      currentClient = updated;
      showApp();
    } catch (err) {
      setStatus(configStatus, "Mise à jour échouée: " + err.message);
    }
    return;
  }

  if (!signupToken) {
    setStatus(configStatus, "Inscription introuvable. Recommencez.");
    return;
  }

  const advancedJson = clientJsonField?.value?.trim();
  let payload = { signup_token: signupToken, mode: "assistant" };

  if (advancedJson) {
    try {
      payload = {
        signup_token: signupToken,
        mode: "json",
        client_json: JSON.parse(advancedJson),
      };
    } catch (err) {
      setStatus(configStatus, "JSON invalide: " + err.message);
      return;
    }
  } else {
    if (!currentDriver) {
      setStatus(configStatus, "Driver manquant.");
      return;
    }
    payload.assistant = buildAssistantFromForm();
  }

  try {
    const res = await api("/api/signup/complete", { method: "POST", body: JSON.stringify(payload) });
    setStatus(configStatus, "Inscription validée. Chargement...", true);
    token = res.token;
    localStorage.removeItem("optimasol_signup");
    signupToken = null;
    localStorage.setItem("optimasol_token", token);
    await loadDashboard();
  } catch (err) {
    setStatus(configStatus, "Finalisation échouée: " + err.message);
    const msg = String(err.message || "");
    if (msg.includes("Inscription introuvable") || msg.includes("Clé") || msg.includes("Compte déjà créé")) {
      signupToken = null;
      localStorage.removeItem("optimasol_signup");
      showSection(authScreen);
    }
  }
});

resumeBtn?.addEventListener("click", async () => {
  setStatus(resumeStatus, "");
  const storedSignup = localStorage.getItem("optimasol_signup");
  if (!storedSignup) {
    setStatus(resumeStatus, "Aucune inscription en cours.");
    showResumeCard(false);
    return;
  }
  try {
    const res = await api(`/api/signup/pending?token=${encodeURIComponent(storedSignup)}`);
    if (!res.valid) {
      localStorage.removeItem("optimasol_signup");
      setStatus(resumeStatus, "Inscription expirée. Recommencez.");
      showResumeCard(false);
      return;
    }
    signupToken = storedSignup;
    await loadDrivers();
    openConfigForSignup();
    updatePriceFields();
  } catch (err) {
    setStatus(resumeStatus, "Impossible de reprendre: " + err.message);
  }
});

navItems.forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.panel;
    if (target) setActivePanel(target);
  });
});

navSettings?.addEventListener("click", async () => {
  try {
    if (!drivers.length) await loadDrivers();
    openConfigForEdit();
  } catch (err) {
    setStatus(configStatus, "Impossible de charger les drivers: " + err.message);
  }
});

logoutBtn?.addEventListener("click", logout);

passwordForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus(pwdStatus, "");
  const payload = {
    current_password: document.querySelector("#pwd-current").value,
    new_password: document.querySelector("#pwd-new").value,
    new_password_confirm: document.querySelector("#pwd-confirm").value,
  };
  if (payload.new_password !== payload.new_password_confirm) {
    setStatus(pwdStatus, "Les mots de passe ne correspondent pas.");
    return;
  }
  try {
    await api("/api/password/change", { method: "POST", body: JSON.stringify(payload) });
    setStatus(pwdStatus, "Mot de passe mis à jour.", true);
    passwordForm.reset();
  } catch (err) {
    setStatus(pwdStatus, err.message);
  }
});

function drawChart(canvas, points) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const width = canvas.clientWidth;
  const height = canvas.height;
  canvas.width = width;
  ctx.clearRect(0, 0, width, height);

  if (!points.length) {
    ctx.fillStyle = "#6b7280";
    ctx.fillText("Aucune donnée pour la période sélectionnée.", 10, 20);
    return;
  }

  const values = points.map((p) => p.temperature);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const span = maxVal - minVal || 1;

  ctx.strokeStyle = "#0ea5e9";
  ctx.lineWidth = 2;
  ctx.beginPath();

  points.forEach((p, idx) => {
    const x = (idx / (points.length - 1 || 1)) * (width - 20) + 10;
    const y = height - ((p.temperature - minVal) / span) * (height - 20) - 10;
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.stroke();
}

async function loadHistoryRange() {
  try {
    const params = new URLSearchParams();
    if (historyStart?.value) params.set("start", historyStart.value);
    if (historyEnd?.value) params.set("end", historyEnd.value);
    const res = await api(`/api/history/temperature?${params.toString()}`);
    const temps = res.temperatures || [];
    drawChart(historyChart, temps);
    historyList.innerHTML = temps
      .slice(-10)
      .map((t) => `${t.timestamp}: ${t.temperature}`)
      .join("<br>");
  } catch (err) {
    historyList.textContent = "Erreur de chargement: " + err.message;
  }
}

historyLoad?.addEventListener("click", loadHistoryRange);

async function loadMe() {
  const me = await api("/api/me");
  userInfo.textContent = `${me.name} (${me.email})`;
}

async function loadClient() {
  const res = await api("/api/client");
  currentClient = res;
}

async function loadSummary() {
  const res = await api("/api/summary");
  const items = [
    { label: "Température", data: res.temperature },
    { label: "Production mesurée", data: res.production_measured },
    { label: "Production prévue", data: res.production_forecast },
    { label: "Dernière décision", data: res.decision },
  ];
  summaryBox.innerHTML = items
    .map((item) => {
      const value = item.data ? item.data.value : "—";
      const ts = item.data ? item.data.timestamp : "";
      return `<div class="summary-item"><div class="label">${item.label}</div><div class="value">${value}</div><div class="muted">${ts}</div></div>`;
    })
    .join("");
}

async function loadDashboard() {
  await loadMe();
  showApp();
  await Promise.allSettled([loadClient(), loadSummary()]);
}

async function bootstrap() {
  const storedToken = localStorage.getItem("optimasol_token");
  const storedSignup = localStorage.getItem("optimasol_signup");
  if (storedToken) {
    token = storedToken;
    try {
      await loadDashboard();
      return;
    } catch (err) {
      token = null;
      localStorage.removeItem("optimasol_token");
    }
  }

  showSection(authScreen);
  updatePriceFields();

  if (storedSignup) {
    try {
      const res = await api(`/api/signup/pending?token=${encodeURIComponent(storedSignup)}`);
      if (res.valid) {
        showResumeCard(true);
        return;
      }
    } catch (err) {
      // ignore
    }
    localStorage.removeItem("optimasol_signup");
    showResumeCard(false);
  }
}

bootstrap();
