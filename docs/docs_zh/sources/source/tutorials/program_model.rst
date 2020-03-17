编程模型
-------------------

一个典型的使用 NeMo APIs 构建的应用包含三个逻辑步骤：

1) 创建 :class:`NeuralModuleFactory<nemo.core.neural_factory.NeuralModuleFactory>` 类和必要的 :class:`NeuralModule<nemo.core.neural_modules.NeuralModule>` 类
2) 定义 :class:`NeuralModule<nemo.core.neural_modules.NeuralModule>` 类的有向无环图（DAG） 
3) 调用像是 :class:`train<nemo.core.neural_factory.Actions.train>` 类的操作

NeMo 遵循 *lazy execution* 模型 - 实际的计算只会在训练和推理的操作被调用后才会执行。

:class:`NeuralModule<nemo.core.neural_modules.NeuralModule>` 是层和神经网络的一个抽象，比如：编码器，解码器，语言模型，声学模型等。每个 :class:`NeuralModule<nemo.core.neural_modules.NeuralModule>` 从一系列的输入计算一系列的输出。
每个 :class:`NmTensor<nemo.core.neural_types.NmTensor>` 有 :class:`NeuralType<nemo.core.neural_types.NeuralType>` 。
:class:`NeuralType<nemo.core.neural_types.NeuralType>` 描述了张量的语义，轴的次序和维度。用这些类型
来确定模块之间如何连接起来。

你也可以给操作传递 *回调函数* ，这些回调函数可以用来做评估验证，打印日志和性能监测。
