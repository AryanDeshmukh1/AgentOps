export default {
  rootDir: ".",
  testEnvironment: "node",
  testMatch: ["<rootDir>/**/*.test.js"],
  transform: {},
  setupFiles: ["<rootDir>/setup.js"],
  verbose: true,
  testTimeout: 10000,
};