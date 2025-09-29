# GT4Py - GridTools Framework
#
# Copyright (c) 2014-2024, ETH Zurich
# All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import copy
from typing import Any, Optional

import dace
from dace import (
    data as dace_data,
    properties as dace_properties,
    transformation as dace_transformation,
)
from dace.sdfg import nodes as dace_nodes
from dace.transformation import helpers

from gt4py.next.program_processors.runners.dace import transformations as gtx_transformations
from gt4py.next.program_processors.runners.dace.transformations import (
    map_fusion_utils as gtx_mfutils,
    splitting_tools as gtx_dace_split,
)

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
        return [dace.sdfg.utils.node_path_graph(cls.first_node, cls.second_node, cls.third_node, cls.fourth_node)]

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

        scope = graph.scope_dict()

        if first_desc.transient is False and second_desc.transient is True and third_desc.transient is True and fourth_desc.transient is False:
            print("[RemoveAccessNodeCopies] {} -> {} -> {} -> {}".format(first_node.data, second_node.data, third_node.data, fourth_node.data))
        else:
            return False

        if first_node.data != fourth_node.data:
            return False

        first_edge = None
        first_node_out_edges = graph.out_edges(first_node)

        second_node_in_edges = graph.in_edges(second_node)

        # Find the edge in first_node_out_edges that is also present in second_node_in_edges
        for edge in first_node_out_edges:
            if edge in second_node_in_edges:
                first_edge = edge
                break
              
        fourth_node_in_edges = graph.in_edges(fourth_node)

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
        fourth_node: dace_nodes.AccessNode = self.fourth_node
        fourth_desc: dace_data.Data = fourth_node.desc(sdfg)

        scope = graph.scope_dict()

        second_node_in_edges = graph.in_edges(second_node)
        second_node_out_edges = graph.out_edges(second_node)

        for edge in graph.edges():
            if edge.data.data == second_node.data:
                edge.data.data = first_node.data
            if edge.data.data == third_node.data:
                edge.data.data = first_node.data

        second_node.data = first_node.data
        third_node.data = first_node.data

        # sdfg.save('after_remove_access_node_copies.sdfg')

        return

        # import pdb; pdb.set_trace()
        new_first_node = copy.deepcopy(first_node)
        graph.add_node(new_first_node)

        # Redirect all edges from second_node to new_first_node
        for edge in list(graph.in_edges(second_node)):
            # if edge.src != first_node:
                # new_data = copy.deepcopy(edge.data)
                # new_data.data = new_first_node.label
            new_edge = helpers.redirect_edge(
                graph, edge, new_dst=new_first_node, new_dst_conn=new_first_node.label #, new_data=edge.data.data
            )

        for edge in list(graph.out_edges(second_node)):
            # if edge.dst == third_node:
            # new_data = copy.deepcopy(edge.data)
            # new_data.data = new_first_node.label
            new_edge = helpers.redirect_edge(
                graph, edge, new_src=new_first_node, new_src_conn=new_first_node.label #, new_data=new_first_node.label
            )
        sdfg.view()
        import pdb; pdb.set_trace()
        # if second_node.data in sdfg.arrays:
        #     sdfg.arrays.pop(second_node.data)

        new_first_node_2 = copy.deepcopy(first_node)
        graph.add_node(new_first_node_2)
        # Redirect all edges from third_node to new_first_node_2
        for edge in list(graph.in_edges(third_node)):
            # if edge.src == second_node:
            # new_data = copy.deepcopy(edge.data)
            # new_data.data = new_first_node_2.label
            new_edge = helpers.redirect_edge(
                graph, edge, new_dst=new_first_node_2, new_dst_conn=new_first_node_2.label, new_data=new_first_node.label
            )
                # if new_edge.data.data == second_node.data:
                #     new_edge.data.data = new_first_node_2.data
                #     new_edge.data.subset = copy.deepcopy(edge.data.subset)
                # else:
                #     new_edge.data.other_subset = copy.deepcopy(edge.data.subset)
                # graph.remove_edge(edge)
        for edge in list(graph.out_edges(third_node)):
            # if edge.dst == fourth_node:
            # new_data = copy.deepcopy(edge.data)
            # new_data.data = new_first_node_2.label
            new_edge = helpers.redirect_edge(
                graph, edge, new_src=new_first_node_2, new_src_conn=new_first_node_2.label, new_data=new_first_node.label
            )
                # if new_edge.data.data == second_node.data:
                #     new_edge.data.data = new_first_node_2.data
                #     new_edge.data.subset = copy.deepcopy(edge.data.subset)
                # else:
                #     new_edge.data.other_subset = copy.deepcopy(edge.data.subset)
                # graph.remove_edge(edge)
        sdfg.remove_data(second_node.data, validate=False)
        graph.remove_node(second_node)
        sdfg.remove_data(third_node.data, validate=False)
        # if third_node.data in sdfg.arrays:
        #     sdfg.arrays.pop(third_node.data)
        graph.remove_node(third_node)
        sdfg.view()
        import pdb; pdb.set_trace()
