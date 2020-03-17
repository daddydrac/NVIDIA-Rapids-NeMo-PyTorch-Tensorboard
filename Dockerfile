# syntax=docker/dockerfile:experimental

# Copyright (c) 2019, NVIDIA CORPORATION. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ARG BASE_IMAGE=nvcr.io/nvidia/pytorch:19.08-py3

# build an image that includes only the nemo dependencies, ensures that dependencies
# are included first for optimal caching, and useful for building a development
# image (by specifying build target as `nemo-deps`)
FROM ${BASE_IMAGE} as nemo-deps

# Ensure apt-get won't prompt for selecting options
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y \
    libsndfile1 sox \
    build-essential \
    python-dev \
    apt-transport-https \
    ca-certificates \
    gnupg \
    software-properties-common \
    wget \
    git \
    checkinstall \
    zlib1g-dev \
    python-setuptools \
    python-dev && \
    rm -rf /var/lib/apt/lists/*

#RUN echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/conda/lib/' >> ~/.bashrc
#RUN source ~/.bashrc

RUN conda install -c rapidsai -c nvidia -c conda-forge \
    -c defaults rapids=0.12 python=3.6 cudatoolkit=10.1

RUN pip install Cython
WORKDIR /
# Apparently it doesnt know how to remove everything w one cmd
RUN apt remove cmake -y
RUN apt-get purge cmake -y
RUN apt-get update

RUN wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null | apt-key add -
RUN apt-add-repository 'deb https://apt.kitware.com/ubuntu/ bionic main'
RUN apt-get update
RUN apt-get install cmake -y --silent
RUN cmake --version

# build trt open source plugins
ENV PATH=$PATH:/usr/src/tensorrt/bin
WORKDIR /tmp/trt-oss
RUN git clone --recursive --branch release/7.0 https://github.com/NVIDIA/TensorRT.git && cd TensorRT && \
     mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DTRT_LIB_DIR=/usr/lib/x86_64-linux-gnu/ -DTRT_BIN_DIR=`pwd` \
    -DBUILD_PARSERS=OFF -DBUILD_SAMPLES=OFF -DBUILD_PLUGINS=ON -DGPU_ARCHS="70 75" && \
    make -j nvinfer_plugin

# install nemo dependencies
WORKDIR /tmp/nemo
COPY requirements/requirements_docker.txt requirements.txt
RUN pip install --disable-pip-version-check --no-cache-dir -r requirements.txt

# copy nemo source into a scratch image
FROM scratch as nemo-src
COPY . .

# start building the final container
FROM nemo-deps as nemo
ARG NEMO_VERSION
ARG BASE_IMAGE

# copy oss trt plugins
COPY --from=nemo-deps /tmp/trt-oss/TensorRT/build/libnvinfer_plugin.so* /usr/lib/x86_64-linux-gnu/

# Check that NEMO_VERSION is set. Build will fail without this. Expose NEMO and base container
# version information as runtime environment variable for introspection purposes
RUN /usr/bin/test -n "0.9.0" && \
    /bin/echo "export NEMO_VERSION=0.9.0" >> /root/.bashrc && \
    /bin/echo "export BASE_IMAGE=${BASE_IMAGE}" >> /root/.bashrc
RUN --mount=from=nemo-src,target=/tmp/nemo cd /tmp/nemo && pip install ".[all]"


# copy scripts/examples/tests into container for end user
WORKDIR /workspace/nemo
COPY scripts /workspace/nemo/scripts
COPY examples /workspace/nemo/examples
COPY tests /workspace/nemo/tests
COPY README.rst LICENSE /workspace/nemo/

RUN printf "#!/bin/bash\njupyter lab --no-browser --allow-root --ip=0.0.0.0" >> start-jupyter.sh && \
   chmod +x start-jupyter.sh

RUN pip install dask distributed
RUN pip install nltk
RUN pip install -U spacy
RUN pip install gensim
RUN pip install tensorboard
RUN pip install jupyter-tabnine

VOLUME /workspace
WORKDIR /workspace
EXPOSE 8888 6006

CMD ["bash", "-c", "source /etc/bash.bashrc && jupyter notebook --notebook-dir=/workspace --ip 0.0.0.0 --no-browser --allow-root --NotebookApp.custom_display_url='http://localhost:8888'"]
