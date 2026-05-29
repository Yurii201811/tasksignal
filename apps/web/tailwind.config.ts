import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        signal: "#0f766e",
        amberline: "#d97706"
      },
      boxShadow: {
        soft: "0 14px 35px rgba(23, 32, 51, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;

