# =============================================================================
# Copyright 2020 NVIDIA. All Rights Reserved.
# Copyright 2018 The Google AI Language Team Authors and
# The HuggingFace Inc. team.
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
# =============================================================================

"""
Utility functions for Token Classification NLP tasks
Some parts of this code were adapted from the HuggingFace library at
https://github.com/huggingface/pytorch-pretrained-BERT
"""

import itertools
import os
import pickle

import numpy as np
from torch.utils.data import Dataset

from nemo import logging
from nemo.collections.nlp.data.datasets.datasets_utils.data_preprocessing import get_label_stats, get_stats

__all__ = ['BertTokenClassificationDataset', 'BertTokenClassificationInferDataset']


def get_features(
    queries,
    max_seq_length,
    tokenizer,
    label_ids=None,
    pad_label='O',
    raw_labels=None,
    ignore_extra_tokens=False,
    ignore_start_end=False,
):
    """
    Args:
    queries (list of str): text sequences
    max_seq_length (int): max sequence length minus 2 for [CLS] and [SEP]
    tokenizer (Tokenizer): such as NemoBertTokenizer
    pad_label (str): pad value use for labels.
        by default, it's the neutral label.
    raw_labels (list of str): list of labels for every word in a sequence
    label_ids (dict): dict to map labels to label ids. Starts
        with pad_label->0 and then increases in alphabetical order.
        Required for training and evaluation, not needed for inference.
    ignore_extra_tokens (bool): whether to ignore extra tokens in
        the loss_mask,
    ignore_start_end (bool): whether to ignore bos and eos tokens in
        the loss_mask
    """
    all_subtokens = []
    all_loss_mask = []
    all_subtokens_mask = []
    all_segment_ids = []
    all_input_ids = []
    all_input_mask = []
    sent_lengths = []
    all_labels = []
    with_label = False

    if raw_labels is not None:
        with_label = True

    for i, query in enumerate(queries):
        words = query.strip().split()

        # add bos token
        subtokens = ['[CLS]']
        loss_mask = [1 - ignore_start_end]
        subtokens_mask = [0]
        if with_label:
            pad_id = label_ids[pad_label]
            labels = [pad_id]
            query_labels = [label_ids[lab] for lab in raw_labels[i]]

        for j, word in enumerate(words):
            word_tokens = tokenizer.text_to_tokens(word)
            subtokens.extend(word_tokens)

            loss_mask.append(1)
            loss_mask.extend([int(not ignore_extra_tokens)] * (len(word_tokens) - 1))

            subtokens_mask.append(1)
            subtokens_mask.extend([0] * (len(word_tokens) - 1))

            if with_label:
                labels.extend([query_labels[j]] * len(word_tokens))
        # add eos token
        subtokens.append('[SEP]')
        loss_mask.append(1 - ignore_start_end)
        subtokens_mask.append(0)
        sent_lengths.append(len(subtokens))
        all_subtokens.append(subtokens)
        all_loss_mask.append(loss_mask)
        all_subtokens_mask.append(subtokens_mask)
        all_input_mask.append([1] * len(subtokens))

        if with_label:
            labels.append(pad_id)
            all_labels.append(labels)

    max_seq_length = min(max_seq_length, max(sent_lengths))
    logging.info(f'Max length: {max_seq_length}')
    get_stats(sent_lengths)
    too_long_count = 0

    for i, subtokens in enumerate(all_subtokens):
        if len(subtokens) > max_seq_length:
            subtokens = ['[CLS]'] + subtokens[-max_seq_length + 1 :]
            all_input_mask[i] = [1] + all_input_mask[i][-max_seq_length + 1 :]
            all_loss_mask[i] = [int(not ignore_start_end)] + all_loss_mask[i][-max_seq_length + 1 :]
            all_subtokens_mask[i] = [0] + all_subtokens_mask[i][-max_seq_length + 1 :]

            if with_label:
                all_labels[i] = [pad_id] + all_labels[i][-max_seq_length + 1 :]
            too_long_count += 1

        all_input_ids.append([tokenizer.tokens_to_ids(t) for t in subtokens])

        if len(subtokens) < max_seq_length:
            extra = max_seq_length - len(subtokens)
            all_input_ids[i] = all_input_ids[i] + [0] * extra
            all_loss_mask[i] = all_loss_mask[i] + [0] * extra
            all_subtokens_mask[i] = all_subtokens_mask[i] + [0] * extra
            all_input_mask[i] = all_input_mask[i] + [0] * extra

            if with_label:
                all_labels[i] = all_labels[i] + [pad_id] * extra

        all_segment_ids.append([0] * max_seq_length)

    logging.warning(f'{too_long_count} are longer than {max_seq_length}')

    for i in range(min(len(all_input_ids), 5)):
        logging.debug("*** Example ***")
        logging.debug("i: %s", i)
        logging.debug("subtokens: %s", " ".join(list(map(str, all_subtokens[i]))))
        logging.debug("loss_mask: %s", " ".join(list(map(str, all_loss_mask[i]))))
        logging.debug("input_mask: %s", " ".join(list(map(str, all_input_mask[i]))))
        logging.debug("subtokens_mask: %s", " ".join(list(map(str, all_subtokens_mask[i]))))
        if with_label:
            logging.debug("labels: %s", " ".join(list(map(str, all_labels[i]))))
    return (all_input_ids, all_segment_ids, all_input_mask, all_loss_mask, all_subtokens_mask, all_labels)


class BertTokenClassificationDataset(Dataset):
    """
    Creates dataset to use during training for token classification
    tasks with a pretrained model.

    Converts from raw data to an instance that can be used by
    NMDataLayer.

    For dataset to use during inference without labels, see
    BertTokenClassificationInferDataset.

    Args:
        text_file (str): file to sequences, each line should a sentence,
            No header.
        label_file (str): file to labels, each line corresponds to
            word labels for a sentence in the text_file. No header.
        max_seq_length (int): max sequence length minus 2 for [CLS] and [SEP]
        tokenizer (Tokenizer): such as NemoBertTokenizer
        num_samples (int): number of samples you want to use for the dataset.
            If -1, use all dataset. Useful for testing.
        pad_label (str): pad value use for labels.
            by default, it's the neutral label.
        label_ids (dict): label_ids (dict): dict to map labels to label ids.
            Starts with pad_label->0 and then increases in alphabetical order
            For dev set use label_ids generated during training to support
            cases when not all labels are present in the dev set.
            For training set label_ids should be None.
        ignore_extra_tokens (bool): whether to ignore extra tokens in
            the loss_mask,
        ignore_start_end (bool): whether to ignore bos and eos tokens in
            the loss_mask
    """

    def __init__(
        self,
        text_file,
        label_file,
        max_seq_length,
        tokenizer,
        num_samples=-1,
        pad_label='O',
        label_ids=None,
        ignore_extra_tokens=False,
        ignore_start_end=False,
        use_cache=False,
    ):

        if use_cache:
            # Cache features
            data_dir = os.path.dirname(text_file)
            filename = os.path.basename(text_file)

            if not filename.endswith('.txt'):
                raise ValueError("{text_file} should have extension .txt")

            features_pkl = os.path.join(data_dir, filename[:-4] + "_features.pkl")
            label_ids_pkl = os.path.join(data_dir, "label_ids.pkl")

        if use_cache and os.path.exists(features_pkl) and os.path.exists(label_ids_pkl):
            # If text_file was already processed, load from pickle
            features = pickle.load(open(features_pkl, 'rb'))
            logging.info(f'features restored from {features_pkl}')

            label_ids = pickle.load(open(label_ids_pkl, 'rb'))
            logging.info(f'Labels to ids dict restored from {label_ids_pkl}')
        else:
            if num_samples == 0:
                raise ValueError("num_samples has to be positive", num_samples)

            with open(text_file, 'r') as f:
                text_lines = f.readlines()

            # Collect all possible labels
            unique_labels = set([])
            labels_lines = []
            with open(label_file, 'r') as f:
                for line in f:
                    line = line.strip().split()
                    labels_lines.append(line)
                    unique_labels.update(line)

            if len(labels_lines) != len(text_lines):
                raise ValueError("Labels file should contain labels for every word")

            if num_samples > 0:
                dataset = list(zip(text_lines, labels_lines))
                dataset = dataset[:num_samples]

                dataset = list(zip(*dataset))
                text_lines = dataset[0]
                labels_lines = dataset[1]

            # for dev/test sets use label mapping from training set
            if label_ids:
                if len(label_ids) != len(unique_labels):
                    logging.warning(
                        f'Not all labels from the specified'
                        + ' label_ids dictionary are present in the'
                        + ' current dataset. Using the provided'
                        + ' label_ids dictionary.'
                    )
                else:
                    logging.info(f'Using the provided label_ids dictionary.')
            else:
                logging.info(
                    f'Creating a new label to label_id dictionary.'
                    + ' It\'s recommended to use label_ids generated'
                    + ' during training for dev/test sets to avoid'
                    + ' errors if some labels are not'
                    + ' present in the dev/test sets.'
                    + ' For training set label_ids should be None.'
                )

                label_ids = {pad_label: 0}
                if pad_label in unique_labels:
                    unique_labels.remove(pad_label)
                for label in sorted(unique_labels):
                    label_ids[label] = len(label_ids)

            features = get_features(
                text_lines,
                max_seq_length,
                tokenizer,
                pad_label=pad_label,
                raw_labels=labels_lines,
                label_ids=label_ids,
                ignore_extra_tokens=ignore_extra_tokens,
                ignore_start_end=ignore_start_end,
            )

            if use_cache:
                pickle.dump(features, open(features_pkl, "wb"))
                logging.info(f'features saved to {features_pkl}')

                pickle.dump(label_ids, open(label_ids_pkl, "wb"))
                logging.info(f'labels to ids dict saved to {label_ids_pkl}')

        self.all_input_ids = features[0]
        self.all_segment_ids = features[1]
        self.all_input_mask = features[2]
        self.all_loss_mask = features[3]
        self.all_subtokens_mask = features[4]
        self.all_labels = features[5]
        self.label_ids = label_ids

        infold = text_file[: text_file.rfind('/')]
        merged_labels = itertools.chain.from_iterable(self.all_labels)
        logging.info('Three most popular labels')
        _, self.label_frequencies = get_label_stats(merged_labels, infold + '/label_stats.tsv')

        # save label_ids
        out = open(infold + '/label_ids.csv', 'w')
        labels, _ = zip(*sorted(self.label_ids.items(), key=lambda x: x[1]))
        out.write('\n'.join(labels))
        logging.info(f'Labels: {self.label_ids}')
        logging.info(f'Labels mapping saved to : {out.name}')

    def __len__(self):
        return len(self.all_input_ids)

    def __getitem__(self, idx):
        return (
            np.array(self.all_input_ids[idx]),
            np.array(self.all_segment_ids[idx]),
            np.array(self.all_input_mask[idx], dtype=np.long),
            np.array(self.all_loss_mask[idx]),
            np.array(self.all_subtokens_mask[idx]),
            np.array(self.all_labels[idx]),
        )


class BertTokenClassificationInferDataset(Dataset):
    """
    Creates dataset to use during inference for token classification
    tasks with a pretrained model.

    Converts from raw data to an instance that can be used by
    NMDataLayer.

    For dataset to use during training with labels, see
    BertTokenClassificationDataset.

    Args:
        queries (list): list of queries to run inference on
        max_seq_length (int): max sequence length minus 2 for [CLS] and [SEP]
        tokenizer (Tokenizer): such as NemoBertTokenizer
    """

    def __init__(self, queries, max_seq_length, tokenizer):
        features = get_features(queries, max_seq_length, tokenizer)

        self.all_input_ids = features[0]
        self.all_segment_ids = features[1]
        self.all_input_mask = features[2]
        self.all_loss_mask = features[3]
        self.all_subtokens_mask = features[4]

    def __len__(self):
        return len(self.all_input_ids)

    def __getitem__(self, idx):
        return (
            np.array(self.all_input_ids[idx]),
            np.array(self.all_segment_ids[idx]),
            np.array(self.all_input_mask[idx], dtype=np.long),
            np.array(self.all_loss_mask[idx]),
            np.array(self.all_subtokens_mask[idx]),
        )
