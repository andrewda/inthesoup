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
from tqdm import tqdm

credentials, project = google.auth.default()


def get_weather_data():
  """Get weather data from NOAA.
  @return: Tuple of (nbh, nbs) where nbh is the weather data for the next 24 hours
  and nbs is the weather data for the next 72 hours (in 3hr increments).
  """

  print('Accessing NOAA FTP server...')

  ftp = FTP('ftp.ncep.noaa.gov')
  ftp.login()

  ftp.cwd('pub/data/nccf/com/blend/prod')

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


def parse_weather_data(data, fmt):
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
  # Retry up to 6 times with 30 second delay
  nbh = None
  nbs = None
  for i in range(6):
    try:
      nbh, nbs = get_weather_data()
      break
    except Exception as e:
      print(e)
      print(f'Error getting weather data. Retrying in 30 seconds... ({i + 1}/5)')
      time.sleep(30)

  # Exit if we couldn't get the data
  if nbh is None or nbs is None:
    print('Error getting weather data. Exiting...')
    exit(1)

  # Split the data into separate locations
  nbh = nbh.strip().split(' ' * 50)[1:]
  nbs = nbs.strip().split(' ' * 50)[1:]

  print('Parsing NBH forecast data...')

  df_nbh = pd.DataFrame()
  for forecast in tqdm(nbh):
    location_forecast = parse_weather_data(forecast, 'nbh')
    df_nbh = pd.concat([df_nbh, location_forecast])

  df_nbh.to_csv('wx_nbh.csv', index=False)

  print('Parsing NBS forecast data...')

  df_nbs = pd.DataFrame()
  for forecast in tqdm(nbs):
    location_forecast = parse_weather_data(forecast, 'nbs')
    df_nbs = pd.concat([df_nbs, location_forecast])

  df_nbs.to_csv('wx_nbs.csv', index=False)

  print('Uploading to BigQuery...')

  # Upload to BigQuery
  pandas_gbq.to_gbq(df_nbh, 'weather.nbh', project, if_exists='replace', credentials=credentials)
  pandas_gbq.to_gbq(df_nbs, 'weather.nbs', project, if_exists='replace', credentials=credentials)
