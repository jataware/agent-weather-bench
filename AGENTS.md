# Local investigation practices

Scientific HDF5/NetCDF/xarray work must run in one thread per Python process.
Parallelize it with fresh Python subprocesses and bound worker counts to fit
CPU and memory; the current validation batches use two workers each. Threads
may orchestrate subprocesses but must not read scientific files themselves.
Threaded HDF5 control validation caused a real macOS Python crash in this repo.
Simulate native-crash records in tests; never send crash signals to host Python.

Keep model submissions and original assessments immutable. Diagnose grading
defects on controls before launching additional attempts. Record controller
revisions and any frozen reassessment separately. Optional scratch-state links
must never be followed onto the controller filesystem.
