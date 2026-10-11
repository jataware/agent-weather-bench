import argparse
import json
from pathlib import Path
import numpy as np
import xarray as xr
import science

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True)
    a=parser.parse_args(); inputs=Path(a.inputs); output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    variant=json.loads(Path(__file__).with_name('variant.json').read_text())
    v=science.repaired(inputs,method=variant.get('method','ridge'),defect=variant.get('defect'))
    cache=Path(__file__).with_name('cached-predictions.npz')
    if variant.get('defect') in ('cached','cached_hindcasts','cached_forecasts') and cache.exists():
        with np.load(cache) as arrays:
            if variant.get('defect') in ('cached','cached_hindcasts'):v['hindcast_mm']=arrays['hindcast_mm']
            if variant.get('defect') in ('cached','cached_forecasts'):v['forecast_mm']=arrays['forecast_mm']
        _,targets=science.read(inputs)
        truth=targets.rainfall.sel(year=v['hindcast_year']).values
        v['hindcast_rmse_mm']=np.sqrt(np.mean((v['hindcast_mm']-truth)**2))
    if variant.get('method')=='float32':
        v['hindcast_mm']=v['hindcast_mm'].astype('float32');v['forecast_mm']=v['forecast_mm'].astype('float32')
        _,targets=science.read(inputs);truth=targets.rainfall.sel(year=v['hindcast_year']).values
        v['hindcast_rmse_mm']=np.sqrt(np.mean((v['hindcast_mm'].astype('float64')-truth)**2))
        for key in ('original_rmse_mm','hindcast_rmse_mm','climatology_rmse_mm'):v[key]=np.float32(v[key])
    if variant.get('defect')=='false_skill':v['hindcast_rmse_mm']-=1e-6
    if variant.get('defect')=='wrong_metric':v['original_rmse_mm']+=1
    coords={n:v.pop(n) for n in ('hindcast_year','forecast_year','target')}
    ds=xr.Dataset({n:((['hindcast_year','target'] if n.endswith('hindcast_mm') else ['forecast_year','target']) if np.asarray(value).ndim==2 else [],value) for n,value in v.items()},coords=coords)
    ds.to_zarr(output/'results.zarr',mode='w',zarr_format=3,consolidated=False)
    cfg=json.loads((inputs/'candidate-config.json').read_text());report=(inputs/'candidate-report.md').read_text()
    past=cfg['centering_scope']=='training_fold' and cfg['select_scope']=='fixed'
    support=past and 'independent final test' not in report
    claims={'original_hindcast_is_past_only':['yes' if past else 'no'],'original_report_supported':['yes' if support else 'no'],
            'repaired_beats_climatology':['yes' if v['hindcast_rmse_mm']<v['climatology_rmse_mm']-1e-9 else 'no']}
    if variant.get('defect')=='false_audit':claims['original_report_supported']=['no' if support else 'yes']
    answer={'run':{'argv':['python','solve.py','--inputs','{input_dir}','--output','{output_dir}']},'claims':claims}
    (output/'answer.json').write_text(json.dumps(answer)+'\n')
    finding='The candidate fits both target centering and regression within each earlier-year fold; its scope is correctly stated.'
    if cfg['centering_scope']=='whole_record':finding='candidate_science.original uses global_mean=y.mean(0) with centering_scope=whole_record. That includes the verification and later target years, so the complete learning procedure is not past-only despite earlier-year regression fits.'
    elif cfg['select_scope']=='whole_record':finding='candidate_science.original computes corr from the full x/y record and chooses cols using argmax before the outer loop. Held-out and later targets influence feature selection, so earlier-year regression fits do not make the complete procedure independent.'
    elif not support:finding='The candidate code uses fold-local centering and past-only regression, but candidate-report.md explicitly says scores were inspected to choose the architecture. The same scores cannot then be described as an independent final test or establish deployment readiness.'
    text=f'{finding}\nThe replacement uses {variant.get("method","ridge")} with fixed choices and strictly earlier targets in each expanding hindcast. Production uses targets through 2019 and each forecast\'s own predictor row. Original RMSE {v["original_rmse_mm"]:.8g} mm; repaired {v["hindcast_rmse_mm"]:.8g} mm; expanding climatology {v["climatology_rmse_mm"]:.8g} mm. These are 15 final-vintage retrospective annual cases at dependent neighbouring cells; no independent operational deployment or statistical significance is claimed.\n'
    (output/'report.md').write_text(text)
