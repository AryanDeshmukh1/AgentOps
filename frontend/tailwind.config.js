module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#1B4F72',
          light: '#2E86C1',
          dark: '#154360',
        },
        success: '#27AE60',
        warning: '#E67E22',
        danger: '#E74C3C',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};