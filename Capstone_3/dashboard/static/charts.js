/* ==========================================================================
   QuickMart Analytics Dashboard - chart builders (Chart.js 4.x, vendored)
   Exposes window.QMCharts (applyTheme) and window.QMFmt (en-IN formatting).
   Every builder guards against missing/empty data and never throws.
   ========================================================================== */
(function () {
  "use strict";

  var registry = [];

  var PALETTE = {
    blue: "#1f77b4",
    teal: "#075056",
    navy: "#024879",
    turq: "#71D8C5",
    cobalt: "#324EB5",
    sky: "#C5DCEE",
    amber: "#B97A1A",
    green: "#1e7d4f",
    red: "#b3402f",
    gray: "#8fa5b0"
  };

  var CAT_COLORS = ["#1f77b4", "#075056", "#324EB5", "#71D8C5", "#b97a1a",
                    "#024879", "#8fa5b0", "#b3402f", "#2e6f5e", "#c5dcee"];

  var PAY_COLORS = ["#324EB5", "#1f77b4", "#71D8C5", "#b97a1a", "#024879", "#8fa5b0"];

  /* ----------------------------- helpers -------------------------------- */

  function isDark() { return document.documentElement.getAttribute("data-theme") === "dark"; }
  function muted() { return isDark() ? "#93a9b4" : "#556872"; }
  function ink() { return isDark() ? "#dce8ee" : "#15262e"; }
  function gridColor() { return isDark() ? "rgba(220,232,238,0.10)" : "rgba(2,72,121,0.08)"; }

  var nf0 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
  var nf2 = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function inr(v) { return v === null || v === undefined ? "n/a" : "Rs " + nf2.format(v); }
  function inr0(v) { return v === null || v === undefined ? "n/a" : "Rs " + nf0.format(Math.round(v)); }
  function inrShort(v) {
    if (v === null || v === undefined) { return "n/a"; }
    var a = Math.abs(v);
    if (a >= 1e7) { return "Rs " + (v / 1e7).toFixed(2) + " Cr"; }
    if (a >= 1e5) { return "Rs " + (v / 1e5).toFixed(1) + " L"; }
    if (a >= 1e3) { return "Rs " + (v / 1e3).toFixed(0) + "K"; }
    return "Rs " + nf0.format(v);
  }
  function intFmt(v) { return v === null || v === undefined ? "n/a" : nf0.format(v); }
  function pctFmt(v) { return v === null || v === undefined ? "n/a" : (Math.round(v * 10) / 10) + "%"; }

  window.QMFmt = { inr: inr, inr0: inr0, inrShort: inrShort, int: intFmt, pct: pctFmt };

  function nonEmpty(arr) { return Array.isArray(arr) && arr.length > 0; }

  function merge(base, extra) {
    var out = {};
    var k;
    for (k in base) { if (Object.prototype.hasOwnProperty.call(base, k)) { out[k] = base[k]; } }
    for (k in extra) {
      if (Object.prototype.hasOwnProperty.call(extra, k)) {
        if (out[k] && typeof out[k] === "object" && !Array.isArray(out[k]) && typeof extra[k] === "object" && !Array.isArray(extra[k])) {
          out[k] = merge(out[k], extra[k]);
        } else {
          out[k] = extra[k];
        }
      }
    }
    return out;
  }

  function baseOptions(extra) {
    return merge({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 550 },
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: { labels: { color: muted(), boxWidth: 12, boxHeight: 12, font: { size: 12 } } },
        tooltip: {
          backgroundColor: isDark() ? "#0e2027" : "#0a1d25",
          titleColor: "#ffffff",
          bodyColor: "#e6eef2",
          borderColor: gridColor(),
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          boxPadding: 4
        }
      }
    }, extra || {});
  }

  function axis(opts) {
    return merge({ ticks: { color: muted(), font: { size: 11 } }, grid: { color: gridColor() } }, opts || {});
  }

  function render(entry) {
    var el = document.getElementById(entry.id);
    if (!el || typeof Chart === "undefined" || entry.data === null || entry.data === undefined) { return; }
    if (entry.chart) { entry.chart.destroy(); entry.chart = null; }
    Chart.defaults.color = ink();
    Chart.defaults.borderColor = gridColor();
    try {
      entry.chart = new Chart(el.getContext("2d"), entry.make(entry.data));
      el.setAttribute("aria-busy", "false");
    } catch (err) {
      el.setAttribute("aria-busy", "false");
      el.setAttribute("title", "Chart could not be drawn: " + err.message);
    }
  }

  function upsert(id, make, data) {
    var entry = null;
    for (var i = 0; i < registry.length; i++) {
      if (registry[i].id === id) { entry = registry[i]; break; }
    }
    if (!entry) { entry = { id: id, make: make, data: null, chart: null }; registry.push(entry); }
    entry.make = make;
    entry.data = data;
    render(entry);
  }

  /* ----------------------------- builders ------------------------------- */

  function monthly(series) {
    if (!nonEmpty(series)) { return; }
    var labels = series.map(function (r) { return r.order_month; });
    var values = series.map(function (r) { return r.value; });
    upsert("chart-monthly", function (rows) {
      return {
        type: "bar",
        data: {
          labels: rows.map(function (r) { return r.order_month; }),
          datasets: [{
            label: "Delivered sales",
            data: rows.map(function (r) { return r.value; }),
            backgroundColor: "rgba(31,119,180,0.85)",
            borderColor: PALETTE.blue,
            borderWidth: 1,
            borderRadius: 3,
            hoverBackgroundColor: "rgba(7,80,86,0.92)",
            maxBarThickness: 42
          }]
        },
        options: baseOptions({
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  var row = rows[ctx.dataIndex] || {};
                  return " " + inr(ctx.parsed.y) + " - " + intFmt(row.orders) + " orders";
                }
              }
            }
          },
          scales: {
            x: axis({ minRotation: 90, maxRotation: 90, ticks: { color: muted(), font: { size: 10 } } }),
            y: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return inrShort(v); } } })
          }
        })
      };
    }, series.length ? series : null);
  }

  function city(rows) {
    if (!nonEmpty(rows)) { return; }
    upsert("chart-city", function (data) {
      return {
        type: "bar",
        data: {
          labels: data.map(function (r) { return r.city_std; }),
          datasets: [{
            label: "Delivered sales",
            data: data.map(function (r) { return r.value; }),
            backgroundColor: "rgba(2,72,121,0.82)",
            borderColor: PALETTE.navy,
            borderWidth: 1,
            borderRadius: 4,
            hoverBackgroundColor: "rgba(7,80,86,0.92)"
          }]
        },
        options: baseOptions({
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  var row = data[ctx.dataIndex] || {};
                  return " " + inr(ctx.parsed.x) + " - " + pctFmt(row.share_pct) + " of total - " + intFmt(row.orders) + " orders";
                }
              }
            }
          },
          scales: {
            x: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return inrShort(v); } } }),
            y: axis()
          }
        })
      };
    }, rows);
  }

  function category(rows) {
    if (!nonEmpty(rows)) { return; }
    upsert("chart-category", function (data) {
      return {
        type: "doughnut",
        data: {
          labels: data.map(function (r) { return r.category_std; }),
          datasets: [{
            data: data.map(function (r) { return r.value; }),
            backgroundColor: CAT_COLORS,
            borderColor: isDark() ? "#0e2027" : "#ffffff",
            borderWidth: 2,
            hoverOffset: 8
          }]
        },
        options: baseOptions({
          cutout: "58%",
          plugins: {
            legend: { position: "bottom", labels: { color: muted(), boxWidth: 12, boxHeight: 12 } },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  var row = data[ctx.dataIndex] || {};
                  return " " + inr(ctx.parsed) + " - " + pctFmt(row.share_pct);
                }
              }
            }
          }
        })
      };
    }, rows);
  }

  function topCustomers(rows) {
    if (!nonEmpty(rows)) { return; }
    upsert("chart-top-customers", function (data) {
      return {
        type: "bar",
        data: {
          labels: data.map(function (r) { return r.label; }),
          datasets: [{
            label: "Value",
            data: data.map(function (r) { return r.value; }),
            backgroundColor: data.map(function (_, i) {
              return i === 0 ? "rgba(7,80,86,0.9)" : "rgba(50,78,181,0.75)";
            }),
            borderColor: data.map(function (_, i) { return i === 0 ? PALETTE.teal : PALETTE.cobalt; }),
            borderWidth: 1,
            borderRadius: 4
          }]
        },
        options: baseOptions({
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: function (items) {
                  var row = data[items[0].dataIndex] || {};
                  return row.label + " - " + (row.city || "n/a") + (row.tied ? " (tied)" : "");
                },
                label: function (ctx) {
                  var row = data[ctx.dataIndex] || {};
                  return " " + inr(ctx.parsed.x) + " - " + intFmt(row.orders) + " orders";
                }
              }
            }
          },
          scales: {
            x: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return inrShort(v); } } }),
            y: axis()
          }
        })
      };
    }, rows);
  }

  function cohort(rows) {
    if (!nonEmpty(rows)) { return; }
    var totals = {};
    rows.forEach(function (r) { totals[r.signup_month] = (totals[r.signup_month] || 0) + (r.value || 0); });
    var topCohorts = Object.keys(totals)
      .sort(function (a, b) { return totals[b] - totals[a]; })
      .slice(0, 6)
      .sort();
    var months = [];
    rows.forEach(function (r) { if (months.indexOf(r.order_month) === -1) { months.push(r.order_month); } });
    months.sort();
    var colors = [PALETTE.cobalt, PALETTE.turq, PALETTE.amber, PALETTE.teal, PALETTE.blue, PALETTE.gray];
    var datasets = topCohorts.map(function (cohortMonth, i) {
      var lookup = {};
      rows.forEach(function (r) { if (r.signup_month === cohortMonth) { lookup[r.order_month] = r.value; } });
      return {
        label: "Signed up " + cohortMonth,
        data: months.map(function (m) { return lookup[m] === undefined ? null : lookup[m]; }),
        borderColor: colors[i % colors.length],
        backgroundColor: colors[i % colors.length],
        tension: 0.25,
        pointRadius: 2,
        pointHoverRadius: 4,
        borderWidth: 2,
        spanGaps: true
      };
    });
    upsert("chart-cohort", function () {
      return {
        type: "line",
        data: { labels: months, datasets: datasets },
        options: baseOptions({
          plugins: {
            legend: { position: "bottom" },
            tooltip: { callbacks: { label: function (ctx) { return " " + ctx.dataset.label + ": " + inr(ctx.parsed.y); } } }
          },
          scales: {
            x: axis({ ticks: { color: muted(), font: { size: 10 }, maxRotation: 60, minRotation: 45 } }),
            y: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return inrShort(v); } } })
          }
        })
      };
    }, rows);
  }

  function payment(rows) {
    if (!nonEmpty(rows)) { return; }
    upsert("chart-payment", function (data) {
      return {
        type: "doughnut",
        data: {
          labels: data.map(function (r) { return r.payment_std; }),
          datasets: [{
            data: data.map(function (r) { return r.value; }),
            backgroundColor: PAY_COLORS,
            borderColor: isDark() ? "#0e2027" : "#ffffff",
            borderWidth: 2,
            hoverOffset: 8
          }]
        },
        options: baseOptions({
          cutout: "58%",
          plugins: {
            legend: { position: "bottom" },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  var row = data[ctx.dataIndex] || {};
                  return " " + inr(ctx.parsed) + " - " + pctFmt(row.share_pct) + " - " + intFmt(row.orders) + " orders";
                }
              }
            }
          }
        })
      };
    }, rows);
  }

  function delivery(rows) {
    if (!nonEmpty(rows)) { return; }
    upsert("chart-delivery", function (data) {
      return {
        type: "bar",
        data: {
          labels: data.map(function (r) { return r.city_std; }),
          datasets: [
            {
              label: "Average days",
              data: data.map(function (r) { return r.avg_days; }),
              backgroundColor: "rgba(50,78,181,0.82)",
              borderColor: PALETTE.cobalt,
              borderWidth: 1,
              borderRadius: 4
            },
            {
              label: "Median days",
              data: data.map(function (r) { return r.median_days; }),
              backgroundColor: "rgba(113,216,197,0.85)",
              borderColor: PALETTE.turq,
              borderWidth: 1,
              borderRadius: 4
            }
          ]
        },
        options: baseOptions({
          indexAxis: "y",
          plugins: {
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  var row = data[ctx.dataIndex] || {};
                  return " " + ctx.dataset.label + ": " + (Math.round(ctx.parsed.x * 100) / 100) + " days (" + intFmt(row.orders) + " orders)";
                }
              }
            }
          },
          scales: {
            x: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return v + " d"; } } }),
            y: axis()
          }
        })
      };
    }, rows);
  }

  function deliveryAnomalies(rows) {
    if (!nonEmpty(rows)) { return; }
    var defs = [
      { key: "negative_orders", label: "Negative days", color: PALETTE.red },
      { key: "impossible_orders", label: "Impossible", color: PALETTE.amber },
      { key: "over_30_orders", label: "Over 30 days", color: PALETTE.cobalt },
      { key: "missing_orders", label: "Missing", color: PALETTE.gray }
    ];
    upsert("chart-delivery-anomalies", function (data) {
      return {
        type: "bar",
        data: {
          labels: data.map(function (r) { return r.city_std; }),
          datasets: defs.map(function (d) {
            return {
              label: d.label,
              data: data.map(function (r) { return r[d.key]; }),
              backgroundColor: d.color,
              borderRadius: 2,
              maxBarThickness: 26
            };
          })
        },
        options: baseOptions({
          indexAxis: "y",
          plugins: {
            legend: { position: "bottom" },
            tooltip: { callbacks: { label: function (ctx) { return " " + ctx.dataset.label + ": " + intFmt(ctx.parsed.x) + " orders"; } } }
          },
          scales: {
            x: axis({ stacked: true, beginAtZero: true, ticks: { color: muted(), precision: 0 } }),
            y: axis({ stacked: true })
          }
        })
      };
    }, rows);
  }

  function rules(rows) {
    if (!nonEmpty(rows)) { return; }
    upsert("chart-rules", function (data) {
      return {
        type: "bar",
        data: {
          labels: data.map(function (r) { return r.rule_id; }),
          datasets: [
            {
              label: "FAIL",
              data: data.map(function (r) { return r.fail; }),
              backgroundColor: "rgba(179,64,47,0.85)",
              borderRadius: 2
            },
            {
              label: "WARNING",
              data: data.map(function (r) { return r.warning; }),
              backgroundColor: "rgba(185,122,26,0.85)",
              borderRadius: 2
            }
          ]
        },
        options: baseOptions({
          indexAxis: "y",
          plugins: {
            legend: { position: "bottom" },
            tooltip: {
              callbacks: {
                title: function (items) {
                  var row = data[items[0].dataIndex] || {};
                  return row.rule_id + (row.name ? " - " + row.name : "");
                },
                label: function (ctx) { return " " + ctx.dataset.label + ": " + intFmt(ctx.parsed.x) + " rows"; }
              }
            }
          },
          scales: {
            x: axis({ stacked: true, beginAtZero: true, ticks: { color: muted(), precision: 0 } }),
            y: axis({ stacked: true })
          }
        })
      };
    }, rows);
  }

  function profile(rows) {
    if (!nonEmpty(rows)) { return; }
    var top = rows.slice(0, 8);
    upsert("chart-profile", function () {
      return {
        type: "bar",
        data: {
          labels: top.map(function (r) { return r.table + "." + r.column; }),
          datasets: [{
            label: "Missing %",
            data: top.map(function (r) { return r.missing_pct; }),
            backgroundColor: "rgba(185,122,26,0.82)",
            borderColor: PALETTE.amber,
            borderWidth: 1,
            borderRadius: 4
          }]
        },
        options: baseOptions({
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  var row = top[ctx.dataIndex] || {};
                  return " " + pctFmt(ctx.parsed.x) + " missing (" + intFmt(row.missing) + " of " + intFmt(row.rows) + " rows)";
                }
              }
            }
          },
          scales: {
            x: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return v + "%"; } } }),
            y: axis({ ticks: { color: muted(), font: { size: 11 }, autoSkip: false } })
          }
        })
      };
    }, rows);
  }

  function waterfall(stages) {
    if (!nonEmpty(stages)) { return; }
    var colors = ["#1f77b4", "#1f77b4", "#024879", "#b3402f", "#075056", "#71D8C5"];
    upsert("chart-waterfall", function (data) {
      return {
        type: "bar",
        data: {
          labels: data.map(function (r) { return r.stage; }),
          datasets: [{
            label: "Orders",
            data: data.map(function (r) { return r.rows; }),
            backgroundColor: data.map(function (_, i) { return colors[i % colors.length]; }),
            borderRadius: 4,
            maxBarThickness: 34
          }]
        },
        options: baseOptions({
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: function (ctx) { return " " + intFmt(ctx.parsed.x) + " orders"; } } }
          },
          scales: {
            x: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return intFmt(v); } } }),
            y: axis({ ticks: { color: muted(), font: { size: 11 }, autoSkip: false } })
          }
        })
      };
    }, stages);
  }

  function commission(rows) {
    if (!nonEmpty(rows)) { return; }
    upsert("chart-commission", function (data) {
      return {
        type: "bar",
        data: {
          labels: data.map(function (r) { return r.city_std; }),
          datasets: [
            {
              label: "Before cleaning",
              data: data.map(function (r) { return r.commission_before; }),
              backgroundColor: "rgba(50,78,181,0.82)",
              borderColor: PALETTE.cobalt,
              borderWidth: 1,
              borderRadius: 4
            },
            {
              label: "After cleaning",
              data: data.map(function (r) { return r.commission_after; }),
              backgroundColor: "rgba(113,216,197,0.85)",
              borderColor: PALETTE.turq,
              borderWidth: 1,
              borderRadius: 4
            }
          ]
        },
        options: baseOptions({
          plugins: {
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  var row = data[ctx.dataIndex] || {};
                  return " " + ctx.dataset.label + ": " + inr(ctx.parsed.y) + " (" + intFmt(row.orders_before) + " orders before)";
                }
              }
            }
          },
          scales: {
            x: axis({ ticks: { color: muted(), maxRotation: 45, minRotation: 0 } }),
            y: axis({ beginAtZero: true, ticks: { color: muted(), callback: function (v) { return inrShort(v); } } })
          }
        })
      };
    }, rows);
  }

  window.QMCharts = {
    monthly: monthly,
    city: city,
    category: category,
    topCustomers: topCustomers,
    cohort: cohort,
    payment: payment,
    delivery: delivery,
    deliveryAnomalies: deliveryAnomalies,
    rules: rules,
    profile: profile,
    waterfall: waterfall,
    commission: commission,
    applyTheme: function () {
      for (var i = 0; i < registry.length; i++) { render(registry[i]); }
    }
  };
})();
