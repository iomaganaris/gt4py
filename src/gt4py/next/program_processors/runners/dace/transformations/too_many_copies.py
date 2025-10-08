# GT4Py - GridTools Framework
#
# Copyright (c) 2014-2024, ETH Zurich
# All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Any, Optional

import dace
from dace import (
    data as dace_data,
    properties as dace_properties,
    transformation as dace_transformation,
)
from dace.sdfg import nodes as dace_nodes


@dace_properties.make_properties
class RemoveAccessNodeCopies(dace_transformation.SingleStateTransformation):
    """
    Remove pointwise views from the SDFG.
    This transformation is used to remove views that are created for pointwise operations.
    It redirects the edges from the view to the original data and removes the view node.
    The view generation is non-deterministic and usually happens after reduction `Library` nodes.
    """

    first_node = dace_transformation.PatternNode(dace_nodes.AccessNode)
    second_node = dace_transformation.PatternNode(dace_nodes.AccessNode)
    third_node = dace_transformation.PatternNode(dace_nodes.AccessNode)
    fourth_node = dace_transformation.PatternNode(dace_nodes.AccessNode)

    # Name of all data that is used at only one place. Is computed by the
    #  `FindSingleUseData` pass and be passed at construction time. Needed until
    #  [issue#1911](https://github.com/spcl/dace/issues/1911) has been solved.
    _single_use_data: Optional[dict[dace.SDFG, set[str]]]

    def __init__(
        self,
        *args: Any,
        single_use_data: Optional[dict[dace.SDFG, set[str]]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._single_use_data = None
        if single_use_data is not None:
            self._single_use_data = single_use_data

    @classmethod
    def expressions(cls) -> Any:
        return [
            dace.sdfg.utils.node_path_graph(
                cls.first_node, cls.second_node, cls.third_node, cls.fourth_node
            )
        ]

    def can_be_applied(
        self,
        graph: dace.SDFGState,
        expr_index: int,
        sdfg: dace.SDFG,
        permissive: bool = False,
    ) -> bool:
        first_node: dace_nodes.AccessNode = self.first_node
        first_desc: dace_data.Data = first_node.desc(sdfg)
        second_node: dace_nodes.AccessNode = self.second_node
        second_desc: dace_data.Data = second_node.desc(sdfg)
        third_node: dace_nodes.AccessNode = self.third_node
        third_desc: dace_data.Data = third_node.desc(sdfg)
        fourth_node: dace_nodes.AccessNode = self.fourth_node
        fourth_desc: dace_data.Data = fourth_node.desc(sdfg)

        # scope = graph.scope_dict()

        if (
            first_desc.transient is False
            and second_desc.transient is True
            and third_desc.transient is True
            and fourth_desc.transient is False
        ):
            print(
                "[RemoveAccessNodeCopies] {} -> {} -> {} -> {}".format(
                    first_node.data, second_node.data, third_node.data, fourth_node.data
                )
            )
        else:
            return False

        if first_node.data != fourth_node.data:
            return False

        # Make sure that there is no other AccessNode with the same data in the SDFG state

        # Make sure that the data written to the first node are not a subset of the data written to the fourth node

        # Make sure that data written to second_node and third_node are not a superset of the data written to fourth_node

        first_edge = None
        first_node_out_edges = graph.out_edges(first_node)

        second_node_in_edges = graph.in_edges(second_node)

        # Find the edge in first_node_out_edges that is also present in second_node_in_edges
        for edge in first_node_out_edges:
            if edge in second_node_in_edges:
                first_edge = edge
                break

        # fourth_node_in_edges = graph.in_edges(fourth_node)

        # for fourth_edge in fourth_node_in_edges:
        #     if gtx_dace_split.are_intersecting(first_edge.dst_subset, fourth_edge.src_subset):
        #         return False

        # import pdb; pdb.set_trace()

        return True

    def apply(
        self,
        graph: dace.SDFGState,
        sdfg: dace.SDFG,
    ) -> None:
        first_node: dace_nodes.AccessNode = self.first_node
        first_desc: dace_data.Data = first_node.desc(sdfg)
        second_node: dace_nodes.AccessNode = self.second_node
        second_desc: dace_data.Data = second_node.desc(sdfg)
        third_node: dace_nodes.AccessNode = self.third_node
        third_desc: dace_data.Data = third_node.desc(sdfg)
        # fourth_node: dace_nodes.AccessNode = self.fourth_node
        # fourth_desc: dace_data.Data = fourth_node.desc(sdfg)

        # scope = graph.scope_dict()

        # second_node_in_edges = graph.in_edges(second_node)
        # second_node_out_edges = graph.out_edges(second_node)

        first_node_shape = first_desc.shape
        second_node_shape = second_desc.shape
        second_node_offset = tuple(0 for _ in range(len(second_node_shape)))
        third_node_shape = third_desc.shape
        third_node_offset = tuple(0 for _ in range(len(third_node_shape)))

        if second_node_shape != first_node_shape:
            second_node_offset = tuple(f - s for f, s in zip(first_node_shape, second_node_shape))
        if third_node_shape != first_node_shape:
            third_node_offset = tuple(f - s for f, s in zip(first_node_shape, third_node_shape))

        for edge in graph.edges():
            if edge.data.data == second_node.data:
                edge.data.data = first_node.data
                if edge.data.dst_subset != tuple([0]):
                    for i, offset in enumerate(second_node_offset):
                        new_subset = []
                        if edge.data.dst_subset is not None:
                            for j in range(len(edge.data.dst_subset[i]) - 1):
                                new_subset.append(edge.data.dst_subset[i][j] + offset)
                            new_subset.append(edge.data.dst_subset[i][-1])
                            edge.data.dst_subset[i] = tuple(new_subset)
                        else:
                            for j in range(len(edge.data.src_subset[i]) - 1):
                                new_subset.append(edge.data.src_subset[i][j] + offset)
                            new_subset.append(edge.data.src_subset[i][-1])
                            edge.data.src_subset[i] = tuple(new_subset)
            if edge.data.data == third_node.data:
                edge.data.data = first_node.data
                if edge.data.dst_subset != tuple([0]):
                    for i, offset in enumerate(third_node_offset):
                        new_subset = []
                        if edge.data.dst_subset is not None:
                            for j in range(len(edge.data.dst_subset[i]) - 1):
                                new_subset.append(edge.data.dst_subset[i][j] + offset)
                            new_subset.append(edge.data.dst_subset[i][-1])
                            edge.data.dst_subset[i] = tuple(new_subset)
                        else:
                            for j in range(len(edge.data.src_subset[i]) - 1):
                                new_subset.append(edge.data.src_subset[i][j] + offset)
                            new_subset.append(edge.data.src_subset[i][-1])
                            edge.data.src_subset[i] = tuple(new_subset)

        second_node.data = first_node.data
        third_node.data = first_node.data
