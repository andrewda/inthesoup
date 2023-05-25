import { BigQuery } from '@google-cloud/bigquery';
import { NextApiRequest, NextApiResponse } from 'next';

const bigquery = new BigQuery();

const baseQuery = `WITH
  NearAirport AS (
    SELECT
      ST_GEOGPOINT(Longitude, Latitude) AS point
    FROM
      \`inthesoup.aeronautical.airport\`
    WHERE
      Airport_ICAO_Identifier = @airport
  ),
  FAF_Airport AS (
    SELECT
      faf.*,
      apt.Latitude,
      apt.Longitude,
      apt.Airport_Elevation,
      ST_DISTANCE(ST_GEOGPOINT(apt.Longitude, apt.Latitude), (SELECT point FROM NearAirport)) * 0.000539957 AS Distance_NM
    FROM
      \`inthesoup.aeronautical.faf\` AS faf
    INNER JOIN
      \`inthesoup.aeronautical.airport\` AS apt
    ON
      faf.Airport_Identifier = apt.Airport_ICAO_Identifier
  ),
  Filtered_FAF_Airport AS (
    SELECT
      *
    FROM
      FAF_Airport
    WHERE
      Distance_NM < @radius
  )
SELECT
  wx.Time AS Time,
  apt.Airport_ICAO_Identifier AS Airport_Identifier,
  ANY_VALUE(apt.Airport_Name) AS Airport_Name,
  ANY_VALUE(apt.Airport_Elevation) AS Airport_Elevation,
  CAST(ANY_VALUE(wx.CIG) * 100 as INT) AS CIG,
  CAST(ANY_VALUE(wx.LCB) * 100 as INT) AS LCB,
  CAST(ANY_VALUE(wx.WDR) * 10 as INT) AS WDR,
  ROUND(ANY_VALUE(wx.VIS) / 10) AS VIS,
  ROUND((ANY_VALUE(wx.TMP) - 32) * 5/9) AS TMP,
  ROUND((ANY_VALUE(wx.DPT) - 32) * 5/9) AS DPT,
  ANY_VALUE(wx.WSP) AS WSP,
  ANY_VALUE(wx.IFC) / 100 AS IFC,
  ARRAY_AGG(Filtered_FAF_Airport.SIDSTARApproach_Identifier ORDER BY Filtered_FAF_Airport.SIDSTARApproach_Identifier ASC) AS Approach_Identifier,
  ARRAY_AGG(IFNULL(Filtered_FAF_Airport.Approach_Name, '') ORDER BY Filtered_FAF_Airport.SIDSTARApproach_Identifier ASC) AS Approach_Name,
  ARRAY_AGG(IFNULL(Filtered_FAF_Airport.PDF_Name, '') ORDER BY Filtered_FAF_Airport.SIDSTARApproach_Identifier ASC) AS PDF_Name,
  ARRAY_AGG(Filtered_FAF_Airport.Altitude ORDER BY Filtered_FAF_Airport.SIDSTARApproach_Identifier ASC) AS FAF_MSL,
  ARRAY_AGG(Filtered_FAF_Airport.Altitude - apt.Airport_Elevation ORDER BY Filtered_FAF_Airport.SIDSTARApproach_Identifier ASC) AS FAF_AGL,
  ANY_VALUE(Filtered_FAF_Airport.Latitude) AS Latitude,
  ANY_VALUE(Filtered_FAF_Airport.Longitude) AS Longitude,
  ANY_VALUE(Filtered_FAF_Airport.Distance_NM) AS Distance_NM
FROM
  Filtered_FAF_Airport
INNER JOIN
  \`inthesoup.aeronautical.airport\` AS apt
ON
  Filtered_FAF_Airport.Airport_Identifier = apt.Airport_ICAO_Identifier
INNER JOIN
  \`inthesoup.weather.[FORECAST_TYPE]\` AS wx
ON
  Filtered_FAF_Airport.Airport_Identifier = wx.Location
WHERE
  wx.CIG != -88
  AND (wx.CIG * 100) <= (Filtered_FAF_Airport.Altitude - apt.Airport_Elevation)
GROUP BY wx.Time, apt.Airport_ICAO_Identifier
ORDER BY
  ANY_VALUE(Filtered_FAF_Airport.Distance_NM) ASC,
  wx.Time ASC;`

type Airport = {
  icao: string;
  name: string;
  elevation: number;
  location: {
    lat: number;
    lng: number;
  };
  distance: number;
}

type Approach = {
  id: string;
  name: string;
  faf: {
    msl: number;
    agl: number;
  };
}

type Weather = {
  ceiling: number;
  lowest_cloud_base: number;
  wind_direction: number;
  wind_speed: number;
  visibility: number;
  temperature: number;
  dewpoint: number;
  prob_ifr: number;
}

type Data = {
  time: Date;
  airport: Airport;
  weather: Weather;
  approaches: Approach[];
}[];

type Error = {
  error: string;
}

const approachIdToName = (id: string) => {
  const secondChar = id[1];

  // If second char is a number, it's a runway
  if (secondChar >= '0' && secondChar <= '9') {
    const type = id[0];
    const runway = id.slice(1, 4).replace('-', '');
    const suffix = id[4];

    switch (type) {
      case 'I':
        return `ILS${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'L':
        return `LOC${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'B':
        return `LOC BC${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'R':
        return `RNAV (GPS)${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'H':
        return `RNAV (RNP)${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'P':
        return `GPS${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'S':
        return `VOR${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'D':
        return `VOR/DME${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'V':
        return `VOR${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'X':
        return `LDA${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      case 'Q':
      case 'N':
        return `NDB${suffix ? ' ' + suffix : ''} RWY ${runway}`;
      default:
        return id;
    }
  } else {
    const type = id.slice(0, 3);
    const suffix = id.slice(3);

    switch (type) {
      case 'RNV':
        return `RNAV (GPS)${suffix}`;
      case 'VDM':
        return `VOR/DME${suffix}`;
      case 'LBC':
        return `LOC BC${suffix}`;
    }

    return id;
  }
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Data | Error>
) {
  const airport = req.query.airport as string;
  const radius = Number(req.query.radius);
  const forecast = (Array.isArray(req.query.forecast) ? req.query.forecast[0] : req.query.forecast) ?? 'nbh';

  if (!airport || !radius) {
    res.status(400).json({ error: 'Missing required query parameters' });
    return;
  }

  if (radius < 0 || radius > 500) {
    res.status(400).json({ error: 'Radius must be between 0 and 500' });
    return;
  }

  const validForecastTypes = ['metar', 'nbh', 'nbs'];
  if (!validForecastTypes.includes(forecast)) {
    res.status(400).json({ error: 'Forecast must be METAR, NBH or NBS' });
    return;
  }

  // Use NBH for 24hr forecast, NBS for 72hr forecast
  const query = baseQuery.replace('[FORECAST_TYPE]', forecast)

  const options = {
    query,
    params: { airport, radius },
  };

  // Run the query
  const [rows] = await bigquery.query(options);

  const response = rows.map(row => ({
    time: new Date(row.Time.value),
    airport: {
      icao: row.Airport_Identifier,
      name: row.Airport_Name,
      elevation: row.Airport_Elevation,
      location: {
        lat: row.Latitude,
        lng: row.Longitude,
      },
      distance: row.Distance_NM,
    },
    weather: {
      ceiling: row.CIG >= 0 ? row.CIG : null,
      lowest_cloud_base: row.LCB >= 0 ? row.LCB : null,
      wind_direction: row.WDR,
      wind_speed: row.WSP,
      visibility: row.VIS,
      temperature: row.TMP,
      dewpoint: row.DPT,
      prob_ifr: row.IFC,
    },
    approaches: row.Approach_Identifier.map((id: string, i: number) => ({
      id,
      name: row.Approach_Name[i] || approachIdToName(id),
      chart: row.PDF_Name[i] || null,
      faf: {
        msl: row.FAF_MSL[i],
        agl: row.FAF_AGL[i],
      }
    } as Approach)),
  }));

  // Remove duplicate approaches (based on the name field)
  response.forEach(row => {
    const uniqueApproaches = new Map<string, Approach>();
    row.approaches.forEach((approach: any) => {
      uniqueApproaches.set(approach.name, approach);
    });
    row.approaches = Array.from(uniqueApproaches.values());
  });

  res.status(200).json(response);
}
