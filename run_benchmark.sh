#!/usr/bin/env bash
python -u ./run_benchmark.py \
--noflush \
--model resnet50 \
-np 8 \
-npernode 8 \
-H localhost \
|& tee -a /imagenet-scratch/logs/run_benchmark.log
