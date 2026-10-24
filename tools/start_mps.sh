#!/usr/bin/env bash
# Start NVIDIA's Multi-Process Service so the player and learner processes share the GPU at the same
# time instead of taking turns (without it, async training is barely faster than sync). It uses the
# default pipe directory, so other processes connect without any settings. tools/train_ppo.py runs this
# itself in async mode when MPS is not running. Stop it with: echo quit | nvidia-cuda-mps-control
set -euo pipefail
export CUDA_MPS_LOG_DIRECTORY=/tmp/nvidia-mps-log
mkdir -p "$CUDA_MPS_LOG_DIRECTORY"
if pgrep -f "^nvidia-cuda-mps-control" >/dev/null; then  # the pipe files outlive the daemon, so check the process
  echo "MPS already running"
else
  nvidia-cuda-mps-control -d
  echo "MPS started"
fi
