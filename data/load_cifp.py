"""
Parse the FAA's CIFP file to extract airport and approach/FAF data.
"""

import json
import os
import zipfile

import arinc424.record as a424
import google.auth
import pandas as pd
import pandas_gbq
import requests
from tqdm import tqdm

credentials, project = google.auth.default()


def dms_to_dd(dms):
  """Convert a DMS string to a decimal degree float.
  """

  if dms[0] == 'N' or dms[0] == 'E':
    sign = 1
  else:
    sign = -1

  dms = dms[1:].rjust(9, '0')

  d = int(dms[0:3])
  m = int(dms[3:5])
  s = int(dms[5:9]) / 100

  return sign * (d + m / 60 + s / 3600)


def get_current_cifp_url():
  """Get the download URL for the current CIFP file.
  @return: The current CIFP file download URL
  """

  url = 'https://soa.smext.faa.gov/apra/cifp/chart?edition=current'
  headers = {'accept': 'application/json'}
  r = requests.get(url, headers=headers, verify=False)
  res = r.json()

  for edition in res['edition']:
    if edition['editionName'] == 'CURRENT':
      return edition['product']['url']

  return None


def download_cifp():
  url = get_current_cifp_url()

  if url is None:
    print('Unable to find current CIFP file.')
    return

  print('Downloading CIFP file...')

  r = requests.get(url, stream=True)
  total_size_in_bytes = int(r.headers.get('content-length', 0))
  block_size = 1024 #1 Kibibyte
  progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)

  with open('/tmp/cifp.zip', 'wb') as f:
    for data in r.iter_content(block_size):
      progress_bar.update(len(data))
      f.write(data)

  progress_bar.close()

  print('Extracting CIFP file...')

  with zipfile.ZipFile('/tmp/cifp.zip', 'r') as zip_ref:
    zip_ref.extractall('/tmp/cifp')

  return '/tmp/cifp/FAACIFP18'


def parse_cifp(file_path):
  """Parse the CIFP file and return pandas DataFrames containing the airport and FAF data.
  @param file_path: The path to the CIFP file
  @return: A tuple containing a pandas DataFrame for the airport data and a pandas DataFrame for the FAF data
  """

  cifp = open(file_path, 'r').readlines()
  records = []

  print('Reading CIFP records...')

  for line in tqdm(cifp):
    record = a424.Record()
    record.read(line)
    records.append(record)

  print('Extracting relevant CIFP data...')

  apts = []
  fafs = []

  for record in tqdm(records):
    is_apt = False
    is_faf = False

    for f in record.fields:
      if f.name == 'Section Code' and f.value == 'PA':
        is_apt = True
        break

      if f.name == 'Waypoint Description Code' and f.value == 'E  F':
        is_faf = True
        break

    if is_apt:
      apts.append(json.loads(record.json()))

    if is_faf:
      fafs.append(json.loads(record.json()))

  df_apt = pd.DataFrame(apts)
  df_apt = df_apt.apply(lambda x: x.str.strip())
  df_apt['Latitude'] = df_apt['Airport Reference Pt. Latitude'].apply(lambda x: dms_to_dd(x))
  df_apt['Longitude'] = df_apt['Airport Reference Pt. Longitude'].apply(lambda x: dms_to_dd(x))

  df_faf = pd.DataFrame(fafs)
  df_faf = df_faf.apply(lambda x: x.str.strip())

  return df_apt, df_faf


if __name__ == '__main__':
  file_path = download_cifp()

  df_apt, df_faf = parse_cifp(file_path)

  # Remove special characters from the column names
  df_apt.columns = df_apt.columns.str.replace(r'[^a-zA-Z0-9_ ]', '', regex=True)
  df_faf.columns = df_faf.columns.str.replace(r'[^a-zA-Z0-9_ ]', '', regex=True)

  # Condense multiple spaces in the column names
  df_apt.columns = df_apt.columns.str.replace(r' +', '_', regex=True)
  df_faf.columns = df_faf.columns.str.replace(r' +', '_', regex=True)

  # Set column types
  df_apt = df_apt.mask(df_apt == '')
  columns = ['Longest_Runway', 'Airport_Elevation', 'Transition_Altitude', 'Transition_Level']
  df_apt[columns] = df_apt[columns].apply(pd.to_numeric, errors='coerce')

  df_faf = df_faf.mask(df_faf == '')
  columns = ['RNP', 'Arc_Radius', 'Theta', 'Rho', 'Magnetic_Course', 'Route_Holding_Distance_or_Time', 'Altitude', 'Altitude_2', 'Speed_Limit', 'Transition_Altitude', 'Vertical_Angle']
  df_faf[columns] = df_faf[columns].apply(pd.to_numeric, errors='coerce')

  df_apt.to_csv('apt.csv', index=False)
  df_faf.to_csv('faf.csv', index=False)

  print('Uploading to BigQuery...')

  # Upload to BigQuery
  pandas_gbq.to_gbq(df_apt, 'aeronautical.airport', project, if_exists='replace', credentials=credentials)
  pandas_gbq.to_gbq(df_faf, 'aeronautical.faf', project, if_exists='replace', credentials=credentials)
