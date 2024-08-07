import { useState } from "react";

const colorMap: Record<string, string> = {
  'ILS': 'bg-blue-100',
  'RNAV': 'bg-green-100',
  'VOR': 'bg-yellow-100',
  'LOC': 'bg-red-100',
  'NDB': 'bg-purple-100',
  'GPS': 'bg-indigo-100',
  'LDA': 'bg-pink-100',
};

function ApproachBadge(props: any) {
  const approach = props.approach;
  const approachName: string = approach.name;
  const approachChart: string = approach.chart;

  // split by space and dash
  const type = approachName.split(/[\s-\/]/)[0];

  const colorClass = colorMap[type] ?? 'bg-gray-100';

  const badge = (
    <span
      className={`inline-flex items-center rounded-full ${colorClass} px-2.5 py-0.5 m-0.5 text-xs font-medium text-gray-800`}
      title={`FAF MSL: ${approach.faf.msl} ft, AGL: ${approach.faf.agl} ft`}
    >
      {approachName}
    </span>
  );

  if (approachChart) {
    return (
      <a href={`https://aeronav.faa.gov/d-tpp/${approachChart}`} target="_blank" className="hover:brightness-95 active:brightness-90">
        {badge}
      </a>
    )
  } else {
    return badge;
  }
}

function toLocalTime(time: string) {
  const localTimeOptions: Intl.DateTimeFormatOptions = {
    dateStyle: 'short',
    timeStyle: 'short',
  };

  return new Date(time).toLocaleString(undefined, localTimeOptions);
}

function toZuluTime(time: string) {
  const date = new Date(time);

  const month = (date.getUTCMonth() + 1).toString();
  const day = date.getUTCDate().toString();
  const year = date.getUTCFullYear().toString().slice(-2);
  const hour = date.getUTCHours().toString().padStart(2, '0');
  const minute = date.getUTCMinutes().toString().padStart(2, '0');

  const formattedDate = `${month}/${day}/${year}, ${hour}${minute}Z`;
  return formattedDate;
}

export default function Table(props: { forecasts: any[] }) {
  const [localTime, setLocalTime] = useState(true);

  const forecasts = props.forecasts;

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="-mx-4 mt-8 sm:-mx-0">
        <table className="min-w-full divide-y divide-gray-300">
          <thead>
            <tr>
              <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-0 cursor-pointer" onClick={() => setLocalTime((localTime) => !localTime)}>
                Time ({localTime ? 'Local' : 'Zulu'})
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
                  {localTime ? toLocalTime(forecast.time) : toZuluTime(forecast.time)}
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
