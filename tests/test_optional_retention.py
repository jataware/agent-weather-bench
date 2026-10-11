"""Scratch links cannot discard a valid submission or expose linked host data."""
from assessment.runner import retain_bundle
from assessment.storage import copy_bundle
import pytest


def test_optional_retention_records_links_without_following_them(tmp_path):
    source = tmp_path / 'state'
    source.mkdir()
    (source / 'validate.py').write_text('print("validate")\n')
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'secret.txt').write_text('must not be copied')
    (source / 'inputs').symlink_to(external, target_is_directory=True)
    (source / 'dangling').symlink_to('/work/inputs/missing')
    destination = tmp_path / 'retained'
    result = retain_bundle(source, destination)
    assert (destination / 'validate.py').read_text() == 'print("validate")\n'
    assert sorted(row['path'] for row in result['omitted']) == ['dangling', 'inputs']
    assert list(result['files']) == ['validate.py']
    assert not (destination / 'inputs').exists()
    assert (source / 'inputs').is_symlink()
    # Deliverables themselves keep the strict collection boundary.
    with pytest.raises(ValueError, match='Symlink'):
        copy_bundle(source, tmp_path / 'strict-submission')


def test_optional_state_root_link_is_not_traversed(tmp_path):
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'secret').write_text('do not copy')
    source = tmp_path / 'linked-state'
    source.symlink_to(external, target_is_directory=True)
    result = retain_bundle(source, tmp_path / 'retained')
    assert result['files'] == {}
    assert result['omitted'][0]['path'] == '.'
    assert not list((tmp_path / 'retained').iterdir())
