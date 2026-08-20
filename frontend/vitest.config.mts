import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    clearMocks: true,
    fileParallelism: false,
    maxWorkers: 1,
    // On Windows, the fork pool intermittently times out before jsdom has
    // initialized. Threads keep the same single-worker, serial semantics
    // while making the checked-in component suite reliably runnable.
    pool: 'threads',
  },
});
