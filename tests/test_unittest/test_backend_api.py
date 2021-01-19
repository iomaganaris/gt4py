# -*- coding: utf-8 -*-
#
# GT4Py - GridTools4Py - GridTools for Python
#
# Copyright (c) 2014-2021, ETH Zurich
# All rights reserved.
#
# This file is part the GT4Py project and the GridTools framework.
# GT4Py is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or any later
# version. See the LICENSE.txt file at the top-level directory of this
# distribution for a copy of the license or check <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

import gt4py
from gt4py.gtscript import PARALLEL, Field, computation, interval
from gt4py.stencil_builder import StencilBuilder


@pytest.fixture(
    params=[
        pytest.param(
            name,
            marks=pytest.mark.skipif(
                name.startswith("dawn"), reason="dawn backends not yet supported"
            ),
        )
        for name in gt4py.backend.REGISTRY.keys()
    ]
)
def backend(request):
    """Parametrize by backend name."""
    yield gt4py.backend.from_name(request.param)


# mypy gets confused by gtscript
def init_1(input_field: Field[float]):  # type: ignore
    """Implement simple stencil."""
    with computation(PARALLEL), interval(...):  # type: ignore
        input_field = 1  # noqa - unused var is in/out field


def test_generate_computation(backend, tmp_path):
    """Test if the :py:meth:`gt4py.backend.CLIBackendMixin.generate_computation` generates code."""
    # note: if a backend is added that doesn't use CliBackendMixin it will
    # have to be special cased in the backend fixture
    builder = StencilBuilder(init_1, backend=backend).with_caching(
        "nocaching", output_path=tmp_path / __name__ / "generate_computation"
    )
    result = builder.backend.generate_computation()

    # python backends only generate one module
    py_result = backend.languages["computation"] == "python" and "init_1.py" in result
    # c++ / cuda files generated by gt backends.
    # computation does not include bindings
    gt_result = (
        backend.languages["computation"] in {"c++", "cuda"}
        and "init_1_src" in result
        and "computation.hpp" in result["init_1_src"]
        and ("computation.cpp" in result["init_1_src"] or "computation.cu" in result["init_1_src"])
        and "bindings.cpp" not in result["init_1_src"]
    )
    assert py_result or gt_result


def test_generate_bindings(backend, tmp_path):
    """Test :py:meth:`gt4py.backend.CLIBackendMixin.generate_bindings`."""
    builder = StencilBuilder(init_1, backend=backend).with_caching(
        "nocaching", output_path=tmp_path / __name__ / "generate_bindings"
    )
    if not backend.languages["bindings"]:
        # no bindings supported
        with pytest.raises(NotImplementedError):
            result = builder.backend.generate_bindings("python")
    else:
        # assumption: only gt backends support python bindings
        result = builder.backend.generate_bindings("python")
        assert "init_1_src" in result
        assert "bindings.cpp" in result["init_1_src"]
