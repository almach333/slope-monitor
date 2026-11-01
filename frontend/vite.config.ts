import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Forward /api requests to the FastAPI backend, so the browser only talks
    // to one origin during development. 127.0.0.1 (not "localhost") avoids a
    // ~2 s IPv6 delay on Windows.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
