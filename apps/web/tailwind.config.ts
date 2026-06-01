import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--ts-text)",
        signal: "var(--ts-accent)",
        amberline: "var(--ts-attention)",
        surface: {
          DEFAULT: "var(--ts-surface)",
          muted: "var(--ts-surface-muted)",
          success: "var(--ts-surface-success)",
          warning: "var(--ts-surface-warning)",
          danger: "var(--ts-surface-danger)",
        },
        muted: "var(--ts-text-muted)",
        border: {
          DEFAULT: "var(--ts-border)",
          strong: "var(--ts-border-strong)",
        },
        success: {
          DEFAULT: "var(--ts-success)",
          border: "var(--ts-success-border)",
        },
        warning: {
          DEFAULT: "var(--ts-warning)",
          border: "var(--ts-warning-border)",
        },
        danger: {
          DEFAULT: "var(--ts-danger)",
          border: "var(--ts-danger-border)",
        },
        info: {
          DEFAULT: "var(--ts-info)",
          border: "var(--ts-info-border)",
        },
        chart: {
          1: "var(--ts-chart-1)",
          2: "var(--ts-chart-2)",
          3: "var(--ts-chart-3)",
          4: "var(--ts-chart-4)",
          5: "var(--ts-chart-5)",
        },
      },
      boxShadow: {
        soft: "var(--ts-shadow-soft)",
      },
      transitionDuration: {
        fast: "var(--ts-duration-fast)",
        DEFAULT: "var(--ts-duration)",
      },
      transitionTimingFunction: {
        product: "var(--ts-ease-out)",
      },
      borderRadius: {
        product: "0.5rem",
      },
    },
  },
  plugins: [],
};

export default config;
