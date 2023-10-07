import igraph as ig
import matplotlib.pyplot as plt
import networkx as nx

from web import models


def plot(g):
    nx.draw(g)
    plt.show()


def iplot(g):
    ig.plot(g)
    plt.show()


def __link_to_edge(link):
    return (
        link["from_resource_id"],
        link["to_resource_id"],
        {"anchor_text": link["anchor_text"]},
    )


def links_to_graph():
    links = models.Link.objects.all().values(
        "from_resource_id", "to_resource_id", "anchor_text",
    )

    g = nx.DiGraph()

    edges = (__link_to_edge(link) for link in links.iterator(chunk_size=2000))

    g.add_edges_from(edges)

    return g


def links_to_igraph():
    links = models.Link.objects.all().values_list(
        "from_resource_id",
        "to_resource_id",
    )

    return ig.Graph(directed=True, edges=list(links))



def pagerank(g):
    return nx.pagerank_scipy(g)
