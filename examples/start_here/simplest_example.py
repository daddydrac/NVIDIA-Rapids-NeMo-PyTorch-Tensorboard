# Copyright (c) 2019 NVIDIA Corporation
import nemo

logging = nemo.logging

nf = nemo.core.NeuralModuleFactory()
# To use CPU-only do:
# nf = nemo.core.NeuralModuleFactory(placement=nemo.core.DeviceType.CPU)

# Instantiate the necessary neural modules.
# RealFunctionDataLayer defaults to f_name="sin", sampling from x=[-4, 4]
dl = nemo.tutorials.RealFunctionDataLayer(n=10000, batch_size=128)
fx = nemo.tutorials.TaylorNet(dim=4)
loss = nemo.tutorials.MSELoss()

# Describe the activation flow.
x, y = dl()
p = fx(x=x)
lss = loss(predictions=p, target=y)

# SimpleLossLoggerCallback will print loss values to console.
callback = nemo.core.SimpleLossLoggerCallback(
    tensors=[lss], print_func=lambda x: logging.info(f'Train Loss: {str(x[0].item())}'),
)

# Invoke "train" action.
nf.train([lss], callbacks=[callback], optimization_params={"num_epochs": 3, "lr": 0.0003}, optimizer="sgd")
