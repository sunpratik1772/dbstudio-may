/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0f',
        surface: '#13131c',
        card: '#15151f',
        elevated: '#1a1a25',
        border: 'rgba(255, 255, 255, 0.06)',
        'border-strong': 'rgba(255, 255, 255, 0.12)',
        muted: '#5d5d6c',
        'text-primary': '#f1f1f4',
        'text-secondary': '#9696a6',
        'text-tertiary': '#5d5d6c',
        primary: '#f1f1f4',
        accent: '#9b8cff',

        'port-dataframe': '#fbbf24',
        'port-object': '#22d3ee',
        'port-scalar': '#4ade80',
        'port-string-list': '#9b8cff',
        'port-workflow': '#f472b6',

        success: '#4ade80',
        danger: '#f87171',
        warning: '#fbbf24',
        info: '#60a5fa',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        heading: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      keyframes: {
        'blink-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        dashflow: {
          to: { strokeDashoffset: '-20' },
        },
      },
      animation: {
        'blink-soft': 'blink-soft 1.6s ease-in-out infinite',
        dashflow: 'dashflow 0.9s linear infinite',
      },
    },
  },
  plugins: [],
}
