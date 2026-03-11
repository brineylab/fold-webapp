/**
 * ui.js — shared UI interaction layer
 *
 * Covers: theme persistence, dropdown menus, alert dismissal, dialogs.
 * All pages use data-* attribute patterns (no Bootstrap JS dependency).
 */
(function () {
  "use strict";

  var THEME_KEY = "fold-webapp-theme";
  var SIDEBAR_KEY = "fold-webapp-sidebar";
  var SIDEBAR_GROUPS_KEY = "fold-webapp-sidebar-groups";

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
    document.documentElement.setAttribute("data-theme", resolved);
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

  // ---- Sidebar management ----------------------------------------------

  function isDesktopViewport() {
    return window.matchMedia("(min-width: 1024px)").matches;
  }

  function getSavedSidebarState() {
    return localStorage.getItem(SIDEBAR_KEY) || "expanded";
  }

  function saveSidebarState(state) {
    localStorage.setItem(SIDEBAR_KEY, state);
  }

  function getSidebarGroupState() {
    try {
      return JSON.parse(localStorage.getItem(SIDEBAR_GROUPS_KEY) || "{}");
    } catch (err) {
      return {};
    }
  }

  function saveSidebarGroupState(state) {
    localStorage.setItem(SIDEBAR_GROUPS_KEY, JSON.stringify(state));
  }

  function isFocusableInput(element) {
    if (!element) return false;
    if (element.isContentEditable) return true;
    var tag = element.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  }

  function setBodyScrollLocked(locked) {
    document.body.style.overflow = locked ? "hidden" : "";
  }

  function applySidebarState(options) {
    var sidebar = document.querySelector("[data-sidebar]");
    var backdrop = document.querySelector("[data-sidebar-backdrop]");
    var toggles = document.querySelectorAll("[data-sidebar-toggle]");
    if (!sidebar) return;

    var settings = options || {};
    var desktop = isDesktopViewport();
    var collapsed = !!settings.collapsed;
    var mobileOpen = !!settings.mobileOpen;

    sidebar.classList.toggle("ui-sidebar-collapsed", desktop && collapsed);
    sidebar.classList.toggle("open", !desktop && mobileOpen);
    document.body.setAttribute("data-sidebar-collapsed", desktop && collapsed ? "true" : "false");

    if (backdrop) {
      backdrop.classList.toggle("hidden", desktop || !mobileOpen);
    }

    setBodyScrollLocked(!desktop && mobileOpen);

    toggles.forEach(function (toggle) {
      var mobileToggle = toggle.classList.contains("ui-sidebar-mobile-toggle");
      var expanded = mobileToggle ? mobileOpen : !collapsed;
      toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      toggle.setAttribute(
        "aria-label",
        mobileToggle
          ? (mobileOpen ? "Close sidebar" : "Open sidebar")
          : (collapsed ? "Expand sidebar" : "Collapse sidebar")
      );
    });
  }

  function setGroupCollapsed(group, collapsed) {
    var trigger = group.querySelector("[data-sidebar-collapsible-trigger]");
    var content = group.querySelector("[data-sidebar-collapsible-content]");
    group.classList.toggle("collapsed", collapsed);
    if (trigger) {
      trigger.setAttribute("aria-expanded", collapsed ? "false" : "true");
    }
    if (content) {
      content.setAttribute("aria-hidden", collapsed ? "true" : "false");
    }
  }

  // ---- DOM-ready setup --------------------------------------------------

  document.addEventListener("DOMContentLoaded", function () {
    document.documentElement.setAttribute("data-sidebar-ready", "true");
    var preloadSidebarState = document.getElementById("sidebar-preload-state");
    if (preloadSidebarState) {
      preloadSidebarState.remove();
    }
    var sidebar = document.querySelector("[data-sidebar]");
    var backdrop = document.querySelector("[data-sidebar-backdrop]");
    var lastSidebarToggle = null;
    var sidebarState = {
      collapsed: getSavedSidebarState() === "collapsed",
      mobileOpen: false,
    };

    function closeSidebar() {
      if (!sidebarState.mobileOpen) return;
      sidebarState.mobileOpen = false;
      applySidebarState(sidebarState);
      if (lastSidebarToggle) {
        lastSidebarToggle.focus();
      }
    }

    function openSidebar() {
      if (sidebarState.mobileOpen) return;
      sidebarState.mobileOpen = true;
      applySidebarState(sidebarState);
      requestAnimationFrame(function () {
        var firstLink = sidebar.querySelector(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (firstLink) firstLink.focus();
      });
    }

    function toggleSidebar(toggleSource) {
      if (!sidebar) return;
      lastSidebarToggle = toggleSource || document.activeElement;
      if (isDesktopViewport()) {
        sidebarState.collapsed = !sidebarState.collapsed;
        saveSidebarState(sidebarState.collapsed ? "collapsed" : "expanded");
      } else if (sidebarState.mobileOpen) {
        closeSidebar();
        return;
      } else {
        openSidebar();
        return;
      }
      applySidebarState(sidebarState);
    }

    if (sidebar) {
      applySidebarState(sidebarState);

      document.querySelectorAll("[data-sidebar-toggle]").forEach(function (toggle) {
        toggle.addEventListener("click", function () {
          toggleSidebar(this);
        });
      });

      if (backdrop) {
        backdrop.addEventListener("click", closeSidebar);
      }

      window.addEventListener("resize", function () {
        if (isDesktopViewport()) {
          sidebarState.mobileOpen = false;
        }
        applySidebarState(sidebarState);
      });

      var storedGroups = getSidebarGroupState();
      document.querySelectorAll("[data-sidebar-collapsible]").forEach(function (group) {
        var trigger = group.querySelector("[data-sidebar-collapsible-trigger]");
        var groupName = group.getAttribute("data-sidebar-group");
        var initialCollapsed = group.getAttribute("data-sidebar-default-collapsed") === "true";

        if (groupName && Object.prototype.hasOwnProperty.call(storedGroups, groupName)) {
          initialCollapsed = !!storedGroups[groupName];
        }

        setGroupCollapsed(group, initialCollapsed);

        if (trigger) {
          trigger.addEventListener("click", function () {
            var collapsed = !group.classList.contains("collapsed");
            setGroupCollapsed(group, collapsed);
            if (groupName) {
              storedGroups[groupName] = collapsed;
              saveSidebarGroupState(storedGroups);
            }
          });
        }
      });
    }

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
        if (sidebarState.mobileOpen) {
          closeSidebar();
          return;
        }
        closeAllDropdowns();
      }

      if (
        (e.metaKey || e.ctrlKey) &&
        !e.shiftKey &&
        !e.altKey &&
        e.key &&
        e.key.toLowerCase() === "b" &&
        isDesktopViewport() &&
        !getOpenDialog() &&
        !isFocusableInput(document.activeElement)
      ) {
        e.preventDefault();
        toggleSidebar(document.activeElement);
        return;
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

    document.addEventListener("click", function (e) {
      if (!sidebar || isDesktopViewport()) return;
      if (sidebarState.mobileOpen && e.target.closest("[data-sidebar] a[href]")) {
        closeSidebar();
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
