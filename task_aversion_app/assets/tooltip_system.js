(function () {
  const state = {
    tooltips: {},
    badge: null,
    enabled: true,
    lastTooltipEl: null,
  };

  const STYLE_ID = "tas-tooltip-style";
  const BADGE_ID = "tas-tooltip-badge";
  const TIP_ID = "tas-flyout-tooltip";

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${BADGE_ID} {
        position: fixed;
        bottom: 18px;
        right: 18px;
        background: #0ea5e9;
        color: #fff;
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        box-shadow: 0 10px 30px rgba(14,165,233,0.35);
        z-index: 99999;
        display: none;
        cursor: default;
        user-select: none;
      }
      #${TIP_ID} {
        position: fixed;
        max-width: 280px;
        background: #0f172a;
        color: #e2e8f0;
        padding: 10px 12px;
        border-radius: 10px;
        box-shadow: 0 20px 40px rgba(15, 23, 42, 0.45);
        z-index: 99998;
        font-size: 13px;
        line-height: 1.4;
        pointer-events: none;
        opacity: 0;
        transform: translateY(-4px);
        transition: opacity 120ms ease, transform 120ms ease;
      }
      #${TIP_ID}.show {
        opacity: 1;
        transform: translateY(0);
      }
    `;
    document.head.appendChild(style);
  }

  function ensureBadge() {
    if (state.badge) return state.badge;
    const badge = document.createElement("div");
    badge.id = BADGE_ID;
    badge.textContent = "Ctrl + Click for tips";
    document.body.appendChild(badge);
    state.badge = badge;
    return badge;
  }

  function setBadgeVisible(visible) {
    const badge = ensureBadge();
    badge.style.display = visible ? "block" : "none";
  }

  function hideTooltip() {
    const tip = document.getElementById(TIP_ID);
    if (tip) tip.remove();
    state.lastTooltipEl = null;
  }

  function randomTooltip(tooltips, key) {
    const list = tooltips[key] || [];
    if (!list.length) return null;
    const idx = Math.floor(Math.random() * list.length);
    return list[idx];
  }

  function showTooltip(event, el, tooltipId) {
    hideTooltip();
    const tipText = randomTooltip(state.tooltips, tooltipId) || "No tip available here yet.";
    const tip = document.createElement("div");
    tip.id = TIP_ID;
    tip.textContent = tipText;
    document.body.appendChild(tip);

    const pad = 12;
    let x = event.clientX + pad;
    let y = event.clientY + pad;

    const rect = tip.getBoundingClientRect();
    if (x + rect.width > window.innerWidth - 12) {
      x = event.clientX - rect.width - pad;
    }
    if (y + rect.height > window.innerHeight - 12) {
      y = event.clientY - rect.height - pad;
    }

    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;

    requestAnimationFrame(() => tip.classList.add("show"));
    state.lastTooltipEl = el;
  }

  function onClick(event) {
    if (!state.enabled) return;
    if (!event.ctrlKey) return;
    const el = event.target.closest("[data-tooltip-id]");
    if (!el) return;
    const id = el.getAttribute("data-tooltip-id");
    if (!id) return;
    showTooltip(event, el, id);
  }

  function setTooltips(tooltips) {
    state.tooltips = tooltips || {};
  }

  function setEnabled(enabled) {
    state.enabled = !!enabled;
    setBadgeVisible(enabled);
    if (!enabled) hideTooltip();
  }

  function init(options = {}) {
    injectStyles();
    if (options.tooltips) setTooltips(options.tooltips);
    setEnabled(options.enabled !== false);
    document.addEventListener("click", onClick);
  }

  // Expose minimal API
  window.TAS_TOOLTIP = {
    init,
    setTooltips,
    setEnabled,
    showBadge: () => setBadgeVisible(true),
    hideBadge: () => setBadgeVisible(false),
    hideTooltip,
  };
})();

