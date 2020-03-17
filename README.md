# TensorRT-NVIDIA-Neural-Modules-NeMo
NeMo is a toolkit for defining and building new state of the art deep learning models for Conversational AI applications  Goal of the NeMo toolkit is to make it possible for researchers to easily and safely compose complex neural network architectures for conversational AI using reusable components. Built for speed, NeMo can scale out training to multiple GPUs and multiple nodes.

For some reason with `DOCKER_BUILDKIT`, it takes a very long while for conda repo's to resolve. So installation of any Conda repo and Rapids AI takes a very long time. (Just let it run until it figures itself out). 

### Features

- NVIDIA NeMo
- Jupyterlab & notebook
- CUDA 10.0
- CuPy for CUDA 10
- Dask distributed
- NLTK
- SpaCy
- Scipy
- gensim
- Tensorboard
- PyTorch


### How to build and launch notebook
Port 8888 is the notebook and 6006 is Tensorboard for analysis and debugging

1. ``` DOCKER_BUILDKIT=1 docker build --build-arg NEMO_VERSION=$(git describe --tags) -t nemo . ```

2. ``` docker run --runtime=nvidia -it --rm -v <nemo_github_folder>:/NeMo --shm-size=8g -p 8888:8888 -p 6006:6006 --ulimit memlock=-1 --ulimit stack=67108864 nemo ```

### Set up TensorBoard

This is optional because you can launch Tensorboard right from Jupyter Notebook

1. Get the <container id> (you only need the first 3 char's): ``` docker ps ```

2. Then, exec into the container: ``` docker exec -u root -t -i <container id> /bin/bash ```

3. Then run in cmd line: ``` tensorboard --logdir=//workspace ```

Tensorboard should be avail on port 6006 now.

Links:
  - Jupyter Notebook: http://localhost:8888/
  - Tensorboard: http://localhost:6006/
  
