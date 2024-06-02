"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Fetch trained classifier from file
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch

from joblib import load

import sample.models.fcnn as fcnn
import sample.models.gcn as gcn
import sample.models.gat as gat
import sample.models.transformer as transformer


def fetch_model(config, model_name, model_type, device):
    """
    Fetch trained classifier from file
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_type: which kind of classifier? (ex. GAT)
    :param device: CPU or GPU
    :return: model loaded in PyTorch/ScikitLearn
    """
    if model_type in ['fcnn', 'gcn', 'gat', 'transformer']:
        if model_type == 'fcnn':
            model = fcnn.FullyConnectedNN(69, config, 9).to(device)
        elif model_type == 'gcn':
            model = gcn.GCN(69, config, 9).to(device)
        elif model_type == 'gat':
            model = gat.GAT(69, config, 9).to(device)
        elif model_type == 'transformer':
            model = transformer.GraphTransformer(69, config, 9).to(device)
        model.load_state_dict(torch.load(f'./sample/training/trained_models/{model_name}.pth',
                                         map_location=torch.device(device)))
        return model
    elif model_type in ['dt', 'rf']:
        model = load(f'./sample/training/trained_models/{model_name}.joblib')
        return model
