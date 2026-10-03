(function () {
  if (typeof Chart === "undefined" || Chart.registry?.plugins?.get("marketChartPolish")) return;

  const FONT = '600 10px Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  const SMALL = '800 8px Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

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

  const plugin = {
    id: "marketChartPolish",

    // Intentionally does not mutate chart datasets. This layer must never be
    // able to prevent an existing chart from rendering.
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
      } catch (_) {
        // Never interfere with Chart.js rendering.
      }
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
      } catch (_) {
        // Never interfere with Chart.js rendering.
      }
    }
  };

  try {
    Chart.register(plugin);
    Chart.defaults.animation = { duration: 650, easing: "easeOutQuart" };
    if (Chart.defaults.transitions?.active) {
      Chart.defaults.transitions.active.animation = { duration: 220, easing: "easeOutCubic" };
    }
    if (Chart.defaults.plugins?.legend?.labels) {
      Chart.defaults.plugins.legend.labels.usePointStyle = true;
      Chart.defaults.plugins.legend.labels.padding = 14;
    }
    if (Chart.defaults.plugins?.tooltip) {
      Chart.defaults.plugins.tooltip.backgroundColor = "rgba(15,35,63,.96)";
      Chart.defaults.plugins.tooltip.titleColor = "#dce9f8";
      Chart.defaults.plugins.tooltip.bodyColor = "#ffffff";
      Chart.defaults.plugins.tooltip.borderColor = "rgba(255,255,255,.12)";
      Chart.defaults.plugins.tooltip.borderWidth = 1;
      Chart.defaults.plugins.tooltip.cornerRadius = 9;
      Chart.defaults.plugins.tooltip.padding = 10;
      Chart.defaults.plugins.tooltip.displayColors = true;
    }
  } catch (_) {
    // If the optional polish layer fails, the native Chart.js rendering remains intact.
  }
})();
