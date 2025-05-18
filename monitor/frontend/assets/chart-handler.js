const lastPrices = {};

async function loadEnabledCoins() {
    const coinRes = await fetch('/api/enabled-coins');
    const coins = await coinRes.json();
  
    const balanceRes = await fetch('/api/balances');
    const balances = await balanceRes.json();
    const balanceMap = {};
    balances.forEach(b => balanceMap[b.currency] = b.available_balance);

    const usdc = balanceMap["USDC"] || 0;

    const config = await fetch('/api/config').then(r => r.json());
 
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
    const totalCryptoValue = coinData.reduce((sum, c) => sum + c.value, 0);
    const totalPortfolioValue = totalCryptoValue + usdc;
    // document.getElementById("availableFunds").textContent = `$${usdc.toFixed(2)}`;
    // document.getElementById("portfolioValue").textContent = `$${totalCryptoValue.toFixed(2)}`;
    // document.getElementById("fullPortfolioValue").textContent = `$${totalPortfolioValue.toFixed(2)}`;
    animateValue(document.getElementById("availableFunds"), 0, usdc);
    animateValue(document.getElementById("portfolioValue"), 0, totalCryptoValue);
    animateValue(document.getElementById("fullPortfolioValue"), 0, totalPortfolioValue);
  
    const dashboard = document.getElementById("coinDashboards");
    dashboard.innerHTML = "";
  
    for (const { symbol, balance, value, indicators } of coinData) {
      const pricePrecision = config.coins[symbol]?.precision?.price || 6;
      value.toFixed(pricePrecision)

      const tradeStateRes = await fetch(`/api/trading_state/${symbol}`);
      const tradeStateData = await tradeStateRes.json();
      const initialPrice = tradeStateData.initial_price || indicators.current_price;
      const buyPercentage = config.coins[symbol]?.buy_percentage || 0;
      const currentPrice = indicators.current_price;

      // Calculate price change percentage
      const lastPrice = lastPrices[symbol] || currentPrice;
      const priceDelta = currentPrice - lastPrice;
      const priceChangePercent = (priceDelta / lastPrice) * 100;
      lastPrices[symbol] = currentPrice;

      // 🔥 Determine speed color
      let priceColor = "bg-info";
      if (priceChangePercent > 0.1) priceColor = "bg-success";     // rising fast
      else if (priceChangePercent < -0.1) priceColor = "bg-danger"; // dropping fast
      else if (Math.abs(priceChangePercent) > 0.1) priceColor = "bg-warning"; // moving mildly

      // 🧮 Calculate price difference vs target
      const targetBuyPrice = initialPrice * (1 + buyPercentage / 100);
      const priceDropPercent = ((currentPrice - initialPrice) / initialPrice) * 100;
      const isNearBuyZone = priceDropPercent <= buyPercentage * 0.9; // e.g. 90% to target

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

      // 🎨 Add Current Price badge
      const currentBadge = document.createElement("span");
      currentBadge.className = `badge rounded-pill fs-6 ${priceColor}`;
      currentBadge.textContent = `Current: $${currentPrice.toFixed(pricePrecision)} (${priceChangePercent.toFixed(2)}%)`;

      // 🎨 Add Moving Average (50) badge
      const isAbove = indicators.current_price > indicators.moving_average;
      const maBadge = document.createElement("span");
      maBadge.className = `badge rounded-pill fs-6 ${isAbove ? "bg-success" : "bg-danger"}`;
      maBadge.textContent = `MA(50): $${indicators.moving_average.toFixed(pricePrecision)} (${isAbove ? "Above" : "Below"})`;
  
      indicatorsDiv.appendChild(currentBadge);
      indicatorsDiv.appendChild(maBadge);
 
      // 🎨 Add Avg Buy Price badge
      const avgBuyRes = await fetch(`/api/avg-buy-price/${symbol}`);
      const avgBuyData = await avgBuyRes.json();
      const avgBuyPrice = avgBuyData.avg_buy_price;
      
      if (avgBuyPrice !== null) {
        const currentPrice = indicators.current_price;
        const percentChange = ((currentPrice - avgBuyPrice) / avgBuyPrice) * 100;
        const isProfit = percentChange >= 0;
      
        const avgBuyBadge = document.createElement("span");
        avgBuyBadge.className = `badge rounded-pill fs-6 ${isProfit ? "bg-success" : "bg-danger"}`;
        avgBuyBadge.textContent = `Avg Buy: $${avgBuyPrice.toFixed(pricePrecision)} (${percentChange >= 0 ? "+" : ""}${percentChange.toFixed(2)}%)`;
        
        indicatorsDiv.appendChild(avgBuyBadge);
      }     

      // Show buy zone badge only if value of balance less then 1 USDC
      if (value < 1) {
        const buyZoneBadge = document.createElement("span");
      
        let color = "bg-secondary";
        if (priceDropPercent <= buyPercentage) {
          color = "bg-success"; // in buy zone!
        } else if (isNearBuyZone) {
          color = "bg-warning"; // getting close
        }
      
        buyZoneBadge.className = `badge rounded-pill fs-6 ${color}`;
        buyZoneBadge.textContent = `Buy Zone: ${priceDropPercent.toFixed(2)}% / ${buyPercentage.toFixed(2)}%`;
      
        indicatorsDiv.appendChild(buyZoneBadge);
      }

      // 🔥 Add Target badge
      const sellTarget = config.coins[symbol]?.sell_percentage || 0;
      const percentChange = ((indicators.current_price - avgBuyPrice) / avgBuyPrice) * 100;
      const progressToSell = percentChange / sellTarget;

      if (avgBuyPrice !== null && sellTarget !== 0) {
        const sellBadge = document.createElement("span");
        
        // 🔥 Progress toward target
        const progress = percentChange / sellTarget;
        let color = "bg-danger";
      
        if (progress >= 1) color = "bg-success";
        else if (progress >= 0.8) color = "bg-warning";
      
        sellBadge.className = `badge rounded-pill fs-6 ${color}`;
        sellBadge.textContent = `Target: ${percentChange >= 0 ? "+" : ""}${percentChange.toFixed(2)}% / +${sellTarget.toFixed(2)}%`;
      
        indicatorsDiv.appendChild(sellBadge);
      }

      // generic part
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
  
  function animateValue(element, start, end, duration = 1000, prefix = "$") {
    const stepTime = 20;
    const steps = Math.ceil(duration / stepTime);
    let currentStep = 0;
  
    const timer = setInterval(() => {
      currentStep++;
      const progress = currentStep / steps;
      const value = start + (end - start) * progress;
      element.textContent = `${prefix}${value.toFixed(2)}`;
      if (currentStep >= steps) clearInterval(timer);
    }, stepTime);
  }
  
// INIT
loadEnabledCoins();
loadRecentTrades();

// Auto-refresh every 30s
setInterval(() => {
    loadEnabledCoins();
    loadRecentTrades();
  }, 30000);
