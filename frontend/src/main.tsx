import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Self-hosted fonts (OFL-1.1): nothing is fetched from a font service at runtime.
import '@fontsource/atkinson-hyperlegible-next/400.css'
import '@fontsource/atkinson-hyperlegible-next/500.css'
import '@fontsource/atkinson-hyperlegible-next/600.css'
import '@fontsource/atkinson-hyperlegible-next/700.css'
import '@fontsource/atkinson-hyperlegible-mono/400.css'
import '@fontsource/atkinson-hyperlegible-mono/500.css'
import '@fontsource/source-serif-4/600.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
