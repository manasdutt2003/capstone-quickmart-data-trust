/* ==========================================================================
   QuickMart Analytics Dashboard - application logic
   Loads every panel from the FastAPI JSON API (/api/...), wires filters,
   tables (sortable + searchable + CSV download), heatmap, questions
   explorer, capstone answers, theme and count-up KPIs.
   ========================================================================== */
(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };
  var F = window.QMFmt;

  var state = {
    meta: null,
    filters: { month_from: "", month_to: "", city: "all", category: "all" },
    questions: [],
    sqlList: [],
    qShown: 25,
    tableData: {}
  };

  /* ------------------------------ utilities ------------------------------ */

  function fetchJSON(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) { throw new Error(url + " -> HTTP " + r.status); }
      return r.json();
    });
  }

  function setText(el, text) { if (el) { el.textContent = text; } }

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fail(container, err) {
    var host = typeof container === "string" ? $(container) : container;
    if (host) { host.innerHTML = "<p class=\"muted\">Could not load this panel (" + esc(err.message || err) + "). Check <code>/api/health</code>.</p>"; }
  }

  function qs(params) {
    var parts = [];
    for (var k in params) {
      if (Object.prototype.hasOwnProperty.call(params, k) && params[k] !== "" && params[k] !== null && params[k] !== undefined) {
        parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(params[k]));
      }
    }
    return parts.length ? "?" + parts.join("&") : "";
  }

  function countUp(el, target, fmt) {
    if (!el) { return; }
    if (target === null || target === undefined || isNaN(target)) { el.textContent = "n/a"; return; }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmt(target); return; }
    var duration = 850, start = null, from = 0;
    function step(ts) {
      if (!start) { start = ts; }
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(from + (target - from) * eased);
      if (p < 1) { window.requestAnimationFrame(step); }
    }
    window.requestAnimationFrame(step);
  }

  function kpiCard(label, value, fmt, sub, subTitle) {
    var div = document.createElement("div");
    div.className = "kpi";
    var labelEl = document.createElement("p");
    labelEl.className = "kpi-label";
    labelEl.textContent = label;
    var valueEl = document.createElement("p");
    valueEl.className = "kpi-value";
    valueEl.textContent = "...";
    var subEl = document.createElement("p");
    subEl.className = "kpi-sub";
    subEl.innerHTML = sub || "";
    if (subTitle) { subEl.title = subTitle; }
    div.appendChild(labelEl); div.appendChild(valueEl); div.appendChild(subEl);
    countUp(valueEl, value, fmt);
    return div;
  }

  /* --------------------------- tables + CSV ------------------------------ */

  function paintTable(host) {
    var st = host._state;
    var rows = st.rows.slice();
    if (st.query) {
      var needle = st.query.toLowerCase();
      rows = rows.filter(function (row) {
        return st.cols.some(function (col) {
          var v = row[col.key];
          return v !== null && v !== undefined && String(v).toLowerCase().indexOf(needle) !== -1;
        });
      });
    }
    if (st.sortKey) {
      var col = null;
      st.cols.forEach(function (c) { if (c.key === st.sortKey) { col = c; } });
      rows.sort(function (a, b) {
        var va = a[st.sortKey], vb = b[st.sortKey];
        var na = typeof va === "number", nb = typeof vb === "number";
        if (na && nb) { return st.sortDir === "asc" ? va - vb : vb - va; }
        va = String(va === null ? "" : va).toLowerCase();
        vb = String(vb === null ? "" : vb).toLowerCase();
        if (va < vb) { return st.sortDir === "asc" ? -1 : 1; }
        if (va > vb) { return st.sortDir === "asc" ? 1 : -1; }
        return 0;
      });
      if (col) { rows.sort.stable = true; }
    }

    var html = ["<table><thead><tr>"];
    st.cols.forEach(function (c) {
      var arrow = st.sortKey === c.key ? (st.sortDir === "asc" ? " ^" : " v") : "";
      html.push("<th class=\"" + (c.num ? "num " : "") + (c.sortable === false ? "" : "sortable") +
        "\" data-key=\"" + esc(c.key) + "\" scope=\"col\">" + esc(c.label) + "<span class=\"arrow\">" + arrow + "</span></th>");
    });
    html.push("</tr></thead><tbody>");
    var limit = st.limit || 400;
    rows.slice(0, limit).forEach(function (row) {
      html.push("<tr>");
      st.cols.forEach(function (c) {
        var raw = row[c.key];
        var text = c.format ? c.format(raw, row) : (raw === null || raw === undefined ? "n/a" : String(raw));
        html.push("<td class=\"" + (c.num ? "num" : "") + "\">" + (c.html ? text : esc(text)) + "</td>");
      });
      html.push("</tr>");
    });
    html.push("</tbody></table>");
    if (rows.length > limit) {
      html.push("<p class=\"muted\">Showing first " + limit + " of " + rows.length + " rows - download the CSV for the full set.</p>");
    } else if (rows.length === 0) {
      html.push("<p class=\"muted\">No rows match.</p>");
    }
    host.innerHTML = html.join("");

    host.querySelectorAll("th.sortable").forEach(function (th) {
      th.addEventListener("click", function () {
        var key = th.getAttribute("data-key");
        if (st.sortKey === key) { st.sortDir = st.sortDir === "asc" ? "desc" : "asc"; }
        else { st.sortKey = key; st.sortDir = "desc"; }
        paintTable(host);
      });
    });

    var csvKey = host.getAttribute("data-csv");
    if (csvKey) { state.tableData[csvKey] = { cols: st.cols, rows: rows.slice(0, limit) }; }
  }

  function renderTable(container, cols, rows, opts) {
    var host = typeof container === "string" ? $(container) : container;
    if (!host) { return; }
    opts = opts || {};
    var prevQuery = host._state ? host._state.query : "";
    host._state = {
      cols: cols,
      rows: rows,
      query: opts.keepQuery ? prevQuery : (opts.query || ""),
      sortKey: opts.sortKey || null,
      sortDir: opts.sortDir || "desc",
      limit: opts.limit || 400
    };
    paintTable(host);
  }

  function csvCell(v) {
    var s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? "\"" + s.replace(/"/g, "\"\"") + "\"" : s;
  }

  function downloadCSV(key) {
    var data = state.tableData[key];
    if (!data) { return; }
    var lines = [data.cols.map(function (c) { return csvCell(c.label); }).join(",")];
    data.rows.forEach(function (row) {
      lines.push(data.cols.map(function (c) { return csvCell(row[c.key]); }).join(","));
    });
    var blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "quickmart-" + key + ".csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }

  /* ------------------------------- theme --------------------------------- */

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("qm-theme", theme); } catch (e) { /* private mode */ }
    if (window.QMCharts) { window.QMCharts.applyTheme(); }
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem("qm-theme"); } catch (e) { saved = null; }
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    setTheme(saved || (prefersDark ? "dark" : "light"));
    var btn = $("#theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
      });
    }
  }

  /* ------------------------------ filters -------------------------------- */

  function fillSelect(sel, options) {
    if (!sel) { return; }
    sel.innerHTML = options.map(function (o) {
      return "<option value=\"" + esc(o.value) + "\">" + esc(o.label) + "</option>";
    }).join("");
  }

  function initFilters(meta) {
    var months = meta.months || [];
    var monthOptions = months.map(function (m) { return { value: m, label: m }; });
    fillSelect($("#filter-month-from"), monthOptions);
    fillSelect($("#filter-month-to"), monthOptions);
    fillSelect($("#filter-city"), [{ value: "all", label: "All cities" }].concat(
      (meta.cities || []).map(function (c) { return { value: c, label: c }; })));
    fillSelect($("#filter-category"), [{ value: "all", label: "All categories" }].concat(
      (meta.categories || []).map(function (c) { return { value: c, label: c }; })));

    state.filters.month_from = months[0] || "";
    state.filters.month_to = months[months.length - 1] || "";
    var fromSel = $("#filter-month-from"), toSel = $("#filter-month-to");
    if (fromSel) { fromSel.value = state.filters.month_from; }
    if (toSel) { toSel.value = state.filters.month_to; }

    function changed() {
      var f = {
        month_from: fromSel ? fromSel.value : "",
        month_to: toSel ? toSel.value : "",
        city: $("#filter-city") ? $("#filter-city").value : "all",
        category: $("#filter-category") ? $("#filter-category").value : "all"
      };
      if (f.month_from && f.month_to && f.month_from > f.month_to) {
        var swap = f.month_from; f.month_from = f.month_to; f.month_to = swap;
      }
      state.filters = f;
      loadSales();
      loadPayments();
      loadCustomers();
    }
    ["#filter-month-from", "#filter-month-to", "#filter-city", "#filter-category"].forEach(function (sel) {
      var el = $(sel);
      if (el) { el.addEventListener("change", changed); }
    });
    var reset = $("#filter-reset");
    if (reset) {
      reset.addEventListener("click", function () {
        if (fromSel) { fromSel.value = months[0] || ""; }
        if (toSel) { toSel.value = months[months.length - 1] || ""; }
        var citySel = $("#filter-city"); if (citySel) { citySel.value = "all"; }
        var catSel = $("#filter-category"); if (catSel) { catSel.value = "all"; }
        changed();
      });
    }
  }

  /* ------------------------------ panels --------------------------------- */

  function loadMeta() {
    return fetchJSON("/api/meta").then(function (meta) {
      state.meta = meta;
      setText($("#meta-today"), "2026-10-11 (project constant)");
      var list = $("#freshness-list");
      if (list) {
        list.innerHTML = (meta.files || []).map(function (f) {
          var when = f.modified ? new Date(f.modified).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "missing";
          return "<li><span class=\"file\">" + esc(f.file) + "</span><span class=\"when\">" + esc(when) +
            (f.size_kb ? " - " + esc(f.size_kb) + " KB" : "") + "</span></li>";
        }).join("");
      }
      initFilters(meta);
    }).catch(function (err) { fail("#freshness-list", err); });
  }

  function loadSales() {
    var f = state.filters;
    fetchJSON("/api/kpis" + qs(f)).then(function (k) {
      state.kpis = k;
      var grid = $("#kpi-grid");
      if (grid) {
        grid.innerHTML = "";
        grid.appendChild(kpiCard("Delivered sales", k.delivered_value, F.inr0,
          "<span class=\"src\">data/sales_datamart.csv</span>"));
        grid.appendChild(kpiCard("Delivered orders", k.delivered_orders, F.int,
          "<span class=\"src\">data/report_validation.csv</span>"));
        grid.appendChild(kpiCard("Average order value", k.avg_order_value, F.inr,
          "delivered sales / delivered orders"));
        grid.appendChild(kpiCard("Trusted orders (lenient)", k.trusted_lenient_rows, F.int,
          "<span class=\"src\">outputs/lenient_trusted_orders.csv</span> - Rs " +
          new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(k.trusted_lenient_value)));
        grid.appendChild(kpiCard("Orders rejected (FAIL)", k.rejected_rows, F.int,
          "excluded from every answer"));
        grid.appendChild(kpiCard("Commission leakage", k.commission_leakage, F.inr,
          "<span class=\"src\">data/commission_datamart.csv</span> - cleaning effect"));
      }
      var strip = $("#validation-strip");
      if (strip) {
        var chips = [];
        (k.validation || []).forEach(function (v) {
          chips.push("<span class=\"chip\"><span class=\"dot\"></span>" + esc(v.figure) + " <strong>" + esc(v.status) + "</strong></span>");
        });
        strip.innerHTML = chips.join("") || "<p class=\"muted\">No validation figures.</p>";
      }
    }).catch(function (err) { fail("#kpi-grid", err); });

    fetchJSON("/api/monthly-sales" + qs(f)).then(function (d) {
      window.QMCharts.monthly(d.series || []);
    }).catch(function (err) { fail("#chart-monthly", err); });

    fetchJSON("/api/sales-cuts" + qs({ dim: "city", month_from: f.month_from, month_to: f.month_to, category: f.category }))
      .then(function (d) { window.QMCharts.city(d.rows || []); })
      .catch(function (err) { fail("#chart-city", err); });

    fetchJSON("/api/sales-cuts" + qs({ dim: "category", month_from: f.month_from, month_to: f.month_to, city: f.city }))
      .then(function (d) { window.QMCharts.category(d.rows || []); })
      .catch(function (err) { fail("#chart-category", err); });
  }

  function loadCustomers() {
    var by = $("#sort-customers") ? $("#sort-customers").value : "value";
    var f = state.filters;
    Promise.all([
      fetchJSON("/api/top-customers" + qs({ n: 10, by: by, city: f.city })),
      fetchJSON("/api/cohort")
    ]).then(function (results) {
      var top = results[0], cohort = results[1];
      window.QMCharts.topCustomers(top.rows || []);
      setText($("#top-customers-note"),
        "Identifiers masked as dense-rank labels #1-#10 (ties share a rank). " +
        top.total_customers_with_orders + " customers with delivered orders.");
      window.QMCharts.cohort(cohort.rows || []);

      var cols = [
        { key: "label", label: "Customer" },
        { key: "city", label: "City" },
        { key: "orders", label: "Orders", num: true },
        { key: "value", label: "Value (Rs)", num: true, format: function (v) { return F.inr(v); } },
        { key: "first_order", label: "First order" },
        { key: "last_order", label: "Last order" },
        { key: "tied", label: "Tie", format: function (v) { return v ? "tied" : ""; } }
      ];
      renderTable("#table-customers", cols, top.rows || [], { sortKey: by, sortDir: "desc" });
    }).catch(function (err) { fail("#table-customers", err); });
  }

  function loadPayments() {
    var f = state.filters;
    fetchJSON("/api/payment-mix" + qs({ month_from: f.month_from, month_to: f.month_to, city: f.city }))
      .then(function (d) {
        window.QMCharts.payment(d.rows || []);
        var cols = [
          { key: "payment_std", label: "Payment" },
          { key: "orders", label: "Orders", num: true },
          { key: "value", label: "Value (Rs)", num: true, format: function (v) { return F.inr(v); } },
          { key: "share_pct", label: "Share", num: true, format: function (v) { return F.pct(v); } }
        ];
        renderTable("#table-payments", cols, d.rows || [], { sortKey: "value", sortDir: "desc" });
      }).catch(function (err) { fail("#table-payments", err); });
  }

  function loadDelivery() {
    fetchJSON("/api/delivery").then(function (d) {
      window.QMCharts.delivery(d.by_city || []);
      window.QMCharts.deliveryAnomalies(d.by_city || []);

      var totals = { impossible: 0, negative: 0, over: 0, missing: 0 };
      (d.by_city_category || []).forEach(function (r) {
        totals.impossible += r.impossible_orders || 0;
        totals.negative += r.negative_orders || 0;
        totals.over += r.over_30_orders || 0;
        totals.missing += r.missing_orders || 0;
      });
      var grid = $("#delivery-kpis");
      if (grid) {
        grid.innerHTML = "";
        grid.appendChild(kpiCard("Weighted average days", d.weighted_avg_days, function (v) { return (Math.round(v * 100) / 100) + " days"; }, "weighted by orders"));
        grid.appendChild(kpiCard("Impossible delivery days", totals.impossible, F.int, "set aside, never hidden"));
        grid.appendChild(kpiCard("Over 30 days", totals.over, F.int, "counted and reported"));
        grid.appendChild(kpiCard("Missing delivery days", totals.missing, F.int, "reported as n/a in averages"));
      }

      var cols = [
        { key: "city_std", label: "City" },
        { key: "category_std", label: "Category" },
        { key: "orders", label: "Orders", num: true },
        { key: "avg_days", label: "Avg days", num: true, format: function (v) { return v === null ? "n/a" : (Math.round(v * 100) / 100); } },
        { key: "median_days", label: "Median days", num: true, format: function (v) { return v === null ? "n/a" : (Math.round(v * 100) / 100); } },
        { key: "impossible_orders", label: "Impossible", num: true },
        { key: "negative_orders", label: "Negative", num: true },
        { key: "over_30_orders", label: "Over 30", num: true },
        { key: "missing_orders", label: "Missing", num: true }
      ];
      renderTable("#table-delivery", cols, d.by_city_category || [], { sortKey: "orders", sortDir: "desc" });
    }).catch(function (err) { fail("#table-delivery", err); });
  }

  function loadQuality() {
    fetchJSON("/api/quality/scorecard").then(function (rows) {
      var grid = $("#scorecard-grid");
      if (!grid) { return; }
      grid.innerHTML = "";
      (rows || []).forEach(function (r) {
        grid.appendChild(kpiCard(r.table + " quality score", r.quality_score_pct,
          function (v) { return (Math.round(v * 100) / 100) + "%"; },
          r.rows + " rows - " + r.checks_run + " checks - " + F.int(r.failed_cells) + " failed cells",
          "data/quality_scorecard.csv"));
      });
    }).catch(function (err) { fail("#scorecard-grid", err); });

    fetchJSON("/api/quality/rules").then(function (d) {
      window.QMCharts.rules(d.rows || []);
      var cols = [
        { key: "rule_id", label: "Rule" },
        { key: "name", label: "Check" },
        { key: "fail", label: "FAIL", num: true },
        { key: "warning", label: "Warnings", num: true },
        { key: "treatment", label: "Treatment" },
        { key: "value_removed", label: "Value removed (Rs)", num: true, format: function (v) { return v === null || v === undefined ? "n/a" : F.inr(v); } }
      ];
      renderTable("#table-rules", cols, d.rows || [], { sortKey: "fail", sortDir: "desc", limit: 12 });
    }).catch(function (err) { fail("#table-rules", err); });

    fetchJSON("/api/quality/heatmap").then(function (d) {
      var host = $("#heatmap");
      if (!host) { return; }
      var lookup = {};
      (d.cells || []).forEach(function (c) { lookup[c.city + "|" + c.month] = c; });
      var html = ["<div class=\"heat-months\">"];
      (d.months || []).forEach(function (m) { html.push("<span>" + esc(m.slice(2)) + "</span>"); });
      html.push("</div>");
      (d.cities || []).forEach(function (city) {
        html.push("<div class=\"heat-row\"><span class=\"heat-row-label\">" + esc(city) + "</span>");
        (d.months || []).forEach(function (m) {
          var cell = lookup[city + "|" + m];
          if (!cell) {
            var noOrders = city + " " + m + ": no orders";
            html.push("<div class=\"heat-cell\" style=\"opacity:.25\" title=\"" + esc(noOrders) + "\" aria-label=\"" + esc(noOrders) + "\"></div>");
          } else {
            var alpha = (0.08 + 0.87 * (cell.pct / 100)).toFixed(2);
            var label = city + " - " + m + ": " + cell.pct + "% of " + cell.rows + " orders had at least 1 issue";
            html.push("<div class=\"heat-cell\" style=\"background:rgba(31,119,180," + alpha + ")\" title=\"" +
              esc(label) + "\" aria-label=\"" + esc(label) + "\" role=\"img\"></div>");
          }
        });
        html.push("</div>");
      });
      host.innerHTML = html.join("");
    }).catch(function (err) { fail("#heatmap", err); });

    fetchJSON("/api/quality/profile").then(function (d) {
      window.QMCharts.profile(d.rows || []);
    }).catch(function (err) { fail("#chart-profile", err); });

    fetchJSON("/api/quality/issues").then(function (d) {
      var rows = d.rows || [];
      var keys = rows.length ? Object.keys(rows[0]) : [];
      var cols = keys.map(function (k) {
        return { key: k, label: k.replace(/_/g, " "), num: typeof rows[0][k] === "number" };
      });
      renderTable("#table-issues", cols, rows, { sortKey: "fail_count", sortDir: "desc" });
    }).catch(function (err) { fail("#table-issues", err); });
  }

  function loadTrust() {
    Promise.all([
      fetchJSON("/api/trust"),
      fetchJSON("/api/commission"),
      fetchJSON("/api/duplicates")
    ]).then(function (results) {
      var trust = results[0], commission = results[1], dups = results[2];

      window.QMCharts.waterfall(trust.waterfall || []);
      setText($("#waterfall-note"),
        "Reconciliation: raw " + F.int(trust.reconciliation.raw) + " -> clean " + F.int(trust.reconciliation.clean) +
        " = lenient " + F.int(trust.lenient.rows) + " + rejected " + F.int(trust.rejected.rows) +
        ". Warning-only rows kept: " + F.int(trust.warning_only_rows) + ".");
      window.QMCharts.commission(commission.compare_city || []);
      setText($("#commission-note"),
        "Commission before " + F.inr(commission.summary.commission_before) + " -> after " +
        F.inr(commission.summary.commission_after) + " (leakage " + F.inr(commission.summary.commission_leakage) +
        ", rows removed " + F.int(commission.summary.rows_removed) + ").");

      var grid = $("#trust-kpis");
      if (grid) {
        grid.innerHTML = "";
        grid.appendChild(kpiCard("Strict trusted orders", trust.strict.rows, F.int,
          "value " + F.inr(trust.strict.value) + " - outputs/strict_trusted_orders.csv"));
        grid.appendChild(kpiCard("Rejection rate", trust.rejected.rows / trust.reconciliation.clean * 100,
          function (v) { return (Math.round(v * 10) / 10) + "%"; }, "of clean rows carry a FAIL"));
        grid.appendChild(kpiCard("Rows removed on dedup", dups.headline.rows_removed, F.int,
          "raw " + F.int(dups.headline.raw_rows) + " -> clean " + F.int(dups.headline.clean_rows)));
        grid.appendChild(kpiCard("Duplicate customer pairs", dups.quality_flags.duplicate_order_id_rows !== undefined ? dups.registry_total : dups.registry_total, F.int,
          "registry masked - data/duplicate_registry.csv"));
      }
    }).catch(function (err) { fail("#trust-kpis", err); });
  }

  /* ------------------------- questions explorer --------------------------- */

  function qMatches(item) {
    var search = $("#q-search") ? $("#q-search").value.trim().toLowerCase() : "";
    var segment = $("#q-segment") ? $("#q-segment").value : "all";
    var status = $("#q-status") ? $("#q-status").value : "all";
    if (segment !== "all" && item.segment !== segment) { return false; }
    if (status !== "all" && item.status !== status) { return false; }
    if (search) {
      var hay = (String(item.id) + " " + (item.title || "") + " " + (item.headline || "") + " " + (item.result_text || "") + " " + (item.pending_reason || "")).toLowerCase();
      if (hay.indexOf(search) === -1) { return false; }
    }
    return true;
  }

  function renderQuestions() {
    var host = $("#q-list");
    if (!host) { return; }
    var filtered = state.questions.filter(qMatches);
    var shown = filtered.slice(0, state.qShown);
    setText($("#q-count"), "Showing " + shown.length + " of " + filtered.length +
      " matching questions (" + state.questions.length + " total, " +
      state.questions.filter(function (q) { return q.status === "DONE"; }).length + " DONE).");

    host.innerHTML = shown.map(function (q) {
      var savedQid = null;
      if (state.sqlList.indexOf("q" + q.id) !== -1) { savedQid = q.id; }
      var statusClass = q.status === "DONE" ? "done" : "pending";
      var parts = [];
      parts.push("<div class=\"q-item\">");
      parts.push("<div class=\"q-head\"><span class=\"q-id\">Q" + esc(q.id) + "</span>" +
        "<span class=\"badge " + statusClass + "\">" + esc(q.status) + "</span>" +
        "<span class=\"badge\">Segment " + esc(q.segment) + "</span>" +
        "<span class=\"q-title\">" + esc(q.title) + "</span></div>");
      parts.push("<p class=\"q-headline\">" + esc(q.headline || "Pending - not computed by the pipeline.") + "</p>");
      if (q.status !== "DONE" && q.pending_reason) {
        parts.push("<p class=\"q-reason\"><strong>Missing sub-part:</strong> " + esc(q.pending_reason) + "</p>");
      }
      parts.push("<div class=\"q-meta\">" +
        (q.code ? "<span>code: " + esc(q.code) + "</span>" : "") +
        (q.sql ? "<span>sql: " + esc(q.sql) + "</span>" : "") +
        "<span>parity: " + (q.parity_tested ? "yes" : "no") + "</span></div>");
      if (savedQid !== null) {
        parts.push("<div class=\"q-actions\"><button type=\"button\" class=\"btn small ghost view-result\" data-qid=\"" +
          esc(q.id) + "\">View saved result</button></div>");
      }
      if (q.method) {
        parts.push("<details><summary>Method</summary><p class=\"muted\">" + esc(q.method) + "</p></details>");
      }
      if (q.result_text) {
        parts.push("<details><summary>Result</summary><p class=\"muted\">" + esc(q.result_text) + "</p></details>");
      }
      parts.push("</div>");
      return parts.join("");
    }).join("");

    var more = $("#q-more");
    if (more) { more.hidden = shown.length >= filtered.length; }
  }

  function loadQuestions() {
    Promise.all([
      fetchJSON("/api/questions?limit=200"),
      fetchJSON("/api/sql-list")
    ]).then(function (results) {
      state.questions = results[0].rows || [];
      state.sqlList = results[1].qids || [];
      renderQuestions();
    }).catch(function (err) { fail("#q-list", err); });

    ["#q-search", "#q-segment", "#q-status"].forEach(function (sel) {
      var el = $(sel);
      if (el) {
        el.addEventListener("input", function () { state.qShown = 25; renderQuestions(); });
        el.addEventListener("change", function () { state.qShown = 25; renderQuestions(); });
      }
    });
    var more = $("#q-more");
    if (more) {
      more.addEventListener("click", function () { state.qShown += 25; renderQuestions(); });
    }
    var list = $("#q-list");
    if (list) {
      list.addEventListener("click", function (event) {
        var target = event.target;
        if (!target || !target.classList || !target.classList.contains("view-result")) { return; }
        var qid = target.getAttribute("data-qid");
        var viewer = $("#sql-viewer");
        var title = $("#sql-viewer-title");
        if (title) { title.textContent = "Loading q" + qid + "..."; }
        fetchJSON("/api/sql-file/q" + qid).then(function (d) {
          if (title) { title.textContent = "Source: " + d.source; }
          if (viewer) { viewer.textContent = d.text || "(empty)"; viewer.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
        }).catch(function (err) {
          if (title) { title.textContent = "Could not load q" + qid + " (" + err.message + ")"; }
        });
      });
    }
  }

  /* ------------------------------ capstone -------------------------------- */

  var PANEL_LINKS = {
    Q1: [["#quality", "Data quality"], ["#trust", "Trust"]],
    Q2: [["#trust", "Trust & commission"], ["#quality", "Data quality"]],
    Q3: [["#trust", "Trust & commission"]],
    Q4: [["#sales", "Sales"], ["#customers", "Customers"], ["#payments", "Payments"], ["#delivery", "Delivery"]],
    Q5: [["#capstone", "Provenance"], ["#questions", "Questions explorer"]]
  };

  function loadCapstone() {
    fetchJSON("/api/capstone").then(function (d) {
      var host = $("#capstone-list");
      if (host) {
        host.innerHTML = (d.problems || []).map(function (p) {
          var links = (PANEL_LINKS[p.id] || []).map(function (l) {
            return "<a class=\"btn small ghost\" href=\"" + l[0] + "\">See " + esc(l[1]) + "</a>";
          }).join("");
          return "<article class=\"card capstone-card\">" +
            "<p><span class=\"badge done\">" + esc(p.id) + "</span></p>" +
            "<h3 class=\"capstone-q\">" + esc(p.question) + "</h3>" +
            "<dl class=\"capstone-dl\">" +
            "<dt>Approach</dt><dd>" + esc(p.approach) + "</dd>" +
            "<dt>Decision</dt><dd>" + esc(p.decision) + "</dd>" +
            "<dt>Alternative</dt><dd>" + esc(p.alternative) + "</dd>" +
            "<dt>Effect</dt><dd>" + esc(p.effect) + "</dd>" +
            "<dt>Numbers</dt><dd>" + esc(p.numbers) + "</dd>" +
            "<dt>Code</dt><dd><code>" + esc(p.code) + "</code></dd>" +
            "</dl><div class=\"capstone-links\">" + links + "</div></article>";
        }).join("");
      }

      var insights = $("#insight-list");
      if (insights) {
        insights.innerHTML = (d.insights || []).map(function (i) {
          var figs = (i.figures || []).map(function (f) {
            return "<span class=\"badge\">" + esc(f.mart) + " - " + esc(f.row_key) + " - " +
              esc(typeof f.value === "number" ? F.inr(f.value) : f.value) + "</span>";
          }).join(" ");
          return "<div class=\"insight\"><p class=\"claim\">" + esc(i.claim) + " <span class=\"badge pass\">" +
            esc(i.status) + "</span></p><p class=\"why\">" + esc(i.so_what || i.reason || "") + "</p><p class=\"q-meta\">" + figs + "</p></div>";
        }).join("");
      }

      var rubricNote = $("#rubric-note");
      if (rubricNote && d.rubric) {
        rubricNote.textContent = "Rubric: self-assessed " + d.rubric.score + "/100 (" + d.rubric.note + ").";
      }
    }).catch(function (err) { fail("#capstone-list", err); });

    fetchJSON("/api/manifest").then(function (m) {
      var strip = $("#validation-strip");
      if (strip && m.validations && m.validations.length) {
        var chips = m.validations.map(function (v) {
          return "<span class=\"chip\" title=\"" + esc(v.evidence) + "\"><span class=\"dot\"></span>" +
            esc(v.name) + " <strong>" + esc(v.status) + "</strong></span>";
        }).join("");
        strip.insertAdjacentHTML("beforeend", chips);
      }
      var prov = $("#provenance-list");
      if (prov && m.provenance) {
        var items = [];
        var sections = m.provenance;
        if (sections.extracts) {
          Object.keys(sections.extracts).forEach(function (k) {
            items.push("<li><span class=\"file\">extracts." + esc(k) + "</span><span class=\"when\">" +
              esc(String(sections.extracts[k]).slice(0, 12)) + "...</span></li>");
          });
        }
        if (sections.outputs) {
          Object.keys(sections.outputs).forEach(function (k) {
            items.push("<li><span class=\"file\">" + esc(k) + "</span><span class=\"when\">" +
              esc(String(sections.outputs[k]).slice(0, 12)) + "...</span></li>");
          });
        }
        if (sections.settings) {
          Object.keys(sections.settings).forEach(function (k) {
            items.push("<li><span class=\"file\">" + esc(k) + "</span><span class=\"when\">" +
              esc(String(sections.settings[k])) + "</span></li>");
          });
        }
        prov.innerHTML = items.join("");
      }
      var note = $("#rubric-note");
      if (note && m.rubric && m.rubric.score) {
        note.textContent = "Rubric: self-assessed " + m.rubric.score + "/100 (" + (m.rubric.note || "") +
          ") - run hash " + String(m.run_hash || "n/a").slice(0, 12) + "...";
      }
    }).catch(function (err) { fail("#provenance-list", err); });
  }

  /* ------------------------------ scrollspy ------------------------------- */

  function initScrollspy() {
    var links = document.querySelectorAll(".nav-link");
    if (!links.length || !("IntersectionObserver" in window)) { return; }
    var map = {};
    links.forEach(function (link) { map[link.getAttribute("href").slice(1)] = link; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          links.forEach(function (l) { l.classList.remove("active"); });
          var link = map[entry.target.id];
          if (link) { link.classList.add("active"); }
        }
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    document.querySelectorAll("main section[id]").forEach(function (sec) { observer.observe(sec); });
  }

  /* --------------------------------- boot --------------------------------- */

  function boot() {
    initTheme();
    document.querySelectorAll("[data-download]").forEach(function (btn) {
      btn.addEventListener("click", function () { downloadCSV(btn.getAttribute("data-download")); });
    });
    var sortCustomers = $("#sort-customers");
    if (sortCustomers) { sortCustomers.addEventListener("change", loadCustomers); }
    var searchCustomers = $("#search-customers");
    if (searchCustomers) {
      searchCustomers.addEventListener("input", function () {
        var host = $("#table-customers");
        if (host && host._state) { host._state.query = searchCustomers.value; paintTable(host); }
      });
    }
    initScrollspy();
    loadMeta().then(function () {
      loadSales();
      loadCustomers();
      loadPayments();
      loadDelivery();
      loadQuality();
      loadTrust();
      loadQuestions();
      loadCapstone();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
