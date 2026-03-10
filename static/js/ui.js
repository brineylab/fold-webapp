/**
 * ui.js — shared UI interaction layer
 *
 * Covers: theme persistence, dropdown menus, alert dismissal, dialogs.
 * All pages use data-* attribute patterns (no Bootstrap JS dependency).
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

  // ---- Dialog management ------------------------------------------------

  function openDialog(id) {
    var dialog = document.querySelector('[data-dialog="' + id + '"]');
    if (!dialog) return;
    dialog._returnFocus = document.activeElement;
    dialog.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    requestAnimationFrame(function () {
      var focusable = dialog.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length) focusable[0].focus();
    });
  }

  function closeDialog(dialog) {
    if (!dialog) return;
    dialog.classList.add("hidden");
    document.body.style.overflow = "";
    if (dialog._returnFocus) {
      dialog._returnFocus.focus();
      dialog._returnFocus = null;
    }
  }

  function getOpenDialog() {
    return document.querySelector('[data-dialog]:not(.hidden)');
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

    // Close dropdowns on outside click (skip if inside a dialog)
    document.addEventListener("click", function (e) {
      if (!e.target.closest("[data-dropdown]") && !e.target.closest("[data-dialog]")) {
        closeAllDropdowns();
      }
    });

    // Keyboard handling: Escape closes dialogs/dropdowns, Tab traps focus in dialogs
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        var dialog = getOpenDialog();
        if (dialog) {
          closeDialog(dialog);
          return;
        }
        closeAllDropdowns();
      }

      if (e.key === "Tab") {
        var dialog = getOpenDialog();
        if (!dialog) return;
        var focusable = dialog.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable.length) return;
        var first = focusable[0];
        var last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    });

    // Dialog open, close, and backdrop click
    document.addEventListener("click", function (e) {
      var openTrigger = e.target.closest("[data-dialog-open]");
      if (openTrigger) {
        e.preventDefault();
        openDialog(openTrigger.getAttribute("data-dialog-open"));
        return;
      }
      var closeBtn = e.target.closest("[data-dialog-close]");
      if (closeBtn) {
        e.preventDefault();
        closeDialog(closeBtn.closest("[data-dialog]"));
        return;
      }
      if (e.target.hasAttribute("data-dialog-backdrop")) {
        closeDialog(e.target.closest("[data-dialog]"));
      }
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
