"""Heterogeneous entity graph, maintained incrementally across rounds."""

import networkx as nx
import numpy as np
import pandas as pd

from backend.generate.population import Population

EDGE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("payer_entity_id", "payee_entity_id", "pays"),
    ("device_id", "payer_entity_id", "used_by"),
    ("ip", "device_id", "hosts"),
    ("agent_id", "payer_entity_id", "acts_for"),
)

PAGERANK_ALPHA: float = 0.85
PAGERANK_MAX_ITER: int = 40
PAGERANK_TOLERANCE: float = 1e-6


def edge_table(events: pd.DataFrame) -> pd.DataFrame:
    """Deduplicated edges with first-seen, last-seen and weight, ready for DuckDB."""
    blocks = []
    for source, target, edge_type in EDGE_SPECS:
        if source not in events.columns or target not in events.columns:
            continue
        subset = events[[source, target, "event_ts"]].dropna()
        if subset.empty:
            continue
        grouped = subset.groupby([source, target], sort=False)["event_ts"].agg(
            ["min", "max", "size"]
        )
        grouped = grouped.reset_index()
        grouped.columns = ["src_id", "dst_id", "first_seen_ts", "last_seen_ts", "weight"]
        grouped["edge_type"] = edge_type
        blocks.append(grouped)
    if not blocks:
        return pd.DataFrame(
            columns=["src_id", "dst_id", "edge_type", "first_seen_ts", "last_seen_ts", "weight"]
        )
    combined = pd.concat(blocks, ignore_index=True)
    return combined[["src_id", "dst_id", "edge_type", "first_seen_ts", "last_seen_ts", "weight"]]


def build_entity_graph(entities: pd.DataFrame, events: pd.DataFrame) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    if not entities.empty:
        graph.add_nodes_from(entities["entity_id"].tolist())
    edges = edge_table(events)
    for row in edges.itertuples(index=False):
        graph.add_edge(row.src_id, row.dst_id, edge_type=row.edge_type, weight=int(row.weight))
    return graph


def extend_graph(graph: nx.MultiDiGraph, events: pd.DataFrame) -> nx.MultiDiGraph:
    """Incremental maintenance: a round's campaign edges are folded into the live graph."""
    for row in edge_table(events).itertuples(index=False):
        graph.add_edge(row.src_id, row.dst_id, edge_type=row.edge_type, weight=int(row.weight))
    return graph


def graph_metrics(graph: nx.MultiDiGraph) -> tuple[pd.Series, pd.Series]:
    """PageRank and weakly-connected component size per entity."""
    if graph.number_of_nodes() == 0:
        return pd.Series(dtype="float64"), pd.Series(dtype="float64")
    simple = nx.DiGraph()
    simple.add_nodes_from(graph.nodes())
    for source, target, data in graph.edges(data=True):
        weight = float(data.get("weight", 1))
        if simple.has_edge(source, target):
            simple[source][target]["weight"] += weight
        else:
            simple.add_edge(source, target, weight=weight)
    ranks = nx.pagerank(
        simple,
        alpha=PAGERANK_ALPHA,
        max_iter=PAGERANK_MAX_ITER,
        tol=PAGERANK_TOLERANCE,
        weight="weight",
    )
    sizes: dict[str, int] = {}
    for component in nx.weakly_connected_components(simple):
        size = len(component)
        for node in component:
            sizes[node] = size
    return pd.Series(ranks, dtype="float64"), pd.Series(sizes, dtype="float64")


def motif_counts(graph: nx.Graph | nx.MultiDiGraph) -> tuple[float, float]:
    """Triangle count and 2-star count on the undirected projection."""
    undirected = nx.Graph()
    undirected.add_nodes_from(graph.nodes())
    undirected.add_edges_from((source, target) for source, target in graph.edges())
    triangles = sum(nx.triangles(undirected).values()) / 3.0
    degrees = np.array([d for _, d in undirected.degree()], dtype="float64")
    two_stars = float((degrees * (degrees - 1.0) / 2.0).sum())
    return float(triangles), two_stars


def population_graph(population: Population, events: pd.DataFrame) -> nx.MultiDiGraph:
    from backend.generate.population import entities_frame

    return build_entity_graph(entities_frame(population), events)
