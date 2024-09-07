"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Training and evaluation for GNN classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import torch.nn as nn
import torch_geometric.loader as loader
import torch_geometric.transforms as T

import sample.models.gat as gat
import sample.models.transformer as trans
import sample.models.gcn as gcn
import sample.models.graphsage as sage
import sample.training.train as tr
import sample.training.eval as ev


def train_and_eval_gnn(data, config, model_name, model_type):
    """
    Training and evaluation for GNN classifier
    :param data: graph data object
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_type: which kind of classifier? (ex. GAT)
    :return: model predictions
    """
    # Create undirected graph
    to_undirected = T.ToUndirected()
    data = to_undirected(data)
    if model_type == 'sage' and config.aggr == 'lstm':
        data = data.sort(sort_by_row=False)
    # Load data
    if config.subgraph_type == 'circ':
        # Maximum number of hops is 20 -> make sure that subgraphs can contain at most 20 hops
        num_neighbors = [-1, -1, -1, -1, -1,
                         -1, -1, -1, -1, -1,
                         -1, -1, -1, -1, -1,
                         -1, -1, -1, -1, -1]
    elif config.subgraph_type == 'n_hop':
        if config.hops == 2:
            num_neighbors = [-1, -1]
        elif config.hops == 4:
            num_neighbors = [3, 3, 2, 2]
    dataloader_train = loader.NeighborLoader(data,
                                             input_nodes=data.train_mask.nonzero(as_tuple=True)[0],
                                             num_neighbors=num_neighbors,
                                             batch_size=config.batch_size,
                                             replace=False,
                                             shuffle=True,
                                             subgraph_type='induced')
    dataloader_val = loader.NeighborLoader(data,
                                           input_nodes=data.val_mask.nonzero(as_tuple=True)[0],
                                           num_neighbors=num_neighbors,
                                           batch_size=config.batch_size,
                                           replace=False,
                                           shuffle=False,
                                           subgraph_type='induced')
    dataloader_test = loader.NeighborLoader(data,
                                            input_nodes=data.test_mask.nonzero(as_tuple=True)[0],
                                            num_neighbors=num_neighbors,
                                            batch_size=config.batch_size,
                                            replace=False,
                                            shuffle=False,
                                            subgraph_type='induced')
    # Determine device. Train on GPU if available
    device = (
            'cuda'
            if torch.cuda.is_available()
            else 'mps'
            if torch.backends.mps.is_available()
            else 'cpu'
    )
    print(f'Device: {device}')
    # Set loss function
    loss_fn = nn.NLLLoss()
    input_layer_size = 69
    if model_type == 'gat':
        model = gat.GAT(input_layer_size, config, 9).to(device)
    elif model_type == 'transformer':
        model = trans.GraphTransformer(input_layer_size, config, 9).to(device)
    elif model_type == 'gcn':
        model = gcn.GCN(input_layer_size, config, 9).to(device)
    elif model_type == 'sage':
        model = sage.GraphSAGE(input_layer_size, config, 9).to(device)
    print(model)
    tr.train_and_log(model, device, dataloader_train, dataloader_val,
                  loss_fn, config, model_name, '', model_type)
    y_predict, _ = ev.evaluate_and_log(dataloader_test, model, device, loss_fn, True, None, model_type, 'test',
                                       config)
    return y_predict
