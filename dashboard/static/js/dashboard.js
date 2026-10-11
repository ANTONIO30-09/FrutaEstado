// Dashboard FrutaEstado — cliente Chart.js
// Consulta GET /api/resumen cada REFRESH_MS y actualiza los 3 paneles.

const REFRESH_MS = 6000;

const COLORES = { S: "#ef4444", A: "#22c55e", R: "#f59e0b" };

let chartConteos = null;
let chartSerie = null;

async function fetchResumen() {
  const r = await fetch("/api/resumen");
  if (!r.ok) throw new Error("HTTP " + r.status);
  return await r.json();
}

function initChartConteos() {
  const ctx = document.getElementById("chart-conteos").getContext("2d");
  chartConteos = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Madura (S)", "Inmadura (A)", "Pasada (R)"],
      datasets: [{
        data: [0, 0, 0],
        backgroundColor: [COLORES.S, COLORES.A, COLORES.R],
        borderColor: "#1e293b",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#e2e8f0" } },
      },
    },
  });
}

function initChartSerie() {
  const ctx = document.getElementById("chart-serie").getContext("2d");
  chartSerie = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        label: "Registros por minuto",
        data: [],
        borderColor: "#60a5fa",
        backgroundColor: "rgba(96,165,250,0.2)",
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } },
        y: {
          beginAtZero: true,
          ticks: { color: "#94a3b8", precision: 0 },
          grid: { color: "#1e293b" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e2e8f0" } },
      },
    },
  });
}

function actualizarConteos(conteos) {
  const s = conteos.S || 0;
  const a = conteos.A || 0;
  const r = conteos.R || 0;
  document.getElementById("contador-s").textContent = s;
  document.getElementById("contador-a").textContent = a;
  document.getElementById("contador-r").textContent = r;
  document.getElementById("contador-total").textContent = s + a + r;

  if (chartConteos) {
    chartConteos.data.datasets[0].data = [s, a, r];
    chartConteos.update();
  }
}

function actualizarSerie(serie) {
  if (!chartSerie) return;
  const mapa = new Map();
  for (const item of serie) {
    const prev = mapa.get(item.minuto) || 0;
    mapa.set(item.minuto, prev + item.conteo);
  }
  const minutos = Array.from(mapa.keys()).sort();
  chartSerie.data.labels = minutos.map((m) => m.slice(11));
  chartSerie.data.datasets[0].data = minutos.map((m) => mapa.get(m));
  chartSerie.update();
}

function actualizarTabla(ultimos) {
  const tbody = document.getElementById("tbody-ultimos");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (ultimos.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:#64748b;">Sin registros todavia</td></tr>';
    return;
  }
  for (const r of ultimos) {
    const tr = document.createElement("tr");
    const hora = (r.timestamp || "").slice(11);
    const color = COLORES[r.estado] || "#666";
    tr.innerHTML =
      "<td>" + hora + "</td>" +
      '<td><span class="badge" style="background:' + color + '">' +
      r.estado + "</span></td>" +
      "<td>" + r.pct_verde.toFixed(1) + "%</td>" +
      "<td>" + r.pct_madura.toFixed(1) + "%</td>" +
      "<td>" + r.pct_pasada.toFixed(1) + "%</td>";
    tbody.appendChild(tr);
  }
}

function setEstadoConexion(ok, msg) {
  const el = document.getElementById("estado-conexion");
  if (!el) return;
  el.textContent = msg;
  el.style.color = ok ? "#22c55e" : "#ef4444";
}

async function tick() {
  try {
    const data = await fetchResumen();
    actualizarConteos(data.conteos);
    actualizarSerie(data.serie_por_minuto);
    actualizarTabla(data.ultimos);
    setEstadoConexion(true, "Actualizado " + new Date().toLocaleTimeString());
  } catch (e) {
    setEstadoConexion(false, "Error: " + e.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initChartConteos();
  initChartSerie();
  tick();
  setInterval(tick, REFRESH_MS);
});
