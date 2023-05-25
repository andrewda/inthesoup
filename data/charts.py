import requests
import pandas as pd
import xml.etree.ElementTree as ET
from tqdm import tqdm

def get_charts(cycle):
  # Get the metafile
  metafile_url = f'https://aeronav.faa.gov/d-tpp/{cycle}/xml_data/d-tpp_Metafile.xml'
  metafile_response = requests.get(metafile_url)
  metafile = metafile_response.text

  # Save to file
  # with open(f'./d-tpp_Metafile.xml', 'w') as f:
  #   f.write(metafile)

  # Read the saved file
  # metafile = open(f'./d-tpp_Metafile.xml', 'r').read()

  # Parse the metafile
  metafile_xml = ET.fromstring(metafile)

  print('Parsing chart metafile...')

  # Get the chart URLs
  df_charts = pd.DataFrame(columns=['location', 'chart_name', 'pdf_name'])
  for airport_element in tqdm(metafile_xml.iter('airport_name')):
    location = airport_element.attrib['icao_ident']

    if location == '':
      location = airport_element.attrib['apt_ident']

    for record_element in airport_element.iter('record'):
      chart_name = record_element.find('chart_name').text

      # Remove all text after '(CAT' or '(SA'
      cat_index = chart_name.find(' (CAT')
      if cat_index != -1:
        chart_name = chart_name[:cat_index]

      sa_index = chart_name.find(' (SA')
      if sa_index != -1:
        chart_name = chart_name[:sa_index]

      pdf_name = f'{cycle}/{record_element.find("pdf_name").text}'

      df = pd.DataFrame({
        'location': location,
        'chart_name': chart_name,
        'pdf_name': pdf_name
      }, index=[0])

      df_charts = pd.concat([df_charts, df])

  return df_charts


def approach_id_to_names(approach_id):
  second_char = approach_id[1]

  possible_names = []

  # If second char is a number, it's a runway
  if second_char >= '0' and second_char <= '9':
    approach_type = approach_id[0]
    approach_runway = approach_id[1:4].replace('-', '')
    approach_suffix = approach_id[4] if len(approach_id) > 4 else None

    rwy_name = f'RWY {approach_runway}'

    if approach_type == 'I' or approach_type == 'L':
      possible_names.append(f'ILS{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'ILS OR LOC{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'ILS{f" {approach_suffix}" if approach_suffix else ""} OR LOC {rwy_name}')
      possible_names.append(f'ILS OR LOC/DME{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'ILS OR LOC/NDB{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'ILS{f" {approach_suffix}" if approach_suffix else ""} OR LOC{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'ILS{f" {approach_suffix}" if approach_suffix else ""} OR LOC/DME{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'LOC{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'LOC/DME{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
    elif approach_type == 'B':
      possible_names.append(f'LOC BC{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'LOC/DME BC{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
    elif approach_type == 'R':
      possible_names.append(f'RNAV (GPS){f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
    elif approach_type == 'H':
      possible_names.append(f'RNAV (RNP){f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
    elif approach_type == 'P':
      possible_names.append(f'GPS{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
    elif approach_type == 'S' or approach_type == 'D' or approach_type == 'V':
      possible_names.append(f'VOR{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'VOR/DME{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'VOR{f" {approach_suffix}" if approach_suffix else ""} OR TACAN{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'VOR/DME{f" {approach_suffix}" if approach_suffix else ""} OR TACAN{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'VOR/DME OR TACAN{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'VOR/DME{f" {approach_suffix}" if approach_suffix else ""} OR TACAN {rwy_name}')
      possible_names.append(f'VOR OR GPS{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'VOR/DME OR GPS{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')

      if rwy_name[-1] == 'L' or rwy_name[-1] == 'R':
        rwy_name_lr = rwy_name[:-1] + 'L/R'

        possible_names.append(f'VOR{f" {approach_suffix}" if approach_suffix else ""} {rwy_name_lr}')
        possible_names.append(f'VOR/DME{f" {approach_suffix}" if approach_suffix else ""} {rwy_name_lr}')

    elif approach_type == 'X':
      possible_names.append(f'LDA{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
    elif approach_type == 'Q' or approach_type == 'N':
      possible_names.append(f'NDB{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
      possible_names.append(f'NDB/DME{f" {approach_suffix}" if approach_suffix else ""} {rwy_name}')
    else:
      print(f'Unknown approach type (1): {approach_type}')

  else:
    approach_type = approach_id[0:3]
    approach_suffix = approach_id[-2:]

    if approach_type == 'RNV':
      possible_names.append(f'RNAV (GPS){approach_suffix}')
    elif approach_type == 'GPS':
      possible_names.append(f'GPS{approach_suffix}')
    elif approach_type == 'VDM':
      possible_names.append(f'VOR/DME{approach_suffix}')
      possible_names.append(f'VOR/DME OR GPS{approach_suffix}')
    elif approach_type == 'VOR':
      possible_names.append(f'VOR{approach_suffix}')
      possible_names.append(f'VOR OR TACAN{approach_suffix}')
      possible_names.append(f'VOR OR TACAN OR GPS{approach_suffix}')
    elif approach_type == 'LBC':
      possible_names.append(f'LOC BC{approach_suffix}')
      possible_names.append(f'LOC/DME BC{approach_suffix}')
    elif approach_type == 'LDA':
      possible_names.append(f'LDA{approach_suffix}')
      possible_names.append(f'LDA/DME{approach_suffix}')
    elif approach_type == 'NDB':
      possible_names.append(f'NDB{approach_suffix}')
    elif approach_type == 'LOC':
      possible_names.append(f'LOC{approach_suffix}')
      possible_names.append(f'LOC/DME{approach_suffix}')
    else:
      print(f'Unknown approach type (2): {approach_type}')

  return possible_names


def merge_charts(df_faf, df_charts):
  df_faf = df_faf.copy()
  df_charts = df_charts.copy()

  print('Merging approaches with charts...')

  for index, faf in tqdm(df_faf.iterrows(), total=len(df_faf)):
    # Get the approach name
    possible_names = approach_id_to_names(faf['SIDSTARApproach_Identifier'])

    # Get the chart
    chart = None

    for approach_name in possible_names:
      chart = df_charts[
        (df_charts['location'] == faf['Airport_Identifier']) &
        (df_charts['chart_name'] == approach_name)
      ]

      if not chart.empty:
        break

    if chart is not None and not chart.empty:
      # Set the chart name
      df_faf.at[index, 'Approach_Name'] = chart['chart_name'].values[0]
      df_faf.at[index, 'PDF_Name'] = chart['pdf_name'].values[0]
    else:
      df_faf.at[index, 'Approach_Name'] = None
      df_faf.at[index, 'PDF_Name'] = None

      # print(f'\nNo chart found for {faf["SIDSTARApproach_Identifier"]} at {faf["Airport_Identifier"]}')
      # print(f'Possible names: {possible_names}')
      # print(f'All chart names: {df_charts[df_charts["location"] == faf["Airport_Identifier"]]["chart_name"].unique()}')

  # Get entries with approach_name Null
  null_entries = df_faf[df_faf['Approach_Name'].isnull()]

  print(f'{len(null_entries)} of {len(df_faf)} entries have no approach name')

  return df_faf
