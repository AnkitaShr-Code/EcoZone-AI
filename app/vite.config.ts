import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // MapLibre v6 loads its worker relative to its own module; pre-bundling breaks that path.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  // VITE_API_MODE=http: the dev server forwards /api to the FastAPI service (`make api`).
  server: { proxy: { '/api': process.env.ECOZONE_API_URL ?? 'http://localhost:8000' } },
})
