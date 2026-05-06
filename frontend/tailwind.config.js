/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
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
    },
  },
  plugins: [],
};
