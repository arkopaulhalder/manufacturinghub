/* Analytics page rendering without external chart libraries. */
(function () {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    var el = byId(id);
    if (el) {
      el.textContent = value;
    }
  }

  function ensureCanvasSize(canvas) {
    var ratio = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    var width = Math.max(320, Math.floor(rect.width || canvas.clientWidth || 640));
    var height = Math.max(220, Math.floor(rect.height || canvas.clientHeight || 320));
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    var ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { ctx: ctx, width: width, height: height };
  }

  function drawBarChart(canvas, labels, values) {
    var setup = ensureCanvasSize(canvas);
    var ctx = setup.ctx;
    var width = setup.width;
    var height = setup.height;
    var margin = { top: 20, right: 16, bottom: 56, left: 46 };
    var innerW = width - margin.left - margin.right;
    var innerH = height - margin.top - margin.bottom;
    var maxV = Math.max.apply(null, values);
    if (maxV <= 0) {
      return;
    }

    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, margin.top + innerH);
    ctx.lineTo(margin.left + innerW, margin.top + innerH);
    ctx.stroke();

    var barGap = 10;
    var barW = Math.max(12, (innerW - barGap * (values.length + 1)) / values.length);

    for (var i = 0; i < values.length; i++) {
      var v = values[i];
      var h = (v / maxV) * (innerH - 8);
      var x = margin.left + barGap + i * (barW + barGap);
      var y = margin.top + innerH - h;

      ctx.fillStyle = "#93c5fd";
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 1.5;
      ctx.fillRect(x, y, barW, h);
      ctx.strokeRect(x, y, barW, h);

      ctx.fillStyle = "#374151";
      ctx.font = "11px Inter, Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(String(v), x + barW / 2, y - 6);

      var label = labels[i];
      if (label.length > 12) {
        label = label.slice(0, 12) + "...";
      }
      ctx.fillStyle = "#6b7280";
      ctx.fillText(label, x + barW / 2, margin.top + innerH + 18);
    }
  }

  function drawDonutChart(canvas, used, available) {
    var setup = ensureCanvasSize(canvas);
    var ctx = setup.ctx;
    var width = setup.width;
    var height = setup.height;
    var total = used + available;
    var cx = width / 2;
    var cy = height / 2 - 6;
    var radius = Math.min(width, height) * 0.28;
    var lineW = Math.max(18, Math.floor(radius * 0.35));
    var start = -Math.PI / 2;
    var usedAngle = total > 0 ? (used / total) * Math.PI * 2 : 0;
    var pct = total > 0 ? Math.round((used / total) * 100) : 0;

    ctx.clearRect(0, 0, width, height);
    ctx.lineWidth = lineW;

    ctx.beginPath();
    ctx.strokeStyle = "#e5e7eb";
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.beginPath();
    ctx.strokeStyle = "#3b82f6";
    ctx.arc(cx, cy, radius, start, start + usedAngle);
    ctx.stroke();

    ctx.fillStyle = "#1f2937";
    ctx.font = "700 28px Inter, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(String(pct) + "%", cx, cy + 3);
    ctx.fillStyle = "#6b7280";
    ctx.font = "12px Inter, Arial, sans-serif";
    ctx.fillText("Utilization", cx, cy + 22);
  }

  function drawLineChart(canvas, labels, datasets) {
    var setup = ensureCanvasSize(canvas);
    var ctx = setup.ctx;
    var width = setup.width;
    var height = setup.height;
    var margin = { top: 16, right: 16, bottom: 28, left: 42 };
    var innerW = width - margin.left - margin.right;
    var innerH = height - margin.top - margin.bottom;
    var colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
    var i;
    var j;
    var maxV = 0;

    for (i = 0; i < datasets.length; i++) {
      for (j = 0; j < datasets[i].data.length; j++) {
        if (datasets[i].data[j] > maxV) {
          maxV = datasets[i].data[j];
        }
      }
    }
    maxV = Math.max(1, maxV);

    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = "#e5e7eb";
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, margin.top + innerH);
    ctx.lineTo(margin.left + innerW, margin.top + innerH);
    ctx.stroke();

    for (i = 0; i < datasets.length; i++) {
      var ds = datasets[i];
      ctx.strokeStyle = colors[i % colors.length];
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (j = 0; j < ds.data.length; j++) {
        var x = margin.left + (j * innerW) / Math.max(1, labels.length - 1);
        var y = margin.top + innerH - (ds.data[j] / maxV) * (innerH - 8);
        if (j === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }
  }

  function hideChart(canvasId, emptyId) {
    var canvas = byId(canvasId);
    var empty = byId(emptyId);
    if (canvas) {
      canvas.style.display = "none";
    }
    if (empty) {
      empty.style.display = "flex";
    }
  }

  function render(payload) {
    var prodData = payload.production_volume || { labels: [], data: [] };
    var utilData = payload.machine_utilization || { labels: [], used: [], available: [] };
    var turnData = payload.inventory_turnover || { labels: [], datasets: [] };

    if (!prodData.labels.length) {
      hideChart("chartProductionVolume", "emptyProduction");
      setText("productionInsight", "No production output captured in the selected period.");
    } else {
      var maxQty = Math.max.apply(null, prodData.data);
      var maxIdx = prodData.data.indexOf(maxQty);
      setText("productionInsight", "Top product: " + prodData.labels[maxIdx] + " (" + maxQty + " units).");
      drawBarChart(byId("chartProductionVolume"), prodData.labels, prodData.data);
    }

    if (!utilData.labels.length) {
      hideChart("chartMachineUtil", "emptyUtilization");
      setText("utilizationInsight", "No scheduled workload found for available machines.");
      setText("utilizationMetrics", "Used: 0 hrs | Available: 0 hrs");
    } else {
      var totalUsed = utilData.used.reduce(function (a, b) { return a + b; }, 0);
      var totalAvail = utilData.available.reduce(function (a, b) { return a + b; }, 0);
      var totalCap = totalUsed + totalAvail;
      var utilPct = totalCap > 0 ? ((totalUsed / totalCap) * 100).toFixed(1) : "0.0";
      setText("utilizationInsight", "Overall utilization is " + utilPct + "% across " + utilData.labels.length + " machines.");
      setText("utilizationMetrics", "Used: " + totalUsed.toFixed(1) + " hrs | Available: " + totalAvail.toFixed(1) + " hrs");
      drawDonutChart(byId("chartMachineUtil"), totalUsed, totalAvail);
    }

    if (!turnData.datasets.length) {
      hideChart("chartInventoryTurnover", "emptyTurnover");
      setText("turnoverInsight", "No material consumption detected in the selected period.");
    } else {
      var totals = turnData.datasets.map(function (ds) {
        return { label: ds.label, total: ds.data.reduce(function (a, b) { return a + b; }, 0) };
      });
      totals.sort(function (a, b) { return b.total - a.total; });
      setText("turnoverInsight", "Highest consumption: " + totals[0].label + " (" + totals[0].total.toFixed(1) + " units).");
      drawLineChart(byId("chartInventoryTurnover"), turnData.labels, turnData.datasets);
    }
  }

  function onLoad() {
    fetch("/dashboard/analytics/data", { credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) {
          throw new Error("Failed to load analytics data");
        }
        return res.json();
      })
      .then(render)
      .catch(function () {
        setText("productionInsight", "Could not load chart data.");
        setText("utilizationInsight", "Could not load chart data.");
        setText("turnoverInsight", "Could not load chart data.");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", onLoad);
  } else {
    onLoad();
  }
})();
