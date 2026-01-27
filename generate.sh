#!/bin/sh

. ./.venv/bin/activate
#rm -rf generated
#mkdir -p generated
python -m grpc_tools.protoc \
  -I proto \
  --python_out=src \
  --grpc_python_out=src \
  --mypy_out=src \
  proto/**/*.proto
