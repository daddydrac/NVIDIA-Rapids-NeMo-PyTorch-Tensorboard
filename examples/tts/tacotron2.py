# Copyright 2020 NVIDIA. All Rights Reserved.
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
import argparse
import math
import os
from functools import partial

from ruamel.yaml import YAML

import nemo
import nemo.collections.asr as nemo_asr
import nemo.collections.tts as nemo_tts
import nemo.utils.argparse as nm_argparse
from nemo.collections.tts import (
    tacotron2_eval_log_to_tb_func,
    tacotron2_log_to_tb_func,
    tacotron2_process_eval_batch,
    tacotron2_process_final_eval,
)
from nemo.utils.lr_policies import CosineAnnealing

logging = nemo.logging


def parse_args():
    parser = argparse.ArgumentParser(
        parents=[nm_argparse.NemoArgParser()], description='Tacotron2', conflict_handler='resolve',
    )
    parser.set_defaults(
        checkpoint_dir=None,
        optimizer="adam",
        batch_size=48,
        eval_batch_size=32,
        lr=0.001,
        amp_opt_level="O0",
        create_tb_writer=True,
        lr_policy=None,
        weight_decay=1e-6,
    )

    # Overwrite default args
    parser.add_argument("--max_steps", type=int, default=None, help="max number of steps to train")
    parser.add_argument("--num_epochs", type=int, default=None, help="number of epochs to train")
    parser.add_argument("--model_config", type=str, required=True, help="model configuration file: model.yaml")
    parser.add_argument("--grad_norm_clip", type=float, default=1.0, help="gradient clipping")
    parser.add_argument("--min_lr", type=float, default=1e-5, help="minimum learning rate to decay to")

    # Create new args
    parser.add_argument("--exp_name", default="Tacotron2", type=str)

    args = parser.parse_args()

    if args.lr_policy:
        raise NotImplementedError("Tacotron 2 does not support lr policy arg")
    if args.max_steps is not None and args.num_epochs is not None:
        raise ValueError("Either max_steps or num_epochs should be provided.")
    if args.eval_freq % 25 != 0:
        raise ValueError("eval_freq should be a multiple of 25.")

    exp_directory = [
        f"{args.exp_name}-lr_{args.lr}-bs_{args.batch_size}",
        "",
        f"-wd_{args.weight_decay}-opt_{args.optimizer}-ips_{args.iter_per_step}",
    ]
    if args.max_steps:
        exp_directory[1] = f"-s_{args.max_steps}"
    elif args.num_epochs:
        exp_directory[1] = f"-e_{args.num_epochs}"
    else:
        raise ValueError("Both max_steps and num_epochs were None.")
    return args, "".join(exp_directory)


def create_NMs(tacotron2_config_file, labels, decoder_infer=False):
    data_preprocessor = nemo_asr.AudioToMelSpectrogramPreprocessor.import_from_config(
        tacotron2_config_file, "AudioToMelSpectrogramPreprocessor"
    )
    text_embedding = nemo_tts.TextEmbedding.import_from_config(
        tacotron2_config_file, "TextEmbedding", overwrite_params={"n_symbols": len(labels) + 3}
    )
    t2_enc = nemo_tts.Tacotron2Encoder.import_from_config(tacotron2_config_file, "Tacotron2Encoder")
    if decoder_infer:
        t2_dec = nemo_tts.Tacotron2DecoderInfer.import_from_config(tacotron2_config_file, "Tacotron2DecoderInfer")
    else:
        t2_dec = nemo_tts.Tacotron2Decoder.import_from_config(tacotron2_config_file, "Tacotron2Decoder")
    t2_postnet = nemo_tts.Tacotron2Postnet.import_from_config(tacotron2_config_file, "Tacotron2Postnet")
    t2_loss = nemo_tts.Tacotron2Loss.import_from_config(tacotron2_config_file, "Tacotron2Loss")
    makegatetarget = nemo_tts.MakeGate()

    total_weights = text_embedding.num_weights + t2_enc.num_weights + t2_dec.num_weights + t2_postnet.num_weights

    logging.info('================================')
    logging.info(f"Total number of parameters: {total_weights}")
    logging.info('================================')

    return (
        data_preprocessor,
        text_embedding,
        t2_enc,
        t2_dec,
        t2_postnet,
        t2_loss,
        makegatetarget,
    )


def create_train_dag(
    neural_factory,
    neural_modules,
    tacotron2_config_file,
    train_dataset,
    batch_size,
    log_freq,
    checkpoint_save_freq,
    labels,
    cpu_per_dl=1,
):
    (data_preprocessor, text_embedding, t2_enc, t2_dec, t2_postnet, t2_loss, makegatetarget) = neural_modules

    data_layer = nemo_asr.AudioToTextDataLayer.import_from_config(
        tacotron2_config_file,
        "AudioToTextDataLayer_train",
        overwrite_params={
            "manifest_filepath": train_dataset,
            "batch_size": batch_size,
            "num_workers": cpu_per_dl,
            "bos_id": len(labels),
            "eos_id": len(labels) + 1,
            "pad_id": len(labels) + 2,
        },
    )

    N = len(data_layer)
    steps_per_epoch = math.ceil(N / (batch_size * neural_factory.world_size))
    logging.info(f'Have {N} examples to train on.')

    # Train DAG
    audio, audio_len, transcript, transcript_len = data_layer()
    spec_target, spec_target_len = data_preprocessor(input_signal=audio, length=audio_len)

    transcript_embedded = text_embedding(char_phone=transcript)
    transcript_encoded = t2_enc(char_phone_embeddings=transcript_embedded, embedding_length=transcript_len)
    mel_decoder, gate, alignments = t2_dec(
        char_phone_encoded=transcript_encoded, encoded_length=transcript_len, mel_target=spec_target,
    )
    mel_postnet = t2_postnet(mel_input=mel_decoder)
    gate_target = makegatetarget(mel_target=spec_target, target_len=spec_target_len)
    loss_t = t2_loss(
        mel_out=mel_decoder,
        mel_out_postnet=mel_postnet,
        gate_out=gate,
        mel_target=spec_target,
        gate_target=gate_target,
        target_len=spec_target_len,
        seq_len=audio_len,
    )

    # Callbacks needed to print info to console and Tensorboard
    train_callback = nemo.core.SimpleLossLoggerCallback(
        tensors=[loss_t, spec_target, mel_postnet, gate, gate_target, alignments],
        print_func=lambda x: logging.info(f"Loss: {x[0].data}"),
        log_to_tb_func=partial(tacotron2_log_to_tb_func, log_images=True, log_images_freq=log_freq),
        tb_writer=neural_factory.tb_writer,
    )

    chpt_callback = nemo.core.CheckpointCallback(folder=neural_factory.checkpoint_dir, step_freq=checkpoint_save_freq)

    callbacks = [train_callback, chpt_callback]
    return loss_t, callbacks, steps_per_epoch


def create_eval_dags(
    neural_factory,
    neural_modules,
    tacotron2_config_file,
    eval_datasets,
    eval_batch_size,
    eval_freq,
    labels,
    cpu_per_dl=1,
):
    (data_preprocessor, text_embedding, t2_enc, t2_dec, t2_postnet, t2_loss, makegatetarget) = neural_modules

    callbacks = []
    # assemble eval DAGs
    for eval_dataset in eval_datasets:
        data_layer_eval = nemo_asr.AudioToTextDataLayer.import_from_config(
            tacotron2_config_file,
            "AudioToTextDataLayer_eval",
            overwrite_params={
                "manifest_filepath": eval_dataset,
                "batch_size": eval_batch_size,
                "num_workers": cpu_per_dl,
                "bos_id": len(labels),
                "eos_id": len(labels) + 1,
                "pad_id": len(labels) + 2,
            },
        )

        audio, audio_len, transcript, transcript_len = data_layer_eval()
        spec_target, spec_target_len = data_preprocessor(input_signal=audio, length=audio_len)

        transcript_embedded = text_embedding(char_phone=transcript)
        transcript_encoded = t2_enc(char_phone_embeddings=transcript_embedded, embedding_length=transcript_len)
        mel_decoder, gate, alignments = t2_dec(
            char_phone_encoded=transcript_encoded, encoded_length=transcript_len, mel_target=spec_target,
        )
        mel_postnet = t2_postnet(mel_input=mel_decoder)
        gate_target = makegatetarget(mel_target=spec_target, target_len=spec_target_len)
        loss = t2_loss(
            mel_out=mel_decoder,
            mel_out_postnet=mel_postnet,
            gate_out=gate,
            mel_target=spec_target,
            gate_target=gate_target,
            target_len=spec_target_len,
            seq_len=audio_len,
        )

        # create corresponding eval callback
        tagname = os.path.basename(eval_dataset).split(".")[0]
        eval_tensors = [
            loss,
            spec_target,
            mel_postnet,
            gate,
            gate_target,
            alignments,
        ]
        eval_callback = nemo.core.EvaluatorCallback(
            eval_tensors=eval_tensors,
            user_iter_callback=tacotron2_process_eval_batch,
            user_epochs_done_callback=partial(tacotron2_process_final_eval, tag=tagname),
            tb_writer_func=partial(tacotron2_eval_log_to_tb_func, tag=tagname),
            eval_step=eval_freq,
            tb_writer=neural_factory.tb_writer,
        )

        callbacks.append(eval_callback)
    return callbacks


def create_all_dags(
    neural_factory,
    neural_modules,
    tacotron2_config_file,
    train_dataset,
    batch_size,
    eval_freq,
    labels,
    checkpoint_save_freq=None,
    eval_datasets=None,
    eval_batch_size=None,
):
    # Calculate num_workers for dataloader
    cpu_per_dl = max(int(os.cpu_count() / neural_factory.world_size), 1)

    training_loss, training_callbacks, steps_per_epoch = create_train_dag(
        neural_factory=neural_factory,
        neural_modules=neural_modules,
        tacotron2_config_file=tacotron2_config_file,
        train_dataset=train_dataset,
        batch_size=batch_size,
        log_freq=eval_freq,
        checkpoint_save_freq=checkpoint_save_freq,
        cpu_per_dl=cpu_per_dl,
        labels=labels,
    )

    eval_callbacks = []
    if eval_datasets:
        eval_callbacks = create_eval_dags(
            neural_factory=neural_factory,
            neural_modules=neural_modules,
            tacotron2_config_file=tacotron2_config_file,
            eval_datasets=eval_datasets,
            eval_batch_size=eval_batch_size,
            eval_freq=eval_freq,
            cpu_per_dl=cpu_per_dl,
            labels=labels,
        )
    else:
        logging.info("There were no val datasets passed")

    callbacks = training_callbacks + eval_callbacks
    return training_loss, callbacks, steps_per_epoch


def main():
    args, name = parse_args()

    log_dir = name
    if args.work_dir:
        log_dir = os.path.join(args.work_dir, name)

    # instantiate Neural Factory with supported backend
    neural_factory = nemo.core.NeuralModuleFactory(
        backend=nemo.core.Backend.PyTorch,
        local_rank=args.local_rank,
        optimization_level=args.amp_opt_level,
        log_dir=log_dir,
        checkpoint_dir=args.checkpoint_dir,
        create_tb_writer=args.create_tb_writer,
        files_to_copy=[args.model_config, __file__],
        cudnn_benchmark=args.cudnn_benchmark,
        tensorboard_dir=args.tensorboard_dir,
    )

    if args.local_rank is not None:
        logging.info('Doing ALL GPU')

    yaml = YAML(typ="safe")
    with open(args.model_config) as file:
        tacotron2_params = yaml.load(file)
        labels = tacotron2_params["labels"]
    # instantiate neural modules
    neural_modules = create_NMs(args.model_config, labels)

    # build dags
    train_loss, callbacks, steps_per_epoch = create_all_dags(
        neural_factory=neural_factory,
        neural_modules=neural_modules,
        tacotron2_config_file=args.model_config,
        train_dataset=args.train_dataset,
        batch_size=args.batch_size,
        eval_freq=args.eval_freq,
        checkpoint_save_freq=args.checkpoint_save_freq,
        eval_datasets=args.eval_datasets,
        eval_batch_size=args.eval_batch_size,
        labels=labels,
    )

    # train model
    total_steps = args.max_steps if args.max_steps is not None else args.num_epochs * steps_per_epoch
    neural_factory.train(
        tensors_to_optimize=[train_loss],
        callbacks=callbacks,
        lr_policy=CosineAnnealing(total_steps, min_lr=args.min_lr),
        optimizer=args.optimizer,
        optimization_params={
            "num_epochs": args.num_epochs,
            "max_steps": args.max_steps,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "grad_norm_clip": args.grad_norm_clip,
        },
        batches_per_step=args.iter_per_step,
    )


if __name__ == '__main__':
    main()
