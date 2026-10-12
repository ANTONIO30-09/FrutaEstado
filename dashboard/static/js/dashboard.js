// Dashboard FrutaEstado — cliente JS (rediseño glass verde).
// - Refresca /api/resumen cada 6 s.
// - Anima el gauge circular del panel central (S/A/R como 3 arcos).
// - Actualiza el "Estado actual" (último registro).
// - Toggle del panel flotante de registros.
// - Selector de fruta: POST /api/perfil + refetch.

const REFRESH_MS = 6000;
const COLORES = { S: "#4bb84b", A: "#8ce68c", R: "#227b22" };
const CIRCUNFERENCIA = 2 * Math.PI * 92; // radio del gauge = 92

let chartSerie = null;
let tipoFrutaFiltro = "";

async function fetchResumen() {
  const url = tipoFrutaFiltro
    ? "/api/resumen?tipo_fruta=" + encodeURIComponent(tipoFrutaFiltro)
    : "/api/resumen";
  const r = await fetch(url);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return await r.json();
}

async function setPerfilEnBackend(nombre) {
  try {
    const r = await fetch("/api/perfil", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ perfil: nombre }),
    });
    return r.ok;
  } catch (e) {
    return false;
  }
}

// ---------- Gauge circular ----------
function setArco(idArco, porcentaje, offsetAcumulado) {
  const el = document.getElementById(idArco);
  if (!el) return offsetAcumulado;
  const longitud = (porcentaje / 100) * CIRCUNFERENCIA;
  // Sin hueco: con stroke-linecap: butt los arcos se conectan
  // perfectamente sin bultos en las uniones.
  el.setAttribute("stroke-dasharray", longitud + " " + CIRCUNFERENCIA);
  el.setAttribute("stroke-dashoffset", -offsetAcumulado);
  return offsetAcumulado + longitud;
}

function actualizarGauge(conteos) {
  const s = conteos.S || 0;
  const a = conteos.A || 0;
  const r = conteos.R || 0;
  const total = s + a + r;
  if (total === 0) {
    setArco("arc-s", 0, 0);
    setArco("arc-a", 0, 0);
    setArco("arc-r", 0, 0);
    return;
  }
  const pctS = (s / total) * 100;
  const pctA = (a / total) * 100;
  const pctR = (r / total) * 100;

  let offset = 0;
  offset = setArco("arc-s", pctS, offset);
  offset = setArco("arc-a", pctA, offset);
  setArco("arc-r", pctR, offset);
}

// ---------- Contadores ----------
function actualizarContadores(conteos) {
  const s = conteos.S || 0;
  const a = conteos.A || 0;
  const r = conteos.R || 0;
  document.getElementById("contador-s").textContent = s;
  document.getElementById("contador-a").textContent = a;
  document.getElementById("contador-r").textContent = r;
  document.getElementById("contador-total").textContent = s + a + r;
}

// ---------- Estado actual (último registro) ----------
function actualizarEstadoActual(ultimos) {
  const el = document.getElementById("estado-actual");
  if (!el) return;
  if (!ultimos || ultimos.length === 0) {
    el.innerHTML = 'Estado actual: <strong>—</strong>';
    return;
  }
  const r = ultimos[0];
  const nombre = {
    S: "Madura", A: "Inmadura", R: "Pasada"
  }[r.estado] || r.estado;
  el.innerHTML = 'Estado actual: <strong>' + nombre + '</strong>';
}

// ---------- Gráfica de línea ----------
function initChartSerie() {
  const ctx = document.getElementById("chart-serie").getContext("2d");
  chartSerie = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        label: "Registros por minuto",
        data: [],
        borderColor: "#8ce68c",
        backgroundColor: "rgba(140,230,140,0.12)",
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: "#8ce68c",
        pointBorderColor: "#104010",
        pointBorderWidth: 2,
        borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks: {
            color: "rgba(255,255,255,0.65)",
            font: { family: "Inter", size: 11 },
          },
          grid: { color: "rgba(255,255,255,0.08)", drawBorder: false },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: "rgba(255,255,255,0.65)",
            precision: 0,
            font: { family: "Inter", size: 11 },
          },
          grid: { color: "rgba(255,255,255,0.08)", drawBorder: false },
        },
      },
      plugins: {
        legend: {
          labels: {
            color: "rgba(255,255,255,0.85)",
            font: { family: "Inter", size: 12, weight: 500 },
            usePointStyle: true,
            pointStyle: "circle",
          },
        },
      },
    },
  });
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

// ---------- Tabla del panel flotante ----------
function actualizarTabla(ultimos) {
  const tbody = document.getElementById("tbody-ultimos");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!ultimos || ultimos.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="6" style="text-align:center;opacity:0.6;">Sin registros todavía</td></tr>';
    return;
  }
  for (const r of ultimos) {
    const tr = document.createElement("tr");
    const hora = (r.timestamp || "").slice(11);
    const clase = "badge " + (r.estado || "").toLowerCase();
    tr.innerHTML =
      "<td>" + hora + "</td>" +
      '<td><span class="' + clase + '">' + r.estado + "</span></td>" +
      "<td>" + (r.tipo_fruta || "desconocida") + "</td>" +
      "<td>" + r.pct_verde.toFixed(1) + "%</td>" +
      "<td>" + r.pct_madura.toFixed(1) + "%</td>" +
      "<td>" + r.pct_pasada.toFixed(1) + "%</td>";
    tbody.appendChild(tr);
  }
}

// ---------- Estado de conexión ----------
function setEstadoConexion(ok, msg) {
  const el = document.getElementById("estado-conexion");
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle("error", !ok);
}

// ---------- Tick periódico ----------
async function tick() {
  try {
    const data = await fetchResumen();
    actualizarContadores(data.conteos);
    actualizarGauge(data.conteos);
    actualizarEstadoActual(data.ultimos);
    actualizarSerie(data.serie_por_minuto);
    actualizarTabla(data.ultimos);
    setEstadoConexion(true, "Actualizado " + new Date().toLocaleTimeString());
  } catch (e) {
    setEstadoConexion(false, "Sin conexión");
  }
}

// ---------- Selector ----------
async function onSelectorChange(ev) {
  const valor = ev.target.value;
  tipoFrutaFiltro = valor;
  // Cambia el SVG del panel central segun la fruta elegida
  aplicarFruta(valor);
  // Envia el perfil al backend (incluye "default" y "" para Ver todos)
  if (valor) {
    await setPerfilEnBackend(valor);
  }
  await tick();
}

// ---------- Toggle panel flotante ----------
function initBotonRegistros() {
  const btn = document.getElementById("btn-registros");
  const panel = document.getElementById("floating-panel");
  const btnCerrar = document.getElementById("btn-cerrar-panel");
  if (!btn || !panel) return;

  // Toggle desde el boton del header
  btn.addEventListener("click", () => {
    panel.classList.toggle("open");
    btn.classList.toggle("open");
  });

  // Cerrar desde el chevron dentro del panel
  if (btnCerrar) {
    btnCerrar.addEventListener("click", () => {
      panel.classList.remove("open");
      btn.classList.remove("open");
    });
  }

  // Cerrar tambien con la tecla Escape (bonus de UX)
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && panel.classList.contains("open")) {
      panel.classList.remove("open");
      btn.classList.remove("open");
    }
  });
}

// ---------- Arranque ----------
document.addEventListener("DOMContentLoaded", () => {
  initChartSerie();
  initBotonRegistros();

  const sel = document.getElementById("selector-fruta");
  if (sel) {
    sel.addEventListener("change", onSelectorChange);
    // Muestra el frutero al arrancar (opcion "Ver todos")
    aplicarFruta(sel.value);
  }

  tick();
  setInterval(tick, REFRESH_MS);
});
