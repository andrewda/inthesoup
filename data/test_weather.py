"""
Tests for weather data acquisition pipeline.
Unit tests do not use credentials or the network. WEATHER_LIVE_TEST=1 also
enables a download-and-parse integration test; it never writes to BigQuery.
"""

import gzip
import os
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest
import requests
from datetime import datetime
from unittest.mock import patch
import pandas as pd

# Import functions from load_weather
import load_weather as weather
from load_weather import (
    c_to_f,
    sm_to_km,
    round_to_nearest_10,
    parse_noaa_data,
    get_metar_data,
    get_taf_data,
)


class TestTemperatureConversion:
    """Test Celsius to Fahrenheit conversion."""

    def test_freezing_point(self):
        assert c_to_f(0) == 32

    def test_boiling_point(self):
        assert c_to_f(100) == 212

    def test_negative_temperature(self):
        assert c_to_f(-40) == -40

    def test_room_temperature(self):
        assert c_to_f(20) == 68
        assert c_to_f(25) == 77


class TestDistanceConversion:
    """Test statute miles to kilometers conversion."""

    def test_one_mile(self):
        assert abs(sm_to_km(1) - 1.60934) < 0.001

    def test_ten_miles(self):
        assert abs(sm_to_km(10) - 16.0934) < 0.001

    def test_zero_miles(self):
        assert sm_to_km(0) == 0


class TestRounding:
    """Test rounding to nearest 10."""

    def test_exact_multiple(self):
        assert round_to_nearest_10(10) == 10
        assert round_to_nearest_10(20) == 20

    def test_round_up(self):
        assert round_to_nearest_10(15) == 20
        assert round_to_nearest_10(16) == 20

    def test_round_down(self):
        assert round_to_nearest_10(14) == 10
        # 5 rounds to 0 (banker's rounding)
        assert round_to_nearest_10(5) == 0

    def test_negative_numbers(self):
        # -5 rounds to 0 (banker's rounding)
        assert round_to_nearest_10(-5) == 0
        assert round_to_nearest_10(-15) == -20


def response(text='', status=200, content=b''):
    result = requests.Response()
    result.status_code = status
    result._content = content or text.encode()
    result.url = 'https://example.test/weather'
    return result


def cache(tag, records):
    root = Element('response')
    data = SubElement(root, 'data')
    for record in records:
        node = SubElement(data, tag)
        for name, value in record.items():
            if name == 'clouds':
                for attrs in value:
                    SubElement(node, 'sky_condition', attrs)
            elif value is not None:
                SubElement(node, name).text = str(value)
    return response(content=gzip.compress(tostring(root)))


@pytest.fixture
def observation():
    return {
        'station_id': 'KCVO', 'latitude': 44.5, 'longitude': -123.3,
        'observation_time': '2026-09-06T18:00:00Z',
        'raw_text': 'KCVO 061800Z 27010KT 10SM BKN015 18/12 A3000',
        'temp_c': 18, 'dewpoint_c': 12, 'wind_dir_degrees': 270,
        'wind_speed_kt': 10, 'visibility_statute_mi': '10+',
        'clouds': [
            {'sky_cover': 'SCT', 'cloud_base_ft_agl': '1000'},
            {'sky_cover': 'BKN', 'cloud_base_ft_agl': '1500'},
            {'sky_cover': 'OVC'},  # Unknown base must not break min().
        ],
    }


def metars(mock_get, observations, tafs=None):
    mock_get.side_effect = [
        cache('METAR', observations),
        cache('TAF', tafs or [{'station_id': 'KCVO', 'issue_time': '2026-09-06T17:00:00Z', 'raw_text': 'TAF KCVO'}]),
    ]
    return get_metar_data()


class TestMETARCache:
    @patch('load_weather.requests.get')
    def test_units_and_taf(self, mock_get, observation):
        frame = metars(mock_get, [observation])
        row = frame.iloc[0]
        assert row.CIG == 15  # API multiplies by 100 to return 1,500 ft AGL.
        assert row.LCB == 10
        assert row.TMP == pytest.approx(64.4)
        assert row.DPT == pytest.approx(53.6)
        assert row.WDR == 27
        assert row.WSP == 10
        assert row.VIS == pytest.approx(160.934)
        assert row.TAF == 'TAF KCVO'
        assert pd.isna(row.IFC)
        assert all(frame[col].dtype == 'float64' for col in weather.NUMERIC_METAR_COLUMNS)
        assert mock_get.call_count == 2
        assert 'cache' in mock_get.call_args_list[0].args[0]

    @pytest.mark.parametrize('visibility,expected', [(None, None), ('', None), ('2.5', 2.5), (2.5, 2.5), ('1/2', .5), ('10+', 10), ('0', 0)])
    @patch('load_weather.requests.get')
    def test_visibility(self, mock_get, observation, visibility, expected):
        observation['visibility_statute_mi'] = visibility
        row = metars(mock_get, [observation]).iloc[0]
        if expected is None:
            assert pd.isna(row.VIS)
        else:
            assert row.VIS == pytest.approx(expected * 16.0934)

    @patch('load_weather.requests.get')
    def test_missing_optional_values(self, mock_get, observation):
        for field in ['temp_c', 'dewpoint_c', 'wind_dir_degrees', 'wind_speed_kt', 'visibility_statute_mi', 'clouds']:
            observation.pop(field)
        row = metars(mock_get, [observation]).iloc[0]
        assert all(pd.isna(row[field]) for field in weather.NUMERIC_METAR_COLUMNS)

    @patch('load_weather.requests.get')
    def test_variable_wind_and_vertical_visibility(self, mock_get, observation):
        observation.update(wind_dir_degrees='VRB', clouds=[{'sky_cover': 'OVX'}], vert_vis_ft=300)
        row = metars(mock_get, [observation]).iloc[0]
        assert row.WDR == 0
        assert row.CIG == 3
        assert row.LCB == 3

    @patch('load_weather.requests.get')
    def test_latest_observation_and_geography(self, mock_get, observation):
        old = dict(observation, observation_time='2026-09-06T17:00:00.000Z', temp_c=0)
        outside = dict(observation, station_id='EGLL', longitude=0)
        missing_station = dict(observation, station_id=None)
        frame = metars(mock_get, [old, outside, missing_station, observation])
        assert len(frame) == 1
        assert frame.iloc[0].TMP == pytest.approx(64.4)

    @patch('load_weather.requests.get')
    def test_latest_taf(self, mock_get, observation):
        tafs = [
            {'station_id': 'KCVO', 'issue_time': '2026-09-06T18:00:00Z', 'raw_text': 'new'},
            {'station_id': 'KCVO', 'issue_time': '2026-09-06T17:00:00Z', 'raw_text': 'old'},
        ]
        assert metars(mock_get, [observation], tafs).iloc[0].TAF == 'new'

    @patch('load_weather.requests.get')
    def test_missing_taf_is_null(self, mock_get, observation):
        assert metars(mock_get, [observation], [{'station_id': 'KSEA', 'raw_text': 'TAF KSEA'}]).iloc[0].TAF is None

    @patch('load_weather.requests.get')
    def test_empty_cache_fails(self, mock_get):
        mock_get.return_value = cache('METAR', [])
        with pytest.raises(ValueError, match='Empty metars'):
            get_metar_data()

    @patch('load_weather.requests.get')
    def test_invalid_compressed_data_fails(self, mock_get):
        mock_get.return_value = response('<html>Error</html>')
        with pytest.raises(gzip.BadGzipFile):
            get_metar_data()

    @patch('load_weather.requests.get')
    def test_missing_timestamp_fails(self, mock_get, observation):
        observation.pop('observation_time')
        with pytest.raises(ValueError, match='Missing observation time'):
            metars(mock_get, [observation])


def listing(*names):
    return response(''.join(f'<a href="{name}">{name}</a>' for name in names))


class TestNOAAAccess:
    @patch('load_weather.requests.get')
    def test_latest_complete_pair_crosses_midnight(self, mock_get):
        mock_get.side_effect = [
            listing('blend.20260905/', '../', 'blend.20260906/'),
            listing('00/'), listing('blend_nbhtx.t00z'),
            listing('22/', '23/'), listing('blend_nbhtx.t23z', 'blend_nbstx.t23z'),
            response('NBH data'), response('NBS data'),
        ]
        assert weather.get_noaa_data() == ('NBH data', 'NBS data')
        urls = [call.args[0] for call in mock_get.call_args_list]
        assert all(url.startswith('https://nomads.ncep.noaa.gov/') for url in urls)
        assert urls[-1].endswith('blend.20260905/23/text/blend_nbstx.t23z')
        assert all(call.kwargs['timeout'] == (10, 60) for call in mock_get.call_args_list)

    @patch('load_weather.requests.get')
    def test_missing_text_directory_falls_back(self, mock_get):
        mock_get.side_effect = [listing('blend.20260906/'), listing('16/', '17/'),
                               response(status=404), listing('blend_nbhtx.t16z', 'blend_nbstx.t16z'),
                               response('NBH data'), response('NBS data')]
        assert weather.get_noaa_data() == ('NBH data', 'NBS data')

    @patch('load_weather.requests.get')
    def test_no_complete_cycle_fails(self, mock_get):
        mock_get.side_effect = [listing('blend.20260906/'), listing('17/'), listing('blend_nbhtx.t17z')]
        with pytest.raises(RuntimeError, match='No complete'):
            weather.get_noaa_data()

    @patch('load_weather.requests.get')
    def test_fallback_is_bounded(self, mock_get):
        mock_get.side_effect = [listing('blend.20260906/'), listing(*(f'{h:02}/' for h in range(24)))] + [listing()] * 6
        with pytest.raises(RuntimeError, match='latest six'):
            weather.get_noaa_data()
        assert mock_get.call_count == 8

    @patch('load_weather.time.sleep')
    @patch('load_weather.requests.get')
    def test_timeout_retries_are_bounded(self, mock_get, sleep):
        mock_get.side_effect = requests.Timeout('timed out')
        with pytest.raises(requests.Timeout):
            weather.fetch('https://example.test')
        assert mock_get.call_count == 3
        assert [call.args[0] for call in sleep.call_args_list] == [2, 4]

    @pytest.mark.parametrize('status', [400, 403, 404])
    @patch('load_weather.time.sleep')
    @patch('load_weather.requests.get')
    def test_permanent_http_errors_do_not_retry(self, mock_get, sleep, status):
        mock_get.return_value = response(status=status)
        with pytest.raises(requests.HTTPError):
            weather.fetch('https://example.test')
        assert mock_get.call_count == 1
        sleep.assert_not_called()

    @pytest.mark.parametrize('status', [429, 500, 503])
    @patch('load_weather.time.sleep')
    @patch('load_weather.requests.get')
    def test_transient_http_failure_recovers(self, mock_get, sleep, status):
        mock_get.side_effect = [response(status=status), response('OK')]
        assert weather.fetch('https://example.test').text == 'OK'
        sleep.assert_called_once_with(2)


def station_product(fmt):
    header = 'KCVO NBM V4.3 ' + ('NBH' if fmt == 'nbh' else 'NBS') + ' GUIDANCE 09/06/2026 2300 UTC'
    lines = [header]
    if fmt == 'nbs':
        lines.append(' DT /SEPT 07')
    hours = [0, 1] if fmt == 'nbh' else [3, 6]
    for field in ['UTC', 'CIG', 'LCB', 'VIS', 'IFC', 'TMP', 'DPT', 'WDR', 'WSP']:
        values = hours if field == 'UTC' else [10, 20]
        lines.append(f' {field:<4}' + ''.join(f'{value:3}' for value in values))
    return '\n'.join(lines)


class TestNOAAParsing:
    @pytest.mark.parametrize('fmt,count,first_hour', [('nbh', 25, 18), ('nbs', 23, 21)])
    def test_real_noaa_v5_bulletin(self, fmt, count, first_hour):
        product = (Path(__file__).parent / 'fixtures' / f'noaa_{fmt}.txt').read_text()
        frame = weather.parse_noaa_product(product, fmt)
        assert len(frame) == count
        assert frame.Location.unique().tolist() == ['KCVO']
        assert frame.iloc[0].Time == datetime(2026, 9, 6, first_hour)
        assert frame.Time.is_monotonic_increasing
        assert not frame.UTC.isna().any()

    def test_sparse_row_does_not_split_station(self):
        product = station_product('nbh') + '\n P06 ' + ' ' * 60 + '\n'
        assert len(weather.parse_noaa_product(product, 'nbh')) == 2

    def test_non_aviation_site_can_omit_ifc(self):
        buoy = '\n'.join(line for line in station_product('nbh').replace('KCVO', '46001').splitlines() if not line.startswith(' IFC'))
        frame = weather.parse_noaa_product(station_product('nbh') + '\n' + buoy, 'nbh')
        assert len(frame) == 4
        assert frame.loc[frame.Location == '46001', 'IFC'].isna().all()

    def test_incomplete_station_fails(self):
        product = '\n'.join(line for line in station_product('nbh').splitlines() if not line.startswith(' CIG'))
        with pytest.raises(ValueError, match='Incomplete'):
            weather.parse_noaa_product(product, 'nbh')

    @pytest.mark.parametrize('fmt,hour', [('nbh', 0), ('nbs', 3)])
    def test_forecast_dates_across_midnight(self, fmt, hour):
        frame = parse_noaa_data(station_product(fmt), fmt)
        assert len(frame) == 2
        assert frame.iloc[0].Time == datetime(2026, 9, 7, hour)
        assert frame.iloc[0].Forecast_Time == datetime(2026, 9, 6, 23)
        assert frame.iloc[0].CIG == 10

    @pytest.mark.parametrize('fmt', ['nbh', 'nbs'])
    def test_complete_product(self, fmt):
        product = 'NOAA bulletin\n' + ' ' * 50 + '\n' + station_product(fmt)
        assert len(weather.parse_noaa_product(product, fmt)) == 2

    @pytest.mark.parametrize('text', ['', '<html>Service unavailable</html>', 'invalid'])
    def test_invalid_product_fails(self, text):
        with pytest.raises(ValueError, match='No stations'):
            weather.parse_noaa_product(text, 'nbh')


def taf_period(start, end, change=None, dir=270, speed=10, vis='10+', clouds=None):
    return {
        'fcst_time_from': f'2026-09-{6 + start // 24:02d}T{start % 24:02d}:00:00Z',
        'fcst_time_to': f'2026-09-{6 + end // 24:02d}T{end % 24:02d}:00:00Z',
        'change_indicator': change,
        'wind_dir_degrees': dir,
        'wind_speed_kt': speed,
        'visibility_statute_mi': vis,
        'clouds': clouds if clouds is not None else [{'sky_cover': 'OVC', 'cloud_base_ft_agl': '1500'}],
    }


def taf_record(periods, station='KCVO', issue_time='2026-09-06T17:39:00Z'):
    return {'station_id': station, 'issue_time': issue_time, 'periods': periods}


def taf_cache(records):
    root = Element('response')
    data = SubElement(root, 'data')
    for record in records:
        node = SubElement(data, 'TAF')
        for name, value in record.items():
            if name == 'periods':
                for period in value:
                    forecast = SubElement(node, 'forecast')
                    for key, item in period.items():
                        if key == 'clouds':
                            for attrs in item:
                                SubElement(forecast, 'sky_condition', attrs)
                        elif item is not None:
                            SubElement(forecast, key).text = str(item)
            else:
                SubElement(node, name).text = str(value)
    return response(content=gzip.compress(tostring(root)))


def tafs(mock_get, records):
    mock_get.return_value = taf_cache(records)
    return get_taf_data()


class TestTAFCache:
    @patch('load_weather.requests.get')
    def test_hourly_rows_and_units(self, mock_get):
        frame = tafs(mock_get, [taf_record([taf_period(18, 22)])])
        assert len(frame) == 4
        row = frame.iloc[0]
        assert row.Time == datetime(2026, 9, 6, 18, tzinfo=pd.Timestamp.now(tz='UTC').tz)
        assert row.Location == 'KCVO'
        assert row.Forecast_Time == datetime(2026, 9, 6, 17, 39, tzinfo=pd.Timestamp.now(tz='UTC').tz)
        assert row.CIG == 15  # API multiplies by 100 to return 1,500 ft AGL.
        assert row.LCB == 15
        assert row.WDR == 27
        assert row.WSP == 10
        assert row.VIS == pytest.approx(160.934)
        assert pd.isna(row.IFC)
        assert all(frame[col].dtype == 'float64' for col in weather.NUMERIC_TAF_COLUMNS)

    @patch('load_weather.requests.get')
    def test_tempo_overrides_base_only_in_its_window(self, mock_get):
        periods = [
            taf_period(18, 30, clouds=[{'sky_cover': 'BKN', 'cloud_base_ft_agl': '8000'}]),
            taf_period(20, 23, change='TEMPO', clouds=[{'sky_cover': 'BKN', 'cloud_base_ft_agl': '2000'}]),
        ]
        frame = tafs(mock_get, [taf_record(periods)]).set_index('Time')
        assert frame.loc['2026-09-06 19:00Z', 'CIG'] == 80
        assert frame.loc['2026-09-06 20:00Z', 'CIG'] == 20
        assert frame.loc['2026-09-06 22:00Z', 'CIG'] == 20
        assert frame.loc['2026-09-06 23:00Z', 'CIG'] == 80
        assert frame.loc['2026-09-07 05:00Z', 'CIG'] == 80

    @patch('load_weather.requests.get')
    def test_becmg_and_prob_are_skipped(self, mock_get):
        periods = [
            taf_period(18, 30, clouds=[{'sky_cover': 'BKN', 'cloud_base_ft_agl': '8000'}]),
            taf_period(20, 22, change='BECMG', clouds=[{'sky_cover': 'BKN', 'cloud_base_ft_agl': '1000'}]),
            taf_period(21, 24, change='PROB30', clouds=[{'sky_cover': 'OVC', 'cloud_base_ft_agl': '500'}]),
        ]
        frame = tafs(mock_get, [taf_record(periods)])
        assert frame.CIG.unique().tolist() == [80]

    @patch('load_weather.requests.get')
    def test_few_and_nsc_are_not_ceilings(self, mock_get):
        clouds = [{'sky_cover': 'FEW', 'cloud_base_ft_agl': '500'}, {'sky_cover': 'SCT', 'cloud_base_ft_agl': '900'}]
        row = tafs(mock_get, [taf_record([taf_period(18, 19, clouds=clouds)])]).iloc[0]
        assert pd.isna(row.CIG)
        # Lowest cloud base matches the METAR rule: FEW is excluded.
        assert row.LCB == 9

    @patch('load_weather.requests.get')
    def test_ovx_is_a_surface_ceiling(self, mock_get):
        row = tafs(mock_get, [taf_record([taf_period(18, 19, clouds=[{'sky_cover': 'OVX'}])])]).iloc[0]
        assert row.CIG == 0
        assert row.LCB == 0

    @patch('load_weather.requests.get')
    def test_missing_wind_and_visibility_are_null(self, mock_get):
        row = tafs(mock_get, [taf_record([taf_period(18, 19, dir=None, speed=None, vis=None, clouds=[])])]).iloc[0]
        assert all(pd.isna(row[col]) for col in ['WDR', 'WSP', 'CIG', 'LCB', 'VIS'])

    @patch('load_weather.requests.get')
    def test_empty_cache_fails(self, mock_get):
        mock_get.return_value = taf_cache([])
        with pytest.raises(ValueError, match='Empty tafs'):
            get_taf_data()


class TestRefresh:
    @patch('load_weather.pandas_gbq.to_gbq')
    @patch('load_weather.google.auth.default')
    @patch('load_weather.get_noaa_data', side_effect=requests.Timeout('NOAA unavailable'))
    @patch('load_weather.get_taf_data', return_value=pd.DataFrame({'Location': ['KCVO']}))
    @patch('load_weather.get_metar_data', return_value=pd.DataFrame({'Location': ['KCVO']}))
    def test_failed_download_prevents_all_uploads(self, metar, taf, noaa, auth, upload):
        with pytest.raises(requests.Timeout):
            weather.main()
        auth.assert_not_called()
        upload.assert_not_called()

    @patch('load_weather.pandas_gbq.to_gbq')
    @patch('load_weather.google.auth.default')
    @patch('load_weather.parse_noaa_product')
    @patch('load_weather.get_noaa_data', return_value=('nbh', 'nbs'))
    @patch('load_weather.get_taf_data')
    @patch('load_weather.get_metar_data')
    def test_dry_run_needs_no_credentials_or_writes(self, metar, taf, noaa, parse, auth, upload):
        frame = pd.DataFrame({'Forecast_Time': [datetime(2026, 9, 6)]})
        metar.return_value = taf.return_value = parse.return_value = frame
        assert len(weather.main(dry_run=True)) == 4
        auth.assert_not_called()
        upload.assert_not_called()

    @patch('load_weather.pandas_gbq.to_gbq')
    @patch('load_weather.google.auth.default', return_value=('credentials', 'inthesoup'))
    @patch('load_weather.parse_noaa_product')
    @patch('load_weather.get_noaa_data', return_value=('nbh', 'nbs'))
    @patch('load_weather.get_taf_data')
    @patch('load_weather.get_metar_data')
    def test_uploads_and_explicit_metar_schema(self, metar, taf, noaa, parse, auth, upload):
        frame = pd.DataFrame({'Forecast_Time': [datetime(2026, 9, 6)]})
        metar.return_value = taf.return_value = parse.return_value = frame
        weather.main()
        assert [call.args[1] for call in upload.call_args_list] == ['weather.metar', 'weather.taf', 'weather.nbh', 'weather.nbs']
        assert {'name': 'IFC', 'type': 'FLOAT'} in upload.call_args_list[0].kwargs['table_schema']


@pytest.mark.skipif(os.environ.get('WEATHER_LIVE_TEST') != '1', reason='Set WEATHER_LIVE_TEST=1 for live downloads')
def test_live_weather_downloads():
    tables = weather.main(dry_run=True)
    assert all(not frame.empty for frame in tables.values())
    assert tables['weather.metar'].Location.is_unique
    for frame in tables.values():
        source_time = pd.to_datetime(frame.Forecast_Time, utc=True).max()
        assert pd.Timestamp.now(tz='UTC') - source_time < pd.Timedelta(hours=12)
