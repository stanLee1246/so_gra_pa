#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3.12 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.lock
.venv/bin/python -m pip check
# 已有数据时保留数据；真实接入应使用独立目录和适配器。
if [ ! -f data/raw_demo.csv ]; then
  .venv/bin/python generate_demo.py --seed 42 --scenario baseline
fi
if [ ! -f data/complaints.db ]; then
  .venv/bin/python prepare_data.py
fi
.venv/bin/python verify.py
