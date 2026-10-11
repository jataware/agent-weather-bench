"""Predeclared causal comparators and Docker-only stream execution.

The program mode is a generic persistent JSONL forecaster: no source-file
access, hidden labels, task solver, or dependency on the controller filesystem.
These are local baselines, not claimed reproductions of a published method.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
ROOT = Path(__file__).resolve().parents[1]
METHODS = ("raw", "monthly_climatology", "monthly_static", "expanding_shrinkage",
           "rolling_seasonal_bias", "adaptive_ridge", "adaptive_ensemble")
DESIGNS = {
    "raw": "Unmodified raw CFSv2 rainfall total.",
    "monthly_climatology": "Fixed mean observations by target-start calendar month; initial released history only.",
    "monthly_static": "Add initial-history observed-minus-raw mean by target-start month; clip at zero. Never update.",
    "expanding_shrinkage": "Update monthly observed-minus-raw residuals from released observations, shrink to all-month residual with12pseudo-observations.",
    "rolling_seasonal_bias": "Residual correction from released cases within previous3years and cyclic target-date distance<=45days, triangular seasonalweights,12pseudo-observations of rolling all-season bias.",
    "adaptive_ridge": "Per-cell causal exponentially weighted ridge of rainfall/20 on intercept,raw/20,annualsin/cos andrawinteractions;3yearhalflife,ridge10towardrawforecast,interceptpenalty0.1.",
    "adaptive_ensemble": "Online mixture of monthly_static/rolling_seasonal_bias/adaptive_ridge. Equal initial weights; losses update only when a previously issued forecast is released. Squared error/400,learningrate0.1,cumulative loss clipped percase at25,10%uniformweightfloor."
}


def day(value):
    return date.fromisoformat(value)


def month(record):
    return record["target_start"][5:7]


def average(rows, cells, residual=False, weights=None):
    if weights is None:
        weights = [1.]*len(rows)
    total = math.fsum(weights)
    assert total > 0
    return [math.fsum(w*(r["observed_mm"][j]-(r["raw_mm"][j] if residual else 0)) for r, w in zip(rows, weights))/total for j in range(cells)]


class Forecaster:
    def __init__(self, method, initialization):
        assert method in METHODS
        self.method, self.locations = method, initialization["locations"]
        self.cells = len(self.locations)
        self.initial = list(initialization["training"])
        self.history = list(self.initial)
        self.known = {r["case_id"] for r in self.history}
        assert len(self.history) == len(self.known)
        self.fixed_bias, self.fixed_climo = {}, {}
        for m in range(1,13):
            rows = [r for r in self.initial if month(r) == f"{m:02d}"]
            self.fixed_bias[f"{m:02d}"] = average(rows, self.cells, residual=True)
            self.fixed_climo[f"{m:02d}"] = average(rows, self.cells)
        self.expert_methods = ("monthly_static", "rolling_seasonal_bias", "adaptive_ridge")
        self.losses = [0.]*3
        self.issued_experts = {}

    def update(self, message):
        for record in message["released_observations"]:
            assert record["release_time"] <= message["issue_time"] and record["issue_time"] < message["issue_time"]
            assert record["case_id"] not in self.known
            if record["case_id"] in self.issued_experts:
                experts = self.issued_experts.pop(record["case_id"])
                weights = [math.cos(math.radians(loc["latitude"])) for loc in self.locations]
                for k, prediction in enumerate(experts):
                    loss = math.fsum(w*(p-y)**2 for w,p,y in zip(weights,prediction,record["observed_mm"]))/math.fsum(weights)/400
                    self.losses[k] += min(loss,25.)
            self.history.append(record)
            self.known.add(record["case_id"])

    def predict_method(self, method, message):
        raw = message["raw_mm"]
        if method == "raw":
            return list(raw)
        if method == "monthly_climatology":
            return self.fixed_climo[month(message)]
        if method == "monthly_static":
            bias = self.fixed_bias[month(message)]
        elif method == "expanding_shrinkage":
            global_bias = average(self.history, self.cells, residual=True)
            rows = [r for r in self.history if month(r) == month(message)]
            local = average(rows, self.cells, residual=True)
            bias = [(len(rows)*local[j]+12*global_bias[j])/(len(rows)+12) for j in range(self.cells)]
        elif method == "rolling_seasonal_bias":
            now, target = day(message["issue_time"]), day(message["target_start"])
            history = [r for r in self.history if 0 <= (now-day(r["issue_time"])).days <= round(3*365.25)]
            global_bias = average(history, self.cells, residual=True)
            target_phase = (target.timetuple().tm_yday-1)/ (366 if target.year%4==0 else 365)
            rows, weights = [], []
            for record in history:
                t = day(record["target_start"])
                phase = (t.timetuple().tm_yday-1)/(366 if t.year%4==0 else 365)
                distance = min(abs(phase-target_phase),1-abs(phase-target_phase))*365.25
                if distance < 45:
                    rows.append(record)
                    weights.append(1-distance/45)
            if rows:
                local = average(rows, self.cells, residual=True, weights=weights)
                total = math.fsum(weights)
                bias = [(total*local[j]+12*global_bias[j])/(total+12) for j in range(self.cells)]
            else:
                bias = global_bias
        elif method == "adaptive_ridge":
            import numpy as np
            now = day(message["issue_time"])
            weights = np.array([2**(-max((now-day(r["issue_time"])).days,0)/(3*365.25)) for r in self.history])
            def features(record, j):
                t = day(record["target_start"])
                angle = 2*math.pi*(t.timetuple().tm_yday-1)/365.25
                raw_value = record["raw_mm"][j]/20
                return [1.,raw_value,math.sin(angle),math.cos(angle),raw_value*math.sin(angle),raw_value*math.cos(angle)]
            penalty = np.diag([.1,10.,10.,10.,10.,10.])
            prior = np.array([0.,1.,0.,0.,0.,0.])
            prediction = []
            for j in range(self.cells):
                matrix = np.array([features(r,j) for r in self.history])
                truth = np.array([r["observed_mm"][j]/20 for r in self.history])
                beta = np.linalg.solve(matrix.T@(weights[:,None]*matrix)+penalty,matrix.T@(weights*truth)+penalty@prior)
                prediction.append(max(0.,float(np.dot(features(message,j),beta))*20))
            return prediction
        else:
            raise ValueError(method)
        return [max(0.,p+b) for p,b in zip(raw,bias)]

    def forecast(self, message):
        assert all(record["release_time"] <= message["issue_time"] for record in self.history)
        self.update(message)
        if self.method == "adaptive_ensemble":
            experts = [self.predict_method(method,message) for method in self.expert_methods]
            minimum = min(self.losses)
            unnormalized = [math.exp(-.1*(loss-minimum)) for loss in self.losses]
            total = math.fsum(unnormalized)
            weights = [.9*value/total+.1/3 for value in unnormalized]
            self.issued_experts[message["case_id"]] = experts
            prediction = [math.fsum(w*expert[j] for w,expert in zip(weights,experts)) for j in range(self.cells)]
        else:
            prediction = self.predict_method(self.method,message)
        return {"case_id": message["case_id"], "prediction_mm": prediction}


def program(method):
    first = json.loads(sys.stdin.readline())
    assert first["type"] == "initialize"
    model = Forecaster(method,first)
    for line in sys.stdin:
        message = json.loads(line)
        assert message["type"] == "forecast"
        print(json.dumps(model.forecast(message),allow_nan=False),flush=True)


def run_controls():
    sys.path.insert(0,str(ROOT))
    from assessment.sequential import evaluate
    from experiments.sequential_forecast_data import score_predictions
    from assessment.storage import digest,read,write
    destination = ROOT/"var/review/sequential-controls-20261008"
    plan_path = ROOT/"experiments/sequential-controls-plan-2026-10-08.json"
    result_path = ROOT/"experiments/sequential-controls-results-2026-10-08.json"
    assert not destination.exists() and not plan_path.exists() and not result_path.exists()
    private = ROOT/"var/private/experiments/sequential-forecast-20261008"
    episodes = {split: private/(split+".json") for split in ("development","final")}
    plan = {"schema_version":1,"declared_at":datetime.now(timezone.utc).isoformat(),"methods":DESIGNS,
            "method_settings_frozen_before_any_score":True,"method_source_sha256":digest(Path(__file__)),
            "episodes":{split:{"path":str(path.relative_to(ROOT)),"sha256":digest(path)} for split,path in episodes.items()},
            "image":"sha256:08dbb4fce25955523a4c3caa3e2efdfb75b960dae3d2b8f3b92746e7f19f7c49",
            "selection":"No hyperparameter search or selection. All seven predeclared methods are retained on both splits.",
            "static_baseline":"Fixed at each episode initialization using all then-released observations; final initialization legitimately includes released development observations.",
            "publication_claim":"Local causal methods, no claim of replicating a published algorithm.","model_calls":0}
    write(plan_path,plan)
    rows = []
    for method in METHODS:
        submission = destination/method/"submission"
        submission.mkdir(parents=True)
        shutil.copyfile(Path(__file__),submission/"forecast.py")
        for split,path in episodes.items():
            episode = read(path)
            evaluated = evaluate(submission,["python","forecast.py","--program",method],episode,
                                 image=plan["image"],seconds=120,step_seconds=5)
            row = {"method":method,"split":split,"state":evaluated["state"],"reason":evaluated.get("reason")}
            proof = destination/method/(split+"-evaluation.json")
            write(proof,evaluated)
            row.update(evaluation_path=str(proof.relative_to(ROOT)),evaluation_sha256=digest(proof))
            if evaluated["state"] == "pass":
                predictions = evaluated["predictions"]
                if predictions and not isinstance(predictions[0],dict):
                    predictions = [{"case_id":case["case_id"],"prediction_mm":prediction} for case,prediction in zip(episode["cases"],predictions)]
                row["metrics"] = score_predictions(episode,predictions)
            rows.append(row)
            write(result_path,{"plan_sha256":digest(plan_path),"rows":rows,"complete":False,"model_calls":0})
            print(json.dumps({key:row[key] for key in ("method","split","state")},allow_nan=False),flush=True)
            if evaluated["state"] != "pass":
                print(json.dumps(row,indent=2),file=sys.stderr)
                return 1
    write(result_path,{"plan_sha256":digest(plan_path),"rows":rows,"complete":True,"model_calls":0,
                      "source_unchanged":all(digest(path)==plan["episodes"][split]["sha256"] for split,path in episodes.items()),
                      "comparators_retuned_on_final":False,"actor_execution":"Docker only","scientific_workers":1})
    return 0


if __name__ == "__main__":
    if len(sys.argv)==3 and sys.argv[1]=="--program":
        program(sys.argv[2])
    elif sys.argv[1:]==["--run"]:
        sys.exit(run_controls())
    else:
        raise SystemExit("Use --program METHOD or --run")
