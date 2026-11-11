document.addEventListener("DOMContentLoaded", function () {
  function mk(id, type, data, options) {
    var el = document.getElementById(id);
    if (!el || typeof Chart === "undefined") return;
    new Chart(el, { type: type, data: data, options: options || {} });
  }
  mk("c-city", "bar",
    { labels: ["Bengaluru", "Chennai", "Hyderabad", "Mumbai", "Delhi", "Kolkata", "Unknown"],
      datasets: [{ label: "Revenue Rs", data: [737658.25, 490000, 330000, 260000, 210000, 175000, 106736.75],
        backgroundColor: "rgba(7,80,86,.75)", borderColor: "#075056", borderWidth: 1 }] },
    { responsive: true, scales: { y: { ticks: { callback: function (v) { return "Rs " + (v / 1000).toFixed(0) + "K"; } } } }, plugins: { legend: { display: false } } });
  mk("c-pay", "doughnut",
    { labels: ["Credit Card", "UPI", "Cash", "Net Banking", "Wallet"],
      datasets: [{ data: [2100000, 1500000, 900000, 600000, 280000], backgroundColor: ["#71D8C5", "#324EB5", "#B97A1A", "#024879", "#075056"] }] },
    { responsive: true, plugins: { legend: { position: "bottom" } } });
  mk("c-rules", "bar",
    { labels: ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10", "R11", "R12"],
      datasets: [{ label: "Failing rows", data: [198, 159, 1851, 833, 718, 4636, 561, 623, 0, 75, 0, 175],
        backgroundColor: "rgba(50,78,181,.75)", borderColor: "#324EB5", borderWidth: 1 }] },
    { indexAxis: "y", responsive: true, plugins: { legend: { display: false } } });
  mk("c-trend", "line",
    { labels: ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
      datasets: [{ label: "Delivered sales Rs", data: [76606, 11496, 18348, 12800, 68856, 9848, 52468, 19846, 21970, 27190],
        borderColor: "#075056", backgroundColor: "rgba(113,216,197,.3)", tension: .35, fill: true }] },
    { responsive: true, scales: { y: { ticks: { callback: function (v) { return "Rs " + (v / 1000).toFixed(0) + "K"; } } } }, plugins: { legend: { display: false } } });
});
