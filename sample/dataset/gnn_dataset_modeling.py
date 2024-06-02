"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Create GNN dataset (in the format readable by PyG) for modeling (includes additional information like
 | train/validation/set assignment of graphs)
 |---------------------------------------------------------------------------------------------------------------------|
"""

import pandas as pd
import torch
import torch_geometric

import sample.dataset.preprocessing as pp
import sample.util.feature_names as fn
import sample.db_interaction as db

pd.options.mode.copy_on_write = True


class GNNDatasetModeling(torch_geometric.data.InMemoryDataset):
    def __init__(self, root, dataset_name):
        self.dataset_name = dataset_name
        self.include_edges = True
        super().__init__(root)
        self.load(self.processed_paths[0])

    @property
    def processed_file_names(self):
        return ['data.pt']

    def process(self):
        data_list = []

        # |------------------------------------------------------------------------------------------------------------|
        # Retrieve tables from DB
        # |------------------------------------------------------------------------------------------------------------|

        print('Retrieving tables from DB...')
        # Retrieve 'dataset' table from DB.
        # This table includes various useful columns like node features and the center mask.
        dataset = db.sql_to_df(f"""
                        SELECT *
                        FROM public.nodes
        """)
        # Add column to indicate graph center to table
        dataset['is_center'] = dataset['center_building_id'] == dataset['building_id']
        # Add column for label mask
        dataset['label_mask'] = dataset['numerical_label'] != 9
        # Delete unneeded columns
        dataset = dataset.drop(columns=['id_region', 'center_building_id', 'building_id', 'block_id', 'land_cover'])
        # Retrieve 'e' table from DB.
        # This table includes columns related to edge features.
        e = db.sql_to_df(f"""
                        SELECT graph_id, start_node_id, end_node_id, distance
                        FROM public.edges
        """)

        # | -----------------------------------------------------------------------------------------------------------|
        # Create dataframes for various stuff (like node features, center mask, auxiliary columns...)
        # | -----------------------------------------------------------------------------------------------------------|

        print('Creating dataframes...')
        # Create df for node features
        x = dataset.drop(columns=['is_center'])
        x = pp.preprocess_nodes(x, False, self.dataset_name)
        columns = fn.feature_groups_names['Auxiliary cols for graphs'] \
                  + fn.feature_groups_names['Building-level features'] \
                  + fn.feature_groups_names['Block-level features'] \
                  + fn.feature_groups_names['UA coverage'] \
                  + fn.feature_groups_names['Land cover indicators'] \
                  + fn.feature_groups_names['Urbanization indicators'] \
                  + fn.feature_groups_names['Country indicators']
        x = x[columns]
        # Create df for center mask
        columns = fn.feature_groups_names['Auxiliary cols for graphs'] + ['is_center']
        center_mask = dataset[columns]
        # Create df for auxiliary columns
        columns = fn.feature_groups_names['Auxiliary cols for graphs']
        id_cols = dataset[columns]
        # Pre-process edge features
        e = pp.preprocess_edges(e)
        # Create residual edges as in the DB we only have edges in one direction, but we want undirected graph
        residual = pd.DataFrame({'graph_id': e['graph_id'],
                                 'start_node_id': e['end_node_id'],
                                 'end_node_id': e['start_node_id'],
                                 'distance': e['distance'],
                                 'distance_std': e['distance_std'],
                                 'distance_rob': e['distance_rob']})
        e = e._append(residual, ignore_index=True)
        # Create df for edge index
        columns = ['graph_id', 'start_node_id', 'end_node_id']
        edge_index = e[columns]
        # Create df for edge features
        columns = ['graph_id', 'distance']
        distance = e[columns]
        columns = ['graph_id', 'distance_std']
        distance_std = e[columns]
        columns = ['graph_id', 'distance_rob']
        distance_rob = e[columns]
        # Create df for label
        columns = fn.feature_groups_names['Auxiliary cols for graphs'] + ['numerical_label']
        y = dataset[columns]
        # Create df for label mask
        columns = fn.feature_groups_names['Auxiliary cols for graphs'] + ['label_mask']
        label_mask = dataset[columns]
        # Create df for graph ID array
        columns = fn.feature_groups_names['Auxiliary cols for graphs'] + ['graph_id_arr']
        graph_id_arr = dataset[columns]

        # | -----------------------------------------------------------------------------------------------------------|
        # Convert dataframes to list of tensors (one tensor for each subgraph)
        # | -----------------------------------------------------------------------------------------------------------|

        print('Converting dataframes to lists of tensors...')
        # x to list of tensors
        x_ts_list = [torch.tensor(group.values[:, 2:], dtype=torch.float) for graph_id, group in x.groupby('graph_id')]
        # Center mask to list of tensors
        center_mask_ts_list = [torch.tensor(group['is_center'].values, dtype=torch.bool) for graph_id, group in
                               center_mask.groupby('graph_id')]
        # Edge indices to list of tensors
        edge_index_ts_list = [torch.tensor(group.values[:, 1:], dtype=torch.long) for graph_id, group in
                              edge_index.groupby('graph_id')]
        # Edge features to list of tensors
        distance_ts_list = [torch.tensor(group.values[:, 1:], dtype=torch.float) for graph_id, group in
                              distance.groupby('graph_id')]
        distance_std_ts_list = [torch.tensor(group.values[:, 1:], dtype=torch.float) for graph_id, group in
                            distance_std.groupby('graph_id')]
        distance_rob_ts_list = [torch.tensor(group.values[:, 1:], dtype=torch.float) for graph_id, group in
                            distance_rob.groupby('graph_id')]
        # Auxiliary columns to list of tensors
        id_cols_ts_list = [torch.tensor(group.values, dtype=torch.long) for graph_id, group in
                            id_cols.groupby('graph_id')]
        # Label to list of tensors
        y_ts_list = [torch.tensor(group['numerical_label'].values, dtype=torch.long) for graph_id, group in
                              y.groupby('graph_id')]
        # Label mask to list of tensors
        label_mask_ts_list = [torch.tensor(group['label_mask'].values, dtype=torch.bool) for graph_id, group in
                              label_mask.groupby('graph_id')]
        # Graph IDs to list of lists
        graph_id_arr_ts_list = [group['graph_id_arr'].to_list() for graph_id, group in
                              graph_id_arr.groupby('graph_id')]

        # | -----------------------------------------------------------------------------------------------------------|
        # Convert list of tensors to PyG dataset
        # | -----------------------------------------------------------------------------------------------------------|

        print('Converting lists of tensors to PyG dataset...')
        for i in range(len(id_cols_ts_list)):
            if i % 1000 == 0:
                print(i)
            data = torch_geometric.data.Data(x=x_ts_list[i], edge_index=edge_index_ts_list[i].t().contiguous(),
                                             center_mask=center_mask_ts_list[i], distance=distance_ts_list[i],
                                             distance_std=distance_std_ts_list[i], distance_rob=distance_rob_ts_list[i],
                                             y=y_ts_list[i], label_mask=label_mask_ts_list[i],
                                             graph_id_arr=graph_id_arr_ts_list[i], id_cols=id_cols_ts_list[i])
            if not data.validate(raise_on_error=False):
                continue
            if data.has_self_loops():
                continue
            data_list.append(data)
        self.save(data_list, self.processed_paths[0])


if __name__ == '__main__':
    ds = GNNDatasetModeling('./dataset', 'dataset')
    print(len(ds))