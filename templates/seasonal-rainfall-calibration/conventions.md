# Conventions for this task

These are the conventions the task expects. Each is a statement about the data or about what the guidance means.

- **Forecast rates.** The forecast values are mean daily rates for each month, in mm per day. A monthly total is the rate times the number of days in that month: 31 for October, 30 for November, 31 for December.
- **Observations on the forecast grid.** The observed total for a forecast cell is the mean of the native observation cells whose centres fall inside it. Weight them by the cosine of latitude, or take the plain mean. Record which under `choices`.
- **Category boundaries.** The boundaries used to classify a year's observation are the 1/3 and 2/3 quantiles of the other training years at that cell. The year being classified is left out.
- **Reference forecast for the skill score.** The climatological forecast is one third for each category, or the category frequencies of the other training years. Record which under `choices`.
