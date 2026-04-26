/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Workflow-Forge surface tokens (dark default)
        bg: '#050505',
        surface: '#0B0B0C',
        card: '#1A1A1C',
        elevated: '#212124',
        border: '#27272A',
        'border-strong': '#3F3F46',
        muted: '#71717A',
        'text-primary': '#FAFAFA',
        'text-secondary': '#A1A1AA',
        'text-tertiary': '#71717A',
        primary: '#FAFAFA',
        accent: '#F5A623',

        // Port-type tokens
        'port-dataframe': '#F5A623',
        'port-object': '#00E5FF',
        'port-scalar': '#10B981',
        'port-string-list': '#A78BFA',
        'port-workflow': '#F472B6',

        // Status
        success: '#10B981',
        danger: '#EF4444',
        warning: '#F59E0B',
        info: '#3B82F6',
      },
      fontFamily: {
        sans: ['Manrope', 'system-ui', 'sans-serif'],
        heading: ['Chivo', 'system-ui', 'sans-serif'],
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
