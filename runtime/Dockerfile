ARG BASE=python:3.13-slim
FROM ${BASE}
COPY runtime/requirements.lock /opt/weatherbench/requirements.lock
RUN pip install --no-cache-dir -r /opt/weatherbench/requirements.lock
ENV PYTHONNOUSERSITE=1 MPLCONFIGDIR=/tmp/mpl
WORKDIR /work
