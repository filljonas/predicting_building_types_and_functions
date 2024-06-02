"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Functions for training the classifiers
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import time
import tqdm
import pathlib as pl
from joblib import dump

import sample.training.eval as ev


def train(model, device, dataloader_train, dataloader_val, loss_fn, config,
                  model_name, model_type):
    """
    Train classifier
    :param model: classifier model
    :param device: CPU or GPU
    :param dataloader_train: dataloader for training
    :param dataloader_val: dataloader for validation
    :param loss_fn: loss function
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_type: which kind of classifier? (ex. GAT)
    """
    if model_type in ['fcnn', 'gcn', 'gat', 'transformer']:
        train_nn(model, device, dataloader_train, dataloader_val, loss_fn, config, model_name, model_type)
    elif model_type in ['dt', 'rf']:
        train_tree(model, dataloader_train, config, model_name)


def train_tree(model, dataloader_train, config, model_name):
    """
    Evaluate tree-base classifier
    :param model: classifier model
    :param dataloader_train: dataloader for training
    :param config: various hyperparameters
    :param model_name: name of the model
    """
    x, y = dataloader_train
    model.fit(x, y)
    dump(model, f'./sample/training/trained_models/{model_name}.joblib', compress=3)


def train_nn(model, device, dataloader_train, dataloader_val, loss_fn, config,
                  model_name, model_type):
    """
    Train FCNN classifier
    :param model: classifier model
    :param device: CPU or GPU
    :param dataloader_train: dataloader for training
    :param dataloader_val: dataloader for validation
    :param loss_fn: loss function
    :param config: various hyperparameters
    :param model_name: name of the model in W&B
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
        elif model_type in ['gcn', 'gat', 'transformer']:
            train_fun = train_epoch_gnn
        # Training loop for current epoch
        loss_train, accuracy_score = train_fun(dataloader_train, model, device, loss_fn, optimizer, t + 1, config)
        print(f'Training metrics: Avg loss: {loss_train:>8f}, Accuracy score: {accuracy_score}')
        _, loss_val = ev.evaluate(dataloader_val, model, device, loss_fn, False, t, model_type)
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
    # Total number of samples in the dataset
    size = len(dataloader.dataset)
    # Number of batches in the dataset
    num_batches = len(dataloader)
    loss_train, accuracy_score = 0, 0
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
        loss_item = loss.item()
        # Compute accuracy
        acc_item = (y_pred.argmax(1) == y).type(torch.float).sum().item()
        loss_train += loss_item
        accuracy_score += acc_item
        # Description for progress bar
        loop.set_postfix(loss=loss_item, acc=acc_item / config.batch_size)
        # Perform backpropagation
        loss.backward()
        # Perform gradient step
        optimizer.step()
    loss_train /= num_batches
    accuracy_score /= size
    return loss_train, accuracy_score


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
    # Total number of samples in the dataset
    size = 0
    # Number of batches in the dataset
    num_batches = len(dataloader)
    loss_train, accuracy_score = 0, 0
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
        mask = batch.label_mask
        # Compute loss of current barch
        loss = loss_fn(y_pred[mask], batch.y[mask])
        loss_item = loss.item()
        # Compute accuracy
        acc_item = (y_pred[mask].argmax(1) == batch.y[mask]).type(torch.float).sum().item()
        loss_train += loss_item
        accuracy_score += acc_item
        # How many buildings with labels are there in the batch? -> for accuracy computation
        size += torch.sum(mask).item()
        # Description for progress bar
        loop.set_postfix(loss=loss_item, acc=acc_item / torch.sum(mask).item())
        # Perform backpropagation
        loss.backward()
        # Perform gradient step
        optimizer.step()
    loss_train /= num_batches
    accuracy_score /= size
    return loss_train, accuracy_score