import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: { 500: "#6366f1", 600: "#4f46e5" },
      },
    },
  },
  plugins: [],
};
export default config;
