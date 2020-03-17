import argparse

import onnx
import tensorrt as trt


def build_engine(
    onnx_path,
    seq_len=192,
    max_seq_len=256,
    batch_size=8,
    max_batch_size=64,
    trt_fp16=True,
    verbose=True,
    max_workspace_size=None,
    encoder=True,
):
    """Builds TRT engine from an ONNX file
    Note that network output 1 is unmarked so that the engine will not use
    vestigial length calculations associated with masked_fill
    """
    TRT_LOGGER = trt.Logger(trt.Logger.VERBOSE) if verbose else trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(TRT_LOGGER)
    builder.max_batch_size = max_batch_size

    with open(onnx_path, 'rb') as model_fh:
        model = model_fh.read()

    model_onnx = onnx.load_model_from_string(model)
    input_feats = model_onnx.graph.input[0].type.tensor_type.shape.dim[1].dim_value
    input_name = model_onnx.graph.input[0].name

    if trt_fp16:
        builder.fp16_mode = True
        print("Optimizing for FP16")
        config_flags = 1 << int(trt.BuilderFlag.FP16)  # | 1 << int(trt.BuilderFlag.STRICT_TYPES)
    else:
        config_flags = 0
    builder.max_workspace_size = max_workspace_size if max_workspace_size else (4 * 1024 * 1024 * 1024)

    config = builder.create_builder_config()
    config.flags = config_flags

    profile = builder.create_optimization_profile()
    profile.set_shape(
        input_name,
        min=(1, input_feats, seq_len),
        opt=(batch_size, input_feats, seq_len),
        max=(max_batch_size, input_feats, max_seq_len),
    )
    config.add_optimization_profile(profile)

    explicit_batch = 1 << (int)(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    network = builder.create_network(explicit_batch)

    with trt.OnnxParser(network, TRT_LOGGER) as parser:
        parsed = parser.parse(model)
        print("Parsing returned ", parsed)
        return builder.build_engine(network, config=config)


def get_parser():
    parser = argparse.ArgumentParser(description="Convert Jasper ONNX model to TRT Plan")
    parser.add_argument("onnx", default=None, type=str, help="Path to Jasper ONNX model")
    parser.add_argument("trt_plan", default=None, type=str, help="Path to output Jasper TRT model plan")
    parser.add_argument("--max-seq-len", type=int, default=256, help="Maximum sequence length of input")
    parser.add_argument("--seq-len", type=int, default=192, help="Preferred sequence length of input")
    parser.add_argument("--max-batch-size", type=int, default=64, help="Maximum sequence length of input")
    parser.add_argument("--batch-size", type=int, default=8, help="Preferred batch size of input")
    parser.add_argument("--no-fp16", action="store_true", help="Disable fp16 model building, use fp32 instead")

    return parser


if __name__ == '__main__':
    args = get_parser().parse_args()
    engine = build_engine(
        args.onnx,
        seq_len=args.seq_len,
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
        max_batch_size=args.max_batch_size,
        trt_fp16=not args.no_fp16,
    )
    if engine is not None:
        with open(args.trt_plan, 'wb') as f:
            f.write(engine.serialize())
            print("TRT engine saved at " + args.trt_plan + " ...")
