import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          700: "#1e293b",
          800: "#0f172a",
          900: "#020617",
          950: "#000408",
        },
        panel: {
          DEFAULT: "#131c2d",
          hover: "#1b2740",
          active: "#243352",
        },
        accent: {
          DEFAULT: "#5aa0ff",
          hover: "#7bb3ff",
          muted: "#3a5a8a",
        },
        success: "#3fb950",
        warning: "#d29922",
        danger: "#f85149",
        info: "#58a6ff",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
      },
      borderRadius: {
        card: "12px",
      },
    },
  },
  plugins: [],
};
export default config;
