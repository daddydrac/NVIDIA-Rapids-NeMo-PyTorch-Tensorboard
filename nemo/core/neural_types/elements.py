# ! /usr/bin/python
# -*- coding: utf-8 -*-

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

__all__ = [
    'ElementType',
    'VoidType',
    'ChannelType',
    'AcousticEncodedRepresentation',
    'AudioSignal',
    'SpectrogramType',
    'MelSpectrogramType',
    'MFCCSpectrogramType',
    'LogitsType',
    'LabelsType',
    'LossType',
    'RegressionValuesType',
    'CategoricalValuesType',
    'PredictionsType',
    'LogprobsType',
    'LengthsType',
    'EmbeddedTextType',
    'EncodedRepresentation',
    'MaskType',
]
import abc
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

from nemo.core.neural_types.comparison import NeuralTypeComparisonResult


class ElementType(ABC):
    """Abstract class defining semantics of the tensor elements.
    We are relying on Python for inheritance checking"""

    def __str__(self):
        self.__doc__

    def __repr__(self):
        return self.__class__.__name__

    @property
    def type_parameters(self) -> Dict:
        """Override this property to parametrize your type. For example, you can specify 'storage' type such as
        float, int, bool with 'dtype' keyword. Another example, is if you want to represent a signal with a
        particular property (say, sample frequency), then you can put sample_freq->value in there.
        When two types are compared their type_parameters must match."""
        return {}

    @property
    def fields(self) -> Optional[Tuple]:
        """This should be used to logically represent tuples/structures. For example, if you want to represent a
        bounding box (x, y, width, height) you can put a tuple with names ('x', y', 'w', 'h') in here.
        Under the hood this should be converted to the last tesnor dimension of fixed size = len(fields).
        When two types are compared their fields must match."""
        return None

    def compare(self, second) -> NeuralTypeComparisonResult:
        # First, check general compatibility
        first_t = type(self)
        second_t = type(second)

        if first_t == second_t:
            result = NeuralTypeComparisonResult.SAME
        elif issubclass(first_t, second_t):
            result = NeuralTypeComparisonResult.LESS
        elif issubclass(second_t, first_t):
            result = NeuralTypeComparisonResult.GREATER
        else:
            result = NeuralTypeComparisonResult.INCOMPATIBLE

        if result != NeuralTypeComparisonResult.SAME:
            return result
        else:
            # now check that all parameters match
            check_params = set(self.type_parameters.keys()) == set(second.type_parameters.keys())
            if check_params is False:
                return NeuralTypeComparisonResult.SAME_TYPE_INCOMPATIBLE_PARAMS
            else:
                for k1, v1 in self.type_parameters.items():
                    if v1 != second.type_parameters[k1]:
                        return NeuralTypeComparisonResult.SAME_TYPE_INCOMPATIBLE_PARAMS
            # check that all fields match
            if self.fields == second.fields:
                return NeuralTypeComparisonResult.SAME
            else:
                return NeuralTypeComparisonResult.INCOMPATIBLE


class VoidType(ElementType):
    """Void-like type which is compatible with everything.
    It is a good practice to use this type only as necessary.
    For example, when you need template-like functionality.
    """

    def compare(cls, second: abc.ABCMeta) -> NeuralTypeComparisonResult:
        return NeuralTypeComparisonResult.SAME


# TODO: Consider moving these files elsewhere
class ChannelType(ElementType):
    """Element to represent convolutional input/output channel.
    """


class EmbeddedTextType(ChannelType):
    """Element to represent output on word/text embedding layers
    """


class LogitsType(ElementType):
    """Element type to represent logits"""


class LogprobsType(ElementType):
    """Element type to represent log-probabilities. For example, outputs of softmax layers."""


class LabelsType(ElementType):
    """Element type to represent some sort of labels. This is often used as a base class to create
    a more concrete types such as RegressionValuesType, etc."""


class LengthsType(ElementType):
    """Element type representing lengths of something"""


class LossType(ElementType):
    """Element type to represent outputs of Loss modules"""


class EncodedRepresentation(ChannelType):
    """Element type to represent encoded representation, for example, encoder's output"""


class AcousticEncodedRepresentation(EncodedRepresentation):
    """Element type to represent encoded representation returned by the acoustic encoder model"""


class AudioSignal(ElementType):
    """Element type to represent encoded representation returned by the acoustic encoder model
    Args:
        freq (int): sampling frequency of a signal. Note that two signals will only be the same if their
        freq is the same.
    """

    def __init__(self, freq: int = 16000):
        self._params = {}
        self._params['freq'] = freq

    @property
    def type_parameters(self):
        return self._params


class SpectrogramType(ChannelType):
    """Element type to represent generic spectrogram signal"""


class MelSpectrogramType(SpectrogramType):
    """Element type to represent mel spectrogram signal"""


class MFCCSpectrogramType(SpectrogramType):
    """Element type to represent MFCC spectrogram signal"""


class PredictionsType(LabelsType):
    """Element type to represent some sort of predictions returned by model"""


class RegressionValuesType(PredictionsType):
    """Element type to represent labels for regression task"""


class CategoricalValuesType(PredictionsType):
    """Element type to represent labels for categorical classification task"""


class MaskType(PredictionsType):
    """Element type to represent boolean mask"""
