"""CIFP/chart regressions; set CIFP_LIVE_TEST=1 for a read-only live test."""

import os
from unittest.mock import patch
import xml.etree.ElementTree as ET

import pandas as pd
import pytest
import requests

from charts import get_charts, merge_charts
import load_cifp


METAFILE = '''<?xml version="1.0" encoding="{encoding}"?>
<digital_tpp cycle="2609">
  <state_code><city_name>
    <airport_name icao_ident="KCVO" apt_ident="CVO">
      <record><chart_name>ILS OR LOC RWY 17 (CAT II)</chart_name><pdf_name>00001IL17.PDF</pdf_name></record>
      <record><chart_name>RNAV (GPS) RWY 35 (SA CAT I)</chart_name><pdf_name>00001R35.PDF</pdf_name></record>
      <record><chart_name>Café</chart_name><pdf_name>00001AD.PDF</pdf_name></record>
    </airport_name>
    <airport_name icao_ident="" apt_ident="7S5">
      <record><chart_name>RNAV (GPS) RWY 16</chart_name><pdf_name>00002R16.PDF</pdf_name></record>
    </airport_name>
  </city_name></state_code>
</digital_tpp>'''


def response(content, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = 'https://aeronav.faa.gov/d-tpp/2609/xml_data/d-tpp_Metafile.xml'
    result.headers['Content-Type'] = 'text/xml'
    # Reproduce requests' decoding when FAA omits the HTTP charset.
    result.encoding = 'ISO-8859-1'
    result._content = content
    return result


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-8', 'utf-16'])
@patch('charts.requests.get')
def test_xml_encoding_is_taken_from_bytes(mock_get, encoding):
    declaration = 'utf-8' if encoding == 'utf-8-sig' else encoding
    raw = METAFILE.format(encoding=declaration).encode(encoding)
    mock_get.return_value = response(raw)
    if encoding == 'utf-8-sig':
        # This is the exact failure mode in the production workflow.
        with pytest.raises(ET.ParseError):
            ET.fromstring(mock_get.return_value.text)
    charts = get_charts('2609')
    assert len(charts) == 4
    assert charts.chart_name.tolist() == [
        'ILS OR LOC RWY 17', 'RNAV (GPS) RWY 35', 'Café', 'RNAV (GPS) RWY 16',
    ]
    assert charts.location.tolist() == ['KCVO', 'KCVO', 'KCVO', '7S5']
    assert charts.pdf_name.iloc[0] == '2609/00001IL17.PDF'
    assert mock_get.call_args.kwargs['timeout'] == (10, 60)


@pytest.mark.parametrize('status', [403, 404, 500])
@patch('charts.requests.get')
def test_http_failure_is_reported_before_xml_parsing(mock_get, status):
    mock_get.return_value = response(b'Not XML', status)
    with pytest.raises(requests.HTTPError) as error:
        get_charts('2609')
    assert error.value.response.status_code == status


@patch('charts.requests.get')
def test_malformed_xml_fails(mock_get):
    mock_get.return_value = response(b'not XML')
    with pytest.raises(ET.ParseError):
        get_charts('2609')


@pytest.mark.parametrize('xml', [b'<html/>', b'<digital_tpp cycle="2608"/>'])
@patch('charts.requests.get')
def test_wrong_document_or_cycle_fails(mock_get, xml):
    mock_get.return_value = response(xml)
    with pytest.raises(ValueError, match='Unexpected FAA'):
        get_charts('2609')


@patch('charts.requests.get')
def test_empty_chart_catalog_fails(mock_get):
    mock_get.return_value = response(b'<digital_tpp cycle="2609"/>')
    with pytest.raises(ValueError, match='No charts'):
        get_charts('2609')


@patch('charts.requests.get')
def test_parsed_charts_merge_into_approaches(mock_get):
    mock_get.return_value = response(METAFILE.format(encoding='utf-8').encode('utf-8-sig'))
    charts = get_charts('2609')
    faf = pd.DataFrame({
        'Airport_Identifier': ['KCVO', 'KCVO', 'KXYZ'],
        'SIDSTARApproach_Identifier': ['I17', 'R35', 'R09'],
    })
    merged = merge_charts(faf, charts)
    assert merged.PDF_Name.tolist() == ['2609/00001IL17.PDF', '2609/00001R35.PDF', None]


def test_fap_extracted_for_approaches_without_faf():
    # 09J VOR-A has no FAF; the on-airport VOR (SSI) is coded as the FAP ('V  F').
    fixture = os.path.join(os.path.dirname(__file__), 'fixtures', 'fap_vor_a.txt')
    airports, faf = load_cifp.parse_cifp(fixture)
    assert airports['Airport ICAO Identifier'].tolist() == ['09J']
    assert faf['SID/STAR/Approach Identifier'].tolist() == ['VOR-A']
    assert faf['Fix Identifier'].tolist() == ['SSI']
    assert faf['Waypoint Description Code'].tolist() == ['V  F']
    assert faf.Altitude.tolist() == ['01000']


@pytest.mark.parametrize('function,args', [(load_cifp.get_current_cifp_cycle, ()),
                                          (load_cifp.download_cifp, ('https://example.test/cifp.zip',))])
@patch('load_cifp.requests.get')
def test_cifp_http_errors_fail_before_parsing_or_extraction(mock_get, function, args):
    mock_get.return_value = response(b'Not a download', status=503)
    with pytest.raises(requests.HTTPError):
        function(*args)
    assert mock_get.call_args.kwargs['timeout'] == (10, 60)


@pytest.mark.skipif(os.environ.get('CIFP_LIVE_TEST') != '1', reason='Set CIFP_LIVE_TEST=1 for live FAA downloads')
def test_live_cifp_dry_run():
    with patch('load_cifp.google.auth.default') as auth, patch('load_cifp.pandas_gbq.to_gbq') as upload:
        airports, faf = load_cifp.main(dry_run=True)
    auth.assert_not_called()
    upload.assert_not_called()
    assert not airports.empty and not faf.empty
    assert faf.PDF_Name.notna().any()
    assert (airports.Airport_ICAO_Identifier == 'KCVO').any()
    assert faf.loc[faf.Airport_Identifier == 'KCVO', 'PDF_Name'].notna().any()
