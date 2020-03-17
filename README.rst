.. image:: http://www.repostatus.org/badges/latest/active.svg
  :target: http://www.repostatus.org/#active
  :alt: Project Status: Active – The project has reached a stable, usable state and is being actively developed.

.. image:: https://img.shields.io/badge/documentation-github.io-blue.svg
  :target: https://nvidia.github.io/NeMo/
  :alt: NeMo documentation on GitHub pages

.. image:: https://img.shields.io/badge/License-Apache%202.0-brightgreen.svg
  :target: https://github.com/NVIDIA/NeMo/blob/master/LICENSE
  :alt: NeMo core license and license for collections in this repo

.. image:: https://img.shields.io/lgtm/grade/python/g/NVIDIA/NeMo.svg?logo=lgtm&logoWidth=18
  :target: https://lgtm.com/projects/g/NVIDIA/NeMo/context:python
  :alt: Language grade: Python

.. image:: https://img.shields.io/lgtm/alerts/g/NVIDIA/NeMo.svg?logo=lgtm&logoWidth=18
  :target: https://lgtm.com/projects/g/NVIDIA/NeMo/alerts/
  :alt: Total alerts

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
  :target: https://github.com/psf/black
  :alt: Code style: black



NVIDIA Neural Modules: NeMo
===========================

NeMo is a toolkit for defining and building `Conversational AI <https://developer.nvidia.com/conversational-ai#started>`_ applications.

Goal of the NeMo toolkit is to make it possible for researchers to easily compose complex neural network architectures for conversational AI using reusable components. Built for speed, NeMo can utilize NVIDIA's Tensor Cores and scale out training to multiple GPUs and multiple nodes.

**Neural Modules** are conceptual blocks of neural networks that take *typed* inputs and produce *typed* outputs. Such modules typically represent data layers, encoders, decoders, language models, loss functions, or methods of combining activations.

The toolkit comes with extendable collections of pre-built modules for automatic speech recognition (ASR), natural language processing (NLP) and text synthesis (TTS).

**Introduction**

* Watch `this video <https://nvidia.github.io/NeMo/>`_ for a quick walk-through.

* Documentation (latest released version): https://nvidia.github.io/NeMo/

* Read NVIDIA `Developer Blog for example applications <https://devblogs.nvidia.com/how-to-build-domain-specific-automatic-speech-recognition-models-on-gpus/>`_

* Read NVIDIA `Developer Blog for Quartznet ASR model <https://devblogs.nvidia.com/develop-smaller-speech-recognition-models-with-nvidias-nemo-framework/>`_

* Recommended version to install is **0.9.0** via ``pip install nemo-toolkit``

* Recommended NVIDIA `NGC NeMo Toolkit container <https://ngc.nvidia.com/catalog/containers/nvidia:nemo>`_

* Pretrained models are available on NVIDIA `NGC Model repository <https://ngc.nvidia.com/catalog/models?orderBy=modifiedDESC&query=nemo&quickFilter=models&filters=>`_


Getting started
~~~~~~~~~~~~~~~

THE LATEST STABLE VERSION OF NeMo is **0.9.0** (Available via PIP).

**Requirements**

1) Python 3.6 or 3.7
2) PyTorch 1.4.* with GPU support
3) (optional, for best performance) NVIDIA APEX. Install from here: https://github.com/NVIDIA/apex

**NeMo Docker Container**
 NVIDIA `NGC NeMo Toolkit container <https://ngc.nvidia.com/catalog/containers/nvidia:nemo>`_ is now available.

* Pull the docker: ``docker pull nvcr.io/nvidia/nemo:v0.9``
* Run: ``docker run --runtime=nvidia -it --rm -v <nemo_github_folder>:/NeMo --shm-size=8g -p 8888:8888 -p 6006:6006 --ulimit memlock=-1 --ulimit stack=67108864 nvcr.io/nvidia/nemo:v0.9``

If you are using the NVIDIA `NGC PyTorch container <https://ngc.nvidia.com/catalog/containers/nvidia:pytorch>`_ follow these instructions

* Pull the docker: ``docker pull nvcr.io/nvidia/pytorch:20.01-py3``
* Run: ``docker run --runtime=nvidia -it --rm -v <nemo_github_folder>:/NeMo --shm-size=8g -p 8888:8888 -p 6006:6006 --ulimit memlock=-1 --ulimit stack=67108864 nvcr.io/nvidia/pytorch:20.01-py3``
* ``apt-get update && apt-get install -y libsndfile1``
* ``pip install nemo_toolkit`` NeMo core
* ``pip install nemo_asr`` NeMo ASR (Speech Recognition) collection
* ``pip install nemo_nlp`` NeMo NLP (Natural Language Processing) collection
* ``pip install nemo_tts`` NeMo TTS (Speech Synthesis) collection

See `examples/start_here` to get started with the simplest example. The folder `examples` contains several examples to get you started with various tasks in NLP and ASR.

**Tutorials**

* `Speech recognition <https://nvidia.github.io/NeMo/asr/intro.html>`_
* `Natural language processing <https://nvidia.github.io/NeMo/nlp/intro.html>`_
* `Speech Synthesis <https://nvidia.github.io/NeMo/tts/intro.html>`_


DEVELOPMENT
~~~~~~~~~~~
If you'd like to use master branch and/or develop NeMo you can run "reinstall.sh" script.

`Documentation (master branch) <http://nemo-master-docs.s3-website.us-east-2.amazonaws.com/>`_.

**Installing From Github**

If you prefer to use NeMo's latest development version (from GitHub) follow the steps below:

1) Clone the repository ``git clone https://github.com/NVIDIA/NeMo.git``
2) Go to NeMo folder and re-install the toolkit with collections:

.. code-block:: bash

    ./reinstall.sh

**Style tests**

.. code-block:: bash

    python setup.py style  # Checks overall project code style and output issues with diff.
    python setup.py style --fix  # Tries to fix error in-place.
    python setup.py style --scope=tests  # Operates within certain scope (dir of file).

**Unittests**

This command runs unittests:

.. code-block:: bash

    ./reinstall.sh
    python pytest tests


Citation
~~~~~~~~

If you are using NeMo please cite the following publication

.. code-block:: tex

    @misc{nemo2019,
        title={NeMo: a toolkit for building AI applications using Neural Modules},
        author={Oleksii Kuchaiev and Jason Li and Huyen Nguyen and Oleksii Hrinchuk and Ryan Leary and Boris Ginsburg and Samuel Kriman and Stanislav Beliaev and Vitaly Lavrukhin and Jack Cook and Patrice Castonguay and Mariya Popova and Jocelyn Huang and Jonathan M. Cohen},
        year={2019},
        eprint={1909.09577},
        archivePrefix={arXiv},
        primaryClass={cs.LG}
    }

