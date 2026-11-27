import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// SVG backdrop filters (the liquid-glass lens) only render in Chromium; elsewhere glass stays frosted.
const brands = (navigator as Navigator & { userAgentData?: { brands: { brand: string }[] } }).userAgentData?.brands
if (brands?.some((b) => b.brand === 'Chromium')) document.documentElement.classList.add('liquid')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
