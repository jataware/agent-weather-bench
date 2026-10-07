"""Independent explicit cell integrals and empirical interpolation controls."""
import json,math
from pathlib import Path
import numpy as np,xarray as xr
try:from .reference import build,fit,infer,geometry,aggregate
except ImportError:from reference import build,fit,infer,geometry,aggregate


def independent_area_means(fine,lat,lon):
    result=np.zeros((fine.shape[0],4))
    for c,(south,west) in enumerate([(.5,36.5),(.5,37.5),(1.5,36.5),(1.5,37.5)]):
        denominator=0
        for i,y in enumerate(lat):
            for j,x in enumerate(lon):
                if south<y<south+1 and west<x<west+1:
                    area=6371000.0**2*(math.sin(math.radians(y+.025))-math.sin(math.radians(y-.025)))*math.radians(.05)
                    denominator+=area;result[:,c]+=fine[:,i,j]*area
        result[:,c]/=denominator
    return result


def independent_mapping(value,raw,observed):
    # Actual four source cells have unique ranks; ties supported in reference are separately tested.
    xs=sorted(float(x) for x in raw);ys=sorted(float(y) for y in observed)
    if value<=xs[0]:return ys[0]
    if value>=xs[-1]:return ys[-1]
    for j in range(len(xs)-1):
        if xs[j]<=value<=xs[j+1]:return ys[j]+(ys[j+1]-ys[j])*(value-xs[j])/(xs[j+1]-xs[j])
    raise ValueError('No matching empirical interval')


def audit(private):
    private=Path(private);inputs=private/'agent-inputs'
    forecast,hindcasts,state=build(inputs)
    with xr.open_dataset(inputs/'fine-training.nc') as f:training=f.load()
    with xr.open_dataset(inputs/'coarse-forecast.nc') as f:raw=f.load()
    area,cell=geometry(training.lat,training.lon)
    explicit=independent_area_means(training.seasonal_total.values,training.lat.values,training.lon.values)
    vector=aggregate(training.seasonal_total.values,area,cell)
    aggregation_error=float(np.max(abs(explicit-vector)))
    pp=independent_area_means(forecast.rainfall_mm.values,forecast.lat.values,forecast.lon.values)
    conservation_error=float(np.max(abs(pp-forecast.mapped_coarse_mm.values)))
    mappings=np.array([[independent_mapping(x,raw.raw_predictor.sel(year=slice(1993,2008)).values[:,c],explicit[:,c]) for c,x in enumerate(row)] for row in raw.raw_predictor.sel(year=slice(2009,None)).values])
    interpolation_error=float(np.max(abs(mappings-forecast.mapped_coarse_mm.values)))
    scaled=fit(np.asarray(state['training_raw'])*92+7,training.seasonal_total.values,area,cell)
    x=raw.raw_predictor.sel(year=slice(2009,None)).values
    scaled_coarse,scaled_fine=infer(x*92+7,scaled,cell)
    scale_error=float(np.max(abs(scaled_fine-forecast.rainfall_mm.values)))
    # Geometry partition: exact sum of 20×20 fine cells equals each analytic one-degree spherical cell.
    area_error=[]
    for c,south in enumerate([.5,.5,1.5,1.5]):
        exact=6371000.0**2*(math.sin(math.radians(south+1))-math.sin(math.radians(south)))*math.radians(1)
        area_error.append(abs(np.sum(area[cell==c])-exact)/exact)
    assert aggregation_error<1e-9 and conservation_error<1e-9 and interpolation_error<1e-9 and scale_error<1e-9 and max(area_error)<1e-12
    return {'independent_training_aggregation_max_error_mm':aggregation_error,'independent_conservation_max_error_mm':conservation_error,'independent_empirical_mapping_max_error_mm':interpolation_error,'positive_affine_raw_scale_invariance_max_error_mm':scale_error,'maximum_relative_spherical_partition_error':max(area_error),'all_passed':True,'scientific_approval':False,'controller_final_outcomes_pristine':False}
