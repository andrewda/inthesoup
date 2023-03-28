function ApproachBadge(props: any) {
  const approach = props.approach;
  const approachName = approach.name;

  // split by space and dash
  const type = approachName.split(/[\s-\/]/)[0];

  let color = 'bg-gray-100';
  switch (type) {
    case 'ILS':
      color = 'bg-blue-100';
      break;
    case 'RNAV':
      color = 'bg-green-100';
      break;
    case 'VOR':
      color = 'bg-yellow-100';
      break;
    case 'LOC':
      color = 'bg-red-100';
      break;
    case 'NDB':
      color = 'bg-purple-100';
      break;
    case 'GPS':
      color = 'bg-indigo-100';
      break;
    case 'LDA':
      color = 'bg-pink-100';
      break;
  }

  return (
    <span
      className={`inline-flex items-center rounded-full ${color} px-2.5 py-0.5 m-0.5 text-xs font-medium text-gray-800`}
      title={`FAF MSL: ${approach.faf.msl} ft, AGL: ${approach.faf.agl} ft`}
    >
      {approachName}
    </span>
  )
}

export default function Table(props: { forecasts: any[] }) {
  const forecasts = props.forecasts;

  const localTime = true;
  const localTimeOptions: Intl.DateTimeFormatOptions = {
    dateStyle: 'short',
    timeStyle: 'short',
  }

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="-mx-4 mt-8 sm:-mx-0">
        <table className="min-w-full divide-y divide-gray-300">
          <thead>
            <tr>
              <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-0">
                Time
              </th>
              <th
                scope="col"
                className="hidden px-3 py-3.5 text-left text-sm font-semibold text-gray-900 lg:table-cell"
              >
                Airport
              </th>
              <th
                scope="col"
                className="hidden px-3 py-3.5 text-left text-sm font-semibold text-gray-900 sm:table-cell"
              >
                Distance
              </th>
              <th
                scope="col"
                className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
              >
                Ceiling
              </th>
              <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900 max-w-sm">
                Approaches in IMC
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {forecasts?.map((forecast) => (
              <tr key={forecast.airport.icao + forecast.time}>
                <td className="w-44 py-4 pl-4 pr-3 text-sm font-medium text-gray-900 md:w-auto sm:pl-0">
                  {localTime ? new Date(forecast.time).toLocaleString(undefined, localTimeOptions) : new Date(forecast.time).toUTCString().replace('GMT', 'UTC')}
                  <dl className="font-normal lg:hidden">
                    <dt className="sr-only">Airport</dt>
                    <dd className="mt-1 truncate text-gray-700">{forecast.airport.icao}</dd>
                    <dt className="sr-only sm:hidden">Distance</dt>
                    <dd className="mt-1 truncate text-gray-500 sm:hidden">{Math.round(forecast.airport.distance)} nm</dd>
                  </dl>
                </td>
                <td className="hidden px-3 py-4 text-sm text-gray-500 lg:table-cell" title={forecast.airport.name}>{forecast.airport.icao}</td>
                <td className="hidden px-3 py-4 text-sm text-gray-500 sm:table-cell">{Math.round(forecast.airport.distance)} nm</td>
                <td
                  className="px-3 py-4 text-sm text-gray-500"
                  title={`LCB: ${forecast.weather.lowest_cloud_base ? forecast.weather.lowest_cloud_base + ' ft' : 'N/A'}`}
                >
                  {forecast.weather.ceiling} ft
                </td>
                <td className="px-3 py-4 text-gray-500 max-w-sm">
                  {forecast.approaches.sort((a: any, b: any) => a.name > b.name ? 1 : -1).map((i: any) => <ApproachBadge key={i.id} approach={i} />)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
