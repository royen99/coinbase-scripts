async function loadEnabledCoins() {
    const coinRes = await fetch('/api/enabled-coins');
    const coins = await coinRes.json();
  
    const balanceRes = await fetch('/api/balances');
    const balances = await balanceRes.json();
    const balanceMap = {};
    balances.forEach(b => balanceMap[b.currency] = b.available_balance);
  
    const indicatorPromises = coins.map(async symbol => {
      const res = await fetch(`/api/indicators/${symbol}`);
      const data = await res.json();
      const balance = balanceMap[symbol] || 0;
      const value = balance * data.current_price;
      return { symbol, balance, value, indicators: data };
    });
  
    const coinData = await Promise.all(indicatorPromises);
    coinData.sort((a, b) => b.value - a.value);
  
    // 💰 Total portfolio value
    const totalValue = coinData.reduce((sum, c) => sum + c.value, 0);
    document.getElementById("portfolioValue").textContent = `$${totalValue.toFixed(2)}`;
  
    const dashboard = document.getElementById("coinDashboards");
    dashboard.innerHTML = "";
  
    for (const { symbol, balance, value, indicators } of coinData) {
      const card = document.createElement("div");
      card.className = "card bg-dark text-white mb-4 shadow";
  
      const body = document.createElement("div");
      body.className = "card-body";
  
      const headerRow = document.createElement("div");
      headerRow.className = "d-flex justify-content-between align-items-center mb-3";
  
      const title = document.createElement("h4");
      title.className = "card-title text-info fw-bold m-0";
      title.textContent = symbol;
  
      const badge = document.createElement("span");
      badge.className = "badge rounded-pill fs-6";
      badge.textContent = `Balance: ${balance.toFixed(4)} ($${value.toFixed(2)})`;
  
      let colorClass = "bg-outline-light";
      if (value > 200) colorClass = "bg-warning text-dark";
      else if (value > 100) colorClass = "bg-primary";
      else if (value > 50) colorClass = "bg-secondary";
      else if (value > 1) colorClass = "bg-dark";
      badge.className += ` ${colorClass}`;
  
      headerRow.appendChild(title);
      headerRow.appendChild(badge);
  
      const indicatorsDiv = document.createElement("div");
      indicatorsDiv.className = "d-flex gap-3 mb-3 flex-wrap";
  
      const currentBadge = document.createElement("span");
      currentBadge.className = "badge rounded-pill bg-info fs-6";
      currentBadge.textContent = `Current: $${indicators.current_price.toFixed(2)}`;
  
      const isAbove = indicators.current_price > indicators.moving_average;
      const maBadge = document.createElement("span");
      maBadge.className = `badge rounded-pill fs-6 ${isAbove ? "bg-success" : "bg-danger"}`;
      maBadge.textContent = `MA(50): $${indicators.moving_average.toFixed(2)} (${isAbove ? "Above" : "Below"})`;
  
      indicatorsDiv.appendChild(currentBadge);
      indicatorsDiv.appendChild(maBadge);
  
      body.appendChild(headerRow);
      body.appendChild(indicatorsDiv);
      card.appendChild(body);
      dashboard.appendChild(card);
    }
  }
  

  async function loadRecentTrades() {
    const res = await fetch(`/api/recent-trades`);
    const trades = await res.json();
  
    const list = document.getElementById("globalTradeList");
    list.innerHTML = "";
  
    trades.forEach(t => {
      const li = document.createElement("li");
      li.className = `list-group-item d-flex justify-content-between align-items-center list-group-item-${t.side === 'buy' ? 'success' : 'danger'}`;
      li.innerHTML = `
        <div>
          <strong>${t.side.toUpperCase()}</strong> ${t.amount} <code>${t.symbol}</code> @ $${t.price.toFixed(2)}
        </div>
        <small class="text-muted">${new Date(t.timestamp).toLocaleString()}</small>
      `;
      list.appendChild(li);
    });
  }

  async function loadIndicators(symbol, balance = 0) {
    const res = await fetch(`/api/indicators/${symbol}`);
    const data = await res.json();
  
    const container = document.getElementById(`indicators-${symbol}`);
    container.innerHTML = "";
  
    const currentPrice = data.current_price;
    const value = currentPrice * balance;
  
    // 🎨 Determine badge color based on USD value
    let colorClass = "bg-outline-light";
    if (value > 200) colorClass = "bg-warning text-dark";
    else if (value > 100) colorClass = "bg-primary";
    else if (value > 50) colorClass = "bg-secondary";
    else if (value > 1) colorClass = "bg-dark";
  
    // 💰 Update balance badge
    const badge = document.getElementById(`balance-${symbol}`);
    badge.className = `badge rounded-pill fs-6 ${colorClass}`;
    badge.textContent = `Balance: ${balance.toFixed(4)} ($${value.toFixed(2)})`;
  
    const currentBadge = document.createElement("span");
    currentBadge.className = "badge rounded-pill bg-info fs-6";
    currentBadge.textContent = `Current: $${currentPrice.toFixed(2)}`;
  
    const maBadge = document.createElement("span");
    const isAbove = currentPrice > data.moving_average;
    maBadge.className = `badge rounded-pill fs-6 ${isAbove ? "bg-success" : "bg-danger"}`;
    maBadge.textContent = `MA(50): $${data.moving_average.toFixed(2)} (${isAbove ? "Above" : "Below"})`;
  
    container.appendChild(currentBadge);
    container.appendChild(maBadge);
  }
  
  
  async function loadSignalList(symbol) {
    const res = await fetch(`/api/signals/${symbol}`);
    const signals = await res.json();
    const container = document.getElementById(`signalList-${symbol}`);
    container.innerHTML = "";
    signals.slice(-25).reverse().forEach(s => {
      const li = document.createElement("li");
      li.className = `list-group-item list-group-item-${s.action === 'buy' ? 'success' : 'danger'}`;
      li.textContent = `${s.action.toUpperCase()} at $${s.price.toFixed(2)} on ${new Date(s.timestamp).toLocaleString()}`;
      container.appendChild(li);
    });
  }
  
  // INIT
  loadEnabledCoins();
  loadRecentTrades();

// Auto-refresh every 30s
setInterval(() => {
    loadEnabledCoins();
    loadRecentTrades();
  }, 30000);
