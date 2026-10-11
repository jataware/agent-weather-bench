import hashlib
import json

import pytest

from assessment.sources import restore


def test_restore_rejects_changed_source_and_preserves_existing_evidence(tmp_path):
    template, source, private = [tmp_path / name for name in ("template", "source", "private")]
    template.mkdir()
    source.mkdir()
    data = b"frozen weather snapshot"
    (source / "inputs.nc").write_bytes(data)
    (template / "sources.json").write_text(json.dumps({"files": [
        {"file": "inputs.nc", "sha256": hashlib.sha256(data).hexdigest()}
    ]}))
    assert restore(template, private, source)["restored"] == 1
    (source / "inputs.nc").write_bytes(b"changed")
    with pytest.raises(ValueError, match="missing or changed"):
        restore(template, private, source)
    assert (private / "inputs.nc").read_bytes() == data
    (source / "inputs.nc").write_bytes(data)
    (private / "inputs.nc").write_bytes(b"existing evidence")
    with pytest.raises(ValueError, match="Refusing to replace"):
        restore(template, private, source)
    assert (private / "inputs.nc").read_bytes() == b"existing evidence"
