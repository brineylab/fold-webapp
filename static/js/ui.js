/**
 * ui.js — shared UI interaction layer
 *
 * Covers: theme persistence, dropdown menus, alert dismissal.
 * All pages use the data-dropdown-* pattern (no Bootstrap JS dependency).
 */
(function () {
  "use strict";

  var THEME_KEY = "fold-webapp-theme";

  // ---- Theme management ------------------------------------------------

  function getSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function getSavedTheme() {
    return localStorage.getItem(THEME_KEY) || "auto";
  }

  function applyTheme(theme) {
    var resolved = theme === "auto" ? getSystemTheme() : theme;
    document.documentElement.setAttribute("data-bs-theme", resolved);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = resolved === "dark" ? "#09090b" : "#ffffff";
  }

  function saveTheme(theme) {
    localStorage.setItem(THEME_KEY, theme);
  }

  // React to OS theme changes while in auto mode
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", function () {
      if (getSavedTheme() === "auto") applyTheme("auto");
    });

  // ---- Dropdown management ------------------------------------------------

  function closeAllDropdowns() {
    document.querySelectorAll("[data-dropdown-menu]").forEach(function (menu) {
      menu.classList.add("hidden");
      var wrapper = menu.closest("[data-dropdown]");
      if (wrapper) {
        var trigger = wrapper.querySelector("[data-dropdown-trigger]");
        if (trigger) trigger.setAttribute("aria-expanded", "false");
      }
    });
  }

  // ---- DOM-ready setup --------------------------------------------------

  document.addEventListener("DOMContentLoaded", function () {
    // Theme selection buttons ([data-theme-value]) — shared across all pages
    document.querySelectorAll("[data-theme-value]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var theme = this.getAttribute("data-theme-value");
        applyTheme(theme);
        saveTheme(theme);
      });
    });

    // --- Tailwind dropdown toggles ---
    document.querySelectorAll("[data-dropdown-trigger]").forEach(function (trigger) {
      trigger.addEventListener("click", function (e) {
        e.stopPropagation();
        var wrapper = this.closest("[data-dropdown]");
        var menu = wrapper.querySelector("[data-dropdown-menu]");
        var isOpen = !menu.classList.contains("hidden");

        closeAllDropdowns();

        if (!isOpen) {
          menu.classList.remove("hidden");
          this.setAttribute("aria-expanded", "true");
        }
      });
    });

    // Close dropdowns on outside click
    document.addEventListener("click", function (e) {
      if (!e.target.closest("[data-dropdown]")) {
        closeAllDropdowns();
      }
    });

    // Close dropdowns on Escape
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeAllDropdowns();
    });

    // --- Alert dismissal ---
    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-dismiss-alert]");
      if (btn) {
        var alert = btn.closest("[role='alert']");
        if (alert) alert.remove();
      }
    });
  });

  // ---- Public API -------------------------------------------------------

  window.UI = {
    applyTheme: applyTheme,
    saveTheme: saveTheme,
    getSavedTheme: getSavedTheme,
  };
})();
