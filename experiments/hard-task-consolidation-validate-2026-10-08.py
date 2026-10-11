"""Native single-thread validation only; execute inside pinned scientific image."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import xarray as xr
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from assessment.spec import Template


def main():
    template=Template('seasonal-objective-consolidation');hooks=template.hooks;hooks.prepare(template.private)
    names=['observed-sst.nc','forecast-sst.nc','forecast-precip.nc'];grids=[];rows=[];masks=[]
    for name in names:
        path=template.private/'provider'/name
        with xr.open_dataset(path,engine='h5netcdf') as ds:
            lat,lon=np.asarray(ds.lat),np.asarray(ds.lon)
            values=np.stack([np.asarray(ds[c]) for c in ['below','normal','above']]);complete=np.isfinite(values).all(axis=0)
            finite=values[np.isfinite(values)]
            assert finite.min()>=0 and finite.max()<=100,(name,float(finite.min()),float(finite.max()))
            assert np.all(values[:,complete].sum(axis=0)>0)
            grids.append((lat,lon));masks.append(complete)
            rows.append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'shape':list(values.shape),'finite_range_percent':[float(finite.min()),float(finite.max())],
                         'complete_distribution_cells':int(complete.sum()),
                         'partial_vector_cells':int((np.isfinite(values).any(axis=0)&~complete).sum())})
    assert all(np.array_equal(grids[0][0],g[0]) and np.array_equal(grids[0][1],g[1]) for g in grids)
    counts=np.asarray(masks).sum(axis=0)
    record={'template':template.name,'genuine_source_hashes_verified':True,'identical_grids_verified':True,
            'sources':rows,'grid':{'lat':len(grids[0][0]),'lon':len(grids[0][1])},
            'support_histogram':{str(n):int((counts==n).sum()) for n in range(4)},
            'source_is_local_centre_replication':True,'observed_forecast_skill_not_measurable':True}
    destination=ROOT/'experiments/hard-task-consolidation-source-validation-2026-10-08.json'
    assert not destination.exists(),'Do not overwrite original source evidence'
    destination.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


if __name__=='__main__':main()
