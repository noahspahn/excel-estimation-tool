import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import { execSync } from 'child_process'

const baseVersionPath = path.resolve(__dirname, 'version.json')
let baseVersion = '0.0.0'
try {
  const raw = fs.readFileSync(baseVersionPath, 'utf-8')
  const parsed = JSON.parse(raw)
  if (parsed?.version) baseVersion = String(parsed.version)
} catch {}

let gitHash = 'nogit'
try {
  gitHash = execSync('git rev-parse --short HEAD', { cwd: path.resolve(__dirname, '..') })
    .toString()
    .trim()
} catch {}

const appVersion = `${baseVersion}+g${gitHash}`
const devBackendOrigin = process.env.VITE_DEV_BACKEND_ORIGIN || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  server: {
    host: '127.0.0.1',
    port: 3000,
    proxy: {
      '/api-next': {
        target: devBackendOrigin,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-next/, ''),
      },
      '/api': {
        target: devBackendOrigin,
        changeOrigin: true,
      },
    },
  },
})
