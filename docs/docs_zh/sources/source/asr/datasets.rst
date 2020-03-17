数据集
========

.. _LibriSpeech_dataset:

LibriSpeech
-----------

运行下面的脚本下载 LibriSpeech 数据集，并把它转换成 `nemo_asr` 集合需要的格式。
你至少需要 250GB 的空间。

.. code-block:: bash

    # install sox
    sudo apt-get install sox
    mkdir data
    python get_librispeech_data.py --data_root=data --data_set=ALL

之后，你的 `data` 文件夹下应该包含了 wav 文件和给 NeMo 语音识别数据层的 `.json` 文件：


每行是一个训练样本。 `audio_filepath` 包含了 wav 文件的路径, `duration` 这个音频文件多少秒， `text` 是对应的文本：

.. code-block:: json

    {"audio_filepath": "<absolute_path_to>/1355-39947-0000.wav", "duration": 11.3, "text": "psychotherapy and the community both the physician and the patient find their place in the community the life interests of which are superior to the interests of the individual"}
    {"audio_filepath": "<absolute_path_to>/1355-39947-0001.wav", "duration": 15.905, "text": "it is an unavoidable question how far from the higher point of view of the social mind the psychotherapeutic efforts should be encouraged or suppressed are there any conditions which suggest suspicion of or direct opposition to such curative work"}

Fisher English Training Speech
------------------------------

运行这些脚本把 Fisher English Training Speech 数据集转换成 `nemo_asr` 集合需要的格式。

简言之，下面的脚本会把 .sph 文件转成 .wav，把这些文件切成更小的音频样本，把这些小音频和它们相应的文本匹配起来，接着把音频样本分成训练集，验证集和测试集。

.. note::
  你至少需要 106GB 的空间来转换成 .wav，额外的105GB空间做切分和匹配。
  你需要安装 sph2pipe 来运行 .wav 的转换。


**步骤**

下面的脚本假设你已经从 Linguistic Data Consortium 上获得 Fisher 数据集，并且数据集格式看起来这样的：

.. code-block:: bash

  FisherEnglishTrainingSpeech/
  ├── LDC2004S13-Part1
  │   ├── fe_03_p1_transcripts
  │   ├── fisher_eng_tr_sp_d1
  │   ├── fisher_eng_tr_sp_d2
  │   ├── fisher_eng_tr_sp_d3
  │   └── ...
  └── LDC2005S13-Part2
      ├── fe_03_p2_transcripts
      ├── fe_03_p2_sph1
      ├── fe_03_p2_sph2
      ├── fe_03_p2_sph3
      └── ...

文本位于 `fe_03_p<1,2>_transcripts/data/trans` ，音频文件 .sph 位于 `audio` 子目录下的剩下目录中。

首先，把音频文件从 .sph 转换成 .wav：

.. code-block:: bash

  cd <nemo_root>/scripts
  python fisher_audio_to_wav.py \
    --data_root=<fisher_root> --dest_root=<conversion_target_dir>

这个脚本会把未切分的 .wav 文件放到 `<conversion_target_dir>/LDC200[4,5]S13-Part[1,2]/audio-wav/` 。
需要运行几分钟。

接着，处理文本和切分音频数据：

.. code-block:: bash

  python process_fisher_data.py \
    --audio_root=<conversion_target_dir> --transcript_root=<fisher_root> \
    --dest_root=<processing_target_dir> \
    --remove_noises

这个脚本会把整个数据集切分成训练集，验证集和测试集，然后把切分好的音频文件放到对应的目标目录下的文件夹中。
每个数据集都有一个清单文件（.json文件），它包括了音频的文本，时长和路径。

这里程序大概需要20分钟。
一旦完成后，你可以删掉这些10分钟长的音频。

2000 HUB5 English Evaluation Speech
-----------------------------------

运行下面的脚本把HUB5数据集转换成 `nemo_asr` 集合需要的文件格式。

类似于 Fisher 数据集处理脚本，这个脚本把 .sph 文件转换成 .wav 文件，切割音频文件和文本，然后把他们合并成某个最小长度的音频片段（默认是10秒）。
这些音频片段都被保存到一个音频目录下，相应的文本被保存到一个 Json 格式的清单文件中。

.. note::
  你需要 5GB 的空间来运行这个脚本。
  你也需要安装 sph2pipe。

这个脚本假设你已经从 Linguistic Data Consortium 获取到了 2000 HUB5 数据集。

运行下面的脚本来处理 2000 HUB5 English Evaluation Speech 数据集样本：

.. code-block:: bash

  python process_hub5_data.py \
    --data_root=<path_to_HUB5_data> \
    --dest_root=<target_dir>

你可以选择性的加入 ``--min_slice_duration=<num_seconds>`` 如果你想改变最小音频片段长度。

AN4 数据集
-----------

这是一个由卡内基梅隆大学录制和提供的小数据集。它包含很多人说的地址、姓名等内容。关于这个数据集的信息可以在这找到 `official CMU site <http://www.speech.cs.cmu.edu/databases/an4/>`_ 。

请下载并解压数据集（其被标注为“NIST” Sphere（.sph）音频文件格式（64M）在如下的链接中）：http://www.speech.cs.cmu.edu/databases/an4/an4_sphere.tar.gz.

运行如下的脚本，使用 sox 将 .sph 文件转换成 .wav 格式，同时构建训练和测试清单。

.. code-block:: bash

  python process_an4_data.py --data_root=<path_to_extracted_data>

当这个脚本运行结束时，你应该可以在 `<data_root>/an4/` 文件夹下得到 `train_manifest.json` 和 `test_manifest.json` 两个文件。

AISHELL-1
---------

运行下面的脚本下载 AISHELL-1 数据集并把它转换到 `nemo_asr` 集合需要的文件格式。

.. code-block:: bash

    # install sox
    sudo apt-get install sox
    mkdir data
    python get_aishell_data.py --data_root=data

之后，你的 `data` 文件夹应该包含了一个 `data_aishell` 文件夹，它下面包含了 wav 文件夹，transcript 文件夹以及相应的 `.json` 清单文件和 `vocab.txt` 文件：

AISHELL-2
---------

运行下面的脚本处理 AIShell-2 数据集，把它处理成 `nemo_asr` 需要的文件格式。通过设置 ``--audio_folder`` 指定数据目录，用 ``--dest_folder`` 指定处理后的文件目录。

.. code-block:: bash

    python process_aishell2_data.py --audio_folder=<data directory> --dest_folder=<destination directory>

接着在 `dest_folder` 下会生成 `train.json` `dev.json` `test.json` 以及 `vocab.txt` 。
