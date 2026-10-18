import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// MapLibre v6 builds its worker URL as `./maplibre-gl-worker.mjs` next to the module that creates it. Once Vite
// bundles the library into a hashed chunk that file is not emitted, the request for /assets/maplibre-gl-worker.mjs
// 404s and the basemap never draws. Emit the self-contained worker at exactly that path.
function maplibreWorker(): Plugin {
  return {
    name: 'maplibre-worker',
    apply: 'build',
    generateBundle() {
      const worker = fileURLToPath(new URL('./node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs', import.meta.url))
      this.emitFile({ type: 'asset', fileName: 'assets/maplibre-gl-worker.mjs', source: readFileSync(worker) })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), maplibreWorker()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // MapLibre v6 loads its worker relative to its own module; pre-bundling breaks that path.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  // VITE_API_MODE=http: the dev server forwards /api to the FastAPI service (`make api`).
  server: { proxy: { '/api': process.env.ECOZONE_API_URL ?? 'http://localhost:8000' } },
})
