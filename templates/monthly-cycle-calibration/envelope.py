"""Labelled-array delivery of the unchanged archived monthly-cycle procedure."""
import numpy as np
import xarray as xr

COORDINATES = {"outer_year": np.arange(2005,2020), "forecast_year": np.arange(2020,2024),
               "month": np.arange(1,13), "system": np.arange(4), "target": np.arange(3), "candidate": np.arange(6)}
LAYOUT = {
    "hindcast_mm": ["outer_year","system","month","target"],
    "hindcast_coefficient": ["outer_year","system","month","target"],
    "hindcast_standardized_coefficient": ["outer_year","system","month","target"],
    "selected_candidate": ["outer_year"], "inner_loss": ["outer_year","candidate"],
    "xmean": ["outer_year","month"], "xstd": ["outer_year","month"],
    "ymean": ["outer_year","month","target"], "ystd": ["outer_year","month","target"],
    "squared_error": ["outer_year","system","month","target"],
    "monthly_msss": ["system","month"], "msss": ["system"],
    "forecast_mm": ["system","forecast_year","month","target"],
    "forecast_coefficient": ["system","month","target"],
    "forecast_standardized_coefficient": ["system","month","target"],
    "final_candidate": [], "final_inner_loss": ["candidate"],
}
PRODUCTION = ("forecast_mm","forecast_coefficient","forecast_standardized_coefficient","final_candidate","final_inner_loss")


def arrays(hindcast,forecast):
    result = {key:value.copy() for key,value in COORDINATES.items()}
    if hindcast is not None:
        for name,old in (("hindcast_mm","prediction"),("hindcast_coefficient","coefficient"),
                         ("hindcast_standardized_coefficient","standardized_coefficient")):
            result[name] = hindcast[old].values
        for name in ("selected_candidate","inner_loss","xmean","xstd","ymean","ystd","squared_error","monthly_msss","msss"):
            result[name] = hindcast[name].values
    for name,old in (("forecast_mm","prediction"),("forecast_coefficient","coefficient"),
                     ("forecast_standardized_coefficient","standardized_coefficient"),
                     ("final_candidate","selected_candidate"),("final_inner_loss","inner_loss")):
        result[name] = forecast[old].values
    return result


def dataset(values):
    coords = {key:values[key] for key in COORDINATES}
    result = xr.Dataset({key:(LAYOUT[key],value) for key,value in values.items() if key in LAYOUT},coords=coords)
    for name in result.data_vars:
        result[name].attrs["units"] = ("mm2" if name=="squared_error" else "degree_Celsius" if name in ("xmean","xstd")
                                      else "mm/degree_Celsius" if name.endswith("coefficient") and "standardized" not in name
                                      else "mm" if name in ("hindcast_mm","forecast_mm","ymean","ystd") else "1")
    result.attrs["system_names"] = ["climatology","independent-month","constant-slope","nested-cyclic"]
    result.attrs["target_names"] = ["somalia","kenya","eastern-horn"]
    return result
