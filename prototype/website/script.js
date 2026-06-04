// ─── Configuration ────────────────────────────────────────────────────
const API_BASE_URL = window.__API_BACKEND_URL || '';

const API = {
  _url(path) {
    return API_BASE_URL + '/api/' + path;
  },
  async getSchema() {
    const res = await fetch(API._url('schema'));
    if (!res.ok) {
      const err = await res.json().catch(function() { return {}; });
      throw new Error(err.detail || 'Schema fetch error');
    }
    return res.json();
  },
  async getHealth() {
    const res = await fetch(API._url('health'));
    return res.json();
  },
  async submitQuery(query) {
    const res = await fetch(API._url('query'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function() { return {}; });
      throw new Error(err.detail || 'Query error (' + res.status + ')');
    }
    return res.json();
  },
  async uploadDatabase(file, onProgress) {
    return new Promise(function(resolve, reject) {
      var formData = new FormData();
      formData.append('file', file);

      var xhr = new XMLHttpRequest();
      xhr.open('POST', API._url('upload-database'));

      xhr.upload.onprogress = function(e) {
        if (onProgress && e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = function() {
        var text = xhr.responseText || '';
        try {
          var result = JSON.parse(text);
          if (xhr.status >= 400) {
            reject(new Error(result.error || ('HTTP ' + xhr.status)));
            return;
          }
          resolve(result);
        } catch (e) {
          reject(new Error('Invalid server response (HTTP ' + xhr.status + ')'));
        }
      };

      xhr.onerror = function() {
        reject(new Error('Upload failed. Check backend connection.'));
      };

      xhr.send(formData);
    });
  },
  async connectDB(params) {
    const res = await fetch(API._url('connect-db'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.json().catch(function() { return {}; });
      throw new Error(err.error || err.detail || ('HTTP ' + res.status));
    }
    return res.json();
  }
};

const QUICK_QUERIES = [
  "Найди всех сотрудников отдела разработки",
  "Сколько задач в каждом проекте",
  "Средняя зарплата по отделам",
  "Покажи сотрудников с зарплатой выше 100000",
  "Топ-5 проектов по бюджету",
];

const PIPELINE_ICONS = {
  'Preprocessing': '🔍',
  'Schema': '📚',
  'Prompt': '📝',
  'LLM Generation': '🤖',
  'Validation': '✅',
  'Execution': '🚀',
};

// ─── Init ────────────────────────────────────────────────────────────

// ─── Upload Tab Switching ─────────────────────────────────────────

function switchUploadTab(tab) {
  var tabFile = document.getElementById('tabFile');
  var tabServer = document.getElementById('tabServer');
  var panelFile = document.getElementById('panelFile');
  var panelServer = document.getElementById('panelServer');
  var dropZone = document.getElementById('dbDropZone');
  var uploadStatus = document.getElementById('dbUploadStatus');
  var errorEl = document.getElementById('dbError');

  if (tab === 'file') {
    tabFile.classList.add('active');
    tabServer.classList.remove('active');
    panelFile.style.display = '';
    panelServer.style.display = 'none';
    if (dropZone) dropZone.style.display = '';
    if (uploadStatus) uploadStatus.style.display = 'none';
    if (errorEl) errorEl.style.display = 'none';
  } else {
    tabServer.classList.add('active');
    tabFile.classList.remove('active');
    panelServer.style.display = '';
    panelFile.style.display = 'none';
    if (errorEl) errorEl.style.display = 'none';
    // Авто-порт при смене диалекта
    var dialect = document.getElementById('connDialect');
    if (dialect) {
      updatePortForDialect();
    }
  }
}

function updatePortForDialect() {
  var dialect = document.getElementById('connDialect').value;
  var portEl = document.getElementById('connPort');
  if (dialect === 'postgresql' && portEl.value === '3306') portEl.value = '5432';
  if (dialect === 'mysql' && portEl.value === '5432') portEl.value = '3306';
  if (dialect === 'sqlite') portEl.value = '';
}

async function connectToServer() {
  var btnConnect = document.getElementById('btnConnect');
  var errorEl = document.getElementById('dbError');
  var dialect = document.getElementById('connDialect').value;
  var host = document.getElementById('connHost').value.trim();
  var port = parseInt(document.getElementById('connPort').value) || (dialect === 'mysql' ? 3306 : 5432);
  var database = document.getElementById('connDatabase').value.trim();
  var username = document.getElementById('connUsername').value.trim();
  var password = document.getElementById('connPassword').value;

  if (!database && dialect !== 'sqlite') {
    showUploadError('Введите название базы данных');
    return;
  }

  btnConnect.disabled = true;
  btnConnect.innerHTML = '<span class="step-loader" style="width:14px;height:14px;border-width:2px;margin-right:6px"></span> Подключение...';
  if (errorEl) errorEl.style.display = 'none';

  try {
    var params = {
      dialect: dialect,
      host: host,
      port: port,
      database: database,
      username: username,
      password: password,
    };

    var result = await API.connectDB(params);
    if (result.success) {
      // Скрываем экран загрузки, показываем интерфейс
      document.getElementById('uploadScreen').style.display = 'none';
      document.getElementById('mainContent').style.display = '';

      var statusText = document.getElementById('statusText');
      if (statusText) statusText.textContent = 'Connected: ' + result.name;

      var dbHeaderName = document.getElementById('dbHeaderName');
      if (dbHeaderName) dbHeaderName.textContent = result.name;

      clearHistory();
      document.getElementById('resultsSection').style.display = 'none';
      document.getElementById('sqlCard').style.display = 'none';
      document.getElementById('tableCard').style.display = 'none';
      document.getElementById('errorCard').style.display = 'none';

      loadSchema();
    } else {
      showUploadError(result.error || 'Ошибка подключения');
    }
  } catch (e) {
    showUploadError(e.message);
  } finally {
    btnConnect.disabled = false;
    btnConnect.innerHTML = '<span class="btn-demo-icon">🔗</span><span>Подключиться</span>';
    if (uploadMode === 'switch') {
      uploadMode = 'initial';
    }
  }
}

// ─── Init ────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', function() {
  // Привязываем смену диалекта к авто-порту
  var dialectSel = document.getElementById('connDialect');
  if (dialectSel) {
    dialectSel.addEventListener('change', updatePortForDialect);
  }
  checkHealthAndInit();
  renderQuickTags();
  initUpload();
  var input = document.getElementById('queryInput');
  if (input) {
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') submitQuery();
    });
  }
});

// ─── Upload Screen ───────────────────────────────────────────────────

var uploadMode = 'initial'; // 'initial' | 'switch'

function initUpload() {
  var dropZone = document.getElementById('dbDropZone');
  var fileInput = document.getElementById('dbFileInput');
  if (!dropZone) return;

  dropZone.addEventListener('click', function() {
    fileInput.click();
  });

  fileInput.addEventListener('change', function() {
    if (fileInput.files.length > 0) {
      startUpload(fileInput.files[0]);
      fileInput.value = '';
    }
  });

  dropZone.addEventListener('dragenter', function(e) {
    e.preventDefault();
    dropZone.classList.add('db-dragover');
  });

  dropZone.addEventListener('dragover', function(e) {
    e.preventDefault();
    dropZone.classList.add('db-dragover');
  });

  dropZone.addEventListener('dragleave', function(e) {
    dropZone.classList.remove('db-dragover');
  });

  dropZone.addEventListener('drop', function(e) {
    e.preventDefault();
    dropZone.classList.remove('db-dragover');
    var files = e.dataTransfer.files;
    if (files.length > 0) {
      var file = files[0];
      if (!file.name.toLowerCase().endsWith('.db')) {
        showUploadError('Only .db files accepted');
        return;
      }
      startUpload(file);
    }
  });
}

async function startUpload(file) {
  var dropZone = document.getElementById('dbDropZone');
  var uploadStatus = document.getElementById('dbUploadStatus');
  var progressFill = document.getElementById('dbUploadProgress');
  var progressText = document.getElementById('dbUploadText');
  var errorEl = document.getElementById('dbError');

  errorEl.style.display = 'none';
  dropZone.style.display = 'none';
  uploadStatus.style.display = 'block';
  progressFill.style.width = '0%';
  progressText.textContent = 'Uploading ' + file.name + '...';

  try {
    var result = await API.uploadDatabase(file, function(pct) {
      progressFill.style.width = pct + '%';
      progressText.textContent = 'Uploading... ' + pct + '%';
    });

    if (result.success) {
      progressFill.style.width = '100%';
      progressText.textContent = '✅ ' + result.name + ' loaded!';

      setTimeout(function() {
        var isSwitch = uploadMode === 'switch';
        onDatabaseLoaded(result.name, isSwitch);
        if (isSwitch) {
          // Reset upload screen buttons
          var btnCancel = document.getElementById('btnCancelSwitch');
          if (btnCancel) btnCancel.style.display = 'none';
          uploadMode = 'initial';
        }
      }, 600);
    } else {
      showUploadError(result.error || 'Upload error');
    }
  } catch (e) {
    showUploadError(e.message);
  }
}

function showUploadError(msg) {
  var dropZone = document.getElementById('dbDropZone');
  var uploadStatus = document.getElementById('dbUploadStatus');
  var errorEl = document.getElementById('dbError');

  dropZone.style.display = '';
  uploadStatus.style.display = 'none';
  errorEl.style.display = 'block';
  errorEl.textContent = '❌ ' + msg;
}

function onDatabaseLoaded(name, clearHistoryFlag) {
  document.getElementById('uploadScreen').style.display = 'none';
  document.getElementById('mainContent').style.display = '';

  var statusText = document.getElementById('statusText');
  if (statusText) statusText.textContent = 'DB: ' + name;

  var dbHeaderName = document.getElementById('dbHeaderName');
  if (dbHeaderName) dbHeaderName.textContent = name;

  var schemaDesc = document.getElementById('schemaDesc');
  if (schemaDesc) schemaDesc.textContent = 'Auto-detected from: ' + name;

  if (clearHistoryFlag) {
    clearHistory();
  }

  // Hide results on DB switch
  document.getElementById('resultsSection').style.display = 'none';
  document.getElementById('sqlCard').style.display = 'none';
  document.getElementById('tableCard').style.display = 'none';
  document.getElementById('errorCard').style.display = 'none';

  loadSchema();
}

// ─── Query Interface ─────────────────────────────────────────────────

function renderQuickTags() {
  var container = document.getElementById('quickTags');
  if (!container) return;
  container.innerHTML = QUICK_QUERIES.map(function(q) {
    return '<span class="tag" onclick="setQuery(this)">' + q + '</span>';
  }).join('');
}

function setQuery(el) {
  document.getElementById('queryInput').value = el.textContent;
  submitQuery();
}

async function checkHealthAndInit() {
  var dot = document.getElementById('statusDot');
  var text = document.getElementById('statusText');
  try {
    var controller = new AbortController();
    var timeout = setTimeout(function() { controller.abort(); }, 5000);
    var res = await fetch(API_BASE_URL + '/api/health', { signal: controller.signal });
    clearTimeout(timeout);
    var status = await res.json();
    if (status.status === 'ok') {
      if (dot) dot.className = 'status-dot online';
      if (status.api_key_configured) {
        if (text) text.textContent = status.db_loaded
          ? 'Neural (Gemini) | DB: ' + (status.db_path || '').split('/').pop()
          : 'Neural (Gemini) | No DB';
      } else {
        if (text) text.textContent = status.db_loaded
          ? 'API key missing!' : 'Server OK';
      }
      if (status.db_loaded) {
        onDatabaseLoaded((status.db_path || 'database.db').split('/').pop());
      }
    }
  } catch (e) {
    if (dot) dot.className = 'status-dot offline';
    if (text) text.textContent = 'Server offline';
    showUploadError('Server not reachable. Start: python run.py');
  }
}

async function loadSchema() {
  try {
    var schema = await API.getSchema();
    var grid = document.getElementById('schemaGrid');
    grid.innerHTML = '';

    if (!schema.tables || Object.keys(schema.tables).length === 0) {
      grid.innerHTML = '<div class="schema-loading">No tables found in database</div>';
      return;
    }

    Object.entries(schema.tables).forEach(function(entry) {
      var name = entry[0];
      var info = entry[1];
      var card = document.createElement('div');
      card.className = 'schema-table';

      var cols = info.columns || [];
      var lis = '';
      for (var i = 0; i < cols.length; i++) {
        lis += '<li>' + cols[i] + '</li>';
      }

      card.innerHTML =
        '<h3>' + name + '</h3>' +
        '<div class="table-desc">' + (info.row_count || 0) + ' records</div>' +
        '<ul>' + lis + '</ul>';
      grid.appendChild(card);
    });
  } catch (e) {
    var grid = document.getElementById('schemaGrid');
    if (grid) grid.innerHTML = '<div class="schema-loading" style="color:var(--red)">Error loading schema: ' + e.message + '</div>';
  }
}

// ─── Query Submission ────────────────────────────────────────────────

async function submitQuery() {
  var input = document.getElementById('queryInput');
  var query = input.value.trim();
  if (!query) return;

  var btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="step-loader" style="width:18px;height:18px;border-width:2px"></span> Processing...';

  document.getElementById('resultsSection').style.display = 'none';
  document.getElementById('errorCard').style.display = 'none';

  try {
    var result = await API.submitQuery(query);
    renderResults(result);
  } catch (e) {
    showError(e.message || 'Connection error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">⚡</span> Run';
  }
}

function renderResults(result) {
  if (result.error) {
    showError(result.error);
    return;
  }

  document.getElementById('resultsSection').style.display = 'flex';

  // Render pipeline steps
  var pipeline = document.getElementById('pipeline');
  var html = '';

  for (var s = 0; s < result.steps.length; s++) {
    var step = result.steps[s];
    var icon = PIPELINE_ICONS[step.name] || '⚙️';
    var statusClass = step.status === 'success' ? 'success' : step.status;
    var statusColor = step.status === 'success' ? 'var(--green)' : 'var(--red)';
    var statusText = step.status === 'success' ? step.detail || 'OK' : step.detail || 'Error';
    var timingMs = step.ms || 0;

    html += '<div class="pipeline-step ' + statusClass + '">';
    html += '<div class="step-icon">' + icon + '</div>';
    html += '<div class="step-content">';
    html += '<div class="step-name">' + step.name + ' <span style="font-size:11px;color:var(--text2);font-weight:400">(' + timingMs + 'ms)</span></div>';
    html += '<div class="step-status"><span style="color:' + statusColor + '">' + statusText + '</span></div>';

    // Extra info
    if (step.tables) {
      html += '<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">';
      for (var t = 0; t < step.tables.length; t++) {
        html += '<span style="padding:3px 10px;background:var(--surface2);border-radius:6px;font-size:12px;border:1px solid var(--border)">' + step.tables[t] + '</span>';
      }
      html += '</div>';
    }

    html += '</div></div>';
  }

  // Total timing
  if (result.timing_ms) {
    html += '<div style="text-align:right;font-size:12px;color:var(--text2);margin-top:4px">Total: ' + result.timing_ms + 'ms</div>';
  }

  pipeline.innerHTML = html;

  // Show SQL with syntax highlighting
  var sql = result.formatted_sql || result.sql;
  if (sql) {
    document.getElementById('sqlCard').style.display = '';
    var codeEl = document.getElementById('sqlCode');
    codeEl.textContent = sql;
    codeEl.className = 'language-sql';
    if (typeof hljs !== 'undefined') hljs.highlightElement(codeEl);
  }

  // Add to history
  addToHistory(result.query || document.getElementById('queryInput').value.trim(), result);

  // Show results table
  if (result.rows && result.rows.length > 0) {
    var tc = document.getElementById('tableCard');
    tc.style.display = '';
    var badge = document.getElementById('rowBadge');
    badge.innerHTML = result.rows.length + ' rows' +
      ' <button class="btn-export" onclick="exportCSV()" title="Export CSV">📥 CSV</button>' +
      ' <button class="btn-export" onclick="exportJSON()" title="Export JSON">📦 JSON</button>';

    var cols = result.columns || Object.keys(result.rows[0]);
    var th = '<tr>';
    for (var i = 0; i < cols.length; i++) th += '<th>' + cols[i] + '</th>';
    th += '</tr>';
    document.getElementById('tableHead').innerHTML = th;

    var tb = '';
    for (var r = 0; r < result.rows.length; r++) {
      tb += '<tr>';
      for (var c = 0; c < cols.length; c++) {
        var val = result.rows[r][cols[c]];
        tb += '<td>' + (val !== null && val !== undefined ? val : '') + '</td>';
      }
      tb += '</tr>';
    }
    document.getElementById('tableBody').innerHTML = tb;
    tc.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else if (result.success) {
    document.getElementById('tableCard').style.display = '';
    document.getElementById('rowBadge').innerHTML = '0 rows';
    document.getElementById('tableHead').innerHTML = '';
    document.getElementById('tableBody').innerHTML = '<tr><td colspan="100" style="text-align:center;padding:40px;color:var(--text2)">No data returned</td></tr>';
  }
}

function showError(msg) {
  var card = document.getElementById('errorCard');
  card.style.display = '';
  document.getElementById('errorText').textContent = msg;
  card.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

var queryHistory = [];
var MAX_HISTORY = 50;

function addToHistory(query, result) {
  queryHistory.unshift({
    query: query,
    sql: result.sql || result.formatted_sql || '',
    rows: result.rows ? result.rows.length : 0,
    success: result.success,
    time: new Date().toLocaleTimeString(),
  });
  if (queryHistory.length > MAX_HISTORY) queryHistory.pop();
  renderHistory();
}

function renderHistory() {
  var panel = document.getElementById('historyPanel');
  if (!panel) return;
  if (queryHistory.length === 0) {
    panel.innerHTML = '<div class="history-empty">No queries yet</div>';
    return;
  }
  panel.innerHTML = queryHistory.map(function(h, i) {
    var cls = h.success ? 'history-ok' : 'history-err';
    return '<div class="history-item ' + cls + '" onclick="replayQuery(' + i + ')" title="' + (h.sql || '') + '">' +
      '<div class="history-query">' + h.query + '</div>' +
      '<div class="history-meta">' +
      '<span>' + (h.success ? '✓ ' + h.rows + ' rows' : '✗ error') + '</span>' +
      '<span>' + h.time + '</span>' +
      '</div></div>';
  }).join('');
}

function replayQuery(index) {
  var item = queryHistory[index];
  if (!item) return;
  document.getElementById('queryInput').value = item.query;
  submitQuery();
}

function clearHistory() {
  queryHistory = [];
  renderHistory();
}

function exportCSV() {
  var table = document.getElementById('resultTable');
  if (!table || !table.rows.length) return;
  var csv = [];
  for (var r = 0; r < table.rows.length; r++) {
    var row = [];
    var cells = r === 0 ? table.rows[r].querySelectorAll('th') : table.rows[r].querySelectorAll('td');
    for (var c = 0; c < cells.length; c++) {
      var val = cells[c].textContent.replace(/"/g, '""');
      row.push('"' + val + '"');
    }
    csv.push(row.join(','));
  }
  var blob = new Blob(['\uFEFF' + csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'nl2sql_export.csv';
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportJSON() {
  var table = document.getElementById('resultTable');
  if (!table || !table.rows.length) return;
  var headers = [];
  var data = [];
  var headerCells = table.rows[0].querySelectorAll('th');
  for (var c = 0; c < headerCells.length; c++) {
    headers.push(headerCells[c].textContent);
  }
  for (var r = 1; r < table.rows.length; r++) {
    var row = {};
    var cells = table.rows[r].querySelectorAll('td');
    for (var c = 0; c < cells.length; c++) {
      row[headers[c]] = cells[c].textContent;
    }
    data.push(row);
  }
  var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'nl2sql_export.json';
  link.click();
  URL.revokeObjectURL(link.href);
}

function copySQL() {
  var sql = document.getElementById('sqlCode').textContent;
  try {
    navigator.clipboard.writeText(sql);
    var btn = document.querySelector('.btn-copy');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() {
      btn.textContent = '📋';
      btn.classList.remove('copied');
    }, 2000);
  } catch (e) {
    // Fallback
    var ta = document.createElement('textarea');
    ta.value = sql;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
}

// ─── Database Switching ──────────────────────────────────────────────

function switchDatabase() {
  uploadMode = 'switch';

  // Show cancel button, reset upload state
  var btnCancel = document.getElementById('btnCancelSwitch');
  if (btnCancel) btnCancel.style.display = '';

  // Reset upload state
  document.getElementById('dbDropZone').style.display = '';
  document.getElementById('dbUploadStatus').style.display = 'none';
  document.getElementById('dbError').style.display = 'none';

  // Показать экран загрузки
  document.getElementById('mainContent').style.display = 'none';
  document.getElementById('uploadScreen').style.display = '';
}

function cancelSwitchDB() {
  uploadMode = 'initial';

  // Hide upload screen, show interface
  document.getElementById('uploadScreen').style.display = 'none';
  document.getElementById('mainContent').style.display = '';

  // Reset buttons
  var btnCancel = document.getElementById('btnCancelSwitch');
  if (btnCancel) btnCancel.style.display = 'none';
}
