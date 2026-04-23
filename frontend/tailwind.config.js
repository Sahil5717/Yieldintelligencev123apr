/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"],
        serif: ["Fraunces", "Georgia", "serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // Design system — matches the locked Exec Summary
        ink: "#0F1535",           // Primary dark navy
        "ink-2": "#1E2456",       // Hero gradient middle
        "ink-3": "#2D2C6E",       // Hero gradient end
        purple: {
          DEFAULT: "#7C5CFF",     // Accent
          deep: "#5B3FD9",
          tint: "#EEE5FF",
          ink: "#4C2889",
        },
        // Pillar colors
        revenue: { DEFAULT: "#047857", tint: "#DCFCE7" },
        cost: { DEFAULT: "#92400E", tint: "#FEF3D7" },
        cx: { DEFAULT: "#1E40AF", tint: "#DBEAFE" },
        risk: { DEFAULT: "#7C2D12", tint: "#FED7AA" },
        // Motion colors
        opt: { tint: "#DBEAFE", ink: "#1E3A8A" },
        trans: { tint: "#EEE5FF", ink: "#4C2889" },
        // Neutrals
        ash: {
          50: "#F5F6FA",
          100: "#EDEEF5",
          200: "#E5E7EF",
          300: "#D8DCE8",
          400: "#B5BACB",
          500: "#8C92AC",
          600: "#5C6280",
        },
        // Edit/override
        amber: {
          DEFAULT: "#B8893B",
          bg: "#FEF8E7",
          border: "#F9E2A6",
          deep: "#92400E",
          tint: "#FBF3E0",
          ink: "#8C6520",
        },
      },
      boxShadow: {
        "soft": "0 1px 2px rgba(15, 21, 53, .06)",
        "card": "0 2px 8px rgba(15, 21, 53, .04)",
      },
    },
  },
  plugins: [],
};
