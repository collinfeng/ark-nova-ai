import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The game server (python -m arknova.play.server) listens on 8765. Point ARKNOVA_API elsewhere
// (for example an SSH tunnel to the PC) to use a server running there.
const api = process.env.ARKNOVA_API ?? 'http://127.0.0.1:8765'

// base './': the page's files and its API calls are addressed relative to the page, so the same build works
// at the root of a server and under a path (example.com/ark-nova-ai/, where a reverse proxy strips the path).
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: { proxy: { '/api': api } },
})
