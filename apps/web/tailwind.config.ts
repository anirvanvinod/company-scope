import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Inter loaded via next/font/google; --font-inter CSS variable set in layout.tsx
        sans: ["var(--font-inter)", "system-ui", "ui-sans-serif", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      // The stone palette gives us the warm neutral we want — no custom colors needed.
      // Semantic tokens are enforced through consistent class usage, not custom colors.
    },
  },
  plugins: [],
};

export default config;
