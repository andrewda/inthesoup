import Head from 'next/head'
import { useState } from 'react'
import Table from './components/Table'
import { start } from 'repl'

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

      <div className="min-h-full">
        <div className="py-10">
          <header>
            <div className="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
              <h1 className="text-3xl font-bold leading-tight tracking-tight text-gray-900">In the Soup ☁️</h1>
            </div>
          </header>

          <main>
            <form onSubmit={handleSubmit}>
              <div className="mt-10 grid grid-cols-1 gap-y-4 gap-x-6 max-w-6xl sm:grid-cols-8 px-6 lg:px-8 lg:mx-auto">
                <div className="col-span-2">
                  <label htmlFor="airport" className="block text-sm font-medium leading-6 text-gray-900">
                    Airport
                  </label>
                  <div className="mt-2">
                    <input
                      type="text"
                      name="airport"
                      id="airport"
                      className="block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                      placeholder="KSFO"
                      value={airport}
                      onChange={(e) => setAirport(e.target.value.toUpperCase())}
                    />
                  </div>
                </div>

                <div className="col-span-2">
                  <label htmlFor="radius" className="block text-sm font-medium leading-6 text-gray-900">
                    Radius
                  </label>
                  <div className="mt-2">
                    <select
                      id="radius"
                      name="radius"
                      className="block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:max-w-xs sm:text-sm sm:leading-6"
                      value={radius}
                      onChange={(e) => setRadius(e.target.value)}
                    >
                      <option value="50">50 nm</option>
                      <option value="100">100 nm</option>
                      <option value="250">250 nm</option>
                      <option value="500">500 nm</option>
                    </select>
                  </div>
                </div>

                <div className="col-span-2">
                  <label htmlFor="forecast" className="block text-sm font-medium leading-6 text-gray-900">
                    Weather Source
                  </label>
                  <div className="mt-2">
                    <select
                      id="forecast"
                      name="forecast"
                      className="block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:max-w-xs sm:text-sm sm:leading-6"
                      value={forecast}
                      onChange={(e) => setForecast(e.target.value)}
                    >
                      <option value="metar">METAR (current)</option>
                      <option value="nbh">NBH (24hr, 1hr period)</option>
                      <option value="nbs">NBS (72hr, 3hr period)</option>
                    </select>
                  </div>
                </div>

                <div className="col-span-2 flex items-end">
                  <button
                    type="submit"
                    className="w-full h-10 rounded-md bg-indigo-600 py-2 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    disabled={loading}
                  >
                    Search
                  </button>
                </div>
              </div>

              <div className="mt-4 max-w-6xl px-6 lg:px-8 lg:mx-auto">
                <p className="text-sm text-gray-500 select-none cursor-pointer" onClick={() => setShowAdvanced((showAdvanced) => !showAdvanced)}>
                  {showAdvanced ? 'Hide' : 'Show'} advanced options
                </p>
              </div>

              {showAdvanced && (
                <div className="mt-2 grid grid-cols-1 gap-y-4 gap-x-6 max-w-6xl sm:grid-cols-8 px-6 lg:px-8 lg:mx-auto">
                  <div className="col-span-2">
                    <label htmlFor="min_ceiling" className="block text-sm font-medium leading-6 text-gray-900">
                      Min. Ceiling (ft AGL)
                    </label>
                    <div className="mt-2">
                      <input
                        type="number"
                        name="min_ceiling"
                        id="min_ceiling"
                        className="block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                        placeholder=""
                        value={minCeiling}
                        onChange={(e) => setMinCeiling(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="col-span-2">
                    <label htmlFor="start_hour" className="block text-sm font-medium leading-6 text-gray-900">
                      Hour Range (Zulu)
                    </label>
                    <div className="mt-2 flex gap-2">
                      <input
                        type="number"
                        name="start_hour"
                        id="start_hour"
                        className="block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                        placeholder="Start Hour"
                        value={startHour}
                        onChange={(e) => setStartHour(e.target.value)}
                      />
                      <input
                        type="number"
                        name="end_hour"
                        id="end_hour"
                        className="block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                        placeholder="End Hour"
                        value={endHour}
                        onChange={(e) => setEndHour(e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              )}
            </form>

            <div className="mx-auto max-w-7xl sm:px-6 lg:px-8">
              {loading && <h2 className="mt-10 text-center">Loading...</h2>}
              {!loading && forecasts === null && <h2 className="mt-10 text-center">Please enter a query to get started.</h2>}
              {!loading && forecasts?.length === 0 && <h2 className="mt-10 text-center">No approaches in IMC found. Please try another query!</h2>}
              {!loading && forecasts && forecasts?.length > 0 && <Table forecasts={forecasts} /> }
            </div>
          </main>
        </div>
      </div>
    </>
  )
}
