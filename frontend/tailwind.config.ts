import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0e1014", panel: "#161921", panel2: "#1d212b", edge: "#2b3040",
        gold: "#c9a85c", goldDim: "#8f783f", parchment: "#e8e2d0", muted: "#9aa0ad",
        blood: "#b4483c", mana: "#4a7bd0", leaf: "#5a9a6a",
      },
      fontFamily: { serif: ["Georgia", "Cambria", "'Times New Roman'", "serif"], sans: ["system-ui", "Segoe UI", "Roboto", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
