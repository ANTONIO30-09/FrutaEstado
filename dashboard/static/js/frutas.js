// Frutas con imagenes locales PNG transparentes (offline-ready).

const RUTA_FRUTAS = "/static/img/frutas/";

const FRUTAS_ARCHIVO = {
  "manzana_roja":  "manzana_roja.png",
  "manzana_verde": "manzana_verde.png",
  "platano":       "platano.png",
  "mandarina":     "mandarina.png",
  "uva_verde":     "uva_verde.png",
  "uva_morada":    "uva_morada.png",
};

const FRUTERO_ARCHIVO = "frutero.png";

function aplicarFruta(nombre) {
  const cont = document.getElementById("fruit-img");
  if (!cont) return;

  let archivo = FRUTAS_ARCHIVO[nombre];
  if (!archivo && !nombre) archivo = FRUTERO_ARCHIVO;

  if (!archivo) {
    cont.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;color:rgba(255,255,255,0.45);font-size:0.85rem;font-style:italic;">Sin imagen</div>';
    return;
  }

  cont.innerHTML = '<img src="' + RUTA_FRUTAS + archivo + '" alt="' + (nombre || 'frutero') + '" style="max-width:90%;max-height:90%;object-fit:contain;filter:drop-shadow(-12px -14px 30px rgba(255, 250, 220, 0.8)) drop-shadow(0 6px 10px rgba(0,0,0,0.5)) drop-shadow(0 20px 45px rgba(0,0,0,0.4));">';
}
