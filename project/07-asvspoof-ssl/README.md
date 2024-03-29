# SSL-based front-end for spoofing countermeasure




<img src="https://pbs.twimg.com/media/FEc07JGacAA2kfc?format=png&name=small" alt="drawing" width="300"/>


This is the project using self-supervised trained speech model as a front-end feature extractor for speech spoofing countermeasures. 

Arxiv link: [https://arxiv.org/abs/2111.07725](https://arxiv.org/abs/2111.07725)

```
Xin Wang, and Junichi Yamagishi. Investigating Self-Supervised Front Ends for Speech Spoofing Countermeasures. In Proc. Odyssey, 100–106. doi:10.21437/Odyssey.2022-14. 2022.

@inproceedings{wang2021investigating,
author = {Wang, Xin and Yamagishi, Junichi},
booktitle = {Proc. Odyssey},
doi = {10.21437/Odyssey.2022-14},
pages = {100--106},
title = {{Investigating Self-Supervised Front Ends for Speech Spoofing Countermeasures}},
year = {2022}
}
```

SSL models require external dependency, which makes the script and environment quite dirty. This project demonstrates the training and scoring process using **a toy data set**.

If you need to run it on your own databases, check the steps required below. 
Apologize that the code is dirty. `model.py` in `../08-asvspoof-activelearn` is better organized. 


## Quick start

No need to setup anything, just:
```sh
bash 00_demo.sh model-W2V-XLSR-ft-GF config_train_toyset 01
```

Here
* `model-W2V-XLSR-ft-GF` is the model name, it can be other models
* `config_train_toyset` is  the configuration file for the toy data set
* `01` is a random seed

The script will
1. Download a toy data set and SSL models.
2. Build a *conda* environment if it is not available.
3. Train the CM on the toy set
4. Score the evaluation data in a toy set (which is specified in 00_demo.sh)

Notes:
1. To run the experiment on your data, please check `step-by-step` below.
2. We do not compute EER here. See [tutorial](../../tutorials/b2_anti_spoofing) here on how to compute EER in more details.
3. Score file contains three or more fields. Please use the `CM score` column to compute EER
```sh
TRIAL_NAME CM_SCORE CONFIDENCE_SCORE ...
LA_E_9933162 -9.500082 -4.499880 ...
```

## Step-by-step

### Folder structure

Files marked with `=` are generated after running 00_demo.sh.

```sh
|- DATA: data folder 
|  |= toy_example
|  |  |= protocol.txt: 
|  |  |   protocol file
|  |  |   this will be loaded by pytorch code for training and evaluation
|  |  |= scp: 
|  |  |   list of files for train, dev, and eval sets
|  |  |= train_dev: 
|  |  |   waveform for train and dev sets   
|  |  |= eval: 
|  |  |   waveform for eval set   
|
|- 00_demo.sh:  demo script
|- 01_train.sh: script for model training
|- 02_score.sh: script for scoring 
|
|- config_train_toyset.py:       configuration to use toy data set
|- config_auto.py:               generic configuration file for scoring
|- config_train_asvspoof2019.py: configuration to use ASVspoof2019 LA
|- main.py:                      python entrance code 
|
|- model-W2V-XLSR-ft-GF: project to use wav2vec-XLSR-fine-tuned + backend GF
|  |- model.py:                  model definition, Pytorch code
|  |- config_train_asvspoof2019  working folder when using Asvspoof 2019 training data
|  |  |- 01 (running using the first random seed)
|  |  |  |= 01_train.sh:         script copied from the root
|  |  |  |= 02_score.sh:         script copied from the root
|  |  |  |= main.py:             main.py copied from the root
|  |  |  |= config_*.py:         configuration files copied from the root
|  |  |  |= __pretrained
|  |  |  | |= trained_network.pt: pre-trained model by Xin
|  |  |  |
|  |  |  |= trained_network.pt: trained model after the full training process
|  |  |  |= *.dic: 
|  |  |  |   cache files to save the duration information of each trial
|  |  |  |   they are automatically generated by the code
|  |  |  |   they can be deleted freely
|  |  |  |= log_train: training log
|  |  |  |= log_train_err: error log (it also contains the training loss of each trial)
|  |  |  |= log_gen_err: error log during scoring
|  |  |  |= log_output_*: evaluation log
|  |  |  |= log_output_pretrained_*_score.txt: score of each trial, using pre-trained models
|  |  |  |= log_output_trained_*_score.txt: score of each trial, using newly trained models
|  | 
|- ...
```


### How to run the script on other databases

#### Step 1
Follow `DATA/toy_example` and prepare the data for a seed training set and a pool data set.  For each set, you need

```sh
DATA/SEEDSET/
|- train_dev:    folder to save the trn. and dev. sets waveforms
|- eval:         folder to save the eval. set waveforms 
|- protocol.txt: protocol file
|                each line contains SPEAKER TRIAL ... Label
|- scp
|  |- train.lst  list of file names in trn. set 
|  |- val.lst    list of file names in dev. set 
|  |- test.lst   list of file names in eval. set
                 (just file name w/o extension)
```
Note that
* If the pool or seed set contains multiple subsets, just prepare each subset in the same manner as above. 
* Name of `*.lst` can be anything other than `train`, `val`, or `test`.
* We will tell the script which lst to use in the next step.


   
#### Step 2
Create a `config_NNN.py` based on `config_train_toyset.py`. 

#### Step 3
Run 
```
bash 00_demo.sh MODEL config_AL_NNN RAND_SEED
```

The trained CM from each active learning cycle will be saved to `MODEL/config_AL_NNN/RAND_SEED`. 

#### Example

Use ASVspoof 2019 LA: 
1. Please download [ASVspoof 2019 LA](https://doi.org/10.7488/ds/2555) and convert FLAC to WAV
2. Put eval set waves to `./DATA/asvspoof2019_LA/eval`
3. Put train and dev sets to `./DATA/asvspoof2019_LA/train_dev`. 
4. Make sure that the two folders contain the waveform files: 
```
   $: ls DATA/asvspoof2019_LA/eval 
   LA_E_1000147.wav
   LA_E_1000273.wav
   LA_E_1000791.wav
   LA_E_1000841.wav
   LA_E_1000989.wav
   ...
   $: ls DATA/asvspoof2019_LA/eval | wc -l
   71237

   $: ls DATA/asvspoof2019_LA/train_dev
   LA_D_1000265.wav
   LA_D_1000752.wav
   LA_D_1001095.wav
   LA_D_1002130.wav
   LA_D_1002200.wav
   LA_D_1002318.wav
   ...

   $: ls DATA/asvspoof2019_LA/train_dev | wc -l
   50224
```
5. You can use `config_train_asvspoof2019.py` for training:
```
bash 00_demo.sh model-W2V-XLSR-ft-GF config_train_asvspoof2019 01
```

The trained model will be in `model-W2V-XLSR-ft-GF/config_train_asvspoof2019/01`

## Note
1. Downloading pre-trained SSL and CM models may take some time
2. If GPU memory is insufficient, please reduce `--batch-size` in `01_train.sh`    
3. main.py and config.py in this project cannot be mixed with those in other projects.

---
That's all