let configData = {};

window.onload = async () => {
    const res = await fetch('/api/config');
    configData = await res.json();
    buildMainTabs(configData, document.getElementById('configForm'));
  };

function buildMainTabs(data, parent) {
    const nav = document.createElement('ul');
    nav.className = 'nav nav-tabs mb-3';
    const content = document.createElement('div');
    content.className = 'tab-content';
  
    // --- General Tab ---
    const generalTabId = 'tab-general';
    const generalNav = document.createElement('li');
    generalNav.className = 'nav-item';
    const generalLink = document.createElement('a');
    generalLink.className = 'nav-link active';
    generalLink.setAttribute('data-bs-toggle', 'tab');
    generalLink.href = `#${generalTabId}`;
    generalLink.innerHTML = '⚙️ General';
    generalNav.appendChild(generalLink);
    nav.appendChild(generalNav);
  
    const generalPane = document.createElement('div');
    generalPane.className = 'tab-pane fade show active p-3 border rounded bg-secondary';
    generalPane.id = generalTabId;
  
    // Extract coin data and remove from general
    const coins = data.coins;
    delete data.coins;
  
    buildForm(data, generalPane);
  
    content.appendChild(generalPane);
  
    // --- Coins Tab ---
    const coinsTabId = 'tab-coins';
    const coinsNav = document.createElement('li');
    coinsNav.className = 'nav-item';
    const coinsLink = document.createElement('a');
    coinsLink.className = 'nav-link';
    coinsLink.setAttribute('data-bs-toggle', 'tab');
    coinsLink.href = `#${coinsTabId}`;
    coinsLink.innerHTML = `🪙 Coins <span class="badge bg-light text-dark">${Object.keys(coins).length}</span>`;
    coinsNav.appendChild(coinsLink);
    nav.appendChild(coinsNav);
  
    const coinsPane = document.createElement('div');
    coinsPane.className = 'tab-pane fade p-3 border rounded bg-secondary';
    coinsPane.id = coinsTabId;
  
    createCoinTabs(coins, coinsPane);
    content.appendChild(coinsPane);
  
    parent.appendChild(nav);
    parent.appendChild(content);
  
    // Restore coins for save later
    data.coins = coins;
  }

  function addNewCoin(coins, nav, tabContent) {
    const coinName = prompt("Enter new coin name (e.g., ETH-USD):");
    if (!coinName || coinName.trim() === "") return;
  
    const cleanId = `tab-${coinName.replace(/[^a-zA-Z0-9]/g, '')}`;
    if (coins[coinName]) {
      alert("Coin already exists!");
      return;
    }
  
    // Default structure
    coins[coinName] = {
        enabled: true,
        buy_percentage: -3,
        sell_percentage: 3,
        volatility_window: 10,
        trend_window: 26,
        macd_short_window: 12,
        macd_long_window: 26,
        macd_signal_window: 9,
        rsi_period: 14,
        min_order_sizes: {
          buy: 1,
          sell: 0.001
        },
        precision: {
          price: 2,
          amount: 6
        }
      };
  
    // Create new tab
    const navItem = document.createElement('li');
    navItem.className = 'nav-item';
    const link = document.createElement('a');
    link.className = 'nav-link';
    link.setAttribute('data-bs-toggle', 'tab');
    link.href = `#${cleanId}`;
    link.innerText = coinName;
    navItem.appendChild(link);
    nav.appendChild(navItem);
  
    const tabPane = document.createElement('div');
    tabPane.className = 'tab-pane fade p-3 border rounded bg-secondary';
    tabPane.id = cleanId;
    buildForm(coins[coinName], tabPane, `coins.${coinName}.`);
    tabContent.appendChild(tabPane);
  
    // Activate the new tab
    new bootstrap.Tab(link).show();
  }
  
function buildForm(data, parent, prefix = '') {
    if (prefix === '' && data.coins && typeof data.coins === 'object') {
      createCoinTabs(data.coins, parent);
      delete data.coins;
    }
  
    for (const key in data) {
      const value = data[key];
      const id = prefix + key;
  
      const group = document.createElement('div');
      group.className = 'col-md-6';
  
      const label = document.createElement('label');
      label.innerText = key;
      label.className = 'form-label';
  
      let input;
      if (typeof value === 'boolean') {
        input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = value;
        input.className = 'form-check-input';
        input.id = id;
  
        const checkDiv = document.createElement('div');
        checkDiv.className = 'form-check';
        checkDiv.appendChild(input);
        checkDiv.appendChild(label);
        group.appendChild(checkDiv);
      } else if (typeof value === 'object' && value !== null) {
        const fieldset = document.createElement('fieldset');
        const legend = document.createElement('legend');
        legend.innerText = key;
        legend.className = 'text-info';
        fieldset.appendChild(legend);
        buildForm(value, fieldset, id + '.');
        group.appendChild(fieldset);
      } else {
        input = document.createElement('input');
        input.className = 'form-control';
        input.value = value;
        input.id = id;
  
        group.appendChild(label);
        group.appendChild(input);
      }
  
      parent.appendChild(group);
    }
  }

  function createCoinTabs(coins, parent) {
    const nav = document.createElement('ul');
    nav.className = 'nav nav-tabs mb-3';
    const tabContent = document.createElement('div');
    tabContent.className = 'tab-content';
  
    let first = true;
    for (const coin in coins) {
      const tabId = `tab-${coin.replace(/[^a-zA-Z0-9]/g, '')}`;
      
      // Nav tab
      const navItem = document.createElement('li');
      navItem.className = 'nav-item';
      const link = document.createElement('a');
      link.className = 'nav-link' + (first ? ' active' : '');
      link.setAttribute('data-bs-toggle', 'tab');
      link.href = `#${tabId}`;
      link.innerText = coin;
      navItem.appendChild(link);
      nav.appendChild(navItem);
  
      // Tab pane
      const tabPane = document.createElement('div');
      tabPane.className = 'tab-pane fade' + (first ? ' show active' : '');
      tabPane.id = tabId;
      tabPane.classList.add('p-3', 'border', 'rounded', 'bg-secondary');
      
      buildForm(coins[coin], tabPane, `coins.${coin}.`);
      tabContent.appendChild(tabPane);
  
      first = false;
    }
  
    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-sm btn-outline-light mb-3';
    addBtn.innerHTML = '➕ Add New Coin';
    addBtn.onclick = () => addNewCoin(coins, nav, tabContent);
    parent.appendChild(addBtn);
    parent.appendChild(nav);
    parent.appendChild(tabContent);
  }
  
function collectFormData(data, prefix = '') {
  const result = {};
  for (const key in data) {
    const value = data[key];
    const id = prefix + key;

    if (typeof value === 'object' && value !== null) {
      result[key] = collectFormData(value, id + '.');
    } else {
        const input = document.getElementById(id);
        if (!input) continue;
        let val;
        if (input.type === 'checkbox') {
          val = input.checked;
        } else {
          val = input.value;
          if (val === "true" || val === "false") val = val === "true";
          else if (!isNaN(val) && val.trim() !== "") val = Number(val);
        }
        result[key] = val;
    }
  }
  return result;
}

async function saveConfig() {
  const updated = collectFormData(configData);
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updated)
  });

  if (res.ok) {
    alert('Saved successfully! 💖');
  } else {
    alert('Save failed 😢');
  }
}
