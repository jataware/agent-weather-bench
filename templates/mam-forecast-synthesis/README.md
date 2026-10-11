This development template issues fixed-calibration MAM outlooks for twelve blind seasons using genuine four-centre model predictors and twelve training seasons. Its source service exposes only training observations; verification is controller-private. Scientific validity and blind forecast skill are separate instruments.

The first predeclared experiment did **not** establish useful difficulty: its train-selected ECMWF expert scored worse than uniform climatology, so the inference gate stopped before a Luna call. See `experiments/hard-task-mam-baseline-verification-2026-10-08.json`. The candidate was not retuned on its withheld years. Automatic controls pass; scientific approval and model certification remain pending.

Source freezing uses `freeze_source.py` only in a fresh single-thread scientific container and verifies its immutable parent snapshot. Actor payloads are explicitly curator-normalized seasonal mm rather than raw provider exports. Acquisition remains through the task-owned HTTP catalogue. `sources.json` records original and derived hashes; `controller/expert-lock.json` locks train-only selection before verification. A restored source snapshot is required on another machine.

Start feedback with the known-correct control:

```
python -m assessment assess mam-forecast-synthesis kenya-interior--fixed-training-12-blind-seasons --control correct
```

Controls cover expert, uniform climatology, raw equal-centre probabilities, coordinate reorder, percentage/scaling faults and forbidden future-target pooling. Constant forecasts are valid, so no generic response-to-input gate is imposed. The future-input probe checks actual earlier probability arrays. The score is ordered RPS averaged first within years; the separate performance target never changes the validity gate.
