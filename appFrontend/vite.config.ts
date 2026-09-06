import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  // Served from /app/ on the production domain (see server/api.py / nginx),
  // not the domain root -- Vite otherwise emits absolute "/assets/..." paths
  // that 404 once mounted under a subpath.
  base: '/app/',

  plugins: [
    react(),
    tailwindcss(),
  ],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})