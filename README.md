# Accelerated GPU NLP Toolkit: RAPIDS-AI, PyTorch, NeMo, Tensorboard, TensorRT, CUDA 10.1
NeMo is a toolkit for defining and building new state of the art deep learning models for Conversational AI applications  Goal of the NeMo toolkit is to make it possible for researchers to easily and safely compose complex neural network architectures for conversational AI using reusable components. Built for speed, NeMo can scale out training to multiple GPUs and multiple nodes.

For some reason with `DOCKER_BUILDKIT`, it takes a very long while for conda repo's to resolve. So installation of any Conda repo and Rapids AI takes a very long time. (Just let it run until it figures itself out). 

NLP Container, requirements:

- Docker > v19.x
- nvidia-docker => v2.x
- docker container runtime == latest 


### Features

- NVIDIA NeMo
- Jupyter Notebook
- CUDA 10.1 + TensorRT release 7.0
- Dask distributed
- NLTK
- SpaCy
- Scipy
- Gensim
- Tensorboard
- PyTorch


### How to build and launch notebook
Port 8888 is the notebook and 6006 is Tensorboard for analysis and debugging

1. ``` DOCKER_BUILDKIT=1 docker build --build-arg NEMO_VERSION=$(git describe --tags) -t nlp . ```

2. ``` docker run --runtime=nvidia -it --rm -v nemo:/NeMo --shm-size=8g -v "${PWD}:/workspace"  -p 8888:8888 -p 6006:6006 --ulimit memlock=-1 --ulimit stack=67108864 nlp```

### If using DGX2

After the DOCKER_BUILDKIT cmd, run:

sudo docker run -it --rm -v nemo:/NeMo --shm-size=8g -v "<DGX_USER_FILE_PATH_HERE>:/workspace" -p 9999:8888 -p 6006:6006 --ulimit memlock=-1 --ulimit stack=67108864 --runtime=nvidia --detach nlp


3. Click the `localhost` link in the command line with the jupyter security token, it will automatically launch in browser for you.

4. Navigate to `/examples` to see demos and examples

5. Navigate to `/workspace` where your custom application files you develop will be mounted. (This is where you do your work).


### Built in code hinting in Jupyter Notebook ###

Press tab to see what methods you have access to by clicking tab.

![jupyter-tabnine](https://raw.githubusercontent.com/wenmin-wu/jupyter-tabnine/master/images/demo.gif)


### Set up TensorBoard

This is optional because you can simply launch Tensorbord right from Jupyter Notebook.

1. Get the <container id> (you only need the first 3 char's): ``` docker ps ```

2. Then, exec into the container: ``` docker exec -u root -t -i <container id> /bin/bash ```

3. Then run in cmd line: ``` tensorboard --logdir=//workspace ```

Tensorboard should be avail on port 6006 now.

Links:
  - Jupyter Notebook: http://localhost:8888/
  - Tensorboard: http://localhost:6006/
  
