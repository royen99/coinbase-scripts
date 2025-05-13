let configData = {};
let coinTabNavRef = null;
let coinTabContentRef = null;

const sensitiveFields = ['privatekey', 'bot_token', 'chat_id', 'password', 'api_key', 'secret'];

window.onload = async () => {
    const res = await fetch('/api/config');
    configData = await res.json();
    buildMainTabs(configData, document.getElementById('configForm'));
};

function showToast(message, type = 'success') {
    const toastId = `toast-${Date.now()}`;
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0 show`;
    toast.role = 'alert';
    toast.ariaLive = 'assertive';
    toast.ariaAtomic = 'true';
    toast.id = toastId;
  
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    `;
  
    document.getElementById('toast-container').appendChild(toast);
  
    setTimeout(() => {
      toast.classList.remove('show');
      toast.classList.add('hide');
      toast.addEventListener('transitionend', () => toast.remove());
    }, 4000);
  }
  
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
  
    // Temporarily remove coins so they're not included in the General tab
    const coins = data.coins;
    delete data.coins;

    buildForm(data, generalPane);

    // Restore coins
    data.coins = coins;
  
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

function buildForm(data, parent, prefix = '') {
  
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
        const lowerKey = key.toLowerCase();
        const isSensitive = sensitiveFields.some(field => lowerKey.includes(field));
        
        if (typeof value === 'string' && value.includes('\n')) {
          // 🔒 Multiline sensitive field
          input = document.createElement('textarea');
          input.className = 'form-control';
          input.rows = value.split('\n').length || 4;
          input.value = isSensitive ? '••••••••••••••••••••' : value;
          input.id = id;
          input.readOnly = isSensitive;
        
          group.appendChild(label);
          group.appendChild(input);
        
          if (isSensitive) {
            const toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.className = 'btn btn-sm btn-outline-light mt-1';
            toggleBtn.innerText = '👁 Show';
            toggleBtn.onclick = () => {
              if (input.value.startsWith('••')) {
                input.value = value;
                toggleBtn.innerText = '🙈 Hide';
              } else {
                input.value = '••••••••••••••••••••';
                toggleBtn.innerText = '👁 Show';
              }
            };
            group.appendChild(toggleBtn);
          }
        
        } else {
          input = document.createElement('input');
          input.className = 'form-control';
          input.value = value;
          input.id = id;
        
          if (isSensitive) {
            input.type = 'password';
        
            const toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.className = 'btn btn-sm btn-outline-light ms-2';
            toggleBtn.innerText = '👁 Show';
            toggleBtn.onclick = () => {
              input.type = input.type === 'password' ? 'text' : 'password';
              toggleBtn.innerText = input.type === 'password' ? '👁 Show' : '🙈 Hide';
            };
        
            const inputGroup = document.createElement('div');
            inputGroup.className = 'input-group';
        
            const wrapper = document.createElement('div');
            wrapper.className = 'form-control-wrapper flex-grow-1';
            wrapper.appendChild(input);
        
            inputGroup.appendChild(wrapper);
            inputGroup.appendChild(toggleBtn);
        
            group.appendChild(label);
            group.appendChild(inputGroup);
          } else {
            group.appendChild(label);
            group.appendChild(input);
          }
        }
        
      }
  
      parent.appendChild(group);
    }
  }

  function createCoinTabs(coins, parent) {
    const nav = document.createElement('ul');
    nav.className = 'nav nav-tabs mb-3';
    coinTabNavRef = nav; // 👈 save reference
  
    const tabContent = document.createElement('div');
    tabContent.className = 'tab-content';
    coinTabContentRef = tabContent; // 👈 save reference
  
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
 
      // 🗑️ Add delete button to each tab
      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-sm btn-danger mt-3';
      delBtn.innerText = `🗑️ Delete ${coin}`;
      delBtn.onclick = () => deleteCoin(coin);
      tabPane.appendChild(delBtn);

      first = false;
    }
  
    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-sm btn-outline-light mb-3';
    addBtn.innerHTML = '➕ Add New Coin';
    addBtn.onclick = () => addNewCoin();
    parent.appendChild(nav);
    parent.appendChild(addBtn);
    parent.appendChild(tabContent);
  }
  
  function collectFormDataFromDOM() {
    const result = {};
    const inputs = document.querySelectorAll('#configForm input, #configForm textarea');
  
    inputs.forEach(input => {
      const path = input.id.split('.');
      let current = result;
  
      for (let i = 0; i < path.length - 1; i++) {
        const part = path[i];
        if (!current[part]) current[part] = {};
        current = current[part];
      }
  
      const key = path[path.length - 1];
      if (input.type === 'checkbox') {
        current[key] = input.checked;
      } else {
        let val = input.value;
        if (val === "true" || val === "false") {
          val = val === "true";
        } else if (!isNaN(val) && val.trim() !== "") {
          val = Number(val);
        }
        current[key] = val;
      }
    });
  
    return result;
  }
  
  async function saveConfig() {
    console.log("🚨 saveConfig() called");
    const updated = collectFormDataFromDOM(); // 🔥 use the new DOM-only method
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updated)
    });
  
    if (res.ok) {
        showToast("💾 Saved successfully!", 'success');
      } else {
        showToast("❌ Save failed", 'danger');
      }
  }

  async function deleteCoin(coinName) {
    if (!confirm(`Are you sure you want to delete ${coinName}?`)) return;
  
    delete configData.coins[coinName];
  
    const formContainer = document.getElementById('configForm');
    formContainer.innerHTML = '';
    buildMainTabs(configData, formContainer);
  
    await saveConfig();
  
    showToast(`🗑️ ${coinName} deleted`, 'danger');
  }
  
  async function addNewCoin() {
    const coinName = prompt("Enter new coin name (e.g., DOGE):");
    if (!coinName || coinName.trim() === "") return;
  
    if (configData.coins[coinName]) {
        showToast("❌ Coin already exists!", 'danger');
      return;
    }
  
    configData.coins[coinName] = {
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
        buy: 0.01,
        sell: 0.0001
      },
      precision: {
        price: 2,
        amount: 6
      }
    };
  
    const formContainer = document.getElementById('configForm');
    formContainer.innerHTML = '';
    buildMainTabs(configData, formContainer);
  
    setTimeout(() => {
      document.querySelector('a[href="#tab-coins"]')?.click();
      document.querySelector(`a[href="#tab-${coinName}"]`)?.click();
    }, 100);
  
    console.log("🧠 calling saveConfig() to persist new coin");
    await saveConfig();
  }
