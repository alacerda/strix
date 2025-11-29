/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      animation: {
        slideIn: 'slideIn 0.3s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      colors: {
        primary: {
          green: '#22c55e',
          'green-dark': '#16a34a',
        },
        bg: {
          primary: '#0f172a',
          secondary: '#1e293b',
          tertiary: '#334155',
        },
        text: {
          primary: '#f1f5f9',
          secondary: '#cbd5e1',
          muted: '#94a3b8',
        },
        border: {
          color: '#475569',
        },
        success: '#22c55e',
        warning: '#fbbf24',
        error: '#dc2626',
        info: '#0284c7',
        critical: '#dc2626',
        high: '#ea580c',
        medium: '#d97706',
        low: '#65a30d',
        terminal: '#22c55e',
        browser: '#06b6d4',
        python: '#3b82f6',
        'file-edit': '#10b981',
        proxy: '#06b6d4',
        'agents-graph': '#fbbf24',
        thinking: '#a855f7',
        'web-search': '#22c55e',
        finish: '#dc2626',
        reporting: '#ea580c',
      },
    },
  },
  plugins: [],
};

