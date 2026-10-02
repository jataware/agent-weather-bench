"""Make common asynchronous HTTP clients honor the same proxy as requests."""
try:
    import aiohttp
    original = aiohttp.ClientSession.__init__
    def init(self, *args, **kwargs):
        kwargs.setdefault("trust_env", True)
        original(self, *args, **kwargs)
    aiohttp.ClientSession.__init__ = init
except ImportError:
    pass

# Use the same HDF5 backend in every arm. The original netCDF4 wheel aborted
# during reads/cleanup in the smoke; h5netcdf avoids that defective binding.
try:
    import xarray as xr
    xr.set_options(netcdf_engine_order=['h5netcdf', 'scipy', 'netcdf4'])
except ImportError:
    pass
