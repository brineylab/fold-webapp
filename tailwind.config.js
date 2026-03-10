/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./jobs/templates/**/*.html",
    "./console/templates/**/*.html",
    "./templates/**/*.html",
  ],
  // Safelist dynamic component variants used in template partials
  // (e.g. ui-alert-{{ variant }}) that Tailwind's content scanner can't detect.
  safelist: [
    { pattern: /^ui-btn-(primary|secondary|danger|success|warning|outline|outline-danger|outline-warning|outline-success|ghost)$/ },
    { pattern: /^ui-alert-(info|warning|danger|success)$/ },
    { pattern: /^ui-badge-(secondary|success|warning|danger|info)$/ },
    { pattern: /^ui-status-(pending|running|completed|failed|cancelled)$/ },
    "ui-card-title",
    "ui-select",
    "ui-checkbox",
    "ui-input",
    "ui-text-muted",
    "ui-spinner",
    "ui-spinner-sm",
  ],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        border: "hsl(var(--ui-border) / <alpha-value>)",
        input: "hsl(var(--ui-input) / <alpha-value>)",
        ring: "hsl(var(--ui-ring) / <alpha-value>)",
        background: "hsl(var(--ui-background) / <alpha-value>)",
        foreground: "hsl(var(--ui-foreground) / <alpha-value>)",
        primary: {
          DEFAULT: "hsl(var(--ui-primary) / <alpha-value>)",
          foreground: "hsl(var(--ui-primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "hsl(var(--ui-secondary) / <alpha-value>)",
          foreground: "hsl(var(--ui-secondary-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT: "hsl(var(--ui-destructive) / <alpha-value>)",
          foreground: "hsl(var(--ui-destructive-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT: "hsl(var(--ui-muted) / <alpha-value>)",
          foreground: "hsl(var(--ui-muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--ui-accent) / <alpha-value>)",
          foreground: "hsl(var(--ui-accent-foreground) / <alpha-value>)",
        },
        card: {
          DEFAULT: "hsl(var(--ui-card) / <alpha-value>)",
          foreground: "hsl(var(--ui-card-foreground) / <alpha-value>)",
        },
        success: {
          DEFAULT: "hsl(var(--ui-success) / <alpha-value>)",
          foreground: "hsl(var(--ui-success-foreground) / <alpha-value>)",
        },
        warning: {
          DEFAULT: "hsl(var(--ui-warning) / <alpha-value>)",
          foreground: "hsl(var(--ui-warning-foreground) / <alpha-value>)",
        },
        info: {
          DEFAULT: "hsl(var(--ui-info) / <alpha-value>)",
          foreground: "hsl(var(--ui-info-foreground) / <alpha-value>)",
        },
      },
      borderRadius: {
        lg: "var(--ui-radius)",
        md: "calc(var(--ui-radius) - 2px)",
        sm: "var(--ui-radius-sm)",
      },
    },
  },
  corePlugins: {},
  plugins: [],
};
