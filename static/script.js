let configData = {};

window.onload = async () => {
  const res = await fetch('/api/config');
  configData = await res.json();
  buildForm(configData, document.getElementById('configForm'));
};

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

function collectFormData(data, prefix = '') {
  const result = {};
  for (const key in data) {
    const value = data[key];
    const id = prefix + key;

    if (typeof value === 'object' && value !== null) {
      result[key] = collectFormData(value, id + '.');
    } else {
      const input = document.getElementById(id);
      const val = input.value;
      if (val === "true" || val === "false") {
        result[key] = val === "true";
      } else if (!isNaN(val) && val.trim() !== "") {
        result[key] = Number(val);
      } else {
        result[key] = val;
      }
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
