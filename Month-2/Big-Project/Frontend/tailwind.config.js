/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./hooks/**/*.{js,ts,jsx,tsx}",
    "./lib/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Used by the class "font-display-bold" throughout the app
        "display-bold": ["Outfit", "ui-sans-serif", "sans-serif"],
        display: ["Outfit", "ui-sans-serif", "sans-serif"],
        body: ["Inter", "ui-sans-serif", "sans-serif"],
      },
      colors: {
        // Deep navy / midnight scale, dark -> light text.
        // 950/900/800 = backgrounds & borders, 50..400 = text tones.
        // (The previous config had this scale inverted, which rendered
        //  near-black headings on a near-black background.)
        navy: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#131c31",
          950: "#0f172a",
        },
        // "cyan" intentionally NOT overridden: Tailwind's default cyan
        // (electric cyan, e.g. 500 = #06b6d4) matches the brand identity.
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(circle at 50% 0%, var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "aviation-gradient": "linear-gradient(180deg, #0f172a 0%, #1e293b 100%)",
      },
    },
  },
  plugins: [],
};
