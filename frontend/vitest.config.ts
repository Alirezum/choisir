import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// UI tests are separate from the Node-run API client tests. Keep this include
// narrow so Vitest never picks up tests/**/*.test.mjs.
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'happy-dom',
    include: ['tests/ui/**/*.test.ts'],
    restoreMocks: true,
  },
})
