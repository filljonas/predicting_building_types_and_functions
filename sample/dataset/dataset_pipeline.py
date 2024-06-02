"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Pipeline for creating dataset. Consists of the following steps:
 | 1) Create dataset in the form of database tables
 | 2) Create GNN dataset that is usable with PyG
 | `min_nodes_per_graph`: minimum nodes that have to occur in each subgraph
 | `subsample_fraction`: which fraction of all labeled nodes to include into the dataset (take random subset)
 |---------------------------------------------------------------------------------------------------------------------|
"""


import pathlib as pl
import time

import sample.dataset.create_database_table as cd
import sample.dataset.gnn_dataset_modeling as ds

if __name__ == '__main__':
    # Default extract: northern part of Landkreis Muenchen
    x_min = 11.5300
    x_max = 11.7310
    y_min = 48.1640
    y_max = 48.2709
    min_nodes_per_graph = 20
    subsample_fraction = 0.01
    dataset_name = f'pyg_ds'
    # Create database tables
    print(f'---------------------------------------Create PostgreSQL tables-------------------------------------------')
    cd.create_database_table(min_nodes_per_graph, subsample_fraction, x_min, x_max, y_min, y_max)
    # Create GNN dataset
    print(f'---------------------------------------Create PyG dataset-------------------------------------------------')
    directory_path = pl.Path(f'./{dataset_name}')
    directory_path.mkdir(parents=True, exist_ok=True)
    ds.GNNDatasetModeling(str(directory_path), dataset_name)
    end = time.time()