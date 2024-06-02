"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Training and evaluation for FCNN classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import torch.nn as nn

import sample.training.aux_fcnn as ax
import sample.models.fcnn as fcnn
import sample.training.train as tr
import sample.training.eval as ev


def train_and_eval_fcnn(x_train, y_train, x_val, y_val, config, model_name, model_type):
    """
    Training and evaluation for FCNN classifier
    :param x_train: tensor with train features
    :param y_train: tensor with train labels
    :param x_val: tensor with val features
    :param y_val: tensor with val labels
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_type: which kind of classifier? (ex. GAT)
    :return: model predictions
    """
    # Load data
    dataloader_train = ax.load_data(x_train, y_train, config.batch_size, True)
    dataloader_val = ax.load_data(x_val, y_val, config.batch_size, False)
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
    model = fcnn.initialize_model(config, device)
    print(model)
    tr.train(model, device, dataloader_train, dataloader_val,
                  loss_fn, config, model_name, model_type)
    y_predict, _ = ev.evaluate(dataloader_val, model, device, loss_fn, True, None, model_type)
    return y_predict
