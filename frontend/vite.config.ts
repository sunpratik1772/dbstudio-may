import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Keep aliases here in sync with compilerOptions.paths in tsconfig.json.
// The principle is: every cross-cutting concern gets its own short alias
// so features can be moved around without waves of import updates.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@nodes': path.resolve(__dirname, 'src/nodes'),
      '@store': path.resolve(__dirname, 'src/store'),
      '@services': path.resolve(__dirname, 'src/services'),
      '@components': path.resolve(__dirname, 'src/components'),
      '@styles': path.resolve(__dirname, 'src/styles'),
      '@types': path.resolve(__dirname, 'src/types'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
