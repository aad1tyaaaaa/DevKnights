from app.graph.builder import build_dependency_graph
from app.parsers.lockfile import parse_lockfile


def test_graph_marks_direct_packages_and_builds_transitive_edges():
    parsed = parse_lockfile(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"parent": "1.0.0"}},
                "node_modules/parent": {"version": "1.0.0", "dependencies": {"child": "^2.0.0"}},
                "node_modules/child": {"version": "2.2.0"},
            },
        }
    )

    graph = build_dependency_graph(parsed)

    assert [(node.id, node.direct) for node in graph.nodes] == [
        ("child@2.2.0", False),
        ("parent@1.0.0", True),
    ]
    assert [(edge.source, edge.target, edge.dependency_type) for edge in graph.edges] == [
        ("parent@1.0.0", "child@2.2.0", "prod")
    ]


def test_graph_resolves_nearest_nested_version_and_preserves_both_versions():
    parsed = parse_lockfile(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"a": "1.0.0", "shared": "2.0.0"}},
                "node_modules/a": {"version": "1.0.0", "dependencies": {"shared": "1.0.0"}},
                "node_modules/a/node_modules/shared": {"version": "1.0.0"},
                "node_modules/shared": {"version": "2.0.0"},
            },
        }
    )

    graph = build_dependency_graph(parsed)

    assert {node.id for node in graph.nodes} == {"a@1.0.0", "shared@1.0.0", "shared@2.0.0"}
    assert next(node for node in graph.nodes if node.id == "shared@2.0.0").direct is True
    assert [(edge.source, edge.target) for edge in graph.edges] == [("a@1.0.0", "shared@1.0.0")]


def test_graph_resolves_exact_versions_from_pnpm_virtual_paths():
    parsed = parse_lockfile(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"parent": "1.0.0"}},
                "node_modules/.pnpm/parent@1.0.0/node_modules/parent": {
                    "name": "parent",
                    "version": "1.0.0",
                    "dependencies": {"child": "2.0.0"},
                },
                "node_modules/.pnpm/child@2.0.0/node_modules/child": {
                    "name": "child",
                    "version": "2.0.0",
                },
            },
        }
    )

    graph = build_dependency_graph(parsed)

    assert [(node.id, node.direct) for node in graph.nodes] == [
        ("child@2.0.0", False),
        ("parent@1.0.0", True),
    ]
    assert [(edge.source, edge.target) for edge in graph.edges] == [("parent@1.0.0", "child@2.0.0")]


def test_graph_combines_paths_for_identical_package_releases():
    parsed = parse_lockfile(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"a": "1.0.0", "b": "1.0.0"}},
                "node_modules/a": {"version": "1.0.0", "dependencies": {"shared": "1.0.0"}},
                "node_modules/a/node_modules/shared": {"version": "1.0.0"},
                "node_modules/b": {"version": "1.0.0", "dependencies": {"shared": "1.0.0"}},
                "node_modules/b/node_modules/shared": {"version": "1.0.0"},
            },
        }
    )

    graph = build_dependency_graph(parsed)
    shared = next(node for node in graph.nodes if node.id == "shared@1.0.0")

    assert shared.lockfile_paths == (
        "node_modules/a/node_modules/shared",
        "node_modules/b/node_modules/shared",
    )
    assert {(edge.source, edge.target) for edge in graph.edges} == {
        ("a@1.0.0", "shared@1.0.0"),
        ("b@1.0.0", "shared@1.0.0"),
    }


def test_graph_reports_unresolved_dependencies_without_inventing_nodes():
    parsed = parse_lockfile(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"parent": "1.0.0"}},
                "node_modules/parent": {"version": "1.0.0", "dependencies": {"missing": "1.0.0"}},
            },
        }
    )

    graph = build_dependency_graph(parsed)

    assert graph.edges == ()
    assert graph.warnings == ("Could not resolve 'missing' declared by parent@1.0.0",)

def test_aliased_root_dependency_is_marked_direct():
    # "string-utils": "npm:lodash@4.17.21" installs lodash under the alias's folder.
    parsed = parse_lockfile(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"string-utils": "npm:lodash@4.17.21"}},
                "node_modules/string-utils": {"name": "lodash", "version": "4.17.21"},
            },
        }
    )

    graph = build_dependency_graph(parsed)

    assert [(node.id, node.direct) for node in graph.nodes] == [("lodash@4.17.21", True)]


def test_every_relationship_type_between_two_packages_is_kept():
    parsed = parse_lockfile(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"plugin": "1.0.0"}},
                "node_modules/plugin": {
                    "version": "1.0.0",
                    "dependencies": {"core": "^3.0.0"},
                    "peerDependencies": {"core": "^3.0.0"},
                },
                "node_modules/core": {"version": "3.1.0"},
            },
        }
    )

    graph = build_dependency_graph(parsed)

    assert [(edge.source, edge.target, edge.dependency_type) for edge in graph.edges] == [
        ("plugin@1.0.0", "core@3.1.0", "prod"),
        ("plugin@1.0.0", "core@3.1.0", "peer"),
    ]
