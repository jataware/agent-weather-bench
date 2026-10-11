import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import science
import envelope


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inputs",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--model")
    args=p.parse_args()
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parent
    variant=json.loads((root/"variant.json").read_text())["variant"]
    if not args.model and variant=="cached" and (root/"cached-results.zarr").exists():
        shutil.copytree(root/"cached-results.zarr",output/"results.zarr")
        shutil.copyfile(root/"cached-answer.json",output/"answer.json")
        return
    if args.model:
        if variant=="saved_model_needs_observations":
            science.load(args.inputs)
        state=json.loads(Path(args.model).read_text())
        forecast=science.from_state(state,args.inputs)
        values=envelope.arrays(None,forecast)
        if variant in ("cached_inference","cached"):
            values.update({key:np.asarray(value) for key,value in json.loads((root/"cached-forecast.json").read_text()).items()})
    else:
        defect="month-only-year-leak" if variant=="month_only_year_leak" else None
        hindcast,forecast,state=science.build(args.inputs,defect=defect)
        if variant in ("wrong_production","missing_units_and_wrong_production"):
            model=state["models"][1]
            physical=np.asarray(model["physical_coefficient"])
            wrong=np.broadcast_to(physical.mean(axis=0),physical.shape).copy()
            model["physical_coefficient"]=wrong.tolist()
            model["standardized_coefficient"]=(wrong*np.asarray(model["xstd"])[:,None]/np.asarray(model["ystd"])).tolist()
            forecast=science.from_state(state,args.inputs)
        values=envelope.arrays(hindcast,forecast)
        (output/"model.json").write_text(json.dumps(state)+"\n")
        if variant in ("cached_inference","cached"):
            (output/"cached-forecast.json").write_text(json.dumps({key:values[key].tolist() for key in envelope.PRODUCTION})+"\n")
    dataset=envelope.dataset(values)
    if variant in ("missing_units","missing_units_and_wrong_production") and "hindcast_mm" in dataset:
        dataset.hindcast_mm.attrs.pop("units",None)
    dataset.to_zarr(output/"results.zarr",mode="w",zarr_format=3,consolidated=False)
    claims={"rainfall_units":["mm"],"physical_coefficient_units":["mm/degree_Celsius"],
            "dynamical_hindcasts_used":["no"],"full_paper_reproduction":["no"]}
    if variant in ("missing_units","missing_units_and_wrong_production"):
        claims.pop("rainfall_units")
    answer={"run":{"argv":["python","solve.py","--inputs","{input_dir}","--output","{output_dir}"]},
            "model_path":"model.json","predict":{"argv":["python","solve.py","--model","{model_path}","--inputs","{input_dir}","--output","{output_dir}"]},
            "claims":claims}
    (output/"answer.json").write_text(json.dumps(answer)+"\n")
    (output/"report.md").write_text("This is the specified cyclic standardized-slope adaptation, not the original CanSIPS experiment or full paper reproduction. Real final-vintage CHIRPS regional monthly totals and prior-month ERA5 SST come from the supplied source record; original publication timing is assumed retrospectively. Twelve-month whole-year blocks and nested expanding fits exclude each held year. January and December are adjacent in the cyclic penalty. Physical slopes equal standardized slopes times fitted target scale divided by fitted predictor scale; the constant comparator averages standardized monthly slopes. Production loads the frozen1993–2019 fit and does not use2020–2023 rainfall. Negative predictions remain unaltered. Outer monthly and pooled MSSS are descriptive; no independence of36month-region pairs or significance of gains is claimed.\n")


if __name__=="__main__":
    main()
