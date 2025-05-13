const ctx = document.getElementById('priceChart').getContext('2d');
let chart;

async function fetchPrices(symbol) {
  const res = await fetch(`/api/prices/${symbol}`);
  return await res.json();
}

async function fetchSignals(symbol) {
  const res = await fetch(`/api/signals/${symbol}`);
  return await res.json();
}

async function loadChart(symbol) {
  const priceData = await fetchPrices(symbol);
  const signalData = await fetchSignals(symbol);

  const labels = priceData.map(p => new Date(p.timestamp).toLocaleTimeString());
  const prices = priceData.map(p => p.price);

  const buyPoints = signalData.filter(s => s.action === 'buy');
  const sellPoints = signalData.filter(s => s.action === 'sell');

  if (chart) chart.destroy();

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: `${symbol} Price`,
          data: prices,
          borderColor: 'cyan',
          tension: 0.2
        },
        {
          label: 'Buy',
          data: buyPoints.map(s => ({ x: new Date(s.timestamp).toLocaleTimeString(), y: s.price })),
          backgroundColor: 'lime',
          type: 'scatter',
          pointRadius: 5,
        },
        {
          label: 'Sell',
          data: sellPoints.map(s => ({ x: new Date(s.timestamp).toLocaleTimeString(), y: s.price })),
          backgroundColor: 'red',
          type: 'scatter',
          pointRadius: 5,
        }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          labels: {
            color: 'white'
          }
        },
        tooltip: {
          mode: 'nearest',
          intersect: false
        }
      },
      scales: {
        x: {
          ticks: { color: 'white' }
        },
        y: {
          ticks: { color: 'white' }
        }
      }
    }
  });

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
