const $ = (sel) => document.querySelector(sel);

function setStatus(text) {
  $("#status").textContent = text || "";
}

function fmt(value, digits = 2) {
  return value === null || value === undefined ? "—" : Number(value).toFixed(digits);
}

function fmtInt(value) {
  return value === null || value === undefined ? "—" : Number(value).toLocaleString();
}

function ago(iso) {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`;
}

function changeCell(pct) {
  if (pct === null || pct === undefined) return '<td>—</td>';
  const cls = pct >= 0 ? "up" : "down";
  return `<td class="${cls}">${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%</td>`;
}

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

async function loadNews(refresh = false) {
  const button = $("#refresh-news");
  button.disabled = true;
  setStatus(refresh ? "Fetching headlines…" : "Loading…");
  try {
    const data = await api(`/api/news?limit=10${refresh ? "&refresh=true" : ""}`);
    $("#news-meta").textContent = `updated ${ago(data.fetched_at)}`;
    $("#news-list").innerHTML =
      data.articles
        .map((a) => {
          const tickers = (a.tickers || [])
            .map((t) => `<span class="tag ticker">${t}</span>`)
            .join(" ");
          return `<li>
            <a href="${a.url}" target="_blank" rel="noopener">${a.title}</a>
            <div class="news-meta-line">
              <span class="tag source">${a.source}</span>
              ${tickers}
              <span class="meta">${ago(a.published_at)}</span>
            </div>
          </li>`;
        })
        .join("") || '<li class="empty">No stories found.</li>';
    setStatus("");
  } catch (error) {
    setStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

async function loadWatchlist() {
  const tbody = $("#watchlist-table tbody");
  try {
    const data = await api("/api/watchlist");
    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">No symbols yet — add one above.</td></tr>';
      return;
    }
    tbody.innerHTML = data.items
      .map((q) => {
        if (q.error) {
          return `<tr><td><b>${q.symbol}</b></td><td colspan="5" class="empty">${q.error}</td>
            <td><button class="btn" data-remove="${q.symbol}">Remove</button></td></tr>`;
        }
        return `<tr>
          <td><b>${q.symbol}</b><small>${q.name || ""}${q.session_date ? " · " + q.session_date : ""}</small></td>
          <td>${fmt(q.open)}</td>
          <td>${fmt(q.close)}</td>
          ${changeCell(q.change_pct)}
          <td>${fmt(q.low)} – ${fmt(q.high)}</td>
          <td>${fmtInt(q.volume)}</td>
          <td><button class="btn" data-remove="${q.symbol}">Remove</button></td>
        </tr>`;
      })
      .join("");
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="7" class="error">${error.message}</td></tr>`;
  }
}

function renderRecap(recap) {
  const rows = recap.watchlist
    .map((q) =>
      q.error || q.close === null
        ? `<tr><td><b>${q.symbol}</b></td><td colspan="5" class="empty">unavailable</td></tr>`
        : `<tr>
            <td><b>${q.symbol}</b><small>${q.name || ""}</small></td>
            <td>${fmt(q.open)}</td>
            <td>${fmt(q.close)}</td>
            ${changeCell(q.change_pct)}
            <td>${fmt(q.low)} – ${fmt(q.high)}</td>
            <td>${fmtInt(q.volume)}</td>
          </tr>
          ${
            (q.headlines || []).length
              ? `<tr><td colspan="6"><ul class="recap-headlines">${q.headlines
                  .map((h) => `<li><a href="${h.url}" target="_blank" rel="noopener">${h.title}</a></li>`)
                  .join("")}</ul></td></tr>`
              : ""
          }`
    )
    .join("");

  const delivery = recap.delivery || {};
  const deliveryText = Object.entries(delivery)
    .filter(([key]) => key !== "skipped")
    .map(([channel, result]) => `${channel}: ${result.ok ? "sent" : result.reason || "failed"}`)
    .join(" · ");

  $("#recap-meta").textContent = `${recap.recap_date} (${recap.timezone})`;
  $("#recap-body").innerHTML = `
    <div class="table-wrap"><table>
      <thead><tr><th>Symbol</th><th>Open</th><th>Close</th><th>Change</th><th>Day range</th><th>Volume</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="6" class="empty">Watchlist is empty.</td></tr>'}</tbody>
    </table></div>
    <h3>Top stories in this recap</h3>
    <ol class="news-list">${recap.market_news
      .map(
        (a) =>
          `<li><a href="${a.url}" target="_blank" rel="noopener">${a.title}</a>
           <div class="news-meta-line"><span class="tag source">${a.source}</span></div></li>`
      )
      .join("")}</ol>
    <div class="delivery">${deliveryText || "not delivered"}
      <a class="link-btn" href="/api/recap/preview.html" target="_blank" rel="noopener">email preview</a>
    </div>`;
}

async function loadRecap() {
  try {
    renderRecap(await api("/api/recap"));
  } catch {
    $("#recap-body").innerHTML = '<p class="empty">No recap generated yet.</p>';
  }
}

async function runRecap(deliver) {
  const buttons = [$("#run-recap"), $("#send-recap")];
  buttons.forEach((b) => (b.disabled = true));
  setStatus(deliver ? "Generating and sending recap…" : "Generating recap…");
  try {
    renderRecap(await api(`/api/recap/run?deliver=${deliver}`, { method: "POST" }));
    setStatus("");
  } catch (error) {
    setStatus(error.message);
  } finally {
    buttons.forEach((b) => (b.disabled = false));
  }
}

$("#refresh-news").addEventListener("click", () => loadNews(true));
$("#run-recap").addEventListener("click", () => runRecap(false));
$("#send-recap").addEventListener("click", () => runRecap(true));

$("#add-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#symbol-input");
  const symbol = input.value.trim();
  if (!symbol) return;
  $("#watchlist-error").textContent = "";
  try {
    await api("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol }),
    });
    input.value = "";
    await Promise.all([loadWatchlist(), loadNews(false)]);
  } catch (error) {
    $("#watchlist-error").textContent = error.message;
  }
});

$("#watchlist-table").addEventListener("click", async (event) => {
  const symbol = event.target.dataset.remove;
  if (!symbol) return;
  await api(`/api/watchlist/${encodeURIComponent(symbol)}`, { method: "DELETE" });
  loadWatchlist();
});

loadNews(false);
loadWatchlist();
loadRecap();
