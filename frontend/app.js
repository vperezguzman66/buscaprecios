const API = "";  // same origin

// ── Store registry (populated from /api/stores) ───────────────────────────────

let STORES = [];

async function loadStores() {
  try {
    const res = await fetch(`${API}/api/stores`);
    STORES = await res.json();
  } catch {
    STORES = [
      { id: "easy", name: "Easy", configured: true },
      { id: "homecenter", name: "Homecenter", configured: true },
      { id: "construmart", name: "Construmart", configured: true },
    ];
  }
  renderStoreFilters("store-filters", "store");
  renderStoreFilters("batch-store-filters", "batch-store");
}

function renderStoreFilters(containerId, inputName) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const label = container.querySelector(".filter-label");
  container.innerHTML = "";
  if (label) container.appendChild(label);

  STORES.forEach(store => {
    const lbl = document.createElement("label");
    if (!store.configured) lbl.classList.add("store-label-disabled");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.name = inputName;
    cb.value = store.id;
    cb.checked = store.configured;
    cb.disabled = !store.configured;

    lbl.appendChild(cb);
    lbl.append(` ${store.name}`);

    if (!store.configured) {
      const note = document.createElement("span");
      note.className = "store-note";
      note.textContent = "(requiere config)";
      lbl.appendChild(note);
    }

    container.appendChild(lbl);
  });
}

// ── Search history ────────────────────────────────────────────────────────────

const HISTORY_KEY = "buscaprecios_history";
const HISTORY_MAX = 10;

function getHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}

function saveToHistory(query) {
  let h = getHistory().filter(q => q !== query);
  h.unshift(query);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(0, HISTORY_MAX)));
  renderHistory();
}

function renderHistory() {
  const container = document.getElementById("search-history");
  if (!container) return;
  const history = getHistory();
  if (!history.length) { container.innerHTML = ""; return; }

  container.innerHTML = history.map(q =>
    `<button class="history-chip" type="button">${escHtml(q)}</button>`
  ).join("");

  container.querySelectorAll(".history-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.getElementById("query").value = chip.textContent;
      searchForm.requestSubmit();
    });
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getSelectedStores(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)]
    .map(el => el.value).join(",");
}

function storeDisplayName(storeId) {
  return STORES.find(s => s.id === storeId)?.name || storeId;
}

function storeLongName(storeId) {
  const overrides = { homecenter: "Homecenter (Sodimac)", mercadolibre: "MercadoLibre" };
  return overrides[storeId] || storeDisplayName(storeId);
}

function badgeClass(storeId) {
  return { easy: "badge-easy", homecenter: "badge-homecenter", construmart: "badge-construmart", mercadolibre: "badge-mercadolibre" }[storeId] || "";
}

function escHtml(str) {
  return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function safeUrl(url) {
  try {
    const u = new URL(url);
    return (u.protocol === "https:" || u.protocol === "http:") ? url : "#";
  } catch { return "#"; }
}

function productCard(p) {
  const img = p.image
    ? `<img class="product-img" src="${p.image}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    : "";
  const placeholder = `<div class="product-img-placeholder" ${p.image ? 'style="display:none"' : ""}>🛒</div>`;
  return `
    <div class="product-card">
      ${img}${placeholder}
      <div class="product-body">
        <span class="badge ${badgeClass(p.store_id)}">${escHtml(storeDisplayName(p.store_id))}</span>
        <p class="product-name">${escHtml(p.name)}</p>
        <p class="product-price">${escHtml(p.price_text)}</p>
        <p class="product-store">${escHtml(storeLongName(p.store_id))}</p>
        <a class="product-link" href="${safeUrl(p.url)}" target="_blank" rel="noopener noreferrer">Ver producto →</a>
      </div>
    </div>`;
}

// ── Results rendering ─────────────────────────────────────────────────────────

function renderResults(container, data) {
  const { query, count, results, errors } = data;

  let html = `<div class="results-header">
    <h2>${count} resultado${count !== 1 ? "s" : ""} para "<strong>${escHtml(query)}</strong>"</h2>
    ${count > 0 ? `<button class="btn-export" id="btn-export">Exportar CSV</button>` : ""}
  </div>`;

  if (errors?.length) {
    const notConfigured = errors.filter(e => e.code === "not_configured");
    const otherErrors = errors.filter(e => e.code !== "not_configured");
    if (notConfigured.length) {
      html += `<div class="error-banner">⚙️ <strong>MercadoLibre</strong> requiere credenciales de API.
        <a href="https://developers.mercadolibre.com" target="_blank" rel="noopener noreferrer">Regístrate gratis →</a>
        y agrega <code>ML_CLIENT_ID</code> / <code>ML_CLIENT_SECRET</code> al entorno.</div>`;
    }
    if (otherErrors.length) {
      html += `<div class="error-banner">⚠️ Tiendas sin respuesta: ${otherErrors.map(e => escHtml(e.store)).join(", ")}</div>`;
    }
  }

  html += results.length
    ? `<div class="results-grid">${results.map(productCard).join("")}</div>`
    : `<div class="empty-state">😕 Sin resultados<p>Prueba con otro término de búsqueda.</p></div>`;

  container.innerHTML = html;
  document.getElementById("btn-export")?.addEventListener("click", () => exportCSV(query, results));
}

function renderBatchResults(data) {
  const { total_queries, results } = data;
  let html = `<div class="results-header">
    <h2>${total_queries} producto${total_queries !== 1 ? "s" : ""} buscado${total_queries !== 1 ? "s" : ""}</h2>
    <button class="btn-export" id="btn-export-batch">Exportar todo CSV</button>
  </div>`;

  Object.entries(results).forEach(([query, queryData]) => {
    const count = queryData.count;
    html += `<div class="batch-query-block">
      <h3>${escHtml(query)} <span style="color:var(--muted);font-weight:400">(${count} resultado${count !== 1 ? "s" : ""})</span></h3>`;
    html += count
      ? `<div class="results-grid">${queryData.results.slice(0, 5).map(productCard).join("")}</div>`
      : `<div class="empty-state" style="padding:1rem 0">😕 Sin resultados</div>`;
    html += `</div>`;
  });

  batchResultsArea.innerHTML = html;
  document.getElementById("btn-export-batch")?.addEventListener("click", () => exportBatchCSV(results));
}

// ── CSV export ────────────────────────────────────────────────────────────────

function toCsvRow(cells) {
  return cells.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",");
}

function downloadCsv(filename, rows) {
  const csv = rows.map(toCsvRow).join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

function exportCSV(query, results) {
  const rows = [["Producto", "Precio", "Tienda", "URL"]];
  results.forEach(p => rows.push([p.name, p.price_text, storeLongName(p.store_id), p.url]));
  downloadCsv(`buscaprecios-${query.replace(/\s+/g, "_")}.csv`, rows);
}

function exportBatchCSV(allResults) {
  const rows = [["Búsqueda", "Producto", "Precio", "Tienda", "URL"]];
  Object.entries(allResults).forEach(([q, data]) => {
    data.results.forEach(p => rows.push([q, p.name, p.price_text, storeLongName(p.store_id), p.url]));
  });
  downloadCsv("buscaprecios-lote.csv", rows);
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
  });
});

// ── Single search ─────────────────────────────────────────────────────────────

const searchForm = document.getElementById("search-form");
const resultsArea = document.getElementById("results-area");
const btnSearch = document.getElementById("btn-search");

searchForm.addEventListener("submit", async e => {
  e.preventDefault();
  const query = document.getElementById("query").value.trim();
  if (!query) return;

  const stores = getSelectedStores("store");
  if (!stores) { alert("Selecciona al menos una tienda."); return; }

  btnSearch.disabled = true;
  btnSearch.textContent = "Buscando…";
  resultsArea.innerHTML = `<div class="spinner"></div>`;

  try {
    const res = await fetch(`${API}/api/search?query=${encodeURIComponent(query)}&stores=${stores}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    renderResults(resultsArea, data);
    if (data.count > 0) saveToHistory(query);
  } catch (err) {
    resultsArea.innerHTML = `<div class="error-banner">Error: ${escHtml(err.message)}</div>`;
  } finally {
    btnSearch.disabled = false;
    btnSearch.textContent = "Buscar";
  }
});

// ── Batch search ──────────────────────────────────────────────────────────────

let selectedFile = null;
const dropZone = document.getElementById("drop-zone");
const csvInput = document.getElementById("csv-file");
const fileNameEl = document.getElementById("file-name");
const btnBatch = document.getElementById("btn-batch");
const batchResultsArea = document.getElementById("batch-results-area");
const batchProgress = document.getElementById("batch-progress");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const progressQuery = document.getElementById("progress-query");

document.getElementById("btn-browse").addEventListener("click", () => csvInput.click());

csvInput.addEventListener("change", () => { if (csvInput.files[0]) setFile(csvInput.files[0]); });

dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  selectedFile = file;
  fileNameEl.textContent = `📄 ${file.name}`;
  btnBatch.disabled = false;
}

btnBatch.addEventListener("click", async () => {
  if (!selectedFile) return;
  const stores = getSelectedStores("batch-store");
  if (!stores) { alert("Selecciona al menos una tienda."); return; }
  const maxResults = document.getElementById("batch-max-results").value;

  btnBatch.disabled = true;
  btnBatch.textContent = "Buscando…";
  batchResultsArea.innerHTML = "";
  batchProgress.style.display = "block";
  progressFill.style.width = "0%";
  progressText.textContent = "Iniciando…";
  progressQuery.textContent = "";

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("stores", stores);
  form.append("max_results", maxResults);

  const allResults = {};
  let total = 0;

  try {
    const response = await fetch(`${API}/api/search-batch`, { method: "POST", body: form });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Error desconocido" }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();  // keep incomplete last chunk

      for (const part of parts) {
        if (!part.startsWith("data: ")) continue;
        const data = JSON.parse(part.slice(6));

        if (data.done) {
          batchProgress.style.display = "none";
          renderBatchResults({ total_queries: total, results: allResults });
          return;
        }

        total = data.total;
        allResults[data.query] = data.result;
        const pct = Math.round((data.progress / data.total) * 100);
        progressFill.style.width = `${pct}%`;
        progressText.textContent = `Buscando ${data.progress} / ${data.total}`;
        progressQuery.textContent = `"${data.query}"`;
      }
    }

    // Stream ended without a done event — render what we have
    batchProgress.style.display = "none";
    if (Object.keys(allResults).length) {
      renderBatchResults({ total_queries: total, results: allResults });
    }

  } catch (err) {
    batchProgress.style.display = "none";
    batchResultsArea.innerHTML = `<div class="error-banner">Error: ${escHtml(err.message)}</div>`;
  } finally {
    btnBatch.disabled = false;
    btnBatch.textContent = "Buscar precios";
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────

loadStores();
renderHistory();
