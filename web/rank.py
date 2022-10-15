import networkx as nx
import igraph as ig
from web import models
import matplotlib.pyplot as plt


def plot(g):
    nx.draw(g)
    plt.show()


def iplot(g):
    ig.plot(g)
    plt.show()


def __link_to_edge(l):
    return (
        l["from_resource_id"],
        l["to_resource_id"],
        {"anchor_text": l["anchor_text"]},
    )


def links_to_graph():
    links = models.Link.objects.all().values(
        "from_resource_id", "to_resource_id", "anchor_text"
    )

    g = nx.DiGraph()

    edges = (__link_to_edge(l) for l in links.iterator(chunk_size=2000))

    g.add_edges_from(edges)

    return g


def links_to_igraph():
    links = models.Link.objects.all().values_list(
        "from_resource_id",
        "to_resource_id",
    )

    g = ig.Graph(directed=True, edges=list(links))

    return g


def pagerank(g):
    return nx.pagerank_scipy(g)
