import { Fragment, useState } from "react";
import { AirportGroup, formatPeriod, formatCloudBases, formatGapDuration } from "../lib/forecastGroups";

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

export default function Table({ groups }: { groups: AirportGroup[] }) {
  const [localTime, setLocalTime] = useState(true);
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-end gap-2 text-sm text-slate-600 dark:text-slate-400">
        <span>Times shown in</span>
        <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 p-1" role="group" aria-label="Time zone">
          {[true, false].map(local => (
            <button key={String(local)} type="button" aria-pressed={localTime === local}
              onClick={() => setLocalTime(local)}
              className={`rounded-md px-3 py-1 font-medium ${localTime === local ? 'bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-white' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}>
              {local ? 'Local' : 'Zulu'}
            </button>
          ))}
        </div>
      </div>
      {groups.map(({ airport, periods }) => (
        <section key={airport.icao} aria-labelledby={`airport-${airport.icao}`} className="card overflow-hidden">
          <div className="flex items-center justify-between gap-4 px-4 py-4 sm:px-6 border-b border-slate-200 dark:border-slate-700">
            <div>
              <h3 id={`airport-${airport.icao}`} className="text-lg font-semibold text-slate-900 dark:text-white">{airport.icao}</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">{airport.name}</p>
            </div>
            <span className="shrink-0 text-sm text-slate-600 dark:text-slate-400">{Math.round(airport.distance)} nm</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full table-fixed text-left text-sm">
              <caption className="sr-only">{airport.icao} approach weather, {localTime ? 'local' : 'Zulu'} time</caption>
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-900 dark:text-white">
                <tr>
                  <th scope="col" className="w-32 sm:w-56 py-3 pl-4 pr-2 sm:pl-6">Time</th>
                  <th scope="col" className="w-24 sm:w-32 px-2 py-3">Ceiling</th>
                  <th scope="col" className="px-2 py-3 pr-4 sm:pr-6">Approaches</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period, index) => {
                  const label = formatPeriod(period.start, period.end, localTime);
                  return (
                    <Fragment key={period.start}>
                    {period.gapBefore && (
                      <tr>
                        <td colSpan={3} className="p-0">
                          <div className="relative flex h-5 items-center pl-4 sm:pl-6">
                            <svg aria-hidden="true" className="absolute left-0 top-1/2 -translate-y-1/2 block h-3 w-full text-slate-300 dark:text-slate-500" width="100%" height="12">
                              <defs>
                                <pattern id={`gap-${airport.icao}-${index}`} width="24" height="12" patternUnits="userSpaceOnUse">
                                  <path d="M-12 6 Q-6 12 0 6 T12 6 T24 6 T36 6" fill="none" stroke="currentColor" strokeWidth="1.5" />
                                </pattern>
                              </defs>
                              <rect width="100%" height="12" fill={`url(#gap-${airport.icao}-${index})`} />
                            </svg>
                            <span className="relative -ml-1 px-1 rounded-full bg-white dark:bg-slate-800 text-xs font-light text-slate-500 dark:text-slate-400">
                              {formatGapDuration(periods[index - 1].end, period.start)}
                            </span>
                          </div>
                        </td>
                      </tr>
                    )}
                    <tr className={`hover:bg-slate-50 dark:hover:bg-slate-700/50 ${index > 0 && !period.gapBefore ? 'border-t border-slate-200 dark:border-slate-700' : ''}`}>
                      <td className="py-4 pl-4 pr-2 sm:pl-6 align-top">
                        <div className="font-medium text-slate-900 dark:text-white">{label.time}</div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{label.date}</div>
                      </td>
                      <td className="px-2 py-4 align-top" title={formatCloudBases(period.lowestCloudBases)}>
                        <div className="flex items-center gap-1.5">
                          <span className={`hidden sm:block w-2 h-2 shrink-0 rounded-full ${period.ceiling == null ? 'bg-slate-400' : period.ceiling < 500 ? 'bg-red-500' : period.ceiling < 1000 ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                          <span className="font-medium text-slate-700 dark:text-slate-300">{period.ceiling == null ? 'N/A' : period.ceiling.toLocaleString() + ' ft'}</span>
                        </div>
                      </td>
                      <td className="px-2 py-4 pr-4 sm:pr-6 align-top">
                        <div className="flex flex-wrap gap-1.5">
                          {period.approaches.map(approach => <ApproachBadge key={approach.id} approach={approach} />)}
                        </div>
                      </td>
                    </tr>
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
