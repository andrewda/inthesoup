import Head from 'next/head'
import { useState, useEffect } from 'react'
import Table from './components/Table'

export default function Home() {
  const [airport, setAirport] = useState('')
  const [radius, setRadius] = useState('50')
  const [forecast, setForecast] = useState('metar')
  const [minCeiling, setMinCeiling] = useState('0')
  const [startHour, setStartHour] = useState('0')
  const [endHour, setEndHour] = useState('23')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const [loading, setLoading] = useState(false)
  const [forecasts, setForecasts] = useState<any[] | null>(null)
  const [darkMode, setDarkMode] = useState<'light' | 'dark' | 'system'>('system')

  // Handle dark mode
  useEffect(() => {
    const savedMode = localStorage.getItem('darkMode') as 'light' | 'dark' | 'system' | null
    if (savedMode) {
      setDarkMode(savedMode)
    }
  }, [])

  useEffect(() => {
    const root = window.document.documentElement
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches

    if (darkMode === 'system') {
      root.classList.toggle('dark', systemDark)
    } else {
      root.classList.toggle('dark', darkMode === 'dark')
    }

    localStorage.setItem('darkMode', darkMode)
  }, [darkMode])

  const handleSubmit = (e: any) => {
    e.preventDefault()

    if (loading) return;

    const endpoint = '/api/approaches';
    const params = new URLSearchParams({
      airport,
      radius,
      forecast,
    })

    const parsedMinCeiling = Math.round(parseInt(minCeiling) / 100)
    const parsedStartHour = parseInt(startHour)
    const parsedEndHour = parseInt(endHour)

    if (!isNaN(parsedMinCeiling)) {
      params.set('minCeiling', String(parsedMinCeiling))
    }

    if (!isNaN(parsedStartHour)) {
      params.set('startHour', String(parsedStartHour))
    }

    if (!isNaN(parsedEndHour)) {
      params.set('endHour', String(parsedEndHour))
    }

    setLoading(true)
    fetch(`${endpoint}?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          alert(data.error)
          setLoading(false)
          return
        }

        setForecasts(data)
        setLoading(false)
      })
  }

  return (
    <>
      <Head>
        <title>In the Soup</title>
        <meta name="description" content="Find nearby instrument approaches in IMC." />
      </Head>

      <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-900 transition-colors duration-300">
        {/* Header */}
        <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 shadow-sm transition-colors duration-300 flex-shrink-0">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-sky-500 flex items-center justify-center">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-slate-900 dark:text-white">In the Soup</h1>
                  <p className="text-sm text-slate-500 dark:text-slate-400">Find instrument approaches in IMC</p>
                </div>
              </div>

              {/* Dark Mode Toggle */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setDarkMode('light')}
                  className={`p-2 rounded-lg transition-colors ${darkMode === 'light' ? 'bg-sky-100 dark:bg-sky-900 text-sky-600 dark:text-sky-400' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
                  title="Light mode"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                </button>
                <button
                  onClick={() => setDarkMode('system')}
                  className={`p-2 rounded-lg transition-colors ${darkMode === 'system' ? 'bg-sky-100 dark:bg-sky-900 text-sky-600 dark:text-sky-400' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
                  title="System theme"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </button>
                <button
                  onClick={() => setDarkMode('dark')}
                  className={`p-2 rounded-lg transition-colors ${darkMode === 'dark' ? 'bg-sky-100 dark:bg-sky-900 text-sky-600 dark:text-sky-400' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
                  title="Dark mode"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 w-full">
          {/* Search Form */}
          <form onSubmit={handleSubmit} className="animate-fade-in">
            <div className="card p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Airport Input */}
                <div>
                  <label htmlFor="airport" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                    Airport
                  </label>
                  <input
                    type="text"
                    name="airport"
                    id="airport"
                    className="input-field"
                    placeholder="KSFO"
                    value={airport}
                    onChange={(e) => setAirport(e.target.value.toUpperCase())}
                  />
                </div>

                {/* Radius Select */}
                <div>
                  <label htmlFor="radius" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                    Radius
                  </label>
                  <select
                    id="radius"
                    name="radius"
                    className="select-field"
                    value={radius}
                    onChange={(e) => setRadius(e.target.value)}
                  >
                    <option value="50">50 nm</option>
                    <option value="100">100 nm</option>
                    <option value="250">250 nm</option>
                    <option value="500">500 nm</option>
                  </select>
                </div>

                {/* Weather Source Select */}
                <div>
                  <label htmlFor="forecast" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                    Weather Source
                  </label>
                  <select
                    id="forecast"
                    name="forecast"
                    className="select-field"
                    value={forecast}
                    onChange={(e) => setForecast(e.target.value)}
                  >
                    <option value="metar">METAR (current)</option>
                    <option value="nbh">NBH (24hr, 1hr period)</option>
                    <option value="nbs">NBS (72hr, 3hr period)</option>
                  </select>
                </div>

                {/* Search Button */}
                <div className="flex items-end">
                  <button
                    type="submit"
                    className="w-auto min-w-[100px] rounded-lg bg-sky-600 dark:bg-sky-500 py-3 px-6 text-sm font-semibold text-white shadow-sm hover:bg-sky-500 dark:hover:bg-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Searching...
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        Search
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Advanced Options Toggle */}
              <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowAdvanced((showAdvanced) => !showAdvanced)}
                >
                  {showAdvanced ? (
                    <>
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                      </svg>
                      Hide advanced options
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                      Show advanced options
                    </>
                  )}
                </button>
              </div>

              {/* Advanced Options */}
              {showAdvanced && (
                <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700 animate-slide-up">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="min_ceiling" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                        Min. Ceiling (ft AGL)
                      </label>
                      <input
                        type="number"
                        name="min_ceiling"
                        id="min_ceiling"
                        className="input-field"
                        placeholder="e.g., 500"
                        value={minCeiling}
                        onChange={(e) => setMinCeiling(e.target.value)}
                      />
                    </div>

                    <div>
                      <label htmlFor="start_hour" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                        Hour Range (Zulu)
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          name="start_hour"
                          id="start_hour"
                          className="input-field"
                          placeholder="Start"
                          value={startHour}
                          onChange={(e) => setStartHour(e.target.value)}
                        />
                        <input
                          type="number"
                          name="end_hour"
                          id="end_hour"
                          className="input-field"
                          placeholder="End"
                          value={endHour}
                          onChange={(e) => setEndHour(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </form>

          {/* Results Section */}
          <div className="mt-8">
            {loading && (
              <div className="card p-12 text-center animate-fade-in">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-sky-100 dark:bg-sky-900 mb-4">
                  <svg className="animate-spin w-8 h-8 text-sky-600 dark:text-sky-400" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-slate-900 dark:text-white">Searching for approaches...</h3>
                <p className="text-slate-500 dark:text-slate-400 mt-1">This may take a few moments</p>
              </div>
            )}

            {!loading && forecasts === null && (
              <div className="card p-12 text-center animate-fade-in">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-700 mb-4">
                  <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-slate-900 dark:text-white">Ready to search</h3>
                <p className="text-slate-500 dark:text-slate-400 mt-1">Enter an airport code above to find instrument approaches in IMC</p>
              </div>
            )}

            {!loading && forecasts?.length === 0 && (
              <div className="card p-12 text-center animate-fade-in">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 dark:bg-amber-900/30 mb-4">
                  <svg className="w-8 h-8 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-slate-900 dark:text-white">No approaches found</h3>
                <p className="text-slate-500 dark:text-slate-400 mt-1">Try adjusting your search criteria or expanding the radius</p>
              </div>
            )}

            {!loading && forecasts && forecasts.length > 0 && (
              <div className="animate-fade-in">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                    {forecasts.length} {forecasts.length === 1 ? 'result' : 'results'} found
                  </h2>
                </div>
                <Table forecasts={forecasts} />
              </div>
            )}
          </div>
        </main>

        {/* Footer - Fixed to bottom */}
        <footer className="mt-auto border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 transition-colors duration-300 flex-shrink-0">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
            <p className="text-center text-sm text-slate-500 dark:text-slate-400">
              Weather data provided by NOAA Aviation Weather Center
            </p>
          </div>
        </footer>
      </div>
    </>
  )
}
