"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Create GNN dataset (in the format readable by PyG) for training
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import pandas as pd
import torch_geometric
import time
import datetime as dt

import sample.db_interaction as db
import sample.dataset.preprocessing as pp
import sample.util.feature_names as fn
import sample.dataset.sql_queries.sql_dataset as sqlds

pd.options.mode.copy_on_write = True


class GNNDataset(torch_geometric.data.InMemoryDataset):
    def __init__(self, root, type):
        self.include_edges = True
        self.type = type
        super().__init__(root)
        self.load(self.processed_paths[0])

    @property
    def processed_file_names(self):
        return ['data.pt']

    def process(self):
        # Retrieve tables from DB
        print('Retrieving tables from DB...')
        if self.type == 'n_hop':
            db.execute_statement(sqlds.node_features_sequential_id_n_hop)
        elif self.type == 'circ':
            db.execute_statement(sqlds.node_features_sequential_id_circ)
        node_features_with_labels = db.sql_to_df(f'SELECT * FROM public.node_features_sequential_id')
        # Add column for label mask
        node_features_with_labels['label_mask'] = node_features_with_labels['numerical_label'] != 9
        if self.type == 'n_hop':
            db.execute_statement(sqlds.edges_sequential_id_n_hop)
        elif self.type == 'circ':
            db.execute_statement(sqlds.edges_sequential_id_circ)
        edges = db.sql_to_df(f'SELECT * FROM public.edges_sequential_id')
        db.execute_statement(sqlds.drop_tables)
        print('Creating tensors...')
        # Create tensor for node features
        x = pp.preprocess_nodes(node_features_with_labels, False, self.type)
        columns = fn.feature_groups_names['Building-level features'] \
                  + fn.feature_groups_names['Block-level features'] \
                  + fn.feature_groups_names['UA coverage'] \
                  + fn.feature_groups_names['Land cover indicators'] \
                  + fn.feature_groups_names['Urbanization indicators'] \
                  + fn.feature_groups_names['Country indicators']
        x = torch.tensor(x[columns].values, dtype=torch.float)
        # Create tensor for center mask
        center_mask = torch.tensor(node_features_with_labels['center_mask'].values, dtype=torch.bool)
        # Create tensor for ID column
        id = torch.tensor(node_features_with_labels['new_id'].values, dtype=torch.long)
        if self.type == 'circ':
            id_orig = torch.tensor(node_features_with_labels['id_orig'].values, dtype=torch.long)
        # Create tensor for OSM ID column
        osm_id = torch.tensor(node_features_with_labels['osm_id'].values, dtype=torch.long)
        # Create list for hop
        if self.type == 'circ':
            hop = torch.tensor(node_features_with_labels['hop'].values, dtype=torch.long)
        # Create list for center ID
        if self.type == 'circ':
            center_id = torch.tensor(node_features_with_labels['center_id'].values, dtype=torch.long)
        # Create tensor for longitude (Point on Surface)
        lon = torch.tensor(node_features_with_labels['lon'].values, dtype=torch.float)
        # Create tensor for latitude (Point on Surface)
        lat = torch.tensor(node_features_with_labels['lat'].values, dtype=torch.float)
        # Create tensor for label
        y = torch.tensor(node_features_with_labels['numerical_label'].values, dtype=torch.long)
        # Create tensor for label mask
        label_mask = torch.tensor((node_features_with_labels['numerical_label'] != 9).values, dtype=torch.bool)
        edges = pp.preprocess_edges(edges)
        # Create tensor for edge index
        edge_index = torch.tensor(edges[['start_id', 'end_id']].values, dtype=torch.long).t().contiguous()
        # Create tensors for edge features
        distance = torch.tensor(edges['distance'].values, dtype=torch.float).unsqueeze(1)
        distance_std = torch.tensor(edges['distance_std'].values, dtype=torch.float).unsqueeze(1)
        print('Creating PyG dataset...')
        if self.type == 'n_hop':
            data = torch_geometric.data.Data(x=x, edge_index=edge_index,
                                             center_mask=center_mask, distance=distance,
                                             distance_std=distance_std, y=y, label_mask=label_mask, id=id, osm_id=osm_id,
                                             lon=lon, lat=lat)
        elif self.type == 'circ':
            data = torch_geometric.data.Data(x=x, edge_index=edge_index,
                                             center_mask=center_mask, distance=distance,
                                             distance_std=distance_std, y=y, label_mask=label_mask, id=id, id_orig=id_orig,
                                             osm_id=osm_id, hop=hop, center_id=center_id, lon=lon, lat=lat)
        data_list = [data]
        self.save(data_list, self.processed_paths[0])