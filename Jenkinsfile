pipeline {
  agent {
        docker {
            image 'nvcr.io/nvidia/pytorch:20.01-py3'
            args '--device=/dev/nvidia0 --gpus all --user 0:128 -v /home:/home -v $HOME/.cache/torch:/root/.cache/torch --shm-size=8g'
        }
  }
  options {
    timeout(time: 1, unit: 'HOURS')
    disableConcurrentBuilds()
  }
  stages {

    stage('PyTorch version') {
      steps {
        sh 'python -c "import torch; print(torch.__version__)"'
      }
    }
    stage('Install test requirements') {
      steps {
        sh 'apt-get update && apt-get install -y bc && pip install -r requirements/requirements_test.txt'
      }
    }
    stage('Code formatting checks') {
      steps {
        sh 'python setup.py style'
      }
    }
    stage('Documentation check') {
      steps {
        sh './reinstall.sh && pytest -m docs'
      }
    }


    stage('L0: Unit Tests') {
      steps {
        sh 'pytest -m unit'
      }
    }

    stage('L0: Integration Tests') {
      steps {
        sh 'pytest -m integration'
      }
    }

    stage('L1: System Tests') {
      steps {
        sh 'pytest -m system'
      }
    }

    stage('LX: Unclassified Tests') {
      steps {
        sh 'pytest -m unclassified'
      }
    }

    stage('L2: Parallel Stage1') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel {
        stage('Simplest test') {
          steps {
            sh 'cd examples/start_here && CUDA_VISIBLE_DEVICES=0 python simplest_example.py'
          }
        }
        stage ('Chatbot test') {
          steps {
            sh 'cd examples/start_here && CUDA_VISIBLE_DEVICES=1 python chatbot_example.py'
          }
        }
      }
    }

    stage('L2: Parallel NLP-BERT pretraining') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel { 
        stage('BERT on the fly preprocessing') {
          steps {
            sh 'cd examples/nlp/language_modeling && CUDA_VISIBLE_DEVICES=0 python bert_pretraining.py --amp_opt_level O1 --train_data /home/TestData/nlp/wikitext-2/train.txt --eval_data /home/TestData/nlp/wikitext-2/valid.txt --work_dir outputs/bert_lm/wikitext2 --batch_size 64 --lr 0.01 --lr_policy CosineAnnealing --lr_warmup_proportion 0.05 --vocab_size 3200 --hidden_size 768 --intermediate_size 3072 --num_hidden_layers 6 --num_attention_heads 12 --hidden_act "gelu" --save_step_freq 200 data_text  --num_iters=300 --tokenizer sentence-piece --sample_size 10000000 --mask_probability 0.15 --short_seq_prob 0.1 --dataset_name wikitext-2'
            sh 'cd examples/nlp/language_modeling && LOSS=$(cat outputs/bert_lm/wikitext2/log_globalrank-0_localrank-0.txt |   grep "Loss" |tail -n 1| awk \'{print \$7}\' | egrep -o "[0-9.]+" ) && echo $LOSS && if [ $(echo "$LOSS < 8.0" | bc -l) -eq 1 ]; then echo "SUCCESS" && exit 0; else echo "FAILURE" && exit 1; fi'
            sh 'rm -rf examples/nlp/language_modeling/outputs/wikitext2 && rm -rf /home/TestData/nlp/wikitext-2/*.pkl && rm -rf /home/TestData/nlp/wikitext-2/bert'
          }
        }        
        stage('BERT offline preprocessing') {
          steps {
            sh 'cd examples/nlp/language_modeling && CUDA_VISIBLE_DEVICES=1 python bert_pretraining.py --amp_opt_level O1 --train_data /home/TestData/nlp/wiki_book_mini/training --eval_data /home/TestData/nlp/wiki_book_mini/evaluation --work_dir outputs/bert_lm/wiki_book --batch_size 8 --config_file /home/TestData/nlp/bert_configs/uncased_L-12_H-768_A-12.json  --save_step_freq 200 --num_gpus 1 --batches_per_step 1 --lr_policy SquareRootAnnealing --beta2 0.999 --beta1 0.9  --lr_warmup_proportion 0.01 --optimizer adam_w  --weight_decay 0.01  --lr 0.875e-4 data_preprocessed --num_iters 300'
            sh 'cd examples/nlp/language_modeling && LOSS=$(cat outputs/bert_lm/wiki_book/log_globalrank-0_localrank-0.txt |  grep "Loss" |tail -n 1| awk \'{print \$7}\' | egrep -o "[0-9.]+" ) && echo $LOSS && if [ $(echo "$LOSS < 15.0" | bc -l) -eq 1 ]; then echo "SUCCESS" && exit 0; else echo "FAILURE" && exit 1; fi'
            sh 'rm -rf examples/nlp/language_modeling/outputs/wiki_book'
          }
        }
      }
    }

    stage('L2: Parallel NLP Examples 1') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel {
        stage ('Text Classification with BERT Test') {
          steps {
            sh 'cd examples/nlp/text_classification && CUDA_VISIBLE_DEVICES=0 python text_classification_with_bert.py --pretrained_model_name bert-base-uncased --num_epochs=1 --max_seq_length=50 --dataset_name=jarvis --data_dir=/home/TestData/nlp/retail/ --eval_file_prefix=eval --batch_size=10 --num_train_samples=-1 --do_lower_case --work_dir=outputs'
            sh 'rm -rf examples/nlp/text_classification/outputs'
          }
        }
        stage ('Dialogue State Tracking - TRADE - Multi-GPUs') {
          steps {
            sh 'rm -rf /home/TestData/nlp/multiwoz2.1/vocab.pkl'
            sh 'cd examples/nlp/dialogue_state_tracking && CUDA_VISIBLE_DEVICES=0,1 python -m torch.distributed.launch --nproc_per_node=2 dialogue_state_tracking_trade.py --batch_size=10 --eval_batch_size=10 --num_train_samples=-1 --num_eval_samples=-1 --num_epochs=1 --dropout=0.2 --eval_file_prefix=test --num_gpus=2 --lr=0.001 --grad_norm_clip=10 --work_dir=outputs --data_dir=/home/TestData/nlp/multiwoz2.1'
            sh 'rm -rf examples/nlp/dialogue_state_tracking/outputs'
            sh 'rm -rf /home/TestData/nlp/multiwoz2.1/vocab.pkl'
          }
        }
        stage ('GLUE Benchmark Test') {
          steps {
            sh 'cd examples/nlp/glue_benchmark && CUDA_VISIBLE_DEVICES=1 python glue_benchmark_with_bert.py --data_dir /home/TestData/nlp/glue_fake/MRPC --pretrained_model_name bert-base-uncased --work_dir glue_output --save_step_freq -1 --num_epochs 1 --task_name mrpc --batch_size 2 --no_data_cache'
            sh 'rm -rf examples/nlp/glue_benchmark/glue_output'
          }
        }
      }
    }


    stage('L2: Parallel NLP Examples 2') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel {
        stage('Token Classification Training/Inference Test') {
          steps {
            sh 'cd examples/nlp/token_classification && CUDA_VISIBLE_DEVICES=0 python token_classification.py --data_dir /home/TestData/nlp/token_classification_punctuation/ --batch_size 2 --num_epochs 1 --save_epoch_freq 1 --work_dir token_classification_output --pretrained_bert_model bert-base-uncased'
            sh 'cd examples/nlp/token_classification && DATE_F=$(ls token_classification_output/) && CUDA_VISIBLE_DEVICES=0 python token_classification_infer.py --work_dir token_classification_output/$DATE_F/checkpoints/ --labels_dict /home/TestData/nlp/token_classification_punctuation/label_ids.csv --pretrained_bert_model bert-base-uncased'
            sh 'rm -rf examples/nlp/token_classification/token_classification_output'
          }
        }
        stage ('Punctuation and Classification Training/Inference Test') {
          steps {
            sh 'cd examples/nlp/token_classification && CUDA_VISIBLE_DEVICES=1 python punctuation_capitalization.py --data_dir /home/TestData/nlp/token_classification_punctuation/ --work_dir punctuation_output --save_epoch_freq 1 --num_epochs 1 --save_step_freq -1 --batch_size 2'
            sh 'cd examples/nlp/token_classification && DATE_F=$(ls punctuation_output/) && DATA_DIR="/home/TestData/nlp/token_classification_punctuation" && CUDA_VISIBLE_DEVICES=1 python punctuation_capitalization_infer.py --checkpoints_dir punctuation_output/$DATE_F/checkpoints/ --punct_labels_dict $DATA_DIR/punct_label_ids.csv --capit_labels_dict $DATA_DIR/capit_label_ids.csv'
            sh 'rm -rf examples/nlp/token_classification/punctuation_output'
          }
        }
      }
    }

    stage('L2: Parallel NLP-Squad') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel {
        stage('BERT Squad v1.1') {
          steps {
            sh 'cd examples/nlp/question_answering && CUDA_VISIBLE_DEVICES=0 python question_answering_squad.py --no_data_cache --amp_opt_level O1 --train_file /home/TestData/nlp/squad_mini/v1.1/train-v1.1.json --eval_file /home/TestData/nlp/squad_mini/v1.1/dev-v1.1.json --work_dir outputs/squadv1 --batch_size 8 --save_step_freq 200 --max_steps 50 --train_step_freq 5 --lr_policy WarmupAnnealing  --lr 5e-5 --do_lower_case --pretrained_model_name bert-base-uncased'
            sh 'cd examples/nlp/question_answering && FSCORE=$(cat outputs/squadv1/log_globalrank-0_localrank-0.txt |  grep "f1" |tail -n 1 |egrep -o "[0-9.]+"|tail -n 1 ) && echo $FSCORE && if [ $(echo "$FSCORE > 10.0" | bc -l) -eq 1 ]; then echo "SUCCESS" && exit 0; else echo "FAILURE" && exit 1; fi'
            sh 'rm -rf examples/nlp/question_answering/outputs/squadv1 && rm -rf /home/TestData/nlp/squad_mini/v1.1/*cache*'
          }
        }
        stage('BERT Squad v2.0') {
          steps {
            sh 'cd examples/nlp/question_answering && CUDA_VISIBLE_DEVICES=1 python question_answering_squad.py --no_data_cache --amp_opt_level O1 --train_file /home/TestData/nlp/squad_mini/v2.0/train-v2.0.json --eval_file /home/TestData/nlp/squad_mini/v2.0/dev-v2.0.json --work_dir outputs/squadv2 --batch_size 8 --save_step_freq 200 --train_step_freq 2 --max_steps 10 --lr_policy WarmupAnnealing  --lr 1e-5 --do_lower_case --version_2_with_negative --pretrained_model_name bert-base-uncased'
            sh 'cd examples/nlp/question_answering && FSCORE=$(cat outputs/squadv2/log_globalrank-0_localrank-0.txt |  grep "f1" |tail -n 1 |egrep -o "[0-9.]+"|tail -n 1 ) && echo $FSCORE && if [ $(echo "$FSCORE > 40.0" | bc -l) -eq 1 ]; then echo "SUCCESS" && exit 0; else echo "FAILURE" && exit 1; fi'
            sh 'rm -rf examples/nlp/question_answering/outputs/squadv2 && rm -rf /home/TestData/nlp/squad_mini/v2.0/*cache*'
          }
        }
      }
    }

    stage('L2: Parallel NLP-Examples 3') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel { 
        stage('asr_processing') {
          steps {
            sh 'cd examples/nlp/asr_postprocessor && CUDA_VISIBLE_DEVICES=0 python asr_postprocessor.py --data_dir=/home/TestData/nlp/asr_postprocessor/pred_real --restore_from=/home/TestData/nlp/asr_postprocessor/bert-base-uncased_decoder.pt --max_steps=25 --batch_size=64'
            sh 'cd examples/nlp/asr_postprocessor && WER=$(cat outputs/asr_postprocessor/log_globalrank-0_localrank-0.txt | grep "Validation WER" | tail -n 1 | egrep -o "[0-9.]+" | tail -n 1) && echo $WER && if [ $(echo "$WER < 25.0" | bc -l) -eq 1 ]; then echo "SUCCESS" && exit 0; else echo "FAILURE" && exit 1; fi'
            sh 'rm -rf examples/nlp/asr_postprocessor/outputs'
          }
        }
        stage('Roberta Squad v1.1') {
          steps {
            sh 'cd examples/nlp/question_answering && CUDA_VISIBLE_DEVICES=1 python question_answering_squad.py --no_data_cache --amp_opt_level O1 --train_file /home/TestData/nlp/squad_mini/v1.1/train-v1.1.json --eval_file /home/TestData/nlp/squad_mini/v1.1/dev-v1.1.json --work_dir outputs/squadv1_roberta --batch_size 5 --save_step_freq 200 --max_steps 50 --train_step_freq 5  --lr_policy WarmupAnnealing  --lr 1e-5 --pretrained_model_name roberta-base'
            sh 'cd examples/nlp/question_answering && FSCORE=$(cat outputs/squadv1_roberta/log_globalrank-0_localrank-0.txt |  grep "f1" |tail -n 1 |egrep -o "[0-9.]+"|tail -n 1 ) && echo $FSCORE && if [ $(echo "$FSCORE > 7.0" | bc -l) -eq 1 ]; then echo "SUCCESS" && exit 0; else echo "FAILURE" && exit 1; fi'
            sh 'rm -rf examples/nlp/question_answering/outputs/squadv1_roberta && rm -rf /home/TestData/nlp/squad_mini/v1.1/*cache*'
          }
        }
      }
    }

    stage('L2: NLP-Intent Detection/Slot Tagging Examples - Multi-GPU') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
        steps {
          sh 'cd examples/nlp/intent_detection_slot_tagging && CUDA_VISIBLE_DEVICES=0,1 python -m torch.distributed.launch --nproc_per_node=2 joint_intent_slot_with_bert.py --num_gpus=2 --num_epochs=1 --max_seq_length=50 --dataset_name=jarvis-retail --data_dir=/home/TestData/nlp/retail/ --eval_file_prefix=eval --batch_size=10 --num_train_samples=-1 --do_lower_case --work_dir=outputs'
          sh 'cd examples/nlp/intent_detection_slot_tagging && TASK_NAME=$(ls outputs/) && DATE_F=$(ls outputs/$TASK_NAME/) && CHECKPOINT_DIR=outputs/$TASK_NAME/$DATE_F/checkpoints/ && CUDA_VISIBLE_DEVICES=0 python joint_intent_slot_infer.py --work_dir $CHECKPOINT_DIR --eval_file_prefix=eval --dataset_name=jarvis-retail --data_dir=/home/TestData/nlp/retail/ --batch_size=10'
          sh 'cd examples/nlp/intent_detection_slot_tagging && TASK_NAME=$(ls outputs/) && DATE_F=$(ls outputs/$TASK_NAME/) && CHECKPOINT_DIR=outputs/$TASK_NAME/$DATE_F/checkpoints/ && CUDA_VISIBLE_DEVICES=0 python joint_intent_slot_infer_b1.py --data_dir=/home/TestData/nlp/retail/ --work_dir $CHECKPOINT_DIR --dataset_name=jarvis-retail --query="how much is it?"'
          sh 'rm -rf examples/nlp/intent_detection_slot_tagging/outputs'
        }
      }

    stage('L2: NLP-NMT Example') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
        steps {
          sh 'cd examples/nlp/neural_machine_translation/ && CUDA_VISIBLE_DEVICES=0 python machine_translation_tutorial.py --max_steps 100'
          sh 'rm -rf examples/nlp/neural_machine_translation/outputs'        
      }
    }

    stage('L2: Parallel Stage Jasper / GAN') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel {
        // stage('Jasper AN4 O1') {
        //   steps {
        //     sh 'cd examples/asr && CUDA_VISIBLE_DEVICES=0 python jasper_an4.py --amp_opt_level=O1 --num_epochs=35 --test_after_training --work_dir=O1'
        //   }
        // }
        stage('GAN O2') {
          steps {
            sh 'cd examples/image && CUDA_VISIBLE_DEVICES=0 python gan.py --amp_opt_level=O2 --num_epochs=3 --train_dataset=/home/TestData/'
          }
        }
        stage('Jasper AN4 O2') {
          steps {
            sh 'cd examples/asr && CUDA_VISIBLE_DEVICES=1 python jasper_an4.py --amp_opt_level=O2 --num_epochs=35 --test_after_training --work_dir=O2 --train_dataset=/home/TestData/an4_dataset/an4_train.json --eval_datasets=/home/TestData/an4_dataset/an4_val.json'
          }
        }
      }
    }

    // stage('Parallel Stage GAN') {
    //   failFast true
    //   parallel {
    //     stage('GAN O1') {
    //       steps {
    //         sh 'cd examples/image && CUDA_VISIBLE_DEVICES=0 python gan.py --amp_opt_level=O1 --num_epochs=3'
    //       }
    //     }
    //   }
    // }

    stage('L2: Multi-GPU Jasper test') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      parallel {
        stage('Jasper AN4 2 GPUs') {
          steps {
            sh 'cd examples/asr && CUDA_VISIBLE_DEVICES=0,1 python -m torch.distributed.launch --nproc_per_node=2 jasper_an4.py --num_epochs=40 --batch_size=24 --work_dir=multi_gpu --test_after_training  --train_dataset=/home/TestData/an4_dataset/an4_train.json --eval_datasets=/home/TestData/an4_dataset/an4_val.json'
          }
        }
      }
    }
    

    stage('L2: TTS Tests') {
      when {
        anyOf{
          branch 'master'
          changeRequest()
        }
      }
      failFast true
      steps {
        sh 'cd examples/tts && CUDA_VISIBLE_DEVICES=0,1 python -m torch.distributed.launch --nproc_per_node=2 tacotron2.py --max_steps=51 --model_config=configs/tacotron2.yaml --train_dataset=/home/TestData/an4_dataset/an4_train.json --amp_opt_level=O1 --eval_freq=50'
        sh 'cd examples/tts && TTS_CHECKPOINT_DIR=$(ls | grep "Tacotron2") && echo $TTS_CHECKPOINT_DIR && LOSS=$(cat $TTS_CHECKPOINT_DIR/log_globalrank-0_localrank-0.txt | grep -o -E "Loss[ :0-9.]+" | grep -o -E "[0-9.]+" | tail -n 1) && echo $LOSS && if [ $(echo "$LOSS < 3.0" | bc -l) -eq 1 ]; then echo "SUCCESS" && exit 0; else echo "FAILURE" && exit 1; fi'
        // sh 'cd examples/tts && TTS_CHECKPOINT_DIR=$(ls | grep "Tacotron2") && cp ../asr/multi_gpu/checkpoints/* $TTS_CHECKPOINT_DIR/checkpoints'
        // sh 'CUDA_VISIBLE_DEVICES=0 python tacotron2_an4_test.py --model_config=configs/tacotron2.yaml --eval_dataset=/home/TestData/an4_dataset/an4_train.json --jasper_model_config=../asr/configs/jasper_an4.yaml --load_dir=$TTS_CHECKPOINT_DIR/checkpoints'
      }
    }

  }

  post {
    always {
        cleanWs()
    }
  }
}
