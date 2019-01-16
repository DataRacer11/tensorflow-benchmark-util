#!/bin/bash

output_dir="/imagenet-scratch/tfrecords1729"
mkdir -p "${output_dir}"

export CUDA_VISIBLE_DEVICES=""

time mpirun \
--allow-run-as-root \
-np 2 \
-H localhost:2 \
-bind-to none \
--map-by node \
-mca plm_rsh_agent ssh \
-mca plm_rsh_args "-p 2222" \
-x LD_LIBRARY_PATH \
-x PATH \
-x CUDA_VISIBLE_DEVICES \
resize_tfrecords_mpi.py \
-i "/imagenet-scratch/tfrecords/train-*" \
-o ${output_dir}
