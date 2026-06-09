(function() {
let selectedFiles = [];
let markStartTime = 0;

// Version and updates
(async function() {
  try {
    const r = await fetch('/api/version');
    const v = await r.json();
    document.getElementById('version-tag').textContent = 'v' + v.version;
  } catch(e) {}

  try {
    const r = await fetch('/api/check-update');
    const data = await r.json();
    if (data.update_available) {
      const banner = document.getElementById('update-banner');
      document.getElementById('update-text').textContent =
        `v${data.latest} disponible (tenés v${data.current})`;
      document.getElementById('update-link').href = data.url;
      banner.hidden = false;
      document.getElementById('update-dismiss').onclick = () => {
        banner.hidden = true;
      };
    }
  } catch(e) {}
})();

// Load initial config
(async function() {
  try {
    const resp = await fetch('/api/config');
    const cfg = await resp.json();
    document.getElementById('mark-output').value = cfg.output_dir || '';
    if (cfg.scaling_w) {
      const fs = document.getElementById('mark-force');
      const fl = document.getElementById('force-label');
      fs.value = cfg.scaling_w;
      if (fl) fl.textContent = parseFloat(cfg.scaling_w).toFixed(1);
    }
    if (cfg.video_frame_step) {
      const vs = document.getElementById('mark-vstep');
      const vl = document.getElementById('step-label');
      vs.value = cfg.video_frame_step;
      if (vl) vl.textContent = cfg.video_frame_step;
    }
  } catch(e) {}
})();

// Folder picker buttons
function setupFolderPicker(btnId, inputId) {
  const btn = document.getElementById(btnId);
  const input = document.getElementById(inputId);
  if (!btn || !input) return;
  btn.addEventListener('click', () => {
    const picker = document.createElement('input');
    picker.type = 'file';
    picker.webkitdirectory = true;
    picker.directory = true;
    picker.addEventListener('change', () => {
      if (picker.files.length) {
        const path = picker.files[0].webkitRelativePath || picker.files[0].name;
        const dir = path.includes('/') ? path.split('/')[0] : '';
        if (dir) {
          const current = input.value.trim();
          if (current && !current.endsWith('\\') && !current.endsWith('/')) {
            input.value = current.replace(/[^\\\/]+$/, '') + dir;
          } else if (current) {
            input.value = current + dir;
          } else {
            input.value = dir;
          }
        }
      }
    });
    picker.click();
  });
}
setupFolderPicker('btn-pick-output', 'mark-output');
setupFolderPicker('btn-pick-cfg-output', 'cfg-output');
let removeCallbacks = new Map();

// --- TABS ---
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'history') loadHistory();
    if (btn.dataset.tab === 'config') loadConfig();
  });
});

// --- DROP ZONE ---
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  addFiles(Array.from(e.dataTransfer.files));
});
fileInput.addEventListener('change', () => {
  addFiles(Array.from(fileInput.files));
  fileInput.value = '';
});

function addFiles(files) {
  for (const f of files) {
    if (selectedFiles.find(s => s.name === f.name && s.size === f.size)) continue;
    selectedFiles.push(f);
  }
  renderFileList();
}

function renderFileList() {
  const list = document.getElementById('file-list');
  if (!selectedFiles.length) { list.innerHTML = ''; return; }
  list.innerHTML = '';
  selectedFiles.forEach((f, i) => {
    const isVideo = f.type.startsWith('video/') || f.name.match(/\.(mp4|mov|avi|mkv|webm)$/i);
    const size = f.size > 1e6 ? (f.size/1e6).toFixed(1)+' MB' : (f.size/1e3).toFixed(0)+' KB';
    const div = document.createElement('div');
    div.className = 'file-item';

    const thumb = document.createElement('div');
    thumb.className = 'file-thumb';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'name';
    nameSpan.textContent = f.name;

    const sizeSpan = document.createElement('span');
    sizeSpan.className = 'size';
    sizeSpan.textContent = size;

    const btn = document.createElement('button');
    btn.className = 'remove';
    btn.innerHTML = '&#10005;';
    btn.addEventListener('click', () => {
      selectedFiles.splice(i, 1);
      renderFileList();
    });

    div.appendChild(thumb);
    div.appendChild(nameSpan);
    div.appendChild(sizeSpan);
    div.appendChild(btn);
    list.appendChild(div);

    const url = URL.createObjectURL(f);
    if (isVideo) {
      const video = document.createElement('video');
      video.src = url;
      video.preload = 'metadata';
      video.muted = true;
      video.playsInline = true;
      video.addEventListener('loadeddata', () => {
        video.currentTime = 1;
      });
      video.addEventListener('seeked', () => {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const img = document.createElement('img');
        img.src = canvas.toDataURL();
        img.alt = f.name;
        thumb.appendChild(img);
        URL.revokeObjectURL(url);
      });
    } else {
      const img = document.createElement('img');
      img.src = url;
      img.alt = f.name;
      img.onload = () => URL.revokeObjectURL(url);
      thumb.appendChild(img);
    }
  });
}

document.getElementById('btn-clear').addEventListener('click', () => {
  selectedFiles = [];
  renderFileList();
});

// --- MARK ---
document.getElementById('btn-mark').addEventListener('click', async () => {
  if (!selectedFiles.length) { toast('Agregá archivos primero', 'error'); return; }

  const btn = document.getElementById('btn-mark');
  btn.disabled = true;
  btn.textContent = 'Marcando...';

  const form = new FormData();
  for (const f of selectedFiles) form.append('files', f);
  form.append('id_unico', document.getElementById('mark-id').value);
  form.append('vendido_a', document.getElementById('mark-vendido').value);
  form.append('scaling_w', parseFloat(document.getElementById('mark-force').value));
  form.append('video_step', document.getElementById('mark-vstep').value);
  const outputDir = document.getElementById('mark-output').value.trim();
  if (outputDir) form.append('output_dir', outputDir);

  const fill = document.getElementById('progress-fill');
  const container = document.getElementById('progress-container');
  container.hidden = false;
  fill.style.width = '0%';
  document.getElementById('progress-pct').textContent = '0%';
  document.getElementById('progress-eta').textContent = '';
  document.getElementById('progress-file').textContent = '';

  markStartTime = Date.now();

  // Persist scaling_w as new default
  const sw = parseFloat(document.getElementById('mark-force').value);
  fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({scaling_w: sw}),
  }).catch(() => {});

  try {
    const resp = await fetch('/api/mark', { method: 'POST', body: form });
    const data = await resp.json();
    if (data.error) {
      toast(data.error, 'error');
    } else {
      const errs = data.results.filter(r => r.status === 'error');
      if (errs.length) {
        toast(`${errs.length} errores de ${data.results.length}`, 'error');
      } else {
        toast(`Marcados ${data.results.length} archivos (${data.total_time}s)`, 'success');
      }
      if (data.synced > 0) toast(`${data.synced} sincronizados con el monitor`, 'success');
    }
    selectedFiles = [];
    renderFileList();
  } catch(e) {
    toast('Error: ' + e.message, 'error');
  }

  btn.disabled = false;
  btn.textContent = 'Marcar todo';
});

// WebSocket progress - only when on mark tab
let ws = null;
let wsReconnectTimer = null;

function connectWS() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  const activeTab = document.querySelector('.tab.active');
  if (!activeTab || activeTab.dataset.tab !== 'mark') return;

  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/progress';
  ws = new WebSocket(wsUrl);
  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    const fill = document.getElementById('progress-fill');
    const pctSpan = document.getElementById('progress-pct');
    const etaSpan = document.getElementById('progress-eta');
    const fileSpan = document.getElementById('progress-file');
    const container = document.getElementById('progress-container');

    if (msg.type === 'start') {
      container.hidden = false;
      fill.style.width = '0%';
      fill.classList.remove('indeterminate');
      pctSpan.textContent = '0%';
    } else if (msg.type === 'progress') {
      if (msg.status === 'preparing') {
        fileSpan.textContent = 'Preparando: ' + msg.file;
        fill.classList.add('indeterminate');
      } else if (msg.status === 'marking') {
        fileSpan.textContent = 'Marcando: ' + msg.file;
        fill.classList.add('indeterminate');
      } else {
        fill.classList.remove('indeterminate');
        const pct = Math.round(msg.current / msg.total * 100);
        fill.style.width = pct + '%';
        pctSpan.textContent = pct + '%';
        fileSpan.textContent = msg.status === 'ok' ? 'OK: ' + msg.file : 'ERROR: ' + msg.file;
        const elapsed = (Date.now() - markStartTime) / 1000;
        const remaining = msg.current > 0 ? Math.round(elapsed / msg.current * (msg.total - msg.current)) : 0;
        etaSpan.textContent = remaining > 0 ? '~' + formatTime(remaining) : '';
      }
    } else if (msg.type === 'done') {
      fill.classList.remove('indeterminate');
      fill.style.width = '100%';
      pctSpan.textContent = '100%';
      etaSpan.textContent = '';
      fileSpan.textContent = 'Completado';
    }
  };
  ws.onclose = () => {
    ws = null;
    wsReconnectTimer = setTimeout(connectWS, 5000);
  };
}

// Connect WS when on mark tab, disconnect when leaving
function handleTabSwitch(tabName) {
  if (tabName === 'mark') {
    connectWS();
  } else {
    if (ws) { ws.close(); ws = null; }
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  }
}

// Override tab clicks to handle WS
document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    setTimeout(() => handleTabSwitch(t.dataset.tab), 50);
  });
});
// Initial check
setTimeout(() => handleTabSwitch('mark'), 50);

function formatTime(s) {
  if (s < 60) return s + 's';
  return Math.floor(s/60) + 'm ' + Math.round(s%60) + 's';
}

// Force slider
(function() {
  const fs = document.getElementById('mark-force');
  const fl = document.getElementById('force-label');
  if (fs && fl) {
    function updateForce() {
      fl.textContent = parseFloat(fs.value).toFixed(1);
    }
    fs.addEventListener('input', updateForce);
    fs.addEventListener('change', updateForce);
  }
})();

// Video step slider
(function() {
  const vs = document.getElementById('mark-vstep');
  const vl = document.getElementById('step-label');
  if (vs && vl) {
    function updateStep() { vl.textContent = vs.value; }
    vs.addEventListener('input', updateStep);
    vs.addEventListener('change', updateStep);
  }
})();

// --- READ ---
const readDrop = document.getElementById('read-drop-zone');
const readInput = document.getElementById('read-file-input');
readDrop.addEventListener('click', () => readInput.click());
readDrop.addEventListener('dragover', e => { e.preventDefault(); readDrop.classList.add('drag-over'); });
readDrop.addEventListener('dragleave', () => readDrop.classList.remove('drag-over'));
readDrop.addEventListener('drop', e => {
  e.preventDefault();
  readDrop.classList.remove('drag-over');
  if (e.dataTransfer.files.length) doRead(e.dataTransfer.files[0]);
});
readInput.addEventListener('change', () => {
  if (readInput.files.length) { doRead(readInput.files[0]); readInput.value = ''; }
});

async function doRead(file) {
  const resultDiv = document.getElementById('read-result');
  const detailsDiv = document.getElementById('read-details');
  const isVideo = file.type.startsWith('video/') || file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i);
  const thumbUrl = URL.createObjectURL(file);

  // Show thumbnail + pending
  detailsDiv.innerHTML = `<div class="read-header">
    <img class="read-thumb" src="${thumbUrl}" alt="Preview" id="read-thumb-preview">
    <div class="read-file-info">
      <strong>${escapeHtml(file.name)}</strong>
      <br><span class="sub">${(file.size/1e3).toFixed(0)} KB · ${isVideo?'Video':'Imagen'}</span>
    </div>
  </div>
  <p class="loading" style="text-align:center;margin:16px 0">Analizando...</p>`;
  resultDiv.hidden = false;

  const form = new FormData();
  form.append('file', file);

  try {
    const resp = await fetch('/api/read', { method: 'POST', body: form });
    const data = await resp.json();
    if (data.error) {
      const html = `<div class="read-header">
        <img class="read-thumb" src="${thumbUrl}" alt="Preview">
        <div class="read-file-info">
          <strong>${escapeHtml(file.name)}</strong>
          <br><span class="sub">${(file.size/1e3).toFixed(0)} KB</span>
        </div>
      </div>
      <div class="empty-state"><p style="color:var(--red)">${escapeHtml(data.error)}</p><p class="sub">Probá con otra imagen o verificá que tenga marca.</p></div>`;
      detailsDiv.innerHTML = html;
      URL.revokeObjectURL(thumbUrl);
      return;
    }

    let html = `<div class="read-header">
      <img class="read-thumb" src="${thumbUrl}" alt="Preview">
      <div class="read-file-info">
        <strong>${escapeHtml(file.name)}</strong>
        <br><span class="sub">${(file.size/1e3).toFixed(0)} KB</span>
      </div>
    </div>
    <p style="margin-bottom:12px;font-size:.85rem">Fingerprint:</p>
      <div class="fp-box" id="fp-text">${data.fingerprint}<button class="copy-btn" id="copy-fp-btn">Copiar</button></div>
      <h3 style="margin:16px 0 8px;font-size:.9rem">Coincidencias:</h3>`;

    if (!data.matches.length) {
      html += '<div class="empty-state"><p>Sin coincidencias en la DB local.</p><p class="sub">La imagen podría estar marcada en otra computadora.</p></div>';
    } else {
      for (const m of data.matches) {
        let confClass = m.distancia <= 60 ? 'conf-high' : m.distancia <= 80 ? 'conf-mid' : 'conf-low';
        let confLabel = m.distancia <= 60 ? 'IDENTIFICADO' : m.distancia <= 80 ? 'POSIBLE' : 'BAJA CONFIANZA';
        let originLabel = m.origen === 'servidor'
          ? '<span class="origin-tag remote">Servidor</span>'
          : '<span class="origin-tag local">Local</span>';
        html += `<div class="match-item">
          <span class="confidence ${confClass}">${confLabel}</span>
          <strong>${escapeHtml(m.id_unico)}</strong> &mdash; ${escapeHtml(m.vendido_a || 'público')}
          ${originLabel}
          <br><small style="color:var(--text2)">Distancia: ${m.distancia}/256 · ${(m.fecha_marcado||'').slice(0,19)}</small>
        </div>`;
      }
    }
    detailsDiv.innerHTML = html;

    const copyBtn = document.getElementById('copy-fp-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(data.fingerprint).then(() => {
          copyBtn.textContent = 'Copiado!';
          copyBtn.style.color = 'var(--green)';
          setTimeout(() => { copyBtn.textContent = 'Copiar'; copyBtn.style.color = ''; }, 2000);
        });
      });
    }

    setTimeout(() => URL.revokeObjectURL(thumbUrl), 1000);
  } catch(e) {
    detailsDiv.innerHTML = `<div class="read-header">
      <img class="read-thumb" src="${thumbUrl}" alt="Preview">
      <div class="read-file-info">
        <strong>${escapeHtml(file.name)}</strong>
        <br><span class="sub">${(file.size/1e3).toFixed(0)} KB</span>
      </div>
    </div>
    <div class="empty-state"><p style="color:var(--red)">Error de conexión</p><p class="sub">${escapeHtml(e.message)}</p></div>`;
    URL.revokeObjectURL(thumbUrl);
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// --- HISTORY ---
let historyTimer = null;
async function loadHistory() {
  const tbody = document.getElementById('history-body');
  tbody.innerHTML = '<tr><td colspan="5" class="loading">Cargando...</td></tr>';

  const search = document.getElementById('history-search').value.trim();
  const params = new URLSearchParams();
  if (search) {
    if (search.startsWith('wm_')) params.set('id', search);
    else params.set('vendido', search);
  }
  const resp = await fetch('/api/history?' + params);
  const data = await resp.json();
  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No hay registros.</td></tr>';
    return;
  }
  tbody.innerHTML = data.items.map(i =>
    `<tr><td>${escapeHtml(i.id_unico)}</td><td>${i.tipo==='video'?'&#127916;':'&#127748;'}</td><td>${escapeHtml(i.vendido_a||'')}</td><td>${(i.fecha_marcado||'').slice(0,19)}</td><td>${i.sync_status}</td></tr>`
  ).join('');
}
document.getElementById('history-search').addEventListener('input', () => {
  clearTimeout(historyTimer);
  historyTimer = setTimeout(loadHistory, 300);
});
document.getElementById('btn-export-csv').addEventListener('click', () => window.open('/api/export?format=csv'));
document.getElementById('btn-export-json').addEventListener('click', () => window.open('/api/export?format=json'));

// --- CONFIG ---
async function loadConfig() {
  const resp = await fetch('/api/config');
  const cfg = await resp.json();
  document.getElementById('cfg-vstep').value = cfg.video_frame_step;
  document.getElementById('cfg-vstep-val').textContent = cfg.video_frame_step;
  document.getElementById('cfg-server').value = cfg.server_url || '';
  document.getElementById('cfg-apikey').value = cfg.api_key || '';
  document.getElementById('cfg-output').value = cfg.output_dir || '';
  document.getElementById('qr-url').textContent = `http://${cfg.local_ip}:${location.port}`;
  document.getElementById('qr-img').src = `/api/qr?port=${location.port}`;
}
document.getElementById('cfg-vstep').addEventListener('input', function() {
  document.getElementById('cfg-vstep-val').textContent = this.value;
});
document.getElementById('btn-save-config').addEventListener('click', async () => {
  const btn = document.getElementById('btn-save-config');
  btn.disabled = true;
  btn.textContent = 'Guardando...';
  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        video_frame_step: parseInt(document.getElementById('cfg-vstep').value),
        server_url: document.getElementById('cfg-server').value,
        api_key: document.getElementById('cfg-apikey').value,
        output_dir: document.getElementById('cfg-output').value,
      }),
    });
    const data = await resp.json();
    if (data.error) { toast(data.error, 'error'); }
    else { toast('Configuración guardada', 'success'); }
  } catch(e) {
    toast('Error: ' + e.message, 'error');
  }
  btn.disabled = false;
  btn.textContent = 'Guardar';
});

// Force sync button
document.getElementById('btn-sync').addEventListener('click', async () => {
  const btn = document.getElementById('btn-sync');
  const result = document.getElementById('sync-result');
  btn.disabled = true;
  btn.textContent = 'Sincronizando...';
  result.textContent = '';
  try {
    const resp = await fetch('/api/sync', { method: 'POST' });
    const data = await resp.json();
    if (data.error) { result.textContent = data.error; result.style.color = 'var(--red)'; }
    else {
      result.textContent = 'Sincronizados: ' + data.synced;
      result.style.color = 'var(--green)';
      setTimeout(() => { result.textContent = ''; }, 5000);
    }
  } catch(e) {
    result.textContent = 'Error: ' + e.message;
    result.style.color = 'var(--red)';
  }
  btn.disabled = false;
  btn.textContent = 'Sincronizar con servidor';
});

// Shutdown button
document.getElementById('btn-shutdown').addEventListener('click', async () => {
  if (!confirm('Cerrar la aplicacion?')) return;
  try {
    await fetch('/api/shutdown', { method: 'POST' });
  } catch(e) {}
  document.body.innerHTML = '<div style="text-align:center;padding:48px;color:var(--text2)">Aplicacion cerrada. Ya podes cerrar esta ventana.</div>';
});

// --- TOAST ---
function toast(msg, type) {
  const div = document.createElement('div');
  div.className = 'toast ' + (type || '');
  div.textContent = msg;
  document.getElementById('toasts').appendChild(div);
  setTimeout(() => { div.style.opacity = '0'; setTimeout(() => div.remove(), 300); }, 3500);
}

// Keyboard shortcuts - only on mark tab
document.addEventListener('keydown', e => {
  const activeTab = document.querySelector('.tab.active');
  if (!activeTab || activeTab.dataset.tab !== 'mark') return;
  if (e.key === 'Escape') { selectedFiles = []; renderFileList(); }
  if (e.key === 'Enter' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
    document.getElementById('btn-mark').click();
  }
});

})();
