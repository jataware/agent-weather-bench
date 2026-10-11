import argparse,json
from pathlib import Path
import numpy as np
import xarray as xr
import science

def arrays(hindcast, forecast):
    return {"outer_year": hindcast.year.values, "forecast_year": forecast.year.values,
            "target": np.arange(hindcast.sizes["target"]), "system": np.arange(3), "category": np.arange(3),
            "boundary": np.arange(2), "candidate": hindcast.candidate.values,
            "hindcast_mean_mm": hindcast.prediction.values, "hindcast_probability": hindcast.probability.values,
            "hindcast_threshold_mm": hindcast.threshold.values, "selected_candidate": hindcast.selected_candidate.values,
            "inner_loss": hindcast.inner_loss.values, "hindcast_rpss": hindcast.rpss.values,
            "forecast_mean_mm": forecast.prediction.transpose("year", "system", "target").values,
            "forecast_probability": forecast.probability.transpose("year", "system", "target", "category").values,
            "forecast_threshold_mm": forecast.threshold.values, "final_candidate": forecast.selected_candidate.values,
            "final_inner_loss": forecast.inner_loss.values,
            "full_fit_mean_mm": hindcast.full_fit_prediction.values, "full_fit_probability": hindcast.full_fit_probability.values}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    config=Path(__file__).with_name('variant.json');variant=json.loads(config.read_text()) if config.exists() else {}
    hindcast,forecast,state=science.build(a.inputs,defect=variant.get('defect'))
    values=arrays(hindcast,forecast)
    layout=json.loads(Path(__file__).with_name('layout.json').read_text())
    coords={name:values[name] for name,row in layout.items() if row.get('kind')=='coordinate'}
    dataset=xr.Dataset({name:(row['dims'],values[name]) for name,row in layout.items() if row.get('kind')!='coordinate'},coords=coords)
    if variant.get('defect')=='invalid_probability':dataset['forecast_probability']*=1.2
    dataset.to_zarr(output/'results.zarr',mode='w',zarr_format=3,consolidated=False)
    better='yes' if values['hindcast_rpss'][2]-values['hindcast_rpss'][1]>1e-9 else 'no'
    if variant.get('defect')=='false_claim':better='no' if better=='yes' else 'yes'
    answer={'run':{'argv':['python','solve.py','--inputs','{input_dir}','--output','{output_dir}']},'claims':{'nested_beats_fixed':[better],'full_fit_is_independent':['no']}}
    (output/'answer.json').write_text(json.dumps(answer)+'\n')
    (output/'model.json').write_text(json.dumps(state)+'\n')
    (output/'report.md').write_text('This is the specified CPT-inspired regional adaptation, not exact CPT binary parity. Outer hindcasts use expanding past-only fits with nested selection. The full-fit diagnostics overlap training and do not measure independent skill. Production forecasts use the frozen 1993–2019 fit. Observed SST and rainfall are final-vintage public historical records, so this is retrospective, not strict real-time forecasting.\n')
