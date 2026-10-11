"""Alternative science expressions should survive; nearby physical errors should not."""
import importlib.util
from pathlib import Path


def test_alternate_spherical_algebra_and_rank_ties():
    path = Path(__file__).resolve().parents[1] / 'experiments/grader_numerical_stress.py'
    spec = importlib.util.spec_from_file_location('grader_numerical_stress', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.geometry_checks()
    assert result['correct_algebra_accepted']
    assert result['one_metre_radius_error_rejected']
    assert result['tied_rank_and_clamped_tail_analytic_cases_pass']
