"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Functions for training the classifiers
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import time
import tqdm
from joblib import dump

import sample.training.eval as ev


def train_and_log(model, device, dataloader_train, dataloader_val, loss_fn, config,
                  model_name, model_description, model_type):
    """
    Train classifier and log results
    :param model: classifier model
    :param device: CPU or GPU
    :param dataloader_train: dataloader for training
    :param dataloader_val: dataloader for validation
    :param loss_fn: loss function
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_description: description of the model
    :param model_type: which kind of classifier? (ex. GAT)
    """
    if model_type in ['fcnn', 'gcn', 'gat', 'transformer', 'sage']:
        train_nn(model, device, dataloader_train, dataloader_val, loss_fn, config,
                  model_name, model_description, model_type)
    elif model_type in ['dt', 'rf']:
        train_tree(model, dataloader_train, config, model_name, model_description)


def train_tree(model, dataloader_train, config, model_name, model_description):
    """
    Evaluate tree-base classifier
    :param model: classifier model
    :param dataloader_train: dataloader for training
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_description: description of the model
    """
    x, y = dataloader_train
    model.fit(x, y)
    dump(model, f'./sample/training/trained_models/{model_name}.joblib', compress=3)


def train_nn(model, device, dataloader_train, dataloader_val, loss_fn, config,
                  model_name, model_description, model_type):
    """
    Train FCNN classifier
    :param model: classifier model
    :param device: CPU or GPU
    :param dataloader_train: dataloader for training
    :param dataloader_val: dataloader for validation
    :param loss_fn: loss function
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_description: description of the model
    :param model_type: which kind of classifier? (ex. GAT)
    :return: accuracy score of last epoch
    """
    start_training = time.time()

    # | ---------------------------------------------------------------------------------------------------------------|
    # Important part
    # | ---------------------------------------------------------------------------------------------------------------|
    # Variables needed for early stopping
    best_loss_val = float('inf')
    epochs_without_improvement = 0
    patience = 5

    # Set 'Adam' optimizer (this is the quasi-standard one)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    accuracy_score = 0.0
    # Training loop
    for t in range(config.epochs):
        if model_type == 'fcnn':
            train_fun = train_epoch_fcnn
        elif model_type in ['gcn', 'gat', 'transformer', 'sage']:
            train_fun = train_epoch_gnn
        # Training loop for current epoch
        train_fun(dataloader_train, model, device, loss_fn, optimizer, t + 1, config)
        _, loss_val_train = ev.evaluate_and_log(dataloader_train, model, device, loss_fn, False,
                                                t, model_type, 'train', config)
        _, loss_val = ev.evaluate_and_log(dataloader_val, model, device, loss_fn, False,
                                          t, model_type, 'val', config)
        # Early stopping
        if loss_val < best_loss_val:
            best_loss_val = loss_val
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(f"Early stopping at epoch {t + 1}")
                break

    end_training = time.time()
    print(f'Runtime for training: {(end_training - start_training) * 1000.0} ms')

    # | ---------------------------------------------------------------------------------------------------------------|
    # End of important part
    # | ---------------------------------------------------------------------------------------------------------------|

    # Save trained model
    torch.save(model.state_dict(), f'./sample/training/trained_models/{model_name}.pth')
    # Return accuracy score at last epoch
    return accuracy_score


def train_epoch_fcnn(dataloader, model, device, loss_fn, optimizer, current_epoch, config):
    """
    One epoch of FCNN classifier
    :param dataloader: dataloader for training
    :param model: classifier model
    :param device: CPU or GPU
    :param loss_fn: loss function
    :param optimizer: optimizer for gradient descent
    :param current_epoch: current epoch
    :param config: various hyperparameters
    :return: loss, accuracy
    """
    # Switch on training mode of the model (in training model, dropout is activated)
    model.train()
    # Set up progress bar
    loop = tqdm.tqdm(dataloader)
    loop.set_description(f'Epoch [{current_epoch}/{config.epochs}]')
    for batch, (x, y) in enumerate(loop):
        # Reset gradients of model weights
        optimizer.zero_grad()
        # Put tensors to GPU if available
        x, y = x.to(device), y.to(device)
        # Get predictions of current batch
        y_pred = model(x)
        # Compute loss of current batch
        loss = loss_fn(y_pred, y)
        # Description for progress bar
        loop.set_postfix(loss=loss.item())
        # Perform backpropagation
        loss.backward()
        # Perform gradient step
        optimizer.step()


def train_epoch_gnn(dataloader, model, device, loss_fn, optimizer, current_epoch, config):
    """
    One epoch of GNN classifier
    :param dataloader: dataloader for training
    :param model: classifier model
    :param device: CPU or GPU
    :param loss_fn: loss function
    :param optimizer: optimizer for gradient descent
    :param current_epoch: current epoch
    :param config: various hyperparameters
    :return: loss, accuracy
    """
    # Switch on training mode of the model (in training model, dropout is activated)
    model.train()
    # Set up progress bar
    loop = tqdm.tqdm(dataloader)
    loop.set_description(f'Epoch [{current_epoch}/{config.epochs}]')
    for _, batch in enumerate(loop):
        # Reset gradients of model weights
        optimizer.zero_grad()
        # Put tensors to GPU if available
        batch = batch.to(device)
        # Get predictions of current batch
        y_pred = model(batch)
        if config.only_center_labels:
            mask = torch.zeros(batch.label_mask.size(0), dtype=torch.bool)
            mask[:batch.batch_size] = True
        else:
            mask = batch.label_mask_train
        # Compute loss of current batch
        loss = loss_fn(y_pred[mask], batch.y[mask])
        # Description for progress bar
        loop.set_postfix(loss=loss.item())
        # Perform backpropagation
        loss.backward()
        # Perform gradient step
        optimizer.step()