"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Training and evaluation for GNN classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import torch.nn as nn
import torch_geometric.loader as loader

import sample.models.gat as gat
import sample.models.transformer as trans
import sample.models.gcn as gcn
import sample.training.train as tr
import sample.training.eval as ev


def train_and_eval_gnn(dataset_train, dataset_val, config, model_name, model_type):
    """
    Training and evaluation for GNN classifier
    :param dataset_train: dataset for training
    :param dataset_val: dataset for validation
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_type: which kind of classifier? (ex. GAT)
    :return: model predictions
    """
    # Load data
    dataloader_train = loader.DataLoader(dataset_train, batch_size=config.batch_size, shuffle=True)
    dataloader_val = loader.DataLoader(dataset_val, batch_size=config.batch_size, shuffle=False)
    # Determine device. Train on GPU if available
    device = (
            'cuda'
            if torch.cuda.is_available()
            else 'mps'
            if torch.backends.mps.is_available()
            else 'cpu'
    )
    # Set loss function
    loss_fn = nn.NLLLoss()
    if model_type == 'gat':
        model = gat.GAT(69, config, 9).to(device)
    elif model_type == 'transformer':
        model = trans.GraphTransformer(69, config, 9).to(device)
    elif model_type == 'gcn':
        model = gcn.GCN(69, config, 9).to(device)
    tr.train(model, device, dataloader_train, dataloader_val,
                  loss_fn, config, model_name, model_type)
    y_predict, _ = ev.evaluate(dataloader_val, model, device, loss_fn, True, None, model_type)
    return y_predict
