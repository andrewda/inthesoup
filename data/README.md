# Weather loader

`load_weather.py` downloads NBH/NBS guidance from NOAA's HTTPS NOMADS feed and
METAR/TAF observations from the Aviation Weather Center's compressed XML caches.
METARs retain the existing geographic bounds (25–50° N, 125–65° W). Bulk caches
avoid the query API's result limit. Each station retains its newest observation.

Install `data/requirements.txt` in a Python environment, then run from the repo root:

```sh
python3 -m pytest data/test_weather.py -q
python3 -u data/load_weather.py --dry-run
```

The dry run downloads and parses all feeds, prints row counts, source timestamps,
and elapsed time, and needs no Google credentials. To include live downloads and
a source freshness check in pytest:

```sh
WEATHER_LIVE_TEST=1 python3 -m pytest data/test_weather.py -q -s
```

Running without `--dry-run` replaces `weather.metar`, `weather.nbh`, and
`weather.nbs` using Application Default Credentials. All feeds are downloaded
and parsed before any uploads begin. Download or parsing failures exit nonzero;
an upload failure can still leave earlier tables updated, since the three table
replacements are separate operations.

Requests use 10-second connect and 60-second read timeouts, with up to three
attempts for transient failures and 2/4-second retry delays. NOAA selection checks
up to six recent cycles for a complete NBH/NBS pair, including the previous day
when necessary. The GitHub weather job also has a 15-minute overall timeout.

METAR cloud heights are converted from feet AGL to hundreds of feet to match the
forecast tables and API. Optional weather values remain null, and numeric METAR
columns (including the all-null IFC column) have explicit numeric types.

Sources:
- [NOAA text products](https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/)
- [AWC bulk caches and API limits](https://aviationweather.gov/data/api/#cache)

The NOAA regression fixtures contain KCVO bulletins from the September 6, 2026,
17Z cycle. Their original fixed-width spacing is intentional.
