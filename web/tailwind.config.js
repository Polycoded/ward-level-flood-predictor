/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        flood: {
          50: '#fef7f0',
          100: '#fdede3',
          200: '#fadac7',
          300: '#f6b899',
          400: '#f18d5d',
          500: '#ed6b35',
          600: '#e04d1a',
          700: '#c03713',
          800: '#9a3014',
          900: '#7c2a13',
          950: '#411208',
        },
        risk: {
          very_low: '#10b981',
          low: '#84cc16',
          moderate: '#f59e0b',
          high: '#f97316',
          very_high: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Noto Sans', 'Noto Sans Tamil', 'sans-serif'],
      },
    },
  },
  plugins: [],
}