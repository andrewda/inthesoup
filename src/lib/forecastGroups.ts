export type Approach = {
  id: string;
  name: string;
  chart: string | null;
  faf: { msl: number; agl: number };
};

export type Forecast = {
  time: string;
  airport: { icao: string; name: string; distance: number };
  weather: { ceiling: number | null; lowest_cloud_base: number | null };
  approaches: Approach[];
};

export type ForecastPeriod = {
  gapBefore: boolean;
  start: string;
  end: string;
  ceiling: number | null;
  lowestCloudBases: (number | null)[];
  approaches: Approach[];
};

export type AirportGroup = {
  airport: Forecast['airport'];
  periods: ForecastPeriod[];
};

/** Group by visible row values and approach details; summarize cloud bases separately. */
function resultKey(forecast: Forecast) {
  return JSON.stringify([
    forecast.weather.ceiling,
    forecast.approaches.map(({ id, name, chart, faf }) =>
      JSON.stringify([id, name, chart, faf.msl, faf.agl])).sort(),
  ]);
}

export function groupForecasts(forecasts: Forecast[], source: string): AirportGroup[] {
  // NBS samples three hours apart are consecutive. Only missing samples at
  // the source's cadence break a range; never infer cadence from filtered rows.
  const interval = source === 'nbs' ? 3 * 3600000
    : source === 'nbh' || source === 'taf' ? 3600000 : null;
  const airports = new Map<string, Forecast[]>();
  forecasts.forEach(forecast => {
    const rows = airports.get(forecast.airport.icao) ?? [];
    rows.push(forecast);
    airports.set(forecast.airport.icao, rows);
  });

  return Array.from(airports.values()).map(rows => {
    rows.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
    const periods: ForecastPeriod[] = [];
    let previousKey: string | undefined;
    rows.forEach(row => {
      const key = resultKey(row);
      const previous = periods[periods.length - 1];
      if (previous && interval !== null && key === previousKey &&
          Date.parse(row.time) - Date.parse(previous.end) === interval) {
        previous.end = row.time;
        if (!previous.lowestCloudBases.includes(row.weather.lowest_cloud_base)) {
          previous.lowestCloudBases.push(row.weather.lowest_cloud_base);
        }
      } else {
        periods.push({
          gapBefore: Boolean(previous && interval !== null &&
            Date.parse(row.time) - Date.parse(previous.end) > interval),
          start: row.time,
          end: row.time,
          ceiling: row.weather.ceiling,
          lowestCloudBases: [row.weather.lowest_cloud_base],
          approaches: [...row.approaches].sort((a, b) => a.name.localeCompare(b.name)),
        });
      }
      previousKey = key;
    });
    return { airport: rows[0].airport, periods };
  }).sort((a, b) => a.airport.distance - b.airport.distance || a.airport.icao.localeCompare(b.airport.icao));
}

export function formatPeriod(start: string, end: string, local: boolean) {
  const first = new Date(start);
  const last = new Date(end);
  const timeZone = local ? undefined : 'UTC';
  const dateFormat = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric', timeZone });
  const timeFormat = new Intl.DateTimeFormat(undefined, local
    ? { hour: 'numeric', minute: '2-digit' }
    : { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone });
  const time = (date: Date) => timeFormat.format(date) + (local ? '' : 'Z');
  const sameDay = dateFormat.format(first) === dateFormat.format(last);
  // Include offsets across DST changes so repeated wall-clock hours are clear.
  const offsetChanged = local && first.getTimezoneOffset() !== last.getTimezoneOffset();
  const offsetTime = (date: Date) => new Intl.DateTimeFormat(undefined, {
    hour: 'numeric', minute: '2-digit', timeZoneName: 'shortOffset',
  }).format(date);
  const firstTime = offsetChanged ? offsetTime(first) : time(first);
  const lastTime = offsetChanged ? offsetTime(last) : time(last);
  return {
    date: sameDay ? dateFormat.format(first) : `${dateFormat.format(first)} – ${dateFormat.format(last)}`,
    time: start === end ? firstTime : `${firstTime} – ${lastTime}`,
  };
}

export function formatCloudBases(values: (number | null)[]) {
  const known = values.filter((value): value is number => value != null);
  if (!known.length) return 'LCB: N/A';
  const min = Math.min(...known);
  const max = Math.max(...known);
  return `LCB: ${min === max ? min.toLocaleString() : `${min.toLocaleString()}–${max.toLocaleString()}`} ft${known.length < values.length ? ' (some times unavailable)' : ''}`;
}
