/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./jobs/templates/**/*.html",
    "./console/templates/**/*.html",
    "./templates/**/*.html",
  ],
  darkMode: ["selector", '[data-bs-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
    },
  },
  corePlugins: {
    // Disable Tailwind's base reset during Bootstrap coexistence.
    // Re-enable after Bootstrap is fully removed (Phase 9).
    preflight: false,
  },
  plugins: [],
};
