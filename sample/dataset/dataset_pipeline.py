import sample.dataset.create_dataset as cd
import sample.dataset.gnn_dataset as gnn

if __name__ == '__main__':
    # Localized subgraphs generation method
    type = 'circ'
    # Fraction of labeled buildings that are used as center nodes for subgraphs
    subsample_fraction = 0.004
    # Number of hops in a subgraph (n-hop method)
    hops = 4
    # Minimum number of buildings in a subgraph (circ method)
    buildings_in_graph = 20
    # Rectangular spatial extract in Europe
    x_min, x_max, y_min, y_max = 11.4951, 11.6949, 48.1166, 48.2763  # Extract in Northern Munich
    cd.create_dataset(type, subsample_fraction, hops, buildings_in_graph, x_min, x_max, y_min, y_max)
    gnn.GNNDataset(f'./{type}/', type)
