"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Training and evaluation for FCNN classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import torch.nn as nn

import sample.dataset.fcnn_dataset as ds
import sample.models.fcnn as fcnn
import sample.training.train as tr
import sample.training.eval as ev


def train_and_eval_fcnn(x_train, y_train, x_val, y_val, x_test, y_test, config, model_name, model_type):
    """
    Training and evaluation for FCNN classifier
    :param x_train: tensor with train features
    :param y_train: tensor with train labels
    :param x_val: tensor with val features
    :param y_val: tensor with val labels
    :param x_test: tensor with test features
    :param y_test: tensor with test labels
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_type: which kind of classifier? (ex. GAT)
    :return: model predictions
    """
    # Load data
    dataloader_train = ds.load_data(x_train, y_train, config.batch_size, True)
    dataloader_val = ds.load_data(x_val, y_val, config.batch_size, False)
    if x_test is not None:
        dataloader_test = ds.load_data(x_test, y_test, config.batch_size, False)
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
    model = fcnn.initialize_model(config, device)
    print(model)
    tr.train_and_log(model, device, dataloader_train, dataloader_val,
                  loss_fn, config, model_name, '', model_type)
    if x_test is not None:
        final_val_loader = dataloader_test
    else:
        final_val_loader = dataloader_val
    y_predict, _ = ev.evaluate_and_log(final_val_loader, model, device, loss_fn, True, None, model_type, 'val',
                                       config)
    return y_predict
