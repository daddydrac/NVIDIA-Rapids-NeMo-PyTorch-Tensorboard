# ! /usr/bin/python
# -*- coding: utf-8 -*-

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

from unittest import TestCase

import pytest
import torch

import nemo
from nemo.backends.pytorch.nm import NonTrainableNM
from nemo.core.neural_types import AxisKind, AxisType, ChannelType, NeuralType
from nemo.utils.decorators import add_port_docs


class AddsTen(NonTrainableNM):
    def __init__(self):
        super().__init__()

    @property
    @add_port_docs()
    def input_ports(self):
        # return {"mod_in": NeuralType({0: AxisType(BatchTag), 1: AxisType(BaseTag, dim=1)})}
        return {"mod_in": NeuralType((AxisType(AxisKind.Batch), AxisType(AxisKind.Dimension, 1)), ChannelType())}

    @property
    @add_port_docs()
    def output_ports(self):
        # return {"mod_out": NeuralType({0: AxisType(BatchTag), 1: AxisType(BaseTag, dim=1)})}
        return {"mod_out": NeuralType((AxisType(AxisKind.Batch), AxisType(AxisKind.Dimension, 1)), ChannelType())}

    def forward(self, mod_in):
        return mod_in + 10


class SubtractsTen(NonTrainableNM):
    def __init__(self):
        super().__init__()

    @property
    @add_port_docs()
    def input_ports(self):
        return {"mod_in": NeuralType((AxisType(AxisKind.Batch), AxisType(AxisKind.Dimension, 1)), ChannelType())}

    @property
    @add_port_docs()
    def output_ports(self):
        return {"mod_out": NeuralType((AxisType(AxisKind.Batch), AxisType(AxisKind.Dimension, 1)), ChannelType())}

    def forward(self, mod_in):
        return mod_in - 10


@pytest.mark.usefixtures("neural_factory")
class TestInfer(TestCase):
    def setUp(self) -> None:
        """ Re-instantiates Neural Factory for every test. """
        # Re-initialize the default Neural Factory - on the indicated device.
        self.nf = nemo.core.NeuralModuleFactory(placement=self.nf.placement)

    @pytest.mark.system
    def test_infer_caching(self):
        data_source = nemo.backends.pytorch.common.ZerosDataLayer(
            size=1,
            dtype=torch.FloatTensor,
            batch_size=1,
            output_ports={
                "dl_out": NeuralType((AxisType(AxisKind.Batch), AxisType(AxisKind.Dimension, 1)), ChannelType())
            },
        )
        addten = AddsTen()
        minusten = SubtractsTen()

        zero_tensor = data_source()
        ten_tensor = addten(mod_in=zero_tensor)
        twenty_tensor = addten(mod_in=ten_tensor)
        thirty_tensor = addten(mod_in=twenty_tensor)

        evaluated_tensors = self.nf.infer(tensors=[twenty_tensor, thirty_tensor], verbose=False, cache=True)
        self.assertEqual(evaluated_tensors[0][0].squeeze().data, 20)
        self.assertEqual(evaluated_tensors[1][0].squeeze().data, 30)

        new_ten_tensor = minusten(mod_in=twenty_tensor)
        evaluated_tensors = self.nf.infer(tensors=[new_ten_tensor], verbose=False, use_cache=True)
        self.assertEqual(evaluated_tensors[0][0].squeeze().data, 10)

    @pytest.mark.system
    def test_infer_errors(self):

        data_source = nemo.backends.pytorch.common.ZerosDataLayer(
            size=1,
            dtype=torch.FloatTensor,
            batch_size=1,
            output_ports={
                "dl_out": NeuralType((AxisType(AxisKind.Batch), AxisType(AxisKind.Dimension, 1)), ChannelType())
            },
        )
        addten = AddsTen()
        minusten = SubtractsTen()

        zero_tensor = data_source()
        ten_tensor = addten(mod_in=zero_tensor)
        twenty_tensor = addten(mod_in=ten_tensor)
        thirty_tensor = addten(mod_in=twenty_tensor)

        with self.assertRaisesRegex(ValueError, "use_cache was set, but cache was empty"):
            evaluated_tensors = self.nf.infer(tensors=[twenty_tensor, thirty_tensor], verbose=False, use_cache=True)

        new_ten_tensor = minusten(mod_in=twenty_tensor)
        evaluated_tensors = self.nf.infer(tensors=[new_ten_tensor], verbose=False, cache=True)

        with self.assertRaisesRegex(ValueError, "cache was set but was not empty"):
            evaluated_tensors = self.nf.infer(tensors=[twenty_tensor, thirty_tensor], verbose=False, cache=True)

        self.nf.clear_cache()
        evaluated_tensors = self.nf.infer(tensors=[new_ten_tensor], verbose=False, cache=True)

        with self.assertRaisesRegex(ValueError, "cache and use_cache were both set."):
            evaluated_tensors = self.nf.infer(
                tensors=[twenty_tensor, thirty_tensor], verbose=False, cache=True, use_cache=True
            )
        self.assertEqual(evaluated_tensors[0][0].squeeze().data, 10)
