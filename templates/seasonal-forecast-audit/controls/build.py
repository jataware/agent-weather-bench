import json
import shutil
import subprocess
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
CONTROLS={
 'correct':{'kind':'known_correct','expect':{}},
 'valid_climatology':{'kind':'accepted_alternative','variant':{'method':'climatology'},'expect':{}},
 'valid_float32':{'kind':'accepted_alternative','variant':{'method':'float32'},'expect':{}},
 'global_preprocessing':{'kind':'incorrect','variant':{'defect':'global_preprocessing'},'expect':{'probe.first_year_isolation':'fail','probe.middle_year_isolation':'fail','probe.last_year_isolation':'fail'}},
 'global_selection':{'kind':'incorrect','variant':{'defect':'global_selection'},'expect':{'probe.first_year_isolation':'fail','probe.middle_year_isolation':'fail','probe.last_year_isolation':'fail'}},
 'localized_lookahead':{'kind':'incorrect','variant':{'defect':'localized_lookahead'},'expect':{'probe.year_2006_isolation':'fail','probe.year_2007_isolation':'fail'}},
 'uses_targets':{'kind':'incorrect','variant':{'defect':'uses_targets'},'expect':{'probe.first_year_isolation':'fail','probe.middle_year_isolation':'fail','probe.last_year_isolation':'fail'}},
 'localized_future_features':{'kind':'incorrect','variant':{'defect':'localized_future_features'},'expect':{'probe.year_2006_isolation':'fail'}},
 'localized_production_features':{'kind':'incorrect','variant':{'defect':'localized_production_features'},'expect':{'probe.production_2021_isolation':'fail'}},
 'global_future_features':{'kind':'incorrect','variant':{'defect':'global_future_features'},'expect':{}},
 'pooled_features':{'kind':'incorrect','variant':{'defect':'pooled_features'},'expect':{'probe.forecast_batch_isolation':'fail'}},
 'cached':{'kind':'incorrect','variant':{'defect':'cached'},'expect':{'probe.responds_to_inputs':'fail'}},
 'cached_hindcasts':{'kind':'incorrect','variant':{'defect':'cached_hindcasts'},'expect':{'probe.responds_to_inputs':'fail'}},
 'cached_forecasts':{'kind':'incorrect','variant':{'defect':'cached_forecasts'},'expect':{'probe.responds_to_inputs':'fail'}},
 'false_skill':{'kind':'incorrect','variant':{'defect':'false_skill','method':'climatology'},'expect':{'claim.repaired_beats_climatology':'fail'}},
 'wrong_metric':{'kind':'incorrect','variant':{'defect':'wrong_metric'},'expect':{'invariant.metric_identity':'fail'}},
 'false_audit':{'kind':'incorrect','variant':{'defect':'false_audit'},'expect':{'claim.original_report_supported':'fail'}},
}
for _name in ('global_preprocessing','global_selection','uses_targets','global_future_features'):
    CONTROLS[_name]['expect'].update({f'probe.year_{year}_isolation':'fail' for year in range(2005,2020) if year not in (2005,2012,2019)})
CONTROLS['global_future_features']['expect'].update({f'probe.{name}':'fail' for name in ('first_year_isolation','middle_year_isolation','last_year_isolation')})
CONTROLS['pooled_features']['expect'].update({'probe.production_2021_isolation':'fail','probe.production_2023_isolation':'fail'})
CONTROLS['global_selection']['expect'].update({'probe.year_2017_isolation':'pass','probe.year_2018_isolation':'pass'})
NOT_APPLICABLE={'reference_pitfall':'Repaired forecasts are method-free; no reference-reading grid is declared.'}


def build(name,inputs,params,destination):
    dst=Path(destination);dst.mkdir(parents=True)
    shutil.copyfile(HERE/'solve.py',dst/'solve.py');shutil.copyfile(HERE.parent/'science.py',dst/'science.py')
    (dst/'variant.json').write_text(json.dumps(CONTROLS[name].get('variant',{})))
    subprocess.run([sys.executable,'solve.py','--inputs',str(inputs),'--output',str(dst)],cwd=dst,check=True,capture_output=True,text=True)
    if name in ('cached','cached_hindcasts','cached_forecasts'):
        import numpy as np
        import xarray as xr
        with xr.open_zarr(dst/'results.zarr',chunks=None,consolidated=False) as ds:
            np.savez(dst/'cached-predictions.npz',hindcast_mm=ds.hindcast_mm.values,forecast_mm=ds.forecast_mm.values)
    return dst
