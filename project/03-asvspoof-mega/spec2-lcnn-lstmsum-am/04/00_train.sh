python main.py --model-forward-with-file-name --num-workers 3 --epochs 100 --no-best-epochs 50 --batch-size 64 --sampler block_shuffle_by_length --lr-decay-factor 0.5 --lr-scheduler-type 1 --lr 0.0003   --seed 1000 > log_train 2>log_err
