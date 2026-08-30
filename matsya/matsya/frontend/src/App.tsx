import { useState } from 'react'

function App() {
  const [view, setView] = useState<'select' | 'map'>('select')
  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <header className="flex gap-4 mb-4">
        <h1 className="text-2xl font-bold">MATSYA</h1>
        <nav className="flex gap-2">
          <button
            onClick={() => setView('select')}
            className={`px-3 py-1 rounded ${view === 'select' ? 'bg-blue-600 text-white' : 'bg-white border'}`}
          >
            Select Simulation
          </button>
          <button
            onClick={() => setView('map')}
            className={`px-3 py-1 rounded ${view === 'map' ? 'bg-blue-600 text-white' : 'bg-white border'}`}
          >
            Map
          </button>
        </nav>
      </header>
      {view === 'select' ? (
        <div className="p-6 bg-white rounded shadow">Select Simulation — hello</div>
      ) : (
        <div className="p-6 bg-white rounded shadow">Map — hello</div>
      )}
    </div>
  )
}

export default App
