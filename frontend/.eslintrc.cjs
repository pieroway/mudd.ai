module.exports = {
  root: true,
  env: {
    browser: true,
    es2020: true,
  },
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  ignorePatterns: ['dist', 'vite.config.ts'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-hooks'],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  rules: {
    ...require('eslint-plugin-react-hooks').configs.recommended.rules,
  },
}
