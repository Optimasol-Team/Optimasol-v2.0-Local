const API_BASE = '';
const qs = (sel) => document.querySelector(sel);
const dayMap = {mon: 0, tue: 1, wed: 2, thu: 3, fri: 4, sat: 5, sun: 6};

const state = {
  token: null,
  clientId: null,
  email: null,
  name: null,
  chart: null,
};

const num = (v, fallback = null) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
};

const parseSlots = (text) => {
  const slots = [];
  (text || '')
    .split(/\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .forEach((line) => {
      const [start, end] = line.split('-').map((s) => s && s.trim());
      if (start && end) slots.push({start, end});
    });
  return slots;
};

const parsePlanning = (text) => {
  const rows = [];
  (text || '')
    .split(/\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .forEach((line) => {
      const [dayRaw, timeRaw, tempRaw, volRaw] = line.split(/\s+/);
      const day = dayMap[(dayRaw || '').slice(0, 3).toLowerCase()] ?? 0;
      rows.push({
        day,
        time: timeRaw || '07:00',
        target_temp: num(tempRaw, 50),
        volume: num(volRaw, 30),
      });
    });
  if (!rows.length) {
    rows.push({day: 0, time: '07:00', target_temp: 52, volume: 40});
    rows.push({day: 6, time: '20:00', target_temp: 50, volume: 25});
  }
  return rows;
};

function buildConfigPayload(form) {
  const f = form.elements;
  return {
    name: (f.name?.value || '').trim(),
    email: (f.email?.value || '').trim().toLowerCase(),
    password: (f.password?.value || '').trim() || null,
    driver: {
      id: 'smart_electromation_mqtt',
      config: {serial_number: (f.serial?.value || '').trim()},
    },
    weather: {
      position: {
        latitude: num(f.lat?.value, 50.62925),
        longitude: num(f.lon?.value, 3.057256),
        altitude: num(f.alt?.value, 25),
      },
      installation: {
        rendement_global: num(f.pv_eff?.value, null),
        liste_panneaux: [
          {
            azimuth: num(f.azimuth?.value, 180),
            tilt: num(f.tilt?.value, 25),
            surface_panneau: num(f.surface?.value, 2),
            puissance_nominale: num(f.power?.value, 800),
          },
        ],
      },
    },
    engine: {
      water_heater: {
        volume: num(f.wh_volume?.value, 200),
        power: num(f.wh_power?.value, 2400),
        insulation_coeff: num(f.wh_insulation?.value, 2.4),
        temp_cold_water: num(f.wh_cold?.value, 15),
      },
      prices: {
        mode: f.price_mode?.value || 'BASE',
        base_price: num(f.price_base?.value, 0.18),
        hp_price: num(f.price_hp?.value, 0.22),
        hc_price: num(f.price_hc?.value, 0.16),
        resell_price: num(f.price_resell?.value, 0.1),
        hp_slots: parseSlots(f.hp_slots?.value || ''),
      },
      features: {
        gradation: !!f.gradation?.checked,
        mode: f.optim_mode?.value || 'cost',
      },
      constraints: {
        min_temp: num(f.min_temp?.value, 45),
      },
      planning: parsePlanning(f.planning?.value || ''),
    },
  };
}

function persistSession(data) {
  if (!data) {
    state.token = state.clientId = state.email = state.name = null;
    localStorage.removeItem('optimasol_session');
    return;
  }
  state.token = data.token;
  state.clientId = data.client_id;
  state.email = data.email;
  state.name = data.name;
  localStorage.setItem(
    'optimasol_session',
    JSON.stringify({token: data.token, client_id: data.client_id, email: data.email, name: data.name}),
  );
}

async function api(path, options = {}) {
  const headers = options.headers ? {...options.headers} : {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const res = await fetch(API_BASE + path, {...options, headers});
  const text = await res.text();
  const contentType = res.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? JSON.parse(text || '{}') : text;
  if (!res.ok) {
    const msg = payload?.error || payload?.detail || res.statusText;
    if (res.status === 401) {
      persistSession(null);
      showAuth();
    }
    throw new Error(msg);
  }
  return payload;
}

function togglePanels(target) {
  document.querySelectorAll('.panel').forEach((p) => p.classList.add('hidden'));
  document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
  qs(`#panel-${target}`)?.classList.remove('hidden');
  document.querySelector(`.tab[data-panel="${target}"]`)?.classList.add('active');
}

function showAppShell() {
  qs('#authArea').classList.add('hidden');
  qs('#appArea').classList.remove('hidden');
  qs('#userPill').textContent = state.name || state.email || 'Session';
  loadServiceStatus();
  loadOverview();
  loadConfig();
  loadHistory();
}

function showAuth() {
  qs('#authArea').classList.remove('hidden');
  qs('#appArea').classList.add('hidden');
}

async function loadServiceStatus() {
  try {
    const resp = await api('/api/service/status', {headers: {}});
    const dot = qs('#servicePill .status-dot');
    const txt = qs('#serviceText');
    if (resp.running) {
      dot.classList.add('ok');
      txt.textContent = `Service en ligne (PID ${resp.pid || '?'})`;
    } else {
      dot.classList.remove('ok');
      txt.textContent = 'Service arrêté';
    }
    qs('#dbPill').textContent = `DB: ${resp.db_path || 'n/d'}`;
  } catch (err) {
    qs('#serviceText').textContent = 'Service inconnu';
  }
}

async function handleLogin(e) {
  e.preventDefault();
  qs('#loginError').textContent = '';
  const form = e.target;
  try {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({email: form.email.value, password: form.password.value}),
    });
    persistSession(data);
    showAppShell();
  } catch (err) {
    qs('#loginError').textContent = err.message || 'Connexion impossible';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  qs('#registerError').textContent = '';
  const form = e.target;
  const payload = buildConfigPayload(form);
  payload.activation_key = form.activation_key.value.trim();
  try {
    const data = await api('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    persistSession(data);
    showAppShell();
  } catch (err) {
    qs('#registerError').textContent = err.message || 'Activation impossible';
  }
}

function fillConfigForm(data) {
  const form = qs('#configForm');
  const f = form.elements;
  f.name.value = data.name || '';
  f.email.value = data.email || '';
  f.serial.value = data.driver?.config?.serial_number || '';

  const pos = data.weather?.position || {};
  f.lat.value = pos.latitude ?? '';
  f.lon.value = pos.longitude ?? '';
  f.alt.value = pos.altitude ?? '';

  const install = data.weather?.installation || {};
  const panel = (install.liste_panneaux && install.liste_panneaux[0]) || {};
  f.azimuth.value = panel.azimuth ?? '';
  f.tilt.value = panel.tilt ?? '';
  f.surface.value = panel.surface_panneau ?? '';
  f.power.value = panel.puissance_nominale ?? '';
  f.pv_eff.value = install.rendement_global ?? '';

  const wh = data.engine?.water_heater || {};
  f.wh_volume.value = wh.volume ?? '';
  f.wh_power.value = wh.power ?? '';
  f.wh_insulation.value = wh.insulation_coeff ?? '';
  f.wh_cold.value = wh.temp_cold_water ?? '';

  const cons = data.engine?.constraints || {};
  f.min_temp.value = cons.min_temp ?? '';

  const prices = data.engine?.prices || {};
  f.price_mode.value = prices.mode || 'BASE';
  f.price_base.value = prices.base_price ?? '';
  f.price_hp.value = prices.hp_price ?? '';
  f.price_hc.value = prices.hc_price ?? '';
  f.price_resell.value = prices.resell_price ?? '';
  const hpSlots = prices.hp_slots || [];
  f.hp_slots.value = hpSlots.map((s) => `${s.start}-${s.end}`).join('\n');

  const features = data.engine?.features || {};
  f.gradation.checked = !!features.gradation;
  f.optim_mode.value = features.mode || 'cost';

  const planning = data.engine?.planning || [];
  f.planning.value = planning
    .map((p) => {
      const dayName = Object.keys(dayMap).find((k) => dayMap[k] === p.day) || 'mon';
      return `${dayName} ${p.time} ${p.target_temp ?? 50} ${p.volume ?? 30}`;
    })
    .join('\n');
}

async function loadConfig() {
  try {
    const data = await api('/api/client/config');
    fillConfigForm(data);
  } catch (err) {
    qs('#configMsg').textContent = err.message;
  }
}

async function saveConfig() {
  qs('#configMsg').textContent = '';
  const payload = buildConfigPayload(qs('#configForm'));
  try {
    await api('/api/client/config', {method: 'PUT', body: JSON.stringify(payload)});
    qs('#configMsg').textContent = 'Enregistré';
    loadOverview();
  } catch (err) {
    qs('#configMsg').textContent = err.message || 'Erreur de sauvegarde';
  }
}

function formatValue(val, suffix = '') {
  if (val === null || val === undefined || Number.isNaN(val)) return '--';
  if (typeof val === 'number') {
    const fixed = Math.abs(val) >= 10 ? val.toFixed(1) : val.toFixed(2);
    return `${fixed}${suffix}`;
  }
  return `${val}${suffix}`;
}

async function loadOverview() {
  try {
    const data = await api('/api/client/overview');
    qs('#ovName').textContent = data.client?.name || 'Client';
    qs('#ovEmail').textContent = data.client?.email || '';
    qs('#ovDriver').textContent = data.client?.driver_id || '-';
    const pos = data.location || {};
    qs('#ovLocation').textContent = pos.latitude
      ? `Lat ${pos.latitude}, Lon ${pos.longitude}, Alt ${pos.altitude || '-'}`
      : 'Position inconnue';

    const pv = data.pv || {};
    const panel = (pv.liste_panneaux && pv.liste_panneaux[0]) || {};
    const pvDesc = panel.azimuth ? `${panel.azimuth}° / tilt ${panel.tilt || '?'}°` : '--';
    qs('#ovPV').textContent = pvDesc;

    const feat = data.engine?.features;
    const price = data.engine?.prices;
    const optText = feat
      ? `${feat.mode || 'mode'} · gradation ${feat.gradation ? 'ON' : 'OFF'} · tarif ${
          price?.mode || 'BASE'
        }`
      : '--';
    qs('#ovOpt').textContent = optText;

    const temp = data.live?.temperature;
    const prod = data.live?.production;
    const dec = data.live?.decision;
    qs('#ovTemp').textContent = formatValue(temp?.value, '°C');
    qs('#ovProd').textContent = formatValue(prod?.value, 'W');
    qs('#ovDecision').textContent = formatValue(dec?.value);
    const stamps = [];
    if (temp?.timestamp) stamps.push(`T° ${temp.timestamp}`);
    if (prod?.timestamp) stamps.push(`Prod ${prod.timestamp}`);
    if (dec?.timestamp) stamps.push(`Décision ${dec.timestamp}`);
    qs('#ovStamps').textContent = stamps.join(' · ') || 'Pas de données récentes';
  } catch (err) {
    console.error(err);
  }
}

function renderHistory(metric, series) {
  const ctx = qs('#historyChart').getContext('2d');
  const labels = series.map((p) => p.timestamp);
  const values = series.map((p) => Number(p.value));
  if (state.chart) state.chart.destroy();
  state.chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: metric,
          data: values,
          borderColor: '#5efc8d',
          backgroundColor: 'rgba(94,252,141,0.15)',
          tension: 0.3,
          pointRadius: 2,
        },
      ],
    },
    options: {
      plugins: {legend: {display: false}},
      scales: {
        x: {grid: {color: 'rgba(255,255,255,0.05)'}},
        y: {grid: {color: 'rgba(255,255,255,0.08)'}},
      },
    },
  });

  const table = qs('#historyTable');
  const recent = [...series].slice(-8).reverse();
  table.innerHTML =
    '<tr><th>Date</th><th>Valeur</th></tr>' +
    recent
      .map(
        (p) =>
          `<tr><td>${p.timestamp}</td><td>${p.value ?? '--'}</td></tr>`,
      )
      .join('');
}

async function loadHistory() {
  const metric = qs('#histMetric').value;
  const hours = parseInt(qs('#histHours').value, 10);
  try {
    const data = await api(`/api/client/history?metric=${encodeURIComponent(metric)}&hours=${hours}`);
    renderHistory(metric, data.series || []);
  } catch (err) {
    console.error(err);
  }
}

function restoreSession() {
  try {
    const raw = localStorage.getItem('optimasol_session');
    if (!raw) return;
    const parsed = JSON.parse(raw);
    state.token = parsed.token;
    state.clientId = parsed.client_id;
    state.email = parsed.email;
    state.name = parsed.name;
    showAppShell();
  } catch (err) {
    // ignore
  }
}

document.addEventListener('DOMContentLoaded', () => {
  qs('#loginForm').addEventListener('submit', handleLogin);
  qs('#registerForm').addEventListener('submit', handleRegister);
  qs('#saveConfigBtn').addEventListener('click', (e) => {
    e.preventDefault();
    saveConfig();
  });
  qs('#reloadHistory').addEventListener('click', loadHistory);
  document.querySelectorAll('.tab').forEach((btn) => {
    btn.addEventListener('click', () => togglePanels(btn.dataset.panel));
  });
  restoreSession();
});
