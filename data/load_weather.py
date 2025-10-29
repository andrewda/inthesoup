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


def parse_taf(taf_string, icao, report_time):
  """Parse a TAF string and extract forecast periods.
  @param taf_string: The raw TAF string
  @param icao: The ICAO identifier for the airport
  @param report_time: The time the TAF was issued
  @return: A list of forecast periods with weather data
  """
  import re

  if not taf_string or pd.isna(taf_string) or taf_string == 'nan':
    return []

  forecasts = []

  # Extract the valid period from the TAF header (e.g., "TAF KSFO 281723Z 2818/2924")
  # Format: DDhh/DDhh where DD is day and hh is hour
  valid_match = re.search(r'TAF.*?(\d{4})/(\d{4})', taf_string)
  if not valid_match:
    return []

  # Parse the base TAF (conditions before any FM/TEMPO/BECMG groups)
  # Split by FM (From), TEMPO (Temporary), BECMG (Becoming) to get forecast periods
  # For simplicity, we'll focus on FM groups which indicate significant weather changes

  # Split into sections
  parts = re.split(r'\s+(FM\d{6}|TEMPO|BECMG)', taf_string)

  # The first part contains the header and initial conditions
  base_taf = parts[0]

  # Extract initial valid time
  start_day = int(valid_match.group(1)[:2])
  start_hour = int(valid_match.group(1)[2:])
  end_day = int(valid_match.group(2)[:2])
  end_hour = int(valid_match.group(2)[2:])

  # Create datetime objects for the forecast period
  # Assume report_time year and month
  base_time = datetime.strptime(report_time, '%Y-%m-%dT%H:%M:%S.%fZ')

  # Calculate the forecast start time
  forecast_start = base_time.replace(day=start_day, hour=start_hour, minute=0, second=0, microsecond=0)
  if forecast_start < base_time:
    # If the day is earlier in the month, it's likely next month
    if start_day < base_time.day:
      forecast_start = forecast_start.replace(month=base_time.month + 1 if base_time.month < 12 else 1)

  # Parse the base forecast conditions
  base_wx = parse_taf_conditions(base_taf, icao, report_time, forecast_start)
  if base_wx:
    forecasts.append(base_wx)

  # Parse FM groups for additional forecast periods
  for i in range(1, len(parts), 2):
    if i + 1 < len(parts):
      group_type = parts[i]
      group_content = parts[i + 1] if i + 1 < len(parts) else ''

      # Only process FM groups (ignore TEMPO and BECMG for now)
      if group_type.startswith('FM'):
        # Extract time from FM group (e.g., FM281900)
        fm_match = re.match(r'FM(\d{2})(\d{2})(\d{2})', group_type)
        if fm_match:
          fm_day = int(fm_match.group(1))
          fm_hour = int(fm_match.group(2))
          fm_minute = int(fm_match.group(3))

          fm_time = base_time.replace(day=fm_day, hour=fm_hour, minute=fm_minute, second=0, microsecond=0)
          if fm_time < base_time:
            if fm_day < base_time.day:
              fm_time = fm_time.replace(month=base_time.month + 1 if base_time.month < 12 else 1)

          fm_wx = parse_taf_conditions(group_content, icao, report_time, fm_time)
          if fm_wx:
            forecasts.append(fm_wx)

  return forecasts


def parse_taf_conditions(taf_part, icao, report_time, forecast_time):
  """Parse weather conditions from a TAF string segment.
  @param taf_part: A segment of the TAF string
  @param icao: The ICAO identifier
  @param report_time: The time the TAF was issued
  @param forecast_time: The time this forecast is valid for
  @return: A dictionary with weather data
  """
  import re

  wx = {
    'Location': icao,
    'Time': forecast_time,
    'Forecast_Time': datetime.strptime(report_time, '%Y-%m-%dT%H:%M:%S.%fZ'),
    'TMP': None,
    'DPT': None,
    'WDR': None,
    'WSP': None,
    'CIG': None,
    'LCB': None,
    'VIS': None,
    'IFC': None,
  }

  # Parse wind (e.g., "27008KT" = 270 degrees at 8 knots)
  wind_match = re.search(r'(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT', taf_part)
  if wind_match:
    if wind_match.group(1) != 'VRB':
      wx['WDR'] = int(wind_match.group(1)) / 10  # Convert to tenths of degrees
    else:
      wx['WDR'] = 0
    wx['WSP'] = int(wind_match.group(2))

  # Parse visibility (e.g., "5SM" = 5 statute miles, "9999" = 10km or greater)
  vis_match = re.search(r'(\d+)SM', taf_part)
  if vis_match:
    vis_sm = int(vis_match.group(1))
    wx['VIS'] = sm_to_km(vis_sm) * 10  # Convert to tens of kilometers
  else:
    # Check for meters visibility (e.g., "9999" = unlimited, "0400" = 400 meters)
    vis_match = re.search(r'\s(\d{4})\s', taf_part)
    if vis_match:
      vis_m = int(vis_match.group(1))
      if vis_m == 9999:
        wx['VIS'] = 100  # Unlimited visibility (10+ km)
      else:
        wx['VIS'] = (vis_m / 1000) * 10  # Convert to tens of kilometers

  # Parse cloud layers (e.g., "BKN015" = broken at 1500 ft, "OVC008" = overcast at 800 ft)
  # Sky conditions: SKC/CLR (clear), FEW (few), SCT (scattered), BKN (broken), OVC (overcast)
  # Ceiling is defined as BKN or OVC layer
  cloud_layers = re.findall(r'(FEW|SCT|BKN|OVC)(\d{3})', taf_part)

  if cloud_layers:
    # Find the lowest cloud base
    lowest_base = min([int(layer[1]) for layer in cloud_layers])
    wx['LCB'] = lowest_base

    # Find the ceiling (lowest BKN or OVC layer)
    ceiling_layers = [int(layer[1]) for layer in cloud_layers if layer[0] in ['BKN', 'OVC']]
    if ceiling_layers:
      wx['CIG'] = min(ceiling_layers)

  # Check for clear skies
  if re.search(r'\s(SKC|CLR)\s', taf_part):
    wx['CIG'] = None
    wx['LCB'] = None
    wx['VIS'] = 100  # Clear visibility

  return wx


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
  bboxes = [
    '28.524736,-125.771484,49.322923,-102.744141', # Western US
    '25.536738,-103.350588,49.371110,-86.695315', # Central US
    '23.992635,-87.099609,49.408788,-63.193359', # Eastern US
  ]

  metar_data = pd.DataFrame()
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

      if observation['icaoId'] in metar_data.index:
        continue

      # Remove "+" from visibility, if type is string
      if 'visib' in observation and isinstance(observation['visib'], str) and observation['visib'] != '':
        observation['visib'] = int(observation['visib'].replace('+', ''))
      else:
        del observation['visib']

      # Set wind direction to 0 if variable
      if 'wdir' in observation and observation['wdir'] == 'VRB':
        observation['wdir'] = 0

      df = pd.DataFrame(index=[observation['icaoId']])

      df['Location'] = [observation['icaoId']]
      df['Time'] = [datetime.strptime(observation['reportTime'], '%Y-%m-%dT%H:%M:%S.%fZ')]
      df['Forecast_Time'] = [datetime.strptime(observation['reportTime'], '%Y-%m-%dT%H:%M:%S.%fZ')]

      df['TMP'] = [c_to_f(observation['temp']) if 'temp' in observation else None]
      df['DPT'] = [c_to_f(observation['dewp']) if 'dewp' in observation else None]
      df['WDR'] = [observation['wdir'] / 10 if 'wdir' in observation else None]
      df['WSP'] = [observation['wspd'] if 'wspd' in observation else None]
      df['CIG'] = [observation['ceil'] if 'ceil' in observation else None]
      df['LCB'] = [int(observation['cldBas1']) if 'cldBas1' in observation else None]
      df['VIS'] = [sm_to_km(observation['visib']) * 10 if 'visib' in observation else None]
      df['IFC'] = [None]

      df['METAR'] = [observation['rawOb']]
      df['TAF'] = [observation['rawTaf'] if 'rawTaf' in observation else None]

      metar_data = pd.concat([metar_data, df])

  # set column types
  metar_data['Location'] = metar_data['Location'].astype('category')
  metar_data['Time'] = pd.to_datetime(metar_data['Time'])
  metar_data['Forecast_Time'] = pd.to_datetime(metar_data['Forecast_Time'])
  metar_data['TMP'] = metar_data['TMP'].astype('float')
  metar_data['DPT'] = metar_data['DPT'].astype('float')
  metar_data['WDR'] = metar_data['WDR'].astype('float')
  metar_data['WSP'] = metar_data['WSP'].astype('float')
  metar_data['CIG'] = metar_data['CIG'].astype('float')
  metar_data['LCB'] = metar_data['LCB'].astype('float')
  metar_data['VIS'] = metar_data['VIS'].astype('float')
  metar_data['IFC'] = metar_data['IFC'].astype('float')
  metar_data['METAR'] = metar_data['METAR'].astype('str')
  metar_data['TAF'] = metar_data['TAF'].astype('str')

  return metar_data


def process_taf_data(metar_data):
  """Process TAF data from METAR dataframe and create TAF forecast dataframe.
  @param metar_data: DataFrame containing METAR data with TAF strings
  @return: DataFrame containing parsed TAF forecast data
  """

  print('Processing TAF data...')

  taf_data = pd.DataFrame()

  for index, row in metar_data.iterrows():
    if pd.isna(row['TAF']) or row['TAF'] == 'nan':
      continue

    # Parse the TAF string
    forecasts = parse_taf(row['TAF'], row['Location'], row['Time'].strftime('%Y-%m-%dT%H:%M:%S.%fZ'))

    for forecast in forecasts:
      df = pd.DataFrame([forecast])
      taf_data = pd.concat([taf_data, df], ignore_index=True)

  if len(taf_data) == 0:
    print('No TAF data found.')
    return None

  # Set column types
  taf_data['Location'] = taf_data['Location'].astype('category')
  taf_data['Time'] = pd.to_datetime(taf_data['Time'])
  taf_data['Forecast_Time'] = pd.to_datetime(taf_data['Forecast_Time'])
  taf_data['TMP'] = taf_data['TMP'].astype('float')
  taf_data['DPT'] = taf_data['DPT'].astype('float')
  taf_data['WDR'] = taf_data['WDR'].astype('float')
  taf_data['WSP'] = taf_data['WSP'].astype('float')
  taf_data['CIG'] = taf_data['CIG'].astype('float')
  taf_data['LCB'] = taf_data['LCB'].astype('float')
  taf_data['VIS'] = taf_data['VIS'].astype('float')
  taf_data['IFC'] = taf_data['IFC'].astype('float')

  print(f'Processed {len(taf_data)} TAF forecast periods from {len(metar_data)} stations.')

  return taf_data


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
  taf = None

  try:
    metar = get_metar_data()
    if metar is not None:
      taf = process_taf_data(metar)
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

  if taf is not None:
    pandas_gbq.to_gbq(taf, 'weather.taf', project, if_exists='replace', credentials=credentials)

  if df_nbh is not None:
    pandas_gbq.to_gbq(df_nbh, 'weather.nbh', project, if_exists='replace', credentials=credentials)

  if df_nbs is not None:
    pandas_gbq.to_gbq(df_nbs, 'weather.nbs', project, if_exists='replace', credentials=credentials)
