"""
Loads weather data from NOAA and uploads it to BigQuery.
"""

import time
from datetime import datetime, timedelta
from ftplib import FTP
from io import StringIO

import google.auth
import pandas as pd
import pandas_gbq
import requests
from tqdm import tqdm

credentials, project = google.auth.default()


def c_to_f(c):
  """Convert Celsius to Fahrenheit.
  @param c: Temperature in Celsius
  @return: Temperature in Fahrenheit
  """

  return c * 9 / 5 + 32


def sm_to_km(sm):
  """Convert statute miles to kilometers.
  @param sm: Distance in statute miles
  @return: Distance in kilometers
  """

  return sm * 1.60934


def round_to_nearest_10(x):
  """Round a number to the nearest 10.
  @param x: The number to round
  @return: The rounded number
  """

  return int(round(x / 10.0)) * 10


def get_noaa_data():
  """Get weather data from NOAA.
  @return: Tuple of (nbh, nbs) where nbh is the weather data for the next 24 hours
  and nbs is the weather data for the next 72 hours (in 3hr increments).
  """

  print('Accessing NOAA FTP server...')

  ftp = FTP('ftp.ncep.noaa.gov')
  ftp.login()

  ftp.cwd('/pub/data/nccf/com/blend/prod')

  # Get forecast days
  forecast_days = ftp.nlst()
  forecast_day = forecast_days[-1]
  ftp.cwd(forecast_day)

  # Get forecast hours
  forecast_hours = ftp.nlst()
  forecast_hour = forecast_hours[-1]

  print(f'Downloading NBH forecast {forecast_day} {forecast_hour}Z...')

  nbh_str = StringIO()
  ftp.retrlines('RETR {time}/text/blend_nbhtx.t{time}z'.format(time=forecast_hour), lambda line: nbh_str.write(line + '\n'))
  nbh = nbh_str.getvalue()
  nbh_str.close()

  print(f'Downloading NBS forecast {forecast_day} {forecast_hour}Z...')

  nbs_str = StringIO()
  ftp.retrlines('RETR {time}/text/blend_nbstx.t{time}z'.format(time=forecast_hour), lambda line: nbs_str.write(line + '\n'))
  nbs = nbs_str.getvalue()
  nbs_str.close()

  return nbh, nbs


def get_metar_data():
  """Get METAR data from aviationweather.gov.
  """

  # We must split the US into 3 regions to get all the data
  # Format: minLat,minLon,maxLat,maxLon
  bboxes = [
    '25.0,-125.0,50.0,-103.0',     # Western US (Pacific to Rockies)
    '25.0,-103.0,50.0,-87.0',      # Central US (Rockies to Mississippi)
    '25.0,-87.0,50.0,-65.0',       # Eastern US (Mississippi to Atlantic)
  ]

  # Collect rows in a list to avoid FutureWarning
  rows = []
  seen_locations = set()

  for bbox in bboxes:
    print(f'Getting METAR data for bbox {bbox}...')

    # Use the new Aviation Weather Center API
    res = requests.get(f'https://aviationweather.gov/api/data/metar?bbox={bbox}&format=json&taf=true')

    if res.status_code > 400:
      print(f'Error getting METAR data for bbox {bbox}')
      continue

    # The new API returns an array directly, not a GeoJSON features collection
    data = res.json()

    # The new API returns a list of observations
    if not isinstance(data, list):
      print(f'Unexpected response format for bbox {bbox}')
      continue

    for observation in data:
      if 'icaoId' not in observation:
        continue

      if observation['icaoId'] in seen_locations:
        continue
      seen_locations.add(observation['icaoId'])

      # Remove "+" from visibility, if type is string
      if 'visib' in observation and isinstance(observation['visib'], str) and observation['visib'] != '':
        observation['visib'] = int(observation['visib'].replace('+', ''))
      else:
        del observation['visib']

      # Set wind direction to 0 if variable
      if 'wdir' in observation and observation['wdir'] == 'VRB':
        observation['wdir'] = 0

      cloudBases = list(filter(lambda c: c['cover'] == 'SCT' or c['cover'] == 'BKN' or c['cover'] == 'OVC', observation.get('clouds', [])))
      lowestCloudBase = min([c['base'] for c in cloudBases]) if len(cloudBases) > 0 else None

      ceilings = list(filter(lambda c: c['cover'] == 'BKN' or c['cover'] == 'OVC', observation.get('clouds', [])))
      lowestCeiling = min([c['base'] for c in ceilings]) if len(ceilings) > 0 else None

      rows.append({
        'Location': observation['icaoId'],
        'Time': datetime.strptime(observation['reportTime'], '%Y-%m-%dT%H:%M:%S.%fZ'),
        'Forecast_Time': datetime.strptime(observation['reportTime'], '%Y-%m-%dT%H:%M:%S.%fZ'),
        'TMP': c_to_f(observation['temp']) if 'temp' in observation else None,
        'DPT': c_to_f(observation['dewp']) if 'dewp' in observation else None,
        'WDR': observation['wdir'] / 10 if 'wdir' in observation else None,
        'WSP': observation['wspd'] if 'wspd' in observation else None,
        'CIG': lowestCeiling,
        'LCB': lowestCloudBase,
        'VIS': sm_to_km(observation['visib']) * 10 if 'visib' in observation else None,
        'IFC': None,
        'METAR': observation['rawOb'],
        'TAF': observation['rawTaf'] if 'rawTaf' in observation else None,
      })

  # Create DataFrame from rows list
  if rows:
    metar_data = pd.DataFrame(rows)
  else:
    metar_data = pd.DataFrame(columns=['Location', 'Time', 'Forecast_Time', 'TMP', 'DPT', 'WDR', 'WSP', 'CIG', 'LCB', 'VIS', 'IFC', 'METAR', 'TAF'])

  return metar_data


def parse_noaa_data(data, fmt):
  """Parse weather data for a specific location
  @param data: The weather data to parse
  @param fmt: The format of the data. Either 'nbh' or 'nbs'
  @return: A pandas DataFrame containing the weather data
  """

  location = data.strip().split('\n')[0].split(' ')[0]

  forecast_date = None
  if fmt == 'nbh':
    forecast_date_str = data.strip().split('\n')[0].strip().split(' ')
    forecast_date_str = list(filter(len, forecast_date_str))[-3:]
    forecast_date_str = ' '.join(forecast_date_str)
    forecast_date = datetime.strptime(forecast_date_str, '%m/%d/%Y %H%M %Z')
    first_date = forecast_date + timedelta(hours=1)
  elif fmt == 'nbs':
    forecast_date_str = data.strip().split('\n')[0].strip().split(' ')
    forecast_date_str = list(filter(len, forecast_date_str))[-3:]
    forecast_date_str = ' '.join(forecast_date_str)
    utc_hour = int(forecast_date_str[-8:-6])
    forecast_date = datetime.strptime(forecast_date_str, '%m/%d/%Y %H%M %Z')
    first_date = forecast_date + timedelta(hours=6 - (utc_hour % 3))

  skip_lines = 1 if fmt == 'nbh' else 2

  lines = data.strip().split('\n')[skip_lines:]
  parsed_data = {}

  max_len = max([len(line) for line in lines])
  for line in lines:
    var_name = line[:5].strip()
    value_str = line[5:]

    # Split the values into a list of integers every 3 characters
    values = [int(value_str[i:i+3].strip()) if value_str[i:i+3].strip().lstrip('-').isdigit() else None for i in range(0, max_len - 5, 3)]

    parsed_data[var_name] = values

  df = pd.DataFrame(parsed_data)
  df['Location'] = location
  df['Forecast_Time'] = forecast_date

  date = first_date
  dates = []

  prev_hr = None
  for hr in df['UTC']:
    date = date.replace(hour=hr)

    if prev_hr is not None and hr < prev_hr:
      date += timedelta(days=1)

    dates.append(date)
    prev_hr = hr

  df['Time'] = dates

  return df


if __name__ == '__main__':
  nbh = None
  nbs = None
  metar = None

  try:
    metar = get_metar_data()
  except Exception as e:
    print('Error getting METAR data. Skipping...')
    print(e)

  # Retry up to 10 times with 60 second delay
  n_tries = 10
  for i in range(n_tries):
    try:
      nbh, nbs = get_noaa_data()
      break
    except Exception as e:
      print(e)
      print(f'Error getting weather data. Retrying in 60 seconds... ({i + 1}/{n_tries})')
      time.sleep(60)

  df_nbh = None
  if nbh is not None:
    print('Parsing NBH forecast data...')

    nbh = nbh.strip().split(' ' * 50)[1:]

    df_nbh = pd.DataFrame()
    for forecast in tqdm(nbh):
      location_forecast = parse_noaa_data(forecast, 'nbh')
      df_nbh = pd.concat([df_nbh, location_forecast])

    df_nbh.to_csv('wx_nbh.csv', index=False)

  df_nbs = None
  if nbs is not None:
    print('Parsing NBS forecast data...')

    nbs = nbs.strip().split(' ' * 50)[1:]

    df_nbs = pd.DataFrame()
    for forecast in tqdm(nbs):
      location_forecast = parse_noaa_data(forecast, 'nbs')
      df_nbs = pd.concat([df_nbs, location_forecast])

    df_nbs.to_csv('wx_nbs.csv', index=False)

  print('Uploading to BigQuery...')

  # Upload to BigQuery
  if metar is not None:
    pandas_gbq.to_gbq(metar, 'weather.metar', project, if_exists='replace', credentials=credentials)

  if df_nbh is not None:
    pandas_gbq.to_gbq(df_nbh, 'weather.nbh', project, if_exists='replace', credentials=credentials)

  if df_nbs is not None:
    pandas_gbq.to_gbq(df_nbs, 'weather.nbs', project, if_exists='replace', credentials=credentials)
