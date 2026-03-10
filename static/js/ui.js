/**
 * ui.js — shared UI interaction layer
 *
 * Phase 1: theme persistence (moved from inline script)
 * Future: dropdowns, modals, disclosure toggles, submit busy states
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

  // ---- DOM-ready setup --------------------------------------------------

  document.addEventListener("DOMContentLoaded", function () {
    // Theme selection buttons ([data-theme-value])
    document.querySelectorAll("[data-theme-value]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var theme = this.getAttribute("data-theme-value");
        applyTheme(theme);
        saveTheme(theme);
      });
    });

    // Nested theme submenu toggle (Bootstrap dropdown period)
    var toggle = document.getElementById("themeSubmenuToggle");
    var submenu = document.getElementById("themeSubmenu");

    if (toggle && submenu) {
      toggle.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        submenu.classList.toggle("show");
      });

      document.addEventListener("click", function (e) {
        if (!toggle.contains(e.target) && !submenu.contains(e.target)) {
          submenu.classList.remove("show");
        }
      });

      var parentDropdown = toggle.closest(".dropdown");
      if (parentDropdown) {
        parentDropdown.addEventListener("hidden.bs.dropdown", function () {
          submenu.classList.remove("show");
        });
      }
    }
  });

  // ---- Public API (available to other scripts) --------------------------

  window.UI = {
    applyTheme: applyTheme,
    saveTheme: saveTheme,
    getSavedTheme: getSavedTheme,
  };
})();
