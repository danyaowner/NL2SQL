const API = {
  async getSchema() {
    const res = await fetch("/api/schema");
    return res.json();
  },
  async health() {
    const res = await fetch("/api/health");
    return res.json();
  },
  async submitQuery(query) {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    return res.json();
  }
};

const QUICK_QUERIES = [
  "Найди всех сотрудников отдела разработки",
  "Сколько задач в каждом проекте",
  "Средняя зарплата по отделам",
  "Покажи сотрудников с зарплатой выше 100000",
  "Find all employees in sales department",
];

window.addEventListener("DOMContentLoaded", async () => {
  renderQuickTags();
  await checkHealth();
  await loadSchema();
  const input = document.getElementById("queryInput");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitQuery();
  });
});

function renderQuickTags() {
  const container = document.getElementById("quickTags");
  container.innerHTML = QUICK_QUERIES.map(function(q) {
    return "<span class=\"tag\" onclick=\"setQuery(this)\">" + q + "</span>";
  }).join("");
}

function setQuery(el) {
  document.getElementById("queryInput").value = el.textContent;
  submitQuery();
}

async function checkHealth() {
  try {
    const status = await API.health();
    const dot = document.getElementById("statusDot");
    const text = document.getElementById("statusText");
    if (status.status === "ok") {
      dot.className = "status-dot online";
      text.textContent = "Сервер подключен";
    }
  } catch (e) {
    document.getElementById("statusDot").className = "status-dot offline";
    document.getElementById("statusText").textContent = "Сервер не доступен";
  }
}

async function loadSchema() {
  try {
    const schema = await API.getSchema();
    const grid = document.getElementById("schemaGrid");
    grid.innerHTML = "";
    Object.entries(schema).forEach(function(entry) {
      var name = entry[0];
      var info = entry[1];
      var card = document.createElement("div");
      card.className = "schema-table";
      var colEntries = Object.entries(info.columns).slice(0, 8);
      var lis = "";
      for (var i = 0; i < colEntries.length; i++) {
        lis += "<li>" + colEntries[i][0] + ": " + colEntries[i][1] + "</li>";
      }
      card.innerHTML = "<h3>" + name + "</h3><div class=\"table-desc\">" + info.description + "</div><ul>" + lis + "</ul>";
      grid.appendChild(card);
    });
  } catch (e) {
    document.getElementById("schemaGrid").innerHTML =
      "<div class=\"schema-loading\" style=\"color:var(--red)\">Error loading schema</div>";
  }
}

async function submitQuery() {
  var input = document.getElementById("queryInput");
  var query = input.value.trim();
  if (!query) return;
  var btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.innerHTML = "<span class=\"step-loader\" style=\"width:18px;height:18px;border-width:2px\"></span> Выполнение...";
  document.getElementById("resultsSection").style.display = "none";
  document.getElementById("errorCard").style.display = "none";
  try {
    var result = await API.submitQuery(query);
    renderResults(result);
  } catch (e) {
    showError("Connection error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "<span class=\"btn-icon\">⚡</span> Выполнить";
  }
}

function renderResults(result) {
  if (result.error) {
    showError(result.error);
    return;
  }
  document.getElementById("resultsSection").style.display = "flex";
  var pipeline = document.getElementById("pipeline");
  var html = "";
  for (var s = 0; s < result.steps.length; s++) {
    var step = result.steps[s];
    var st = "";
    var dh = "";
    if (step.status === "success") st = "Done";
    else if (step.status === "warning") st = "Warning: " + (step.message || "");
    else if (step.status === "error") st = "Error: " + (step.error || "");
    if (step.details) {
      var ents = Object.entries(step.details);
      dh = "<dl class=\"step-details\">";
      for (var i = 0; i < ents.length; i++) dh += "<dt>" + ents[i][0] + "</dt><dd>" + ents[i][1] + "</dd>";
      dh += "</dl>";
    }
    if (step.tables) {
      dh += "<div style=\"margin-top:8px;display:flex;gap:8px;flex-wrap:wrap\">";
      for (var i = 0; i < step.tables.length; i++) {
        dh += "<span style=\"padding:4px 10px;background:var(--surface2);border-radius:6px;font-size:12px;border:1px solid var(--border)\">" + step.tables[i].name + "</span>";
      }
      dh += "</div>";
    }
    if (step.sql) {
      dh = "<pre style=\"margin-top:8px;background:#0d1117;padding:8px 12px;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:13px;color:#7ec699;overflow-x:auto\">" + step.sql + "</pre>";
    }
    if (step.valid !== undefined) {
      st = step.valid ? "Valid and safe" : "Warning: " + (step.message || "Problem");
    }
    if (step.row_count !== undefined) {
      st = "Got " + step.row_count + " rows";
    }
    if (step.error) st = "Error: " + step.error;
    var sc = step.status === "success" ? "var(--green)" : step.status === "warning" ? "var(--orange)" : step.status === "error" ? "var(--red)" : "var(--text2)";
    html += "<div class=\"pipeline-step " + step.status + "\"><div class=\"step-icon\">" + step.icon + "</div><div class=\"step-content\"><div class=\"step-name\">" + step.name + "</div><div class=\"step-status\"><span class=\"step-status-text\" style=\"color:" + sc + "\">" + st + "</span></div>" + dh + "</div></div>";
  }
  pipeline.innerHTML = html;
  if (result.sql) {
    document.getElementById("sqlCard").style.display = "";
    document.getElementById("sqlCode").textContent = result.sql;
  }
  if (result.rows && result.rows.length > 0) {
    var tc = document.getElementById("tableCard");
    tc.style.display = "";
    document.getElementById("rowBadge").textContent = result.rows.length + " rows";
    var cols = Object.keys(result.rows[0]);
    var th = "<tr>";
    for (var i = 0; i < cols.length; i++) th += "<th>" + cols[i] + "</th>";
    th += "</tr>";
    document.getElementById("tableHead").innerHTML = th;
    var tb = "";
    for (var r = 0; r < result.rows.length; r++) {
      tb += "<tr>";
      for (var c = 0; c < cols.length; c++) tb += "<td>" + (result.rows[r][cols[c]] || "") + "</td>";
      tb += "</tr>";
    }
    document.getElementById("tableBody").innerHTML = tb;
    tc.scrollIntoView({ behavior: "smooth", block: "start" });
  } else if (result.success) {
    document.getElementById("tableCard").style.display = "";
    document.getElementById("rowBadge").textContent = "0 rows";
    document.getElementById("tableHead").innerHTML = "";
    document.getElementById("tableBody").innerHTML = "<tr><td colspan=\"100\" style=\"text-align:center;padding:40px;color:var(--text2)\">No data found</td></tr>";
  }
}

function showError(msg) {
  var card = document.getElementById("errorCard");
  card.style.display = "";
  document.getElementById("errorText").textContent = msg;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function copySQL() {
  var sql = document.getElementById("sqlCode").textContent;
  try {
    await navigator.clipboard.writeText(sql);
    var btn = document.querySelector(".btn-copy");
    btn.textContent = "Copied!";
    btn.classList.add("copied");
    setTimeout(function() {
      btn.textContent = "Copy";
      btn.classList.remove("copied");
    }, 2000);
  } catch (e) {
    alert("Copy failed");
  }
}
