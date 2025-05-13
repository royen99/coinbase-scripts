const ctx = document.getElementById('priceChart').getContext('2d');
let chart;

async function loadEnabledCoins() {
    const res = await fetch('/api/enabled-coins');
    const coins = await res.json();
    const select = document.getElementById("symbolSelect");
    select.innerHTML = "";
  
    coins.forEach(symbol => {
      const opt = document.createElement("option");
      opt.value = symbol;
      opt.textContent = symbol;
      select.appendChild(opt);
    });
  
    if (coins.length) {
      select.value = coins[0];
      loadChart(coins[0]);
    }
}

async function loadIndicators(symbol) {
    const res = await fetch(`/api/indicators/${symbol}`);
    const data = await res.json();
  
    const indicators = document.getElementById("indicators");
    indicators.innerHTML = "";
  
    const currentBadge = document.createElement("span");
    currentBadge.className = "badge rounded-pill bg-info fs-6";
    currentBadge.textContent = `Current: $${data.current_price.toFixed(2)}`;
  
    const maBadge = document.createElement("span");
    const isAbove = data.current_price > data.moving_average;
    maBadge.className = `badge rounded-pill fs-6 ${isAbove ? "bg-success" : "bg-danger"}`;
    maBadge.textContent = `MA(50): $${data.moving_average.toFixed(2)} (${isAbove ? "Above" : "Below"})`;
  
    indicators.appendChild(currentBadge);
    indicators.appendChild(maBadge);
  }
  
document.getElementById("symbolSelect").addEventListener("change", (e) => {
    loadChart(e.target.value);
});
  
loadEnabledCoins(); // 👈 initial load

async function fetchPrices(symbol) {
  const res = await fetch(`/api/prices/${symbol}`);
  return await res.json();
}

async function fetchSignals(symbol) {
  const res = await fetch(`/api/signals/${symbol}`);
  return await res.json();
}

async function loadChart(symbol) {
    // Load indicators
    const indicatorRes = await fetch(`/api/indicators/${symbol}`);
    const indicatorsData = await indicatorRes.json();
  
    const indicators = document.getElementById("indicators");
    indicators.innerHTML = "";
  
    const currentBadge = document.createElement("span");
    currentBadge.className = "badge rounded-pill bg-info fs-6";
    currentBadge.textContent = `Current: $${indicatorsData.current_price.toFixed(2)}`;
  
    const maBadge = document.createElement("span");
    const isAbove = indicatorsData.current_price > indicatorsData.moving_average;
    maBadge.className = `badge rounded-pill fs-6 ${isAbove ? "bg-success" : "bg-danger"}`;
    maBadge.textContent = `MA(50): $${indicatorsData.moving_average.toFixed(2)} (${isAbove ? "Above" : "Below"})`;
  
    indicators.appendChild(currentBadge);
    indicators.appendChild(maBadge);
  
    // Load and show signal history
    const signalRes = await fetch(`/api/signals/${symbol}`);
    const signalData = await signalRes.json();
    renderSignalList(signalData);
  }
  

function renderSignalList(signals) {
  const list = document.getElementById("signalList");
  list.innerHTML = "";
  signals.slice(-10).reverse().forEach(s => {
    const li = document.createElement("li");
    li.className = `list-group-item list-group-item-${s.action === 'buy' ? 'success' : 'danger'}`;
    li.textContent = `${s.action.toUpperCase()} at $${s.price.toFixed(2)} on ${new Date(s.timestamp).toLocaleString()}`;
    list.appendChild(li);
  });
}

document.getElementById("symbolSelect").addEventListener("change", (e) => {
  loadChart(e.target.value);
});

// Load default chart
loadChart("ETC");
