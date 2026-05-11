// service-crm — shared shell behaviours.
//
// Intentionally tiny: clock, theme toggle, mobile nav drawer, service-
// worker registration. No framework, no build step. Everything degrades
// gracefully if JS is off — server-rendered Jinja still works.

(function () {
  "use strict";

  function onReady(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  function startClock() {
    var el = document.querySelector("[data-clock]");
    if (!el) return;
    function tick() {
      var d = new Date();
      var pad = function (n) { return String(n).padStart(2, "0"); };
      el.textContent =
        pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
    }
    tick();
    setInterval(tick, 1000);
  }

  function wireThemeToggle() {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next =
        document.documentElement.getAttribute("data-theme") === "dark"
          ? "light"
          : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        window.localStorage.setItem("scrm-theme", next);
      } catch (e) {
        // Storage blocked (private mode / Safari iframe). Theme still
        // applies for the current tab; just no persistence.
      }
    });
  }

  function wireModals() {
    // Close: any [data-modal-close="<id>"] hides the matching dialog.
    document.addEventListener("click", function (e) {
      var btn = e.target.closest && e.target.closest("[data-modal-close]");
      if (!btn) return;
      var modalId = btn.getAttribute("data-modal-close");
      var modal = document.getElementById(modalId);
      if (modal) modal.setAttribute("hidden", "");
    });

    // Open: any [data-modal-open="<id>"] removes ``hidden`` and focuses
    // the first interactive element inside the dialog.
    document.addEventListener("click", function (e) {
      var btn = e.target.closest && e.target.closest("[data-modal-open]");
      if (!btn) return;
      var modalId = btn.getAttribute("data-modal-open");
      var modal = document.getElementById(modalId);
      if (!modal) return;
      modal.removeAttribute("hidden");
      var first = modal.querySelector("input, select, textarea, button");
      if (first) first.focus();
    });

    // Dismiss on Escape.
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      var open = document.querySelector(".modal-backdrop:not([hidden])");
      if (open) open.setAttribute("hidden", "");
    });
  }

  function wireNavDrawer() {
    var app = document.querySelector(".app");
    var toggle = document.querySelector("[data-nav-toggle]");
    var scrim = document.querySelector("[data-nav-close]");
    if (!app || !toggle) return;
    function close() {
      app.setAttribute("data-nav", "closed");
      if (scrim) scrim.setAttribute("hidden", "");
    }
    function open() {
      app.setAttribute("data-nav", "open");
      if (scrim) scrim.removeAttribute("hidden");
    }
    toggle.addEventListener("click", function () {
      if (app.getAttribute("data-nav") === "open") close();
      else open();
    });
    if (scrim) scrim.addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    // The version is exposed on .app[data-version] by base.html so we can
    // pass it as ``?v=`` at registration. service-worker.js reads that
    // value to derive its CACHE_NAME, so a deploy with a new VERSION
    // invalidates every old cache.
    var app = document.querySelector(".app");
    var version = (app && app.getAttribute("data-version")) || "0.0.0";
    var swUrl = "/static/service-worker.js?v=" + encodeURIComponent(version);
    navigator.serviceWorker
      .register(swUrl, { scope: "/" })
      .then(function (reg) {
        // Skip-waiting + reload path so a bad SW can't pin users on stale
        // assets. We trigger this when the page detects a waiting worker.
        if (reg.waiting) {
          reg.waiting.postMessage({ type: "SKIP_WAITING" });
        }
        reg.addEventListener("updatefound", function () {
          var sw = reg.installing;
          if (!sw) return;
          sw.addEventListener("statechange", function () {
            if (sw.state === "installed" && navigator.serviceWorker.controller) {
              sw.postMessage({ type: "SKIP_WAITING" });
            }
          });
        });
      })
      .catch(function () {
        // Registration failures are best-effort; the app stays usable.
      });

    var reloaded = false;
    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (reloaded) return;
      reloaded = true;
      window.location.reload();
    });
  }

  onReady(function () {
    startClock();
    wireThemeToggle();
    wireNavDrawer();
    wireModals();
    registerServiceWorker();
  });
})();
