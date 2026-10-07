"""Explicit local normalization of bounded real public NOAA downloads.

No remote calls during prepare/replay. Full downloaded annual CSVs live under
controller/source-data; agent gets January original-field records and hashes.
"""
from pathlib import Path
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
import numpy as np
import xarray as xr

TASK="station-verification"
STATIONS=["63450099999","63602099999","63705099999","63740099999","63799099999","63894099999"]
COLUMNS=["STATION","DATE","SOURCE","LATITUDE","LONGITUDE","ELEVATION","NAME","REPORT_TYPE","CALL_SIGN","QUALITY_CONTROL","TMP"]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def normalize(repo=None):
    repo=Path(repo) if repo else Path(__file__).resolve().parents[3]
    private=repo/"var/private/tasks"/TASK
    controller=private/"controller";inputs=private/"agent-inputs"
    archived=controller/"source-data";archived.mkdir(exist_ok=True)
    records=[];metadata=[];sources=[]
    for sid in STATIONS:
        path=controller/(sid+".csv")
        if path.exists():shutil.move(path,archived/path.name)
        path=archived/(sid+".csv")
        with path.open() as f:
            reader=csv.DictReader(f);header=reader.fieldnames;rows=list(reader)
        jan=[r for r in rows if "2020-01-01"<=r["DATE"][:10]<="2020-01-27"]
        assert jan, sid+": no retained January observations"
        # Modal actual January source location; record all source representations.
        from collections import Counter
        loc=Counter((r["LATITUDE"],r["LONGITUDE"],r["ELEVATION"]) for r in jan).most_common(1)[0][0]
        metadata.append({"id":sid,"name":jan[0]["NAME"],"latitude":float(loc[0]),"longitude":float(loc[1]),
                         "elevation_m":float(loc[2]),"source_location_representations":[list(v) for v in sorted(set((r["LATITUDE"],r["LONGITUDE"],r["ELEVATION"]) for r in jan))]})
        records.extend({c:r[c] for c in COLUMNS} for r in jan)
        sources.append({"station":sid,"url":f"https://noaa-global-hourly-pds.s3.amazonaws.com/2020/{sid}.csv",
                        "source_sha256":sha(path),"source_bytes":path.stat().st_size,"original_header":header,
                        "original_first_record":rows[0],"retained_rows":len(jan),"retained_columns":COLUMNS,
                        "controller_file":str(path.relative_to(private)),"header_csv":",".join(header)})
    total=sum(s["source_bytes"] for s in sources)
    assert total<50_000_000
    with (inputs/"observations.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS);writer.writeheader();writer.writerows(records)
    (inputs/"stations.json").write_text(json.dumps(metadata,indent=2)+"\n")
    wb=repo/"var/private/tasks/weatherbench-verification/agent-inputs"
    shutil.copy2(wb/"hres.nc",inputs/"hres.nc")
    with xr.open_dataset(inputs/"hres.nc") as f:
        mask=np.ones((2,f.sizes["init_time"],f.sizes["lead_time"],len(STATIONS)),dtype=np.int8)
        # Explicit artificial reporting/availability probe: never presented as NOAA QC.
        mask[1,:6,2,0]=0;mask[0,5:9,1,2]=0
        xr.Dataset({"available":(("method","init_time","lead_time","station"),mask)},
                   coords={"method":["bilinear","nearest"],"init_time":f.init_time,"lead_time":f.lead_time,"station":STATIONS},
                   attrs={"constructed": "true", "purpose":"Test unequal-method support; forecast and observation values unmodified"}).to_netcdf(inputs/"availability.nc")
    manifest={"schema_version":1,"task":TASK,"retrieved_at":datetime.now(timezone.utc).isoformat(),
              "public_download_bytes":total,"region":"East Africa; IDs fixed before forecast evaluation",
              "selection_note":"Initial five IDs retained, including Arua with no exact 00UTC January reports; Entebbe 637050 added on a reporting-coverage criterion before forecast scores inspected. No score-based station selection.",
              "period":"2020-01-01 through 2020-01-27; all report times retained","sources":["weatherreal-paper","weatherreal-code","noaa-isd","weatherbench2-hres"],"station_sources":sources,
              "forecast_source":{"file":"hres.nc","sha256":sha(inputs/"hres.nc"),"upstream_manifest":json.loads((wb/"source-manifest.json").read_text())},
              "synthetic_weather":False,"constructed_mask":True,"constructed_faults":True,
              "weatherreal_revision":"68b2f9293d2a0a1b1cedf396cffda34c05a21a14",
              "transformations":["Retain original January CSV fields, preserving order and all reports; no value changes", "Modal source latitude/longitude/elevation metadata; preserve alternatives", "Copy actual WB2 HRES coarse-grid temperature field; no station-bias/lapse-rate correction", "Construct method-availability mask explicitly labeled artificial"]}
    (inputs/"source-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    package=repo/"tasks"/TASK
    for name in ("weatherreal-README.md","weatherreal-LICENSE","weatherreal-obs_reformat_catalog.py","isd-format-document.pdf","CSV_HELP.pdf"):
        shutil.copy2(package/"source-material"/name,inputs/name)
    shutil.copy2(package/"source-material/broken-comparison.py",inputs/"broken-comparison.py")
    return manifest

if __name__=="__main__":
    print(json.dumps({k:v for k,v in normalize().items() if k in ("public_download_bytes","synthetic_weather","period")},indent=2))
