"""Controller-only forecast outcomes; observed skill never determines completion."""
import numpy as np


def scores(probability, rainfall, observed, training):
    thresholds = np.quantile(training,[1/3,2/3],axis=0,method="linear")
    category = np.where(observed<thresholds[0],0,np.where(observed>thresholds[1],2,1))
    target = np.moveaxis(np.eye(3)[category],-1,1)
    train_cat = np.where(training<thresholds[0],0,np.where(training>thresholds[1],2,1))
    baseline = np.stack([(train_cat==c).mean(axis=0) for c in range(3)],axis=0)
    rps = ((probability.cumsum(axis=1)[:,:2]-target.cumsum(axis=1)[:,:2])**2).sum(axis=1)
    baseline_rps = ((baseline.cumsum(axis=0)[None,:2]-target.cumsum(axis=1)[:,:2])**2).sum(axis=1)
    return {"RPS":{"submitted":float(rps.mean()),"climatology":float(baseline_rps.mean())},
            "RMSE_mm":{"submitted":float(np.sqrt(np.mean((rainfall-observed)**2))),
                       "climatology":float(np.sqrt(np.mean((training.mean(axis=0)-observed)**2)))},
            "sample_count":int(observed.size), "baseline":"Training category frequencies and mean rainfall"},target


def development(prediction, training):
    p = prediction.probability.transpose("year","tercile","lat","lon").values
    m = prediction.rainfall_mm.transpose("year","lat","lon").values
    obs = training.observed.transpose("year","lat","lon").values
    rows,targets = [],[]
    for i in range(len(obs)):
        row,target = scores(p[i:i+1],m[i:i+1],obs[i:i+1],np.delete(obs,i,axis=0))
        rows.append(row); targets.append(target)
    result = {"RPS":{k:float(np.mean([r["RPS"][k] for r in rows])) for k in ("submitted","climatology")},
              "RMSE_mm":{k:float(np.sqrt(np.mean([r["RMSE_mm"][k]**2 for r in rows]))) for k in ("submitted","climatology")},
              "sample_count":int(obs.size),"definition":"Equal valid grid-cell/year weights; fold-specific linear terciles; equality in middle category"}
    observed_categories = np.concatenate(targets).ravel()
    probabilities = p.ravel()
    bins = []
    for i in range(5):
        mask = (probabilities>=i/5) & ((probabilities<(i+1)/5) if i<4 else (probabilities<=1))
        count = int(mask.sum())
        bins.append({"lower":i/5,"upper":(i+1)/5,"count":count,
                     "mean_probability":float(probabilities[mask].mean()) if count else None,
                     "observed_frequency":float(observed_categories[mask].mean()) if count else None})
    result["reliability"] = {"pooled_category_bins":bins,"note":"Descriptive diagnostic on a short development record, not a calibration guarantee"}
    return result
