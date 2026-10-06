
## Now improve the forecast

Make the final-period forecast as accurate as you can. The tool `score_development` scores a development forecast against the withheld development observations and returns the RMSE and the two baseline scores. It takes the name of a JSON file in `/work/submission` that has the same `results` layout as `answer.json`. You have {max_submissions} requests, and a malformed request uses one. Final-period scores are never shown.

As the claim `development_rmse_mm`, state the development RMSE of the forecast you submit if you measured it, and `null` if you did not.
