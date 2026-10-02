"""Check Rosetta normalization against provider data, without evaluation years.

forecast-provider-raw.nc is the original 56 KB CDS response retained from the
development request, job dfaf0d69-552b-475d-84fb-ff75e2492ee2. This script does
not submit additional forecast jobs. It samples one development CHIRPS COG.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
source = ROOT/'data/forecast-provider-raw.nc'
raw = xr.load_dataset(source)['tprate']
assert raw.attrs['units'] == 'm s**-1'
np.testing.assert_array_equal(raw.forecast_reference_time.dt.year, np.arange(1993, 2009))
renames = dict(number='member', forecast_reference_time='init_time', forecastMonth='lead_time',
               latitude='lat', longitude='lon')
expected = (raw.rename(renames).sortby('lat').sortby('lon') * 86_400_000).transpose('member','init_time','lead_time','lat','lon')
actual = xr.load_dataset(ROOT/'data/forecast-development.nc')['precip'].transpose(*expected.dims)
np.testing.assert_allclose(expected.values, actual.values, atol=1e-5, rtol=1e-6)
for name in expected.dims:
    np.testing.assert_array_equal(expected[name], actual[name])

url = 'https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/chirps-v3.0.1993.10.cog'
obs = xr.load_dataset(ROOT/'data/observations-development.nc')['precip'].sel(time='1993-10-01')
positions = [(i,j) for i in [0,obs.sizes['lat']//2,obs.sizes['lat']-1]
                   for j in [0,obs.sizes['lon']//2,obs.sizes['lon']-1]]
points = [(float(obs.lon[j]), float(obs.lat[i])) for i,j in positions]
with rasterio.open(url) as raster:
    values = np.array([v[0] for v in raster.sample(points)])
normalized = np.array([obs.values[i,j] for i,j in positions])
np.testing.assert_array_equal(values, normalized)
report = {
    'status': 'PASS', 'evaluation_years_accessed': False,
    'forecast': {
        'dataset_url': 'https://cds.climate.copernicus.eu/datasets/seasonal-monthly-single-levels',
        'job_id': 'dfaf0d69-552b-475d-84fb-ff75e2492ee2',
        'request': {'originating_centre':'ecmwf', 'system':'51', 'variable':'total_precipitation',
                    'product_type':'monthly_mean', 'year':list(map(str,range(1993,2009))),
                    'month':['09'], 'leadtime_month':['2','3','4'], 'area':[1,36,-3,39], 'data_format':'netcdf'},
        'provider_units':'m s**-1', 'normalized_units':'mm/day', 'conversion_factor':86_400_000,
        'max_absolute_conversion_difference':float(np.max(np.abs(expected.values-actual.values))),
        'provider_response_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    },
    'observations': {
        'sampled_url':url, 'exact_native_pixel_matches':len(positions),
        'raw_stores':[f'https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/chirps-v3.0.{year}.{month:02d}.cog'
                      for year in range(1993,2009) for month in [10,11,12]],
    },
}
(ROOT/'results/source-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: all ECMWF values/coordinates and unit conversion; nine raw CHIRPS pixel checks.')
