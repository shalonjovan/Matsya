'use client'

import dynamic from 'next/dynamic'

// Dynamically import App with ssr: false to guarantee Leaflet only loads in browser
const App = dynamic(() => import('../src/App'), {
  ssr: false,
  loading: () => (
    <div className="min-h-screen bg-[#070A0F] flex flex-col items-center justify-center p-6 text-slate-100">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-600 via-cyan-500 to-blue-600 flex items-center justify-center shadow-xl shadow-cyan-500/20 border border-cyan-400/30">
          <div className="w-8 h-8 border-3 border-white border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
      <div className="font-mono text-base font-bold tracking-wider text-white">
        INITIALIZING MATSYA DIGITAL TWIN...
      </div>
      <div className="font-mono text-xs text-slate-400 mt-2">
        Loading Chennai DEM, SWD Network & Simulation Matrix
      </div>
    </div>
  ),
})

export default function Page() {
  return <App />
}
