(function () {
  function init() {
    if (typeof Chart === "undefined") {
      setTimeout(init, 50);
      return;
    }

    const FONT = '600 10px Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    const SMALL = '800 8px Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    const boundCharts = new WeakSet();

    function roundedRect(ctx, x, y, w, h, r) {
      const radius = Math.max(0, Math.min(r, w / 2, h / 2));
      ctx.beginPath();
      ctx.moveTo(x + radius, y);
      ctx.arcTo(x + w, y, x + w, y + h, radius);
      ctx.arcTo(x + w, y + h, x, y + h, radius);
      ctx.arcTo(x, y + h, x, y, radius);
      ctx.arcTo(x, y, x + w, y, radius);
      ctx.closePath();
    }

    function finitePoint(meta, index) {
      const el = meta?.data?.[index];
      return el && Number.isFinite(el.x) && Number.isFinite(el.y) ? el : null;
    }

    function lastVisibleIndex(meta) {
      for (let i = (meta?.data?.length || 0) - 1; i >= 0; i -= 1) {
        const el = finitePoint(meta, i);
        if (el && !meta.data[i].hidden) return i;
      }
      return -1;
    }

    function displayValue(value) {
      if (!Number.isFinite(Number(value))) return "—";
      const n = Number(value);
      return Math.abs(n) >= 100
        ? n.toLocaleString("en-IN", { maximumFractionDigits: 0 })
        : n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
    }

    function safeColor(color, fallback = "#2563eb") {
      return typeof color === "string" ? color : fallback;
    }

    function clearTooltip(chart) {
      if (!chart?.tooltip) return;
      try {
        chart.tooltip.setActiveElements([], { x: 0, y: 0 });
        chart.update("none");
      } catch (_) {}
    }

    function showTooltipAtX(chart, clientX, clientY) {
      if (!chart?.tooltip || !chart.canvas) return;
      const rect = chart.canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const scaleX = chart.width / rect.width;
      const scaleY = chart.height / rect.height;
      const x = (clientX - rect.left) * scaleX;
      const y = (clientY - rect.top) * scaleY;
      const area = chart.chartArea;
      if (!area || x < area.left || x > area.right || y < area.top || y > area.bottom) {
        clearTooltip(chart);
        return;
      }

      let bestIndex = -1;
      let bestDistance = Infinity;
      (chart.data?.datasets || []).forEach((_, datasetIndex) => {
        const meta = chart.getDatasetMeta(datasetIndex);
        (meta?.data || []).forEach((el, index) => {
          if (!el || el.hidden || !Number.isFinite(el.x)) return;
          const distance = Math.abs(el.x - x);
          if (distance < bestDistance) {
            bestDistance = distance;
            bestIndex = index;
          }
        });
      });
      if (bestIndex < 0) return;

      const active = [];
      (chart.data?.datasets || []).forEach((_, datasetIndex) => {
        const meta = chart.getDatasetMeta(datasetIndex);
        const el = meta?.data?.[bestIndex];
        if (el && !el.hidden) active.push({ datasetIndex, index: bestIndex });
      });
      if (!active.length) return;

      try {
        chart.tooltip.setActiveElements(active, { x, y });
        chart.update("none");
      } catch (_) {}
    }

    // Direct mouse tracking is intentionally independent of the Chart.js plugin
    // event lifecycle. This covers charts created before or after this file.
    if (!window.__marketAnalysisChartMouseTracking) {
      window.__marketAnalysisChartMouseTracking = true;
      document.addEventListener("mousemove", event => {
        try {
          const canvas = event.target?.closest?.("canvas") ||
            document.elementFromPoint(event.clientX, event.clientY)?.closest?.("canvas");
          const chart = canvas ? Chart.getChart(canvas) : null;
          if (chart) showTooltipAtX(chart, event.clientX, event.clientY);
        } catch (_) {}
      }, true);

      document.addEventListener("mouseout", event => {
        try {
          const canvas = event.target?.closest?.("canvas");
          const chart = canvas ? Chart.getChart(canvas) : null;
          if (chart) clearTooltip(chart);
        } catch (_) {}
      }, true);
    }

    function bindMouseTracking(chart) {
      if (!chart?.canvas || boundCharts.has(chart)) return;
      boundCharts.add(chart);
      const target = chart.canvas.parentElement || chart.canvas;
      const move = event => showTooltipAtX(chart, event.clientX, event.clientY);
      const leave = () => clearTooltip(chart);
      target.addEventListener("mousemove", move, { passive: true });
      target.addEventListener("mouseleave", leave, { passive: true });
      chart.canvas.addEventListener("mousemove", move, { passive: true });
      chart.canvas.addEventListener("mouseleave", leave, { passive: true });
    }

    if (!Chart.registry?.plugins?.get("marketChartPolish")) {
      Chart.register({
        id: "marketChartPolish",
        afterInit(chart) {
          bindMouseTracking(chart);
        },
        beforeDraw(chart) {
          try {
            const area = chart.chartArea;
            if (!area || area.right <= area.left || area.bottom <= area.top) return;
            const ctx = chart.ctx;
            ctx.save();
            const gradient = ctx.createLinearGradient(0, area.top, 0, area.bottom);
            gradient.addColorStop(0, "rgba(248,251,255,.70)");
            gradient.addColorStop(.55, "rgba(255,255,255,.46)");
            gradient.addColorStop(1, "rgba(246,249,253,.72)");
            roundedRect(ctx, area.left, area.top, area.right - area.left, area.bottom - area.top, 10);
            ctx.fillStyle = gradient;
            ctx.fill();
            ctx.restore();
          } catch (_) {}
        },
        afterEvent(chart, args) {
          try {
            const event = args?.event;
            if (event?.type === "mouseout" || event?.type === "mouseleave") clearTooltip(chart);
          } catch (_) {}
        },
        afterDatasetsDraw(chart) {
          try {
            const area = chart.chartArea;
            if (!area) return;
            const ctx = chart.ctx;
            const lineMetas = (chart.data?.datasets || [])
              .map((ds, i) => ({ ds, meta: chart.getDatasetMeta(i) }))
              .filter(x => x.meta?.type === "line");
            if (!lineMetas.length) return;

            ctx.save();
            lineMetas.forEach(({ ds, meta }) => {
              const index = lastVisibleIndex(meta);
              const point = finitePoint(meta, index);
              if (!point) return;
              const color = safeColor(ds.borderColor);
              ctx.beginPath();
              ctx.arc(point.x, point.y, 7, 0, Math.PI * 2);
              ctx.fillStyle = "rgba(37,99,235,.10)";
              ctx.fill();
              ctx.beginPath();
              ctx.arc(point.x, point.y, 4.2, 0, Math.PI * 2);
              ctx.fillStyle = "#fff";
              ctx.fill();
              ctx.beginPath();
              ctx.arc(point.x, point.y, 3, 0, Math.PI * 2);
              ctx.fillStyle = color;
              ctx.fill();
            });

            if (lineMetas.length === 1) {
              const { ds, meta } = lineMetas[0];
              const index = lastVisibleIndex(meta);
              const point = finitePoint(meta, index);
              const value = Number(ds.data?.[index]);
              if (point && Number.isFinite(value)) {
                const color = safeColor(ds.borderColor);
                const text = displayValue(value);
                const label = chart.data.labels?.[index] ?? "Latest";
                ctx.font = FONT;
                const valueW = ctx.measureText(text).width;
                ctx.font = SMALL;
                const boxW = Math.max(58, valueW + 20);
                const boxH = 34;
                let x = point.x + 10;
                let y = point.y - boxH - 8;
                if (x + boxW > area.right - 4) x = point.x - boxW - 10;
                if (y < area.top + 4) y = point.y + 10;
                x = Math.max(area.left + 4, Math.min(x, area.right - boxW - 4));
                y = Math.max(area.top + 4, Math.min(y, area.bottom - boxH - 4));

                roundedRect(ctx, x, y, boxW, boxH, 8);
                ctx.fillStyle = "rgba(255,255,255,.96)";
                ctx.shadowColor = "rgba(15,23,42,.10)";
                ctx.shadowBlur = 10;
                ctx.shadowOffsetY = 3;
                ctx.fill();
                ctx.shadowColor = "transparent";
                ctx.strokeStyle = "rgba(37,99,235,.22)";
                ctx.lineWidth = 1;
                ctx.stroke();

                ctx.font = SMALL;
                ctx.fillStyle = color;
                ctx.fillText("LATEST", x + 9, y + 11);
                ctx.font = FONT;
                ctx.fillStyle = "#17355d";
                ctx.fillText(text, x + 9, y + 25);
                ctx.font = '500 8px Inter, system-ui, sans-serif';
                ctx.fillStyle = "#7b8da1";
                ctx.textAlign = "right";
                ctx.fillText(String(label), x + boxW - 8, y + 11);
                ctx.textAlign = "left";
              }
            }
            ctx.restore();
          } catch (_) {}
        }
      });
    }

    try {
      Object.values(Chart.instances || {}).forEach(bindMouseTracking);
    } catch (_) {}

    // Do NOT overwrite Chart.defaults.animation or transitions here. Chart.js
    // 4.5.1 treats those objects as internally resolved configuration; replacing
    // them at runtime caused core.animation.js "this._fn is not a function".
    // The tooltip itself is configured safely at defaults level only.
    try {
      if (Chart.defaults.plugins?.legend?.labels) {
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.padding = 14;
      }
      Chart.defaults.interaction = {
        ...(Chart.defaults.interaction || {}),
        mode: "index",
        intersect: false,
        axis: "x",
      };
      if (Chart.defaults.plugins?.tooltip) {
        Chart.defaults.plugins.tooltip.enabled = true;
        Chart.defaults.plugins.tooltip.mode = "index";
        Chart.defaults.plugins.tooltip.intersect = false;
        Chart.defaults.plugins.tooltip.backgroundColor = "rgba(15,35,63,.96)";
        Chart.defaults.plugins.tooltip.titleColor = "#dce9f8";
        Chart.defaults.plugins.tooltip.bodyColor = "#ffffff";
        Chart.defaults.plugins.tooltip.borderColor = "rgba(255,255,255,.12)";
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.cornerRadius = 9;
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.displayColors = true;
      }
    } catch (_) {}
  }

  init();
})();
