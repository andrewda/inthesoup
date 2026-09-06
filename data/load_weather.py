"""
Loads weather data from NOAA and uploads it to BigQuery.
"""

import argparse
import gzip
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from fractions import Fraction

from bs4 import BeautifulSoup

import google.auth
import pandas as pd
import pandas_gbq
import requests
from tqdm import tqdm

HTTP_TIMEOUT = (10, 60)  # Connect and read timeouts, in seconds.
NOAA_URL = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/'
CACHE_URL = 'https://aviationweather.gov/data/cache/'
NUMERIC_METAR_COLUMNS = ['TMP', 'DPT', 'WDR', 'WSP', 'CIG', 'LCB', 'VIS', 'IFC']


def fetch(url):
  """Retry transient HTTP failures, with bounded waits and no final sleep."""
  for attempt in range(3):
    try:
      response = requests.get(
        url, timeout=HTTP_TIMEOUT,
        headers={'User-Agent': 'InTheSoup/1.0 (https://inthesoup.xyz)'},
      )
      response.raise_for_status()
      return response
    except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as error:
      status = error.response.status_code if error.response is not None else None
      if attempt == 2 or (status is not None and status != 429 and status < 500):
        raise
      delay = 2 ** (attempt + 1)
      print(f'Download failed: {url}: {error}; retrying in {delay}s', flush=True)
      time.sleep(delay)


def directory_entries(url, pattern):
  response = fetch(url)
  links = BeautifulSoup(response.text, 'html.parser').find_all('a', href=True)
  return sorted({link['href'] for link in links if re.fullmatch(pattern, link['href'])}, reverse=True)


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
  """Download NBH and NBS from the newest complete NOAA HTTPS cycle."""
  days = directory_entries(NOAA_URL, r'blend\.\d{8}/')
  checked = 0
  for day in days[:2]:
    hours = directory_entries(NOAA_URL + day, r'(?:[01]\d|2[0-3])/')
    for hour in hours:
      # New cycles appear before all text products have finished publishing.
      checked += 1
      if checked > 6:
        raise RuntimeError('No complete NBH/NBS pair in the latest six NOAA cycles')
      text_url = NOAA_URL + day + hour + 'text/'
      try:
        files = directory_entries(text_url, r'blend_nb[hs]tx\.t\d{2}z')
        names = [f'blend_{fmt}tx.t{hour[:2]}z' for fmt in ('nbh', 'nbs')]
        if not all(name in files for name in names):
          continue
        print(f'Downloading NOAA cycle {day}{hour}', flush=True)
        products = tuple(fetch(text_url + name).text for name in names)
        if any(not product.strip() or '<html' in product.lower() for product in products):
          raise ValueError('NOAA returned an empty or HTML forecast product')
        return products
      except requests.HTTPError as error:
        if error.response.status_code != 404:
          raise
  raise RuntimeError('No complete NBH/NBS pair found on NOAA')


def number(value):
  """Parse optional weather numbers, including fractional and 10+ visibility."""
  if value is None or str(value).strip() == '':
    return None
  try:
    return float(Fraction(str(value).strip().rstrip('+')))
  except (ValueError, ZeroDivisionError):
    return None


def read_cache(name, tag):
  response = fetch(CACHE_URL + name + '.cache.xml.gz')
  root = ET.fromstring(gzip.decompress(response.content))
  records = root.findall(f'./data/{tag}')
  if not records:
    raise ValueError(f'Empty {name} weather cache')
  return records


def get_metar_data():
  """Read complete AWC caches, retaining the existing continental-US bounds.

  The query API truncates large requests; bulk caches avoid missing stations.
  Cache cloud heights are feet AGL; shared forecast tables use hundreds of feet.
  """
  observations = read_cache('metars', 'METAR')
  tafs = {}
  for taf in read_cache('tafs', 'TAF'):
    station = taf.findtext('station_id')
    issued = taf.findtext('issue_time', '')
    if station not in tafs or issued > tafs[station][0]:
      tafs[station] = (issued, taf.findtext('raw_text'))

  rows = []
  for observation in observations:
    station = observation.findtext('station_id')
    lat = number(observation.findtext('latitude'))
    lon = number(observation.findtext('longitude'))
    if not station or lat is None or lon is None or not (25 <= lat <= 50 and -125 <= lon <= -65):
      continue
    timestamp = observation.findtext('observation_time')
    raw = observation.findtext('raw_text')
    if not timestamp or not raw:
      raise ValueError(f'Missing observation time or METAR text for {station}')
    reported = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    temperature = number(observation.findtext('temp_c'))
    dewpoint = number(observation.findtext('dewpoint_c'))
    direction_text = observation.findtext('wind_dir_degrees')
    direction = 0 if direction_text == 'VRB' else number(direction_text)
    visibility = number(observation.findtext('visibility_statute_mi'))
    cloud_bases = []
    ceilings = []
    for cloud in observation.findall('sky_condition'):
      base = number(cloud.get('cloud_base_ft_agl'))
      cover = cloud.get('sky_cover')
      if base is not None and cover in ('SCT', 'BKN', 'OVC', 'VV'):
        cloud_bases.append(base)
        if cover in ('BKN', 'OVC', 'VV'):
          ceilings.append(base)
    vertical_visibility = number(observation.findtext('vert_vis_ft'))
    if vertical_visibility is not None:
      ceilings.append(vertical_visibility)
      cloud_bases.append(vertical_visibility)
    rows.append({
      'Location': station,
      'Time': reported,
      'Forecast_Time': reported,
      'TMP': c_to_f(temperature) if temperature is not None else None,
      'DPT': c_to_f(dewpoint) if dewpoint is not None else None,
      'WDR': direction / 10 if direction is not None else None,
      'WSP': number(observation.findtext('wind_speed_kt')),
      'CIG': min(ceilings) / 100 if ceilings else None,
      'LCB': min(cloud_bases) / 100 if cloud_bases else None,
      'VIS': sm_to_km(visibility) * 10 if visibility is not None else None,
      'IFC': None,
      'METAR': raw,
      'TAF': tafs.get(station, (None, None))[1],
    })
  if not rows:
    raise ValueError('No METAR observations within the configured US bounds')
  metar_data = pd.DataFrame(rows).sort_values('Time', ascending=False)
  metar_data = metar_data.drop_duplicates('Location').reset_index(drop=True)
  # Explicit numeric dtypes also cover entirely missing optional fields.
  metar_data[NUMERIC_METAR_COLUMNS] = metar_data[NUMERIC_METAR_COLUMNS].astype('float64')
  return metar_data


def parse_noaa_data(data, fmt):
  """Parse weather data for a specific location
  @param data: The weather data to parse
  @param fmt: The format of the data. Either 'nbh' or 'nbs'
  @return: A pandas DataFrame containing the weather data
  """

  if fmt not in ('nbh', 'nbs'):
    raise ValueError(f'Unsupported forecast format: {fmt}')
  lines = data.strip().splitlines()
  header = lines[0].split()
  location = header[0]
  forecast_date = datetime.strptime(' '.join(header[-3:]), '%m/%d/%Y %H%M %Z')
  fields = {line[:5].strip(): line[5:] for line in lines[1:]
            if re.match(r'^ [A-Z][A-Z0-9]{1,2} ', line) and line[:5].strip() != 'DT'}
  if 'UTC' not in fields:
    raise ValueError(f'Missing UTC hours for {location}')
  hours = [int(hour) for hour in fields['UTC'].split()]
  if not hours or any(hour < 0 or hour > 23 for hour in hours):
    raise ValueError(f'Invalid UTC hours for {location}')

  # UTC defines the column count. Trailing spaces and longer annotation lines
  # must not introduce an extra all-null column or turn hours into floats.
  parsed_data = {}
  for name, values in fields.items():
    parsed_data[name] = [int(value) if value.lstrip('-').isdigit() else None
                         for value in (values[i * 3:i * 3 + 3].strip() for i in range(len(hours)))]
  parsed_data['UTC'] = hours
  df = pd.DataFrame(parsed_data)
  df['Location'] = location
  df['Forecast_Time'] = forecast_date

  dates = []
  previous = forecast_date
  for index, hour in enumerate(hours):
    if 'FHR' in parsed_data and parsed_data['FHR'][index] is not None:
      date = forecast_date + timedelta(hours=parsed_data['FHR'][index])
      if date.hour != hour or date <= previous:
        raise ValueError(f'Inconsistent forecast hours for {location}')
    else:
      date = previous.replace(hour=hour)
      if date <= previous:
        date += timedelta(days=1)
    dates.append(date)
    previous = date
  df['Time'] = dates
  return df


def parse_noaa_product(product, fmt):
  """Parse all stations, rejecting invalid/empty downloads before any uploads."""
  # Split on station headers, not long blank runs inside sparse data rows.
  headers = list(re.finditer(r'^[ \t]*\S+\s+NBM\s+V[\d.]+\s+' + fmt.upper() + r'\s+GUIDANCE[^\n]*$', product, re.MULTILINE))
  stations = [product[header.start():headers[index + 1].start() if index + 1 < len(headers) else len(product)]
              for index, header in enumerate(headers)]
  if not stations:
    raise ValueError(f'No stations in NOAA {fmt.upper()} product')
  frames = [parse_noaa_data(station, fmt) for station in tqdm(stations, disable=None)]
  # Some NOAA sites (for example buoys) omit aviation fields. Preserve those
  # as nulls while requiring the overall product to supply the API's columns.
  result = pd.concat(frames, ignore_index=True)
  required = {'Location', 'Time', 'Forecast_Time', 'CIG', 'LCB', 'VIS', 'IFC', 'TMP', 'DPT', 'WDR', 'WSP'}
  if result.empty or not required.issubset(result.columns):
    raise ValueError(f'Incomplete NOAA {fmt.upper()} product')
  return result


def main(dry_run=False):
  started = time.monotonic()
  # Fetch and validate every source before replacing any live tables. Exceptions
  # propagate so CI and Cloud Run report failed refreshes rather than success.
  metar = get_metar_data()
  nbh, nbs = get_noaa_data()
  tables = {
    'weather.metar': metar,
    'weather.nbh': parse_noaa_product(nbh, 'nbh'),
    'weather.nbs': parse_noaa_product(nbs, 'nbs'),
  }
  for table, frame in tables.items():
    print(f'{table}: {len(frame)} rows, latest source time {frame.Forecast_Time.max()}', flush=True)
  print(f'Download and parsing completed in {time.monotonic() - started:.1f}s', flush=True)
  if dry_run:
    return tables

  credentials, project = google.auth.default()
  for table, frame in tables.items():
    schema = None
    if table == 'weather.metar':
      schema = [{'name': name, 'type': 'FLOAT'} for name in NUMERIC_METAR_COLUMNS]
    pandas_gbq.to_gbq(frame, table, project, if_exists='replace',
                      credentials=credentials, table_schema=schema)
  return tables


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--dry-run', action='store_true', help='Download and parse without writing to BigQuery')
  main(dry_run=parser.parse_args().dry_run)
