/**
 * Lightweight unit-test setup for pure TypeScript logic (e.g. the fall
 * detector). Component/native tests would use jest-expo instead.
 */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/*.test.ts'],
};
