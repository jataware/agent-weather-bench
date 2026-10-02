ARG BASE
FROM ${BASE}
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
COPY requirements-common.txt /opt/pilot/requirements-common.txt
RUN pip install --no-cache-dir -r /opt/pilot/requirements-common.txt
COPY sitecustomize.py /opt/pilot/runtime/sitecustomize.py
ENV PYTHONPATH=/opt/pilot/runtime UV_OFFLINE=1 PYTHONNOUSERSITE=1 MPLCONFIGDIR=/tmp/mpl
ENV ACMADDL_CACHE_DIR=/work/.cache ACMADDL_TMP_DIR=/work/.tmp ROSETTA_CACHE_DIR=/work/.cache ROSETTA_TMP_DIR=/work/.tmp
WORKDIR /work
