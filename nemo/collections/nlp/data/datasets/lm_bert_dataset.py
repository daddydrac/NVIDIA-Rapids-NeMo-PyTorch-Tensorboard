# =============================================================================
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
# =============================================================================

"""Pytorch Dataset for training BERT."""

import array
import glob
import os
import pickle
import random

import h5py
import numpy as np
from sentencepiece import SentencePieceTrainer as SPT
from torch.utils.data import Dataset
from tqdm import tqdm

from nemo import logging
from nemo.collections.nlp.data.datasets.datasets_utils.data_preprocessing import DATABASE_EXISTS_TMP, if_exist

__all__ = ['BertPretrainingDataset', 'BertPretrainingPreprocessedDataset']


class BertPretrainingDataset(Dataset):
    def __init__(
        self,
        tokenizer,
        dataset,
        max_seq_length=128,
        mask_probability=0.15,
        short_seq_prob=0.1,
        seq_a_ratio=0.6,
        sentence_idx_file=None,
    ):
        self.tokenizer = tokenizer

        # Loading enormous datasets into RAM isn't always feasible -- for
        # example, the pubmed corpus is 200+ GB, which doesn't fit into RAM on
        # most computers. To get around this, we store the indices of newlines
        # in each file so we can seek to and retrieve sentences immediately
        # from main memory when needed during training.

        if sentence_idx_file is None:
            data_dir = dataset[: dataset.rfind('/')]
            mode = dataset[dataset.rfind('/') + 1 : dataset.rfind('.')]
            sentence_idx_file = f"{data_dir}/{mode}_sentence_indices.pkl"

        if os.path.isfile(sentence_idx_file):
            # If the sentence indices file already exists, load from it
            with open(sentence_idx_file, "rb") as f:
                sentence_indices = pickle.load(f)
        else:
            # Otherwise, generate and store sentence indices
            sentence_indices = {}

            # Finds all of the newline indices in a string
            def find_newlines(contents):
                start = 0

                while True:
                    try:
                        # index and split are much faster than Python for loops
                        new_start = contents.index(b"\n", start)
                        line = (
                            contents[start:new_start]
                            .replace(b"\xc2\x99", b" ")
                            .replace(b"\xc2\xa0", b" ")
                            .decode("utf-8", errors="ignore")
                        )

                        if len(line.split()) > 0:
                            yield start

                        start = new_start + 1

                    except ValueError:
                        break

            if os.path.isdir(dataset):
                dataset_pattern = os.path.join(dataset, "**", "*.txt")
                filenames = glob.glob(dataset_pattern, recursive=True)
            else:
                filenames = [dataset]

            for filename in tqdm(filenames):
                with open(filename, "rb") as f:
                    contents = f.read()
                    newline_indices = find_newlines(contents)

                if os.path.isdir(dataset):
                    # Only keep the parts of the filepath that are invariant to
                    # the dataset's location on disk
                    filename = os.path.basename(filename)

                # In python, arrays are much more space-efficient than lists
                sentence_indices[filename] = array.array("I", newline_indices)

            # Save sentence indices so we don't have to do this again
            with open(sentence_idx_file, "wb") as f:
                pickle.dump(sentence_indices, f)

        corpus_size = 0
        empty_files = []

        # Find total number of newlines across entire corpus and remove files
        # without any newlines
        for filename in sentence_indices:
            if len(sentence_indices[filename]) <= 1:
                empty_files.append(filename)
            else:
                corpus_size += len(sentence_indices[filename])

        for filename in empty_files:
            del sentence_indices[filename]

        self.corpus_size = corpus_size
        self.dataset = dataset
        self.filenames = list(sentence_indices.keys())
        self.mask_probability = mask_probability
        self.max_seq_length = max_seq_length
        self.sentence_indices = sentence_indices
        self.vocab_size = self.tokenizer.vocab_size
        self.short_seq_prob = short_seq_prob
        self.seq_a_ratio = seq_a_ratio

    def __len__(self):
        return self.corpus_size

    def __getitem__(self, idx, min_doc_length=16):
        # Each sequence has three special tokens, as follows:
        # tokenizer.cls_token <document a> tokenizer.sep_token <document b> tokenizer.eos_token
        num_special_tokens = 3

        max_num_tokens = self.max_seq_length - num_special_tokens
        target_seq_length = max_num_tokens
        if random.random() < self.short_seq_prob:
            # TODO: maybe introduce an argument to control this.
            target_seq_length = random.randint(2, max_num_tokens)

        # prefer the seq_a to be slightly longer than seq_b, 0.6 by default
        target_seq_length_a = int(round(target_seq_length * self.seq_a_ratio))
        target_seq_length_b = target_seq_length - target_seq_length_a

        def get_document(filepath, offset):
            # Retrieve a specific line from a file and return as a document
            if os.path.isdir(self.dataset):
                filepath = os.path.join(self.dataset, filepath)

            with open(filepath, "rb") as f:
                f.seek(offset)
                doc_text = f.readline()[:-1].decode("utf-8", errors="ignore")
                document = self.tokenizer.text_to_ids(doc_text)

            return document

        def match_target_seq_length(document, target_seq_length, filename, line_idx, sentence_indices):
            # If document is shorter than target sequence length,
            # append the next line or take a random line as replacement.
            num_lines = len(sentence_indices[filename])

            while len(document) < target_seq_length:
                if line_idx < (num_lines - 1):
                    # append the next line
                    line_idx += 1
                else:
                    # current line is the last line, take a random one
                    line_idx = random.randrange(num_lines)
                    document = []

                offset = sentence_indices[filename][line_idx]
                document += get_document(filename, offset)

            return document, line_idx

        # Take sequence A from a random file and a random line
        a_filename = random.choice(self.filenames)
        a_line_idx = random.randrange(len(self.sentence_indices[a_filename]))
        a_line_offset = self.sentence_indices[a_filename][a_line_idx]
        a_document = get_document(a_filename, a_line_offset)
        a_document, a_line_idx = match_target_seq_length(
            a_document, target_seq_length_a, a_filename, a_line_idx, self.sentence_indices
        )

        is_last_line = a_line_idx >= (len(self.sentence_indices[a_filename]) - 1)
        # About 50% of the time, B is a random sentence from the corpus
        take_random_b = (random.random() < 0.5) or is_last_line

        if take_random_b:
            # This should rarely go for more than one iteration for large
            # corpora. However, just to be careful, we try to make sure that
            # the random document is not the same as the document
            # we're processing.
            for _ in range(10):
                b_filename = random.choice(self.filenames)
                b_line_idx = random.choice(range(len(self.sentence_indices[b_filename])))
                if b_filename != a_filename:
                    break
                else:
                    # Take another line from the same file
                    b_line_pos = self.sentence_indices[b_filename][b_line_idx]
                    a_line_pos = self.sentence_indices[a_filename][a_line_idx]
                    # TODO unclear about the following check
                    if abs(b_line_pos - a_line_pos) > max_num_tokens:
                        break
                    else:
                        pass
        else:
            b_filename = a_filename
            b_line_idx = a_line_idx + 1

        is_next = int(not take_random_b)
        b_line_pos = self.sentence_indices[b_filename][b_line_idx]
        b_document = get_document(b_filename, b_line_pos)
        b_document, b_line_idx = match_target_seq_length(
            b_document, target_seq_length_b, b_filename, b_line_idx, self.sentence_indices
        )

        def truncate_seq_pair(a, b, max_num_tokens):
            # Truncates a pair of sequences to a maximum sequence length
            while (len(a) + len(b)) > max_num_tokens:
                # Truncate the longer sequence
                if len(a) > len(b):
                    trunc_document = a
                else:
                    trunc_document = b

                if len(trunc_document) <= 1:
                    raise ValueError(
                        "Input text corpora probably too small. "
                        "Failed to truncate sequence pair to "
                        "maximum sequence legnth."
                    )

                # Randomly truncate from the front or the back
                if random.random() < 0.5:
                    del trunc_document[0]
                else:
                    trunc_document.pop()

        truncate_seq_pair(a_document, b_document, max_num_tokens)

        output_ids = (
            [self.tokenizer.cls_id] + a_document + [self.tokenizer.sep_id] + b_document + [self.tokenizer.eos_id]
        )

        input_ids, output_mask = self.mask_ids(output_ids)

        input_mask = np.zeros(self.max_seq_length, dtype=np.long)
        input_mask[: len(input_ids)] = 1

        input_type_ids = np.zeros(self.max_seq_length, dtype=np.int)
        input_type_ids[len(a_document) + 2 : len(output_ids) + 1] = 1

        padding_length = max(0, self.max_seq_length - len(input_ids))
        if padding_length > 0:
            input_ids.extend([self.tokenizer.pad_id] * padding_length)
            output_ids.extend([self.tokenizer.pad_id] * padding_length)
            output_mask.extend([0] * padding_length)

        # TODO: wrap the return value with () for consistent style.
        return (
            np.array(input_ids),
            input_type_ids,
            np.array(input_mask, dtype=np.long),
            np.array(output_ids),
            np.array(output_mask, dtype=np.float32),
            is_next,
        )

    def mask_ids(self, ids):
        """
        Args:
          ids: list of token ids representing a chunk of text
        Returns:
          masked_ids: list of input tokens with some of the entries masked
            according to the following protocol from the original BERT paper:
            each token is masked with a probability of 15% and is replaced with
            1) the [MASK] token 80% of the time,
            2) random token 10% of the time,
            3) the same token 10% of the time.
          output_mask: list of binary variables which indicate what tokens has
            been masked (to calculate the loss function for these tokens only)
        """

        # Whole-word masking by default, as it gives better performance.
        cand_indexes = [[ids[0]]]
        for tid in ids[1:]:
            token = self.tokenizer.ids_to_tokens([tid])[0]
            is_suffix = token.startswith('\u2581')
            if is_suffix:
                # group together with its previous token to form a whole-word
                cand_indexes[-1].append(tid)
            else:
                cand_indexes.append([tid])

        masked_ids, output_mask = [], []
        mask_id = self.tokenizer.token_to_id("[MASK]")

        for word_ids in cand_indexes:
            is_special = (word_ids[0] == self.tokenizer.cls_id) or (word_ids[0] == self.tokenizer.sep_id)
            if is_special or (random.random() > self.mask_probability):
                output_mask.extend([0] * len(word_ids))
                masked_ids.extend(word_ids)
            else:
                output_mask.extend([1] * len(word_ids))
                p = random.random()
                # for 80%, replace with mask
                if p < 0.8:
                    masked_ids.extend([mask_id] * len(word_ids))
                # for 10%, replace by a random token
                elif p < 0.9:
                    for _ in word_ids:
                        # randomly select a valid word
                        random_word = random.randrange(self.vocab_size)
                        while random_word in (self.tokenizer.cls_id, self.tokenizer.sep_id):
                            random_word = random.randrange(self.vocab_size)
                        masked_ids.append(random_word)
                # for 10%, use same token
                else:
                    masked_ids.extend(word_ids)

        return masked_ids, output_mask


class BertPretrainingPreprocessedDataset(Dataset):
    def __init__(self, input_file, max_pred_length):
        self.input_file = input_file
        self.max_pred_length = max_pred_length
        f = h5py.File(input_file, "r")
        keys = [
            'input_ids',
            'input_mask',
            'segment_ids',
            'masked_lm_positions',
            'masked_lm_ids',
            'next_sentence_labels',
        ]
        self.inputs = [np.asarray(f[key][:]) for key in keys]
        f.close()

    def __len__(self):
        'Denotes the total number of samples'
        return len(self.inputs[0])

    def __getitem__(self, index):
        [input_ids, input_mask, segment_ids, masked_lm_positions, masked_lm_ids, next_sentence_labels] = [
            input[index].astype(np.int64) for input in self.inputs
        ]

        output_mask = np.zeros_like(input_ids)
        output_ids = input_ids.copy()

        index = self.max_pred_length
        padded_mask_indices = (masked_lm_positions == 0).nonzero()
        if len(padded_mask_indices[0]) != 0:
            index = padded_mask_indices[0][0]

        output_mask[masked_lm_positions[:index]] = 1.0
        output_ids[masked_lm_positions[:index]] = masked_lm_ids[:index]

        input_mask = np.asarray(input_mask, dtype=np.float32)
        output_mask = np.asarray(output_mask, dtype=np.float32)
        return (input_ids, segment_ids, input_mask, output_ids, output_mask, next_sentence_labels)


class BERTPretrainingDataDesc:
    def __init__(
        self, dataset_name, vocab_size, sample_size, special_tokens, train_data, eval_data=None, test_data=None,
    ):
        if dataset_name == 'wikitext-2':
            if not os.path.exists(train_data):
                raise FileNotFoundError(
                    "Dataset not found. Run 'get_wkt2.sh DATA_DIR' from examples/nlp/language_modeling"
                )
            self.data_dir, self.tokenizer_model, self.vocab_file = self.create_vocab_mlm(
                train_data, vocab_size, sample_size, special_tokens
            )
        else:
            raise ValueError(
                "Looks like you passed a dataset name that isn't already supported by NeMo. Please make sure that "
                "you build the preprocessing method for it."
            )

        self.train_file = train_data
        self.eval_file = eval_data
        self.test_file = test_data

    def create_vocab_mlm(
        self, data_file, vocab_size, sample_size, special_tokens=['[PAD]', '[UNK]', '[CLS]', '[SEP]', '[MASK]'],
    ):
        data_dir = os.path.dirname(data_file)
        vocab = special_tokens[:]
        bert_dir = f'{data_dir}/bert'
        if if_exist(bert_dir, ['tokenizer.model']):
            logging.info(DATABASE_EXISTS_TMP.format('WikiText_BERT', bert_dir))
            return data_dir, f'{bert_dir}/tokenizer.model', f'{bert_dir}/vocab.txt'
        logging.info(f'Processing WikiText dataset and store at {bert_dir}')
        os.makedirs(bert_dir, exist_ok=True)

        if not data_file:
            files = glob.glob(f'{data_dir}/*.txt')
            data_file = f'{bert_dir}/merged.txt'
            logging.info(f"Merging {len(files)} txt files into {data_file}")

            with open(data_file, "w") as merged:
                for file in tqdm(files):
                    with open(file, 'r') as inf:
                        content = inf.read().strip()
                    merged.write(content + '\n\n\n')

        cmd = (
            f"--input={data_file} --model_prefix={bert_dir}/tokenizer "
            f"--vocab_size={vocab_size - len(vocab)} "
            f"--input_sentence_size={sample_size} "
            f"--shuffle_input_sentence=true --hard_vocab_limit=false "
            f"--bos_id=-1 --eos_id=-1"
        )

        SPT.Train(cmd)

        # Add BERT control symbols
        tokens = []

        with open(f"{bert_dir}/tokenizer.vocab", "r") as f:
            f.readline()  # skip first <unk> token

            # Read tokens from each line and parse for vocab
            for line in f:
                piece = line.split("\t")[0]
                token = piece[1:] if piece.startswith("▁") else f"##{piece}"
                tokens.append(token)

        vocab.extend(tokens)

        # Save vocabulary to output file
        vocab_file = f'{bert_dir}/vocab.txt'
        with open(vocab_file, "w") as f:
            for token in vocab:
                f.write(f"{token}\n".format())
        return data_dir, f'{bert_dir}/tokenizer.model', vocab_file
