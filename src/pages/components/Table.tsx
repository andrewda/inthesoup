import { useState } from "react";

const colorMap: Record<string, string> = {
  'ILS': 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 ring-blue-200 dark:ring-blue-800',
  'RNAV': 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 ring-emerald-200 dark:ring-emerald-800',
  'VOR': 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 ring-amber-200 dark:ring-amber-800',
  'LOC': 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 ring-red-200 dark:ring-red-800',
  'NDB': 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 ring-purple-200 dark:ring-purple-800',
  'GPS': 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 ring-indigo-200 dark:ring-indigo-800',
  'LDA': 'bg-pink-50 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300 ring-pink-200 dark:ring-pink-800',
};

function ApproachBadge(props: any) {
  const approach = props.approach;
  const approachName: string = approach.name;
  const approachChart: string = approach.chart;

  // split by space and dash
  const type = approachName.split(/[\s-\/]/)[0];

  const colorClass = colorMap[type] ?? 'bg-slate-50 dark:bg-slate-700 text-slate-700 dark:text-slate-300 ring-slate-200 dark:ring-slate-600';

  const badge = (
    <span
      className={`inline-flex items-center rounded-full ${colorClass} px-3 py-1 text-xs font-medium ring-1 ring-inset transition-all duration-200 hover:shadow-sm cursor-help`}
      title={`FAF MSL: ${approach.faf.msl} ft, AGL: ${approach.faf.agl} ft`}
    >
      {approachName}
    </span>
  );

  if (approachChart) {
    return (
      <a href={`https://aeronav.faa.gov/d-tpp/${approachChart}`} target="_blank" rel="noopener noreferrer" className="hover:brightness-95 dark:hover:brightness-110 inline-block">
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
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
          <thead className="bg-slate-50 dark:bg-slate-800/50">
            <tr>
              <th
                scope="col"
                className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-slate-900 dark:text-white sm:pl-6 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors select-none"
                onClick={() => setLocalTime((localTime) => !localTime)}
              >
                <div className="flex items-center gap-1">
                  <span>Time</span>
                  <span className="text-xs font-normal text-slate-500 dark:text-slate-400">({localTime ? 'Local' : 'Zulu'})</span>
                  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                </div>
              </th>
              <th
                scope="col"
                className="hidden px-3 py-3.5 text-left text-sm font-semibold text-slate-900 dark:text-white lg:table-cell"
              >
                Airport
              </th>
              <th
                scope="col"
                className="hidden px-3 py-3.5 text-left text-sm font-semibold text-slate-900 dark:text-white sm:table-cell"
              >
                Distance
              </th>
              <th
                scope="col"
                className="px-3 py-3.5 text-left text-sm font-semibold text-slate-900 dark:text-white"
              >
                Ceiling
              </th>
              <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-slate-900 dark:text-white max-w-sm">
                Approaches
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-700 bg-white dark:bg-slate-800">
            {forecasts?.map((forecast) => (
              <tr key={forecast.airport.icao + forecast.time} className="hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                <td className="w-44 py-4 pl-4 pr-3 text-sm font-medium text-slate-900 dark:text-white md:w-auto sm:pl-6">
                  <div className="flex flex-col">
                    <span>{localTime ? toLocalTime(forecast.time) : toZuluTime(forecast.time)}</span>
                    <dl className="font-normal lg:hidden mt-1">
                      <dt className="sr-only">Airport</dt>
                      <dd className="text-slate-600 dark:text-slate-400">{forecast.airport.icao}</dd>
                      <dt className="sr-only sm:hidden">Distance</dt>
                      <dd className="text-slate-500 dark:text-slate-500 sm:hidden">{Math.round(forecast.airport.distance)} nm</dd>
                    </dl>
                  </div>
                </td>
                <td className="hidden px-3 py-4 text-sm text-slate-600 dark:text-slate-400 lg:table-cell" title={forecast.airport.name}>
                  <div className="flex flex-col">
                    <span className="font-medium text-slate-900 dark:text-white">{forecast.airport.icao}</span>
                    <span className="text-xs text-slate-500 dark:text-slate-500 truncate max-w-[200px]">{forecast.airport.name}</span>
                  </div>
                </td>
                <td className="hidden px-3 py-4 text-sm text-slate-600 dark:text-slate-400 sm:table-cell">
                  <div className="flex items-center gap-1">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span>{Math.round(forecast.airport.distance)} nm</span>
                  </div>
                </td>
                <td
                  className="px-3 py-4 text-sm"
                  title={`LCB: ${forecast.weather.lowest_cloud_base ? forecast.weather.lowest_cloud_base + ' ft' : 'N/A'}`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${parseInt(forecast.weather.ceiling) < 500 ? 'bg-red-500' : parseInt(forecast.weather.ceiling) < 1000 ? 'bg-amber-500' : 'bg-emerald-500'}`}></div>
                    <span className="font-medium text-slate-700 dark:text-slate-300">{forecast.weather.ceiling.toLocaleString()} ft</span>
                  </div>
                </td>
                <td className="px-3 py-4 text-slate-500 dark:text-slate-400 max-w-sm">
                  <div className="flex flex-wrap gap-1.5">
                    {forecast.approaches.sort((a: any, b: any) => a.name > b.name ? 1 : -1).map((i: any) => <ApproachBadge key={i.id} approach={i} />)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
