Pretraining BERT
================

In this tutorial, we will build and train a masked language model, either from scratch or from a pretrained BERT model, using the BERT architecture :cite:`nlp-bert-devlin2018bert`.
Make sure you have ``nemo`` and ``nemo_nlp`` installed before starting this tutorial. See the :ref:`installation` section for more details.

The code used in this tutorial can be found at ``examples/nlp/language_modeling/bert_pretraining.py``.

.. tip::
    Pretrained BERT models can be found at 
    `https://ngc.nvidia.com/catalog/models/nvidia:bertlargeuncasedfornemo <https://ngc.nvidia.com/catalog/models/nvidia:bertlargeuncasedfornemo>`__
    `https://ngc.nvidia.com/catalog/models/nvidia:bertbaseuncasedfornemo <https://ngc.nvidia.com/catalog/models/nvidia:bertbaseuncasedfornemo>`__
    `https://ngc.nvidia.com/catalog/models/nvidia:bertbasecasedfornemo <https://ngc.nvidia.com/catalog/models/nvidia:bertbasecasedfornemo>`__

Introduction
------------

Creating domain-specific BERT models can be advantageous for a wide range of applications. One notable is domain-specific BERT in a biomedical setting,
similar to BioBERT :cite:`nlp-bert-lee2019biobert` and SciBERT :cite:`nlp-bert-beltagy2019scibert`.

.. _bert_data_download:

Download Corpus
---------------

The training corpus can be either raw text where data preprocessing is done on the fly or an already preprocessed data set. In the following we will give examples for both.
To showcase how to train on raw text data, we will be using the very small WikiText-2 dataset :cite:`nlp-bert-merity2016pointer`.

To download the dataset, run the script ``examples/nlp/language_modeling/get_wkt2.sh download_dir``. After downloading and unzipping, the folder is located at `download_dir` and should include 3 files that look like this:

    .. code-block:: bash

        test.txt
        train.txt
        valid.txt

To train BERT on a Chinese dataset, you may download the Chinese Wikipedia corpus wiki2019zh_. After downloading, you may unzip and
use the script ``examples/nlp/language_modeling/process_wiki_zh.py`` for preprocessing the raw text.

.. _wiki2019zh: https://github.com/brightmart/nlp_chinese_corpus

    .. code-block:: bash

        python examples/nlp/language_modeling/process_wiki_zh.py --data_dir=./wiki_zh --output_dir=./wiki_zh --min_frequency=3

For already preprocessed data, we will be using a large dataset composed of Wikipedia and BookCorpus as in the original BERT paper.

To download the dataset, go to `https://github.com/NVIDIA/DeepLearningExamples/blob/master/PyTorch/LanguageModeling/BERT <https://github.com/NVIDIA/DeepLearningExamples/blob/master/PyTorch/LanguageModeling/BERT>`__
and run the script ``./data/create_datasets_from_start.sh``.
The downloaded folder should include a 2 sub folders with the prefix `lower_case_[0,1]_seq_len_128_max_pred_20_masked_lm_prob_0.15_random_seed_12345_dupe_factor_5`
and `lower_case_[0,1]_seq_len_512_max_pred_80_masked_lm_prob_0.15_random_seed_12345_dupe_factor_5`, containing sequences of length 128 with a maximum of 20 masked tokens
and sequences of length 512 with a maximum of 80 masked tokens respectively.


Create the tokenizer
--------------------------
A tokenizer will be used for data preprocessing and, therefore, is only required for training using raw text data.

`BERTPretrainingDataDesc` converts your dataset into the format compatible with `BertPretrainingDataset`. The most computationally intensive step is to tokenize
the dataset to create a vocab file and a tokenizer model.

You can also use an available vocab or tokenizer model to skip this step. If you already have a pretrained tokenizer model
copy it to the `[data_dir]/bert` folder under the name `tokenizer.model` and the script will skip this step.

If have an available vocab, such as `vocab.txt` file from any pretrained BERT model, copy it to the `[data_dir]/bert` folder under the name `vocab.txt`.

    .. code-block:: python
      
        import nemo.collections.nlp as nemo_nlp

        data_desc = nemo_nlp.data.BERTPretrainingDataDesc(
                        dataset_name=args.dataset_name,
                        train_data=args.train_data,
                        eval_data=args.eval_data,
                        vocab_size=args.vocab_size,
                        sample_size=args.sample_size,
                        special_tokens=special_tokens)

We need to define our tokenizer. If you'd like to use a custom vocabulary file, we strongly recommend you use our `SentencePieceTokenizer`.
Otherwise, if you'll be using a vocabulary file from another pre-trained BERT model, you should use `NemoBertTokenizer`.

To train on a Chinese dataset, you should use `NemoBertTokenizer`.

    .. code-block:: python

        # If you're using a custom vocabulary, create your tokenizer like this
        tokenizer = nemo_nlp.data.SentencePieceTokenizer(model_path="tokenizer.model")
        special_tokens = nemo_nlp.data.get_bert_special_tokens('bert')
        tokenizer.add_special_tokens(special_tokens)

        # Otherwise, create your tokenizer like this
        tokenizer = nemo_nlp.data.NemoBertTokenizer(pretrained_model="bert-base-uncased") 
        # or 
        tokenizer = nemo_nlp.data.NemoBertTokenizer(vocab_file="vocab.txt")

Create the model
----------------

.. tip::

    We recommend you try this out in a Jupyter notebook. It'll make debugging much easier!

First, we need to create our neural factory with the supported backend. How you should define it depends on whether you'd like to multi-GPU or mixed-precision training.
This tutorial assumes that you're training on one GPU, without mixed precision. If you want to use mixed precision, set ``amp_opt_level`` to ``O1`` or ``O2``.

    .. code-block:: python

        nf = nemo.core.NeuralModuleFactory(backend=nemo.core.Backend.PyTorch,
                                           local_rank=args.local_rank,
                                           optimization_level=args.amp_opt_level,
                                           log_dir=work_dir,
                                           create_tb_writer=True,
                                           files_to_copy=[__file__])

We also need to define the BERT model that we will be pre-training. Here, you can configure your model size as needed. If you want to train from scratch, use this:

    .. code-block:: python

        bert_model = nemo_nlp.nm.trainables.huggingface.BERT(
            vocab_size=args.vocab_size,
            num_hidden_layers=args.num_hidden_layers,
            hidden_size=args.hidden_size,
            num_attention_heads=args.num_attention_heads,
            intermediate_size=args.intermediate_size,
            max_position_embeddings=args.max_seq_length,
            hidden_act=args.hidden_act)


.. note::
    If you want to start pre-training from existing BERT checkpoints, specify the checkpoint folder path with the argument ``--load_dir``. 

The following code will automatically load the checkpoints if they exist and are compatible to the previously defined model

    .. code-block:: python

        ckpt_callback = nemo.core.CheckpointCallback(folder=nf.checkpoint_dir,
                            load_from_folder=args.load_dir)

To initialize the model with already pretrained checkpoints, specify ``pretrained_model_name``. For example, to initialize BERT Base trained on cased Wikipedia and BookCorpus with 12 layers, run
    
    .. code-block:: python

        bert_model = nemo_nlp.nm.trainables.huggingface.BERT(pretrained_model_name="bert-base-cased")

For the full list of BERT model names, check out `nemo_nlp.nm.trainables.huggingface.BERT.list_pretrained_models()`.

Next, we will define our classifier and loss functions. We will demonstrate how to pre-train with both MLM (masked language model) and NSP (next sentence prediction) losses,
but you may observe higher downstream accuracy by only pre-training with MLM loss.

    .. code-block:: python

        mlm_classifier = nemo_nlp.nm.trainables.BertTokenClassifier(
                                    args.hidden_size,
                                    num_classes=args.vocab_size,
                                    activation=ACT2FN[args.hidden_act],
                                    log_softmax=True)

        mlm_loss_fn = nemo_nlp.nm.losses.SmoothedCrossEntropyLoss()

        nsp_classifier = nemo_nlp.nm.trainables.SequenceClassifier(
                                                args.hidden_size,
                                                num_classes=2,
                                                num_layers=2,
                                                activation='tanh',
                                                log_softmax=False)

        nsp_loss_fn = nemo.backends.pytorch.common.CrossEntropyLossNM()

        bert_loss = nemo.backends.pytorch.common.losses.LossAggregatorNM(num_inputs=2)

Finally we will tie the weights of the encoder embedding layer and the MLM output embedding:

    .. code-block:: python

        mlm_classifier.tie_weights_with(
            bert_model,
            weight_names=["mlp.last_linear_layer.weight"],
            name2name_and_transform={
                "mlp.last_linear_layer.weight": ("bert.embeddings.word_embeddings.weight", nemo.core.WeightShareTransform.SAME)
            },
        )

Then, we create the pipeline from input to output that can be used for both training and evaluation:

For training from raw text use `nemo_nlp.nm.data_layers.BertPretrainingDataLayer`, for preprocessed data use `nemo_nlp.nm.data_layers.BertPretrainingPreprocessedDataLayer`

    .. code-block:: python

        def create_pipeline(**args):
            data_layer = nemo_nlp.nm.data_layers.BertPretrainingDataLayer(
                                    tokenizer,
                                    data_file,
                                    max_seq_length,
                                    mask_probability,
                                    short_seq_prob,
                                    batch_size)
            # for preprocessed data
            # data_layer = nemo_nlp.BertPretrainingPreprocessedDataLayer(
            #        data_file,
            #        max_predictions_per_seq,
            #        batch_size,
            #        mode)

            steps_per_epoch = len(data_layer) // (batch_size * args.num_gpus * args.batches_per_step)

            input_data = data_layer()

            hidden_states = bert_model(input_ids=input_data.input_ids,
                                       token_type_ids=input_data.input_type_ids,
                                       attention_mask=input_data.input_mask)

            mlm_logits = mlm_classifier(hidden_states=hidden_states)
            mlm_loss = mlm_loss_fn(logits=mlm_logits,
                                   labels=input_data.output_ids,
                                   output_mask=input_data.output_mask)

            nsp_logits = nsp_classifier(hidden_states=hidden_states)
            nsp_loss = nsp_loss_fn(logits=nsp_logits, labels=input_data.labels)

            loss = bert_loss(loss_1=mlm_loss, loss_2=nsp_loss)

            return loss, mlm_loss, nsp_loss, steps_per_epoch


        train_loss, _, _, steps_per_epoch = create_pipeline(
                                    data_file=data_desc.train_file,
                                    preprocessed_data=False,
                                    max_seq_length=args.max_seq_length,
                                    mask_probability=args.mask_probability,
                                    short_seq_prob=args.short_seq_prob,
                                    batch_size=args.batch_size,
                                    batches_per_step=args.batches_per_step,
                                    mode="train")

        # for preprocessed data 
        # train_loss, _, _, steps_per_epoch = create_pipeline(
        #                            data_file=args.train_data,
        #                            preprocessed_data=True,
        #                            max_predictions_per_seq=args.max_predictions_per_seq,
        #                            batch_size=args.batch_size,
        #                            batches_per_step=args.batches_per_step,
        #                            mode="train")

        eval_loss, _, _, _ = create_pipeline(
                                        data_file=data_desc.eval_file,
                                        preprocessed_data=False,
                                        max_seq_length=args.max_seq_length,
                                        mask_probability=args.mask_probability,
                                        short_seq_prob=args.short_seq_prob,
                                        batch_size=args.batch_size,
                                        batches_per_step=args.batches_per_step,
                                        mode="eval")
        
        # for preprocessed data 
        # eval_loss, eval_mlm_loss, eval_nsp_loss, _ = create_pipeline(
        #                            data_file=args.eval_data,
        #                            preprocessed_data=True,
        #                            max_predictions_per_seq=args.max_predictions_per_seq,
        #                            batch_size=args.batch_size,
        #                            batches_per_step=args.batches_per_step,
        #                            mode="eval")


Run the model
----------------

Define your learning rate policy

    .. code-block:: python

        lr_policy_fn = get_lr_policy(args.lr_policy,
                                    total_steps=args.num_iters,
                                    warmup_ratio=args.lr_warmup_proportion)

        # if you are training on raw text data, you have use the alternative to set the number of training epochs
        lr_policy_fn = get_lr_policy(args.lr_policy,
                                     total_steps=args.num_epochs * steps_per_epoch,
                                     warmup_ratio=args.lr_warmup_proportion)

Next, we define necessary callbacks:

1. `SimpleLossLoggerCallback`: tracking loss during training
2. `EvaluatorCallback`: tracking metrics during evaluation at set intervals
3. `CheckpointCallback`: saving model checkpoints at set intervals

    .. code-block:: python

        train_callback = nemo.core.SimpleLossLoggerCallback(tensors=[train_loss],
            print_func=lambda x: logging.info("Loss: {:.3f}".format(x[0].item())))),
            step_freq=args.train_step_freq,
        eval_callback = nemo.core.EvaluatorCallback(eval_tensors=[eval_loss],
            user_iter_callback=nemo_nlp.callbacks.lm_bert_callback.eval_iter_callback,
            user_epochs_done_callback=nemo_nlp.callbacks.lm_bert_callback.eval_epochs_done_callback
            eval_step=args.eval_step_freq)
        ckpt_callback = nemo.core.CheckpointCallback(folder=nf.checkpoint_dir,
            epoch_freq=args.save_epoch_freq,
            load_from_folder=args.load_dir,
            step_freq=args.save_step_freq)


We recommend you export your model's parameters to a config file. This makes it easier to load your BERT model into NeMo later, as explained in our Named Entity Recognition :ref:`ner_tutorial` tutorial.

    .. code-block:: python

        config_path = f'{nf.checkpoint_dir}/bert-config.json'

        if not os.path.exists(config_path):
            bert_model.config.to_json_file(config_path)

Finally, you should define your optimizer, and start training!

    .. code-block:: python

        nf.train(tensors_to_optimize=[train_loss],
                 lr_policy=lr_policy_fn,
                 callbacks=[train_callback, eval_callback, ckpt_callback],
                 optimizer=args.optimizer,
                 optimization_params={"batch_size": args.batch_size,
                                      "num_epochs": args.num_epochs,
                                      "lr": args.lr,
                                      "betas": (args.beta1, args.beta2),
                                      "weight_decay": args.weight_decay})


How to use the training script 
--------------------------------

You can find the example training script at ``examples/nlp/language_modeling/bert_pretraining.py``.

For single GPU training, the script can be started with 

.. code-block:: bash

    cd examples/nlp/language_modeling
    python bert_pretraining.py [args]


For multi-GPU training with ``x`` GPUs, the script can be started with 

.. code-block:: bash

    cd examples/nlp/language_modeling
    python -m torch.distributed.launch --nproc_per_node=x bert_pretraining.py --num_gpus=x [args]
  

If you running the model on raw text data, please remember to add the argument ``data_text`` to the python command.

.. code-block:: bash

    python bert_pretraining.py [args] data_text [args]

Similarly, to run the model on already preprocessed data add the argument ``data_preprocessed`` to the python command.

.. code-block:: bash

    python bert_pretraining.py [args] data_preprocessed [args]

.. note::
    By default, the script assumes ``data_preprocessed`` as input mode.

.. note::
    For downloading or preprocessing data offline please refer to :ref:`bert_data_download`.


.. tip::

    Tensorboard_ is a great debugging tool. It's not a requirement for this tutorial, but if you'd like to use it, you should install tensorboardX_ and run the following command during pre-training:

    .. code-block:: bash

        tensorboard --logdir outputs/bert_lm/tensorboard

.. _Tensorboard: https://www.tensorflow.org/tensorboard
.. _tensorboardX: https://github.com/lanpa/tensorboardX

References
----------

.. bibliography:: nlp_all_refs.bib
    :style: plain
    :labelprefix: NLP-BERT-PRETRAINING
    :keyprefix: nlp-bert-    
