# In the Soup ☁️

Find nearby instrument approaches in IMC.

> **Warning**
> This app is not to be used for flight planning or navigational purposes. The
> weather data is not guaranteed to be accurate, and the instrument approach
> data is not guaranteed to be complete. Use at your own risk.

## What is this?

This is a web app that allows you to search for nearby instrument approaches in
instrument meteorological conditions (IMC). It uses the [NOAA National Blend of Models][nbm]
to get cloud ceiling forecasts, and joins them with instrument approach data
from the FAA's [Coded Instrument Flight Procedures (CIFP)][cifp]. With this
information, pilots can more easily plan flights to improve their proficiency
flying in IMC.

[nbm]: https://blend.mdl.nws.noaa.gov/
[cifp]: https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/cifp/

## Infrastructure

This app uses [Google App Engine][gae] to host a Node.js server running
[Next.js][next]. The backend portion of the app is very simple, and just runs
a query against a few [Google BigQuery][bq] tables. Weather forecasts are
regularly fetched from NOAA using GitHub Actions and loaded into BigQuery.
Similarly, the FAA's CIFP data is periodically fetched by a GitHub Action and
loaded into BigQuery.

[gae]: https://cloud.google.com/appengine/
[next]: https://nextjs.org/
[bq]: https://cloud.google.com/bigquery/

## Running locally

*TODO*
