import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Design tokens and custom colours will be added in Phase 7 (frontend MVP)
      // following docs/07-frontend-wireframes.md §Design tokens
    },
  },
  plugins: [],
};

export default config;
