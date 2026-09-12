import unittest

from nixoscope.module_graph import UNKNOWN_SOURCE, ModuleGraph

_SOURCE: str = "abc123"
_STORE_PATH: str = f"/nix/store/{_SOURCE}-source"


def make_node(filename: str, *imports: dict, option: str | None = None, disabled: bool = False, key: str = "") -> dict:
    file = f"{_STORE_PATH}/{filename}" if option is None else f"{_STORE_PATH}/{filename}, via option {option}"
    return {
        "disabled": disabled,
        "file": file,
        "key": key,
        "imports": list(imports),
    }


def make_unknown_node(unique_key: str, *imports: dict, option: str | None = None) -> dict:
    file = "<unknown-file>" if option is None else f"<unknown-file>, via option {option}"
    return {
        "disabled": False,
        "file": file,
        "key": unique_key,
        "imports": list(imports),
    }


_SIMPLE_GRAPH = make_node(
    "flake.nix",
    make_node("foo.nix"),
    make_node("bar.nix"),
    make_node("baz.nix"),
)

_NESTED_GRAPH = make_node(
    "flake.nix",
    make_node(
        "level1.nix",
        make_node(
            "level2.nix",
            make_node("level3.nix"),
        ),
    ),
)

_OPTION_GRAPH = make_node(
    "flake.nix",
    make_node(
        "services.nix",
        make_node("nginx.nix", option="services.nginx"),
        option="services",
    ),
    make_node("networking.nix", option="networking"),
)


class TestSimpleGraph(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = ModuleGraph([_SIMPLE_GRAPH], option_filter=None)

    def test_graph_has_four_nodes(self) -> None:
        self.assertEqual(len(self.graph.modules), 4)

    def test_graph_contains_flake_nix(self) -> None:
        self.assertIn((_SOURCE, "flake.nix", ""), self.graph.modules)

    def test_graph_contains_leaves(self) -> None:
        for leaf in ("foo.nix", "bar.nix", "baz.nix"):
            self.assertIn((_SOURCE, leaf, ""), self.graph.modules)

    def test_flake_nix_imports_all_leaves(self) -> None:
        flake_node = self.graph.modules[(_SOURCE, "flake.nix", "")]
        imported_modules = {edge.module for edge in flake_node.imports}
        self.assertEqual(imported_modules, {"foo.nix", "bar.nix", "baz.nix"})

    def test_leaves_have_no_imports(self) -> None:
        for leaf in ("foo.nix", "bar.nix", "baz.nix"):
            node = self.graph.modules[(_SOURCE, leaf, "")]
            self.assertEqual(node.imports, [])


class TestNestedGraph(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = ModuleGraph([_NESTED_GRAPH], option_filter=None)

    def test_graph_has_four_nodes(self) -> None:
        self.assertEqual(len(self.graph.modules), 4)

    def test_all_nodes_present(self) -> None:
        for module in ("flake.nix", "level1.nix", "level2.nix", "level3.nix"):
            self.assertIn((_SOURCE, module, ""), self.graph.modules)

    def test_flake_imports_level1(self) -> None:
        flake_node = self.graph.modules[(_SOURCE, "flake.nix", "")]
        imported = {edge.module for edge in flake_node.imports}
        self.assertEqual(imported, {"level1.nix"})

    def test_level1_imports_level2(self) -> None:
        node = self.graph.modules[(_SOURCE, "level1.nix", "")]
        imported = {edge.module for edge in node.imports}
        self.assertEqual(imported, {"level2.nix"})

    def test_level2_imports_level3(self) -> None:
        node = self.graph.modules[(_SOURCE, "level2.nix", "")]
        imported = {edge.module for edge in node.imports}
        self.assertEqual(imported, {"level3.nix"})

    def test_level3_has_no_imports(self) -> None:
        node = self.graph.modules[(_SOURCE, "level3.nix", "")]
        self.assertEqual(node.imports, [])


class TestOptionFilter(unittest.TestCase):
    def test_no_filter_includes_all_nodes(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter=None)
        self.assertEqual(len(graph.modules), 4)
        for module in ("flake.nix", "services.nix", "nginx.nix", "networking.nix"):
            self.assertIn((_SOURCE, module, ""), graph.modules)

    def test_filter_includes_matching_excludes_non_matching(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="services")
        for module in ("flake.nix", "services.nix", "nginx.nix"):
            self.assertIn((_SOURCE, module, ""), graph.modules)
        self.assertNotIn((_SOURCE, "networking.nix", ""), graph.modules)

    def test_filter_excludes_unrelated_option_tree(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="networking")
        self.assertIn((_SOURCE, "flake.nix", ""), graph.modules)
        self.assertIn((_SOURCE, "networking.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "services.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "nginx.nix", ""), graph.modules)

    def test_filter_no_match_only_root_node_remains(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="nonexistent")
        self.assertEqual(len(graph.modules), 1)
        self.assertIn((_SOURCE, "flake.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "services.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "nginx.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "networking.nix", ""), graph.modules)

    def test_filter_matched_nodes_linked_to_root(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="networking")
        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        imported = {edge.module for edge in flake_node.imports}
        self.assertIn("networking.nix", imported)
        self.assertNotIn("services.nix", imported)

    def test_nested_filter_reparents_children_to_root(self) -> None:
        # When a parent is filtered out, its matching children should link directly to root
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="services.nginx")
        self.assertIn((_SOURCE, "nginx.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "services.nix", ""), graph.modules)
        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        imported = {edge.module for edge in flake_node.imports}
        self.assertIn("nginx.nix", imported)
        self.assertNotIn("services.nix", imported)


def _unknown_keys(graph: ModuleGraph) -> list[tuple[str, str, str]]:
    return [key for key in graph.modules if key[0] == UNKNOWN_SOURCE]


class TestUnknownModuleCollapsing(unittest.TestCase):
    def test_trailing_chain_collapses_into_one_node(self) -> None:
        # Known -> Unknown(optA) -> Unknown(optA)  =>  Known -> [2 Unknown]
        graph = ModuleGraph(
            [
                make_node(
                    "flake.nix",
                    make_unknown_node("u1", make_unknown_node("u2", option="optA"), option="optA"),
                )
            ],
            option_filter=None,
        )
        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 1)
        group_node = graph.modules[unknown_keys[0]]
        self.assertEqual(group_node.collapsed_count, 2)

        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        self.assertEqual(len(flake_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in flake_node.imports}, {unknown_keys[0]})

    def test_sandwiched_chain_collapses_and_reconnects_to_known(self) -> None:
        # Known -> Unknown(optA) -> Unknown(optA) -> Known2  =>  Known -> [2 Unknown] -> Known2
        graph = ModuleGraph(
            [
                make_node(
                    "flake.nix",
                    make_unknown_node(
                        "u1",
                        make_unknown_node("u2", make_node("known2.nix"), option="optA"),
                        option="optA",
                    ),
                )
            ],
            option_filter=None,
        )
        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 1)
        group_node = graph.modules[unknown_keys[0]]
        self.assertEqual(group_node.collapsed_count, 2)
        self.assertEqual(len(group_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in group_node.imports}, {(_SOURCE, "known2.nix", "")})

        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        self.assertEqual(len(flake_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in flake_node.imports}, {unknown_keys[0]})

    def test_option_change_starts_a_new_group(self) -> None:
        # Known -> Unknown(optA) -> Unknown(optB)  =>  Known -> groupA -> groupB (not merged)
        graph = ModuleGraph(
            [
                make_node(
                    "flake.nix",
                    make_unknown_node("u1", make_unknown_node("u2", option="optB"), option="optA"),
                )
            ],
            option_filter=None,
        )
        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 2)
        for key in unknown_keys:
            self.assertEqual(graph.modules[key].collapsed_count, 1)

    def test_independent_branches_with_same_option_and_destination_merge_globally(self) -> None:
        # Two unrelated leaves with the same option and the same (empty) destination
        # set carry no distinguishing information, so they merge even though they
        # aren't a chain and don't share a parent.
        graph = ModuleGraph(
            [
                make_node(
                    "flake.nix",
                    make_unknown_node("u1", option="optA"),
                    make_unknown_node("u2", option="optA"),
                )
            ],
            option_filter=None,
        )
        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 1)
        self.assertEqual(graph.modules[unknown_keys[0]].collapsed_count, 2)

        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        self.assertEqual(len(flake_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in flake_node.imports}, {unknown_keys[0]})

    def test_independent_branches_with_same_option_but_different_destinations_stay_separate(self) -> None:
        graph = ModuleGraph(
            [
                make_node(
                    "flake.nix",
                    make_unknown_node("u1", make_node("known1.nix"), option="optA"),
                    make_unknown_node("u2", make_node("known2.nix"), option="optA"),
                )
            ],
            option_filter=None,
        )
        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 2)
        for key in unknown_keys:
            self.assertEqual(graph.modules[key].collapsed_count, 1)


class TestRedundantUnknownNodeMerging(unittest.TestCase):
    def test_siblings_with_same_option_and_destination_merge(self) -> None:
        graph = ModuleGraph(
            [
                make_node(
                    "flake.nix",
                    make_unknown_node("u1", make_node("known.nix"), option="optA"),
                    make_unknown_node("u2", make_node("known.nix"), option="optA"),
                )
            ],
            option_filter=None,
        )
        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 1)
        group_node = graph.modules[unknown_keys[0]]
        self.assertEqual(group_node.collapsed_count, 2)
        self.assertEqual(len(group_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in group_node.imports}, {(_SOURCE, "known.nix", "")})

        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        self.assertEqual(len(flake_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in flake_node.imports}, {unknown_keys[0]})

    def test_self_referential_siblings_collapse_to_one_edge(self) -> None:
        # Mirrors the real recursive-submodule case: a known node K has several
        # same-option unknown children that each import K back. They merge into
        # one node with a single edge back to K -- the cycle is reduced to one
        # clean edge, not eliminated (K genuinely is self-referential).
        known_raw = make_node(
            "known.nix",
            make_unknown_node("u1", make_node("known.nix"), option="optA"),
            make_unknown_node("u2", make_node("known.nix"), option="optA"),
            make_unknown_node("u3", make_node("known.nix"), option="optA"),
        )
        graph = ModuleGraph([make_node("flake.nix", known_raw)], option_filter=None)

        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 1)
        group_node = graph.modules[unknown_keys[0]]
        self.assertEqual(group_node.collapsed_count, 3)
        self.assertEqual(len(group_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in group_node.imports}, {(_SOURCE, "known.nix", "")})

        known_node = graph.modules[(_SOURCE, "known.nix", "")]
        self.assertEqual(len(known_node.imports), 1)
        self.assertEqual({(e.source, e.module, e.key) for e in known_node.imports}, {unknown_keys[0]})

    def test_merge_requires_two_rounds_to_reach_fixed_point(self) -> None:
        # U2a/U2b only become equivalent once merged; U1a/U1b only become
        # equivalent to *each other* once that first merge redirects both of
        # them to the same U2 survivor. A single non-iterating pass would
        # leave U1a and U1b unmerged.
        u2a = make_unknown_node("u2a", make_node("known.nix"), option="optB")
        u2b = make_unknown_node("u2b", make_node("known.nix"), option="optB")
        u1a = make_unknown_node("u1a", u2a, option="optA")
        u1b = make_unknown_node("u1b", u2b, option="optA")
        graph = ModuleGraph(
            [make_node("flake.nix", make_node("p1.nix", u1a), make_node("p2.nix", u1b))],
            option_filter=None,
        )

        unknown_keys = _unknown_keys(graph)
        self.assertEqual(len(unknown_keys), 2)
        for key in unknown_keys:
            self.assertEqual(graph.modules[key].collapsed_count, 2)

        p1_node = graph.modules[(_SOURCE, "p1.nix", "")]
        p2_node = graph.modules[(_SOURCE, "p2.nix", "")]
        self.assertEqual(len(p1_node.imports), 1)
        self.assertEqual(len(p2_node.imports), 1)
        # p1 and p2 must now point at the *same* merged U1 survivor.
        self.assertEqual(
            (p1_node.imports[0].source, p1_node.imports[0].module, p1_node.imports[0].key),
            (p2_node.imports[0].source, p2_node.imports[0].module, p2_node.imports[0].key),
        )


if __name__ == "__main__":
    unittest.main()
