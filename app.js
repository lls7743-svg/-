// Chart x-axes should always read in JST, not the viewer's local timezone.
if (window.luxon) luxon.Settings.defaultZone = "Asia/Tokyo";

const REASON_LABELS = {
  golden_cross: "ゴールデンクロス（買い）",
  stop_loss: "損切り",
  trailing_take_profit: "利益確定（トレーリング）",
  bearish_reversal_pattern: "反転パターン（陰線包み足/流れ星）",
  dead_cross: "デッドクロス",
  day_trade_close: "大引け前の手仕舞い",
  new_high_breakout: "直近高値更新（買い）",
  new_low_exit: "直近安値割れ（手仕舞い）",
};

// ?data=<name> points the same dashboard at data/<name>/ instead of data/, so
// any backtest's trades can be reviewed on the same charts as live trades.
const ALT_DATA_LABELS = {
  backtest: "バックテスト結果（ルールベース戦略）",
  breakout_backtest: "高値更新ブレイクアウト検証（日足・6ヶ月）",
};
const DATA_PARAM = new URLSearchParams(location.search).get("data");
const DATA_BASE = DATA_PARAM ? `data/${DATA_PARAM}` : "data";
const IS_BACKTEST = DATA_PARAM !== null;

const fmtYen = (n) => "¥" + Math.round(n).toLocaleString("ja-JP");
const fmtPct = (n) => (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
// Always render in JST regardless of the viewer's own timezone -- this is a
// Japan-market app, so times should read the same on any device.
const fmtDateTime = (iso) =>
  new Date(iso).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });

async function fetchJSON(path) {
  const res = await fetch(`${path}?_=${Date.now()}`);
  if (!res.ok) throw new Error(`Failed to load ${path}`);
  return res.json();
}

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function statTile(label, value, cls = "") {
  const el = document.createElement("div");
  el.className = "stat-tile";
  el.innerHTML = `<div class="label">${label}</div><div class="value ${cls}">${value}</div>`;
  return el;
}

function renderStats(portfolio, lastPrices) {
  const marketValue = Object.entries(portfolio.positions).reduce(
    (sum, [sym, pos]) => sum + pos.qty * (lastPrices[sym] ?? pos.entry_price),
    0
  );
  const equity = portfolio.cash + marketValue;
  const unrealized = Object.entries(portfolio.positions).reduce((sum, [sym, pos]) => {
    const price = lastPrices[sym] ?? pos.entry_price;
    return sum + (price - pos.entry_price) * pos.qty;
  }, 0);
  const returnPct = ((equity - portfolio.initial_cash) / portfolio.initial_cash) * 100;

  const row = document.getElementById("stat-row");
  row.innerHTML = "";
  row.appendChild(statTile("総資産", fmtYen(equity)));
  row.appendChild(statTile("現金", fmtYen(portfolio.cash)));
  row.appendChild(statTile("保有株評価額", fmtYen(marketValue)));
  row.appendChild(
    statTile("確定損益", fmtYen(portfolio.realized_pnl), portfolio.realized_pnl >= 0 ? "good" : "critical")
  );
  row.appendChild(statTile("含み損益", fmtYen(unrealized), unrealized >= 0 ? "good" : "critical"));
  row.appendChild(statTile("リターン", fmtPct(returnPct), returnPct >= 0 ? "good" : "critical"));

  document.getElementById("last-updated").textContent = portfolio.last_updated
    ? fmtDateTime(portfolio.last_updated)
    : "まだ実行されていません";
}

function renderEquityChart(equityPoints) {
  const ctx = document.getElementById("equity-chart");
  if (equityPoints.length === 0) {
    ctx.parentElement.innerHTML = '<div class="empty">まだデータがありません</div>';
    return;
  }
  new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "総資産",
          data: equityPoints.map((p) => ({ x: p.t, y: p.equity })),
          borderColor: css("--series-price"),
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { type: "time", time: { unit: "day" }, grid: { color: css("--gridline") }, ticks: { color: css("--text-muted") } },
        y: { grid: { color: css("--gridline") }, ticks: { color: css("--text-muted"), callback: (v) => fmtYen(v) } },
      },
    },
  });
}

function legendRow(items) {
  const el = document.createElement("div");
  el.className = "chart-legend";
  el.innerHTML = items
    .map((i) => `<span class="item"><span class="swatch" style="background:${i.color}"></span>${i.label}</span>`)
    .join("");
  return el;
}

function renderSymbolChart(symbol, bars, trades) {
  const card = document.createElement("div");
  card.innerHTML = `<h2>${symbol}</h2><div class="card-sub">${bars.length ? bars[bars.length - 1].c + " 円（直近終値）" : ""}</div>`;
  card.appendChild(
    legendRow([
      { color: css("--series-price"), label: "株価" },
      { color: css("--good"), label: "▲ 買い" },
      { color: css("--critical"), label: "▼ 売り" },
    ])
  );
  const box = document.createElement("div");
  box.className = "chart-box";
  const canvas = document.createElement("canvas");
  box.appendChild(canvas);
  card.appendChild(box);

  const buys = trades.filter((t) => t.symbol === symbol && t.side === "BUY");
  const sells = trades.filter((t) => t.symbol === symbol && t.side === "SELL");

  new Chart(canvas, {
    data: {
      datasets: [
        {
          type: "line",
          label: "株価",
          data: bars.map((b) => ({ x: b.t, y: b.c })),
          borderColor: css("--series-price"),
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
        },
        {
          type: "scatter",
          label: "買い",
          data: buys.map((t) => ({ x: t.time, y: t.price, reason: t.reason })),
          backgroundColor: css("--good"),
          pointStyle: "triangle",
          rotation: 0,
          radius: 8,
        },
        {
          type: "scatter",
          label: "売り",
          data: sells.map((t) => ({ x: t.time, y: t.price, reason: t.reason, pnl: t.pnl })),
          backgroundColor: css("--critical"),
          pointStyle: "triangle",
          rotation: 180,
          radius: 8,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const raw = ctx.raw;
              const base = `${ctx.dataset.label}: ${Math.round(raw.y).toLocaleString("ja-JP")}円`;
              if (raw.reason) {
                const reason = REASON_LABELS[raw.reason] ?? raw.reason;
                const pnl = raw.pnl != null ? ` (損益 ${fmtYen(raw.pnl)})` : "";
                return `${base} - ${reason}${pnl}`;
              }
              return base;
            },
          },
        },
      },
      scales: {
        x: { type: "time", time: { unit: "day" }, grid: { color: css("--gridline") }, ticks: { color: css("--text-muted") } },
        y: { grid: { color: css("--gridline") }, ticks: { color: css("--text-muted") } },
      },
    },
  });

  return card;
}

function renderSymbolCharts(pricesBySymbol, trades) {
  const container = document.getElementById("symbol-charts");
  container.innerHTML = "";
  const symbols = new Set([...Object.keys(pricesBySymbol), ...trades.map((t) => t.symbol)]);
  if (symbols.size === 0) {
    container.innerHTML = '<div class="empty">まだ取引がありません</div>';
    return;
  }
  for (const symbol of [...symbols].sort()) {
    const card = document.createElement("div");
    card.className = "card";
    const inner = renderSymbolChart(symbol, pricesBySymbol[symbol]?.bars ?? [], trades);
    card.appendChild(inner);
    container.appendChild(card);
  }
}

function renderTradeLog(trades) {
  const el = document.getElementById("trade-log");
  if (trades.length === 0) {
    el.innerHTML = '<div class="empty">まだ取引がありません</div>';
    return;
  }
  const rows = [...trades]
    .reverse()
    .map((t) => {
      const badge = t.side === "BUY" ? '<span class="badge buy">買</span>' : '<span class="badge sell">売</span>';
      const time = fmtDateTime(t.time);
      const reason = REASON_LABELS[t.reason] ?? t.reason ?? "-";
      const pnl = t.pnl != null ? fmtYen(t.pnl) : "-";
      const pnlClass = t.pnl > 0 ? "good" : t.pnl < 0 ? "critical" : "";
      return `<tr>
        <td>${time}</td>
        <td>${badge} ${t.symbol}</td>
        <td>${t.qty}</td>
        <td>${Math.round(t.price).toLocaleString("ja-JP")}円</td>
        <td>${reason}</td>
        <td class="${pnlClass}">${pnl}</td>
      </tr>`;
    })
    .join("");
  el.innerHTML = `<table>
    <thead><tr><th>時刻</th><th>銘柄</th><th>株数</th><th>価格</th><th>理由</th><th>損益</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

async function main() {
  if (IS_BACKTEST) {
    const label = ALT_DATA_LABELS[DATA_PARAM] ?? `参考結果（${DATA_PARAM}）`;
    document.querySelector("h1").textContent = `デイトレ・シミュレーター（${label}）`;
    document.querySelector(".subtitle").innerHTML =
      '過去データを使った検証結果です（参考値・将来の成績を保証するものではありません） / ' +
      '最終データ時点: <span id="last-updated">-</span> / <a href="index.html">ライブ運用の結果に戻る</a>';
  }

  const [portfolio, trades, equityPoints, symbolIndex] = await Promise.all([
    fetchJSON(`${DATA_BASE}/portfolio.json`),
    fetchJSON(`${DATA_BASE}/trades.json`),
    fetchJSON(`${DATA_BASE}/equity.json`),
    fetchJSON(`${DATA_BASE}/prices/index.json`),
  ]);

  const pricesBySymbol = {};
  await Promise.all(
    symbolIndex.map(async (symbol) => {
      try {
        pricesBySymbol[symbol] = await fetchJSON(`${DATA_BASE}/prices/${symbol}.json`);
      } catch (e) {
        console.warn(`price history missing for ${symbol}`, e);
      }
    })
  );

  const lastPrices = {};
  for (const [symbol, data] of Object.entries(pricesBySymbol)) {
    if (data.bars.length) lastPrices[symbol] = data.bars[data.bars.length - 1].c;
  }

  renderStats(portfolio, lastPrices);
  renderEquityChart(equityPoints);
  renderSymbolCharts(pricesBySymbol, trades);
  renderTradeLog(trades);
}

main().catch((err) => {
  console.error(err);
  document.querySelector(".wrap").innerHTML +=
    `<div class="card"><div class="empty">データの読み込みに失敗しました: ${err.message}<br>ローカルで見る場合は "python3 -m http.server" などでHTTP経由で開いてください（file://では動作しません）。</div></div>`;
});
