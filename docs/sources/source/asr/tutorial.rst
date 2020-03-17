Tutorial
========

Make sure you have installed ``nemo`` and the ``nemo_asr`` collection.
See the :ref:`installation` section.

.. note::
  You only need to have ``nemo`` and the ``nemo_asr`` collection for this tutorial.

A more introductory, Jupyter notebook ASR tutorial can be found `on GitHub <https://github.com/NVIDIA/NeMo/tree/master/examples/asr/notebooks>`_.


Introduction
-------------

This Automatic Speech Recognition (ASR) tutorial is focused on QuartzNet :cite:`asr-tut-kriman2019quartznet` model.
QuartzNet is a CTC-based :cite:`asr-tut-graves2006` end-to-end model. The model is called "end-to-end" because it
transcribes speech samples without any additional alignment information. CTC allows for finding an alignment between
audio and text.

The CTC-ASR training pipeline consists of the following blocks:

1. Audio preprocessing (feature extraction): signal normalization, windowing, (log) spectrogram (or mel scale spectrogram, or MFCC)
2. Neural acoustic model (which predicts a probability distribution P_t(c) over vocabulary characters c per each time step t given input features per each timestep)
3. CTC loss function

.. image:: ctc_asr.png
    :align: center
    :alt: CTC-based ASR


Get data
--------
We will be using an open-source LibriSpeech :cite:`asr-tut-panayotov2015librispeech` dataset. These scripts will download and convert LibriSpeech into format expected by `nemo_asr`:

.. code-block:: bash

    mkdir data
    # note that this script requires sox to be installed
    # to install sox on Ubuntu, simply do: sudo apt-get install sox
    # and then: pip install sox
    # get_librispeech_data.py script is located under <nemo_git_repo_root>/scripts
    python get_librispeech_data.py --data_root=data --data_set=dev_clean,train_clean_100
    # To get all LibriSpeech data, do:
    # python get_librispeech_data.py --data_root=data --data_set=ALL

.. note::
    You should have at least 52GB of disk space available if you've used ``--data_set=dev_clean,train_clean_100``; and
    at least 250GB if you used ``--data_set=ALL``. Also, it will take some time to download and process, so go grab a
    coffee. After downloading, you can remove the original .tar.gz archives and .flac files to cut the disk usage in
    half.


After download and conversion, your `data` folder should contain 2 json files:

* dev_clean.json
* train_clean_100.json

In the tutorial we will use `train_clean_100.json` for training and `dev_clean.json` for evaluation.
Each line in json file describes a training sample - `audio_filepath` contains path to the wav file, `duration` it's duration in seconds, and `text` is it's transcript:

.. code-block:: json

    {"audio_filepath": "<absolute_path_to>/1355-39947-0000.wav", "duration": 11.3, "text": "psychotherapy and the community both the physician and the patient find their place in the community the life interests of which are superior to the interests of the individual"}
    {"audio_filepath": "<absolute_path_to>/1355-39947-0001.wav", "duration": 15.905, "text": "it is an unavoidable question how far from the higher point of view of the social mind the psychotherapeutic efforts should be encouraged or suppressed are there any conditions which suggest suspicion of or direct opposition to such curative work"}



Training
--------

We will train a small model from the QuartzNet family :cite:`asr-tut-kriman2019quartznet`. QuartzNet models are similar
to time delay neural networks (TDNN) composed of 1D convolutions. However QuartzNet models use separable convolutions
to reduce the total number of parameters. The Quartznet family of models are denoted as QuartzNet_[BxR] where B is the
number of blocks, and R - the number of convolutional sub-blocks within a block. Each sub-block contains a
1-D separable convolution, batch normalization, and ReLU:

.. image:: quartz_vertical.png
    :align: center
    :alt: quartznet model


In the tutorial we will be using model [12x1] and will be using separable convolutions.
The script below does both training (on `train_clean_100.json`) and evaluation (on `dev_clean.json`) on single GPU:

.. tip::
    Run a Jupyter notebook and walk through this script step-by-step


**Training script**

.. code-block:: python

    # NeMo's "core" package
    import nemo
    # NeMo's ASR collection
    import nemo.collections.asr as nemo_asr

    # Create a Neural Factory
    # It creates log files and tensorboard writers for us among other functions
    nf = nemo.core.NeuralModuleFactory(
        log_dir='QuartzNet12x1',
        create_tb_writer=True)
    tb_writer = nf.tb_writer

    # Path to our training manifest
    train_dataset = "<path_to_where_you_put_data>/train_clean_100.json"

    # Path to our validation manifest
    eval_datasets = "<path_to_where_you_put_data>/dev_clean.json"

    # QuartzNet Model definition
    from ruamel.yaml import YAML

    # Here we will be using separable convolutions
    # with 12 blocks (k=12 repeated once r=1 from the picture above)
    yaml = YAML(typ="safe")
    with open("<nemo_git_repo_root>/examples/asr/configs/quartznet12x1.yaml") as f:
        quartznet_model_definition = yaml.load(f)
    labels = quartznet_model_definition['labels']

    # Instantiate neural modules
    data_layer = nemo_asr.AudioToTextDataLayer(
        manifest_filepath=train_dataset,
        labels=labels, batch_size=32)
    data_layer_val = nemo_asr.AudioToTextDataLayer(
        manifest_filepath=eval_datasets,
        labels=labels, batch_size=32, shuffle=False)

    data_preprocessor = nemo_asr.AudioToMelSpectrogramPreprocessor()
    spec_augment = nemo_asr.SpectrogramAugmentation(rect_masks=5)

    encoder = nemo_asr.JasperEncoder(
        feat_in=64,
        **quartznet_model_definition['JasperEncoder'])
    decoder = nemo_asr.JasperDecoderForCTC(
        feat_in=1024, num_classes=len(labels))
    ctc_loss = nemo_asr.CTCLossNM(num_classes=len(labels))
    greedy_decoder = nemo_asr.GreedyCTCDecoder()

    # Training DAG (Model)
    audio_signal, audio_signal_len, transcript, transcript_len = data_layer()
    processed_signal, processed_signal_len = data_preprocessor(
        input_signal=audio_signal, length=audio_signal_len)
    aug_signal = spec_augment(input_spec=processed_signal)
    encoded, encoded_len = encoder(
        audio_signal=aug_signal, length=processed_signal_len)
    log_probs = decoder(encoder_output=encoded)
    predictions = greedy_decoder(log_probs=log_probs)
    loss = ctc_loss(
        log_probs=log_probs, targets=transcript,
        input_length=encoded_len, target_length=transcript_len)

    # Validation DAG (Model)
    # We need to instantiate additional data layer neural module
    # for validation data
    audio_signal_v, audio_signal_len_v, transcript_v, transcript_len_v = data_layer_val()
    processed_signal_v, processed_signal_len_v = data_preprocessor(
        input_signal=audio_signal_v, length=audio_signal_len_v)
    # Note that we are not using data-augmentation in validation DAG
    encoded_v, encoded_len_v = encoder(
        audio_signal=processed_signal_v, length=processed_signal_len_v)
    log_probs_v = decoder(encoder_output=encoded_v)
    predictions_v = greedy_decoder(log_probs=log_probs_v)
    loss_v = ctc_loss(
        log_probs=log_probs_v, targets=transcript_v,
        input_length=encoded_len_v, target_length=transcript_len_v)

    # These helper functions are needed to print and compute various metrics
    # such as word error rate and log them into tensorboard
    # they are domain-specific and are provided by NeMo's collections
    from nemo.collections.asr.helpers import monitor_asr_train_progress, \
        process_evaluation_batch, process_evaluation_epoch

    from functools import partial
    # Callback to track loss and print predictions during training
    train_callback = nemo.core.SimpleLossLoggerCallback(
        tb_writer=tb_writer,
        # Define the tensors that you want SimpleLossLoggerCallback to
        # operate on
        # Here we want to print our loss, and our word error rate which
        # is a function of our predictions, transcript, and transcript_len
        tensors=[loss, predictions, transcript, transcript_len],
        # To print logs to screen, define a print_func
        print_func=partial(
            monitor_asr_train_progress,
            labels=labels
        ))

    saver_callback = nemo.core.CheckpointCallback(
        folder="./",
        # Set how often we want to save checkpoints
        step_freq=100)

    # PRO TIP: while you can only have 1 train DAG, you can have as many
    # val DAGs and callbacks as you want. This is useful if you want to monitor
    # progress on more than one val dataset at once (say LibriSpeech dev clean
    # and dev other)
    eval_callback = nemo.core.EvaluatorCallback(
        eval_tensors=[loss_v, predictions_v, transcript_v, transcript_len_v],
        # how to process evaluation batch - e.g. compute WER
        user_iter_callback=partial(
            process_evaluation_batch,
            labels=labels
            ),
        # how to aggregate statistics (e.g. WER) for the evaluation epoch
        user_epochs_done_callback=partial(
            process_evaluation_epoch, tag="DEV-CLEAN"
            ),
        eval_step=500,
        tb_writer=tb_writer)

    # Run training using your Neural Factory
    # Once this "action" is called data starts flowing along train and eval DAGs
    # and computations start to happen
    nf.train(
        # Specify the loss to optimize for
        tensors_to_optimize=[loss],
        # Specify which callbacks you want to run
        callbacks=[train_callback, eval_callback, saver_callback],
        # Specify what optimizer to use
        optimizer="novograd",
        # Specify optimizer parameters such as num_epochs and lr
        optimization_params={
            "num_epochs": 50, "lr": 0.02, "weight_decay": 1e-4
            }
        )

.. note::
    This script trains should finish 50 epochs in about 7 hours on GTX 1080. You should get an evaluation WER of about 30%.

.. tip::
    To improve your word error rates:
        (1) Train longer
        (2) Train on more data
        (3) Use larger model
        (4) Train on several GPUs and use mixed precision (on NVIDIA Volta and Turing GPUs)
        (5) Start with pre-trained checkpoints


Mixed Precision training
-------------------------
Mixed precision and distributed training in NeMo is based on `NVIDIA's APEX library <https://github.com/NVIDIA/apex>`_.
Make sure it is installed.

To train with mixed-precision all you need is to set `optimization_level` parameter of `nemo.core.NeuralModuleFactory`  to `nemo.core.Optimization.mxprO1`. For example:

.. code-block:: python

    nf = nemo.core.NeuralModuleFactory(
        backend=nemo.core.Backend.PyTorch,
        local_rank=args.local_rank,
        optimization_level=nemo.core.Optimization.mxprO1,
        cudnn_benchmark=True)

.. note::
    Because mixed precision requires Tensor Cores it only works on NVIDIA Volta and Turing based GPUs

Multi-GPU training
-------------------

Enabling multi-GPU training with NeMo is easy:

   (1) First set `placement` to `nemo.core.DeviceType.AllGpu` in NeuralModuleFactory
   (2) Have your script accept 'local_rank' argument and do not set it yourself: `parser.add_argument("--local_rank", default=None, type=int)`
   (3) Use `torch.distributed.launch` package to run your script like this (replace <num_gpus> with number of gpus):

.. code-block:: bash

    python -m torch.distributed.launch --nproc_per_node=<num_gpus> <nemo_git_repo_root>/examples/asr/quartznet.py ...


Large Training Example
~~~~~~~~~~~~~~~~~~~~~~

Please refer to the `<nemo_git_repo_root>/examples/asr/quartznet.py` for comprehensive example. It builds one train DAG
and multiple validation DAGs. Each validation DAG shares the same model and parameters as the training DAG and can
be used to evaluate a different evaluation dataset.

Assuming, you are working with Volta-based DGX, you can run training like this:

.. code-block:: bash

    python -m torch.distributed.launch --nproc_per_node=<num_gpus> <nemo_git_repo_root>/examples/asr/quartznet.py --batch_size=64 --num_epochs=100 --lr=0.015 --warmup_steps=8000 --weight_decay=0.001 --train_dataset=/manifests/librivox-train-all.json --eval_datasets /manifests/librivox-dev-clean.json /manifests/librivox-dev-other.json --model_config=<nemo_git_repo_root>/nemo/examples/asr/configs/quartznet15x5.yaml --exp_name=MyLARGE-ASR-EXPERIMENT

The command above should trigger 8-GPU training with mixed precision. In the command above various manifests (.json) files are various datasets. Substitute them with the ones containing your data.

.. tip::
    You can pass several manifests (comma-separated) to train on a combined dataset like this: `--train_manifest=/manifests/librivox-train-all.json,/manifests/librivox-train-all-sp10pcnt.json,/manifests/cv/validated.json`. Here it combines 3 data sets: LibriSpeech, Mozilla Common Voice and LibriSpeech speed perturbed.


Fine-tuning
-----------
Training time can be dramatically reduced if starting from a good pre-trained model:

    (1) Obtain a pre-trained model (encoder, decoder and configuration files) `from here <https://ngc.nvidia.com/catalog/models/nvidia:quartznet15x5>`_.
    (2) load pre-trained weights right after you've instantiated your encoder and decoder, like this:

.. code-block:: python

    encoder.restore_from("<path_to_checkpoints>/15x5SEP/JasperEncoder-STEP-247400.pt")
    decoder.restore_from("<path_to_checkpoints>/15x5SEP/JasperDecoderForCTC-STEP-247400.pt")
    # in case of distributed training add args.local_rank
    decoder.restore_from("<path_to_checkpoints>/15x5SEP/JasperDecoderForCTC-STEP-247400.pt", args.local_rank)

.. tip::
    When fine-tuning, use smaller learning rate.


Evaluation
----------

First download pre-trained model (encoder, decoder and configuration files) `from here <https://ngc.nvidia.com/catalog/models/nvidia:quartznet15x5>`_ into `<path_to_checkpoints>`. We will use this pre-trained model to measure WER on LibriSpeech dev-clean dataset.

.. code-block:: bash

    python <nemo_git_repo_root>/examples/asr/jasper_eval.py --model_config=<nemo_git_repo_root>/examples/asr/configs/quartznet15x5.yaml --eval_datasets "<path_to_data>/dev_clean.json" --load_dir=<directory_containing_checkpoints>


Evaluation with Language Model
------------------------------

Using KenLM
~~~~~~~~~~~
We will be using `Baidu's CTC decoder with LM implementation. <https://github.com/PaddlePaddle/DeepSpeech>`_.

Perform the following steps:

    * Go to ``cd <nemo_git_repo_root>/scripts``
    * Install Baidu's CTC decoders (NOTE: no need for "sudo" if inside the container):
        * ``sudo apt-get update && sudo apt-get install swig``
        * ``sudo apt-get install pkg-config libflac-dev libogg-dev libvorbis-dev libboost-dev``
        * ``sudo apt-get install libsndfile1-dev python-setuptools libboost-all-dev python-dev``
        * ``sudo apt-get install cmake``
        * ``./install_decoders.sh``
    * Build 6-gram KenLM model on LibriSpeech ``./build_6-gram_OpenSLR_lm.sh``
    * Run jasper_eval.py with the --lm_path flag

    .. code-block:: bash

        python <nemo_git_repo_root>/examples/asr/jasper_eval.py --model_config=<nemo_git_repo_root>/examples/asr/configs/quartznet15x5.yaml --eval_datasets "<path_to_data>/dev_clean.json" --load_dir=<directory_containing_checkpoints> --lm_path=<path_to_6gram.binary>

Kaldi Compatibility
-------------------

The ``nemo_asr`` collection can also load datasets that are in a Kaldi-compatible format using the ``KaldiFeatureDataLayer``.
In order to load your Kaldi-formatted data, you will need to have a directory that contains the following files:

* ``feats.scp``, the file that maps from utterance IDs to the .ark files with the corresponding audio data.
* ``text``, the file that contains a mapping from the utterance IDs to transcripts.
* (Optional) ``utt2dur``, the file that maps the utterance IDs to the audio file durations. This is required if you want to filter your audio based on duration.

Of course, you will also need the .ark files that contain the audio data in the location that ``feats.scp`` expects.

To load your Kaldi-formatted data, you can simply use the ``KaldiFeatureDataLayer`` instead of the ``AudioToTextDataLayer``.
The ``KaldiFeatureDataLayer`` takes in an argument ``kaldi_dir`` instead of a ``manifest_filepath``, and this argument should be set to the directory that contains the files mentioned above.
See `the documentation <https://nvidia.github.io/NeMo/collections/nemo_asr.html#nemo_asr.data_layer.KaldiFeatureDataLayer>`_ for more detailed information about the arguments to this data layer.

.. note::

  If you are switching to a ``KaldiFeatureDataLayer``, be sure to set any ``feat_in`` parameters to correctly reflect the dimensionality of your Kaldi features, such as in the encoder. Additionally, your data is likely already preprocessed (e.g. into MFCC format), in which case you can leave out any audio preprocessors like the ``AudioToMelSpectrogramPreprocessor``.

References
----------

.. bibliography:: asr_all.bib
    :style: plain
    :labelprefix: ASR-TUT
    :keyprefix: asr-tut-
