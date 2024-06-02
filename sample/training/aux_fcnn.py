"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Auxiliary functions to "flatten" the dataset for usage with an FCNN
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
from torch.utils.data import DataLoader

import sample.dataset.fcnn_dataset as ds


def flatten(dataset, train_mode):
    """
    Flatten the graph.
    This means that only nodes and labels are left, edges are deleted.
    This step makes the dataset suitable for fully connected NNs.
    :param dataset: Graph dataset
    :param train_mode: True if training, False if validation or testing
    :return: flattened graph components (features, labels, masks, auxiliary columns).
    """
    x = []
    y = []
    mask = []
    center_mask = []
    id_cols = []
    usable_label = []
    for i in range(len(dataset)):
        x_i = dataset[i].x
        y_i = dataset[i].y
        mask_i = dataset[i].label_mask
        center_mask_i = dataset[i].center_mask
        id_cols_i = dataset[i].id_cols
        if not train_mode:
            usable_label_i = dataset[i].usable_label
        x.append(x_i)
        y.append(y_i)
        mask.append(mask_i)
        center_mask.append(center_mask_i)
        id_cols.append(id_cols_i)
        if not train_mode:
            usable_label.append(usable_label_i)
    x = torch.cat(x, 0)
    y = torch.cat(y, 0)
    mask = torch.cat(mask, 0)
    center_mask = torch.cat(center_mask, 0)
    id_cols = torch.cat(id_cols, 0)
    if not train_mode:
        usable_label = torch.cat(usable_label, 0)
    return x, y, mask, center_mask, id_cols, usable_label


def filter_buildings_with_labels(x, y, mask, id_cols):
    """
    Filter for buildings with labels
    :param x: node features
    :param y: labels
    :param mask: label mask
    :param id_cols: auxiliary columns
    :return: filtered x, y, id_cols
    """
    x = x[mask]
    y = y[mask]
    id_cols = id_cols[mask]
    return x, y, id_cols


def preprocessing(dataset_train, dataset_val, dataset_test):
    """
    Flatten GNN datasets and filter for labeled buildings
    :param dataset_train: GNN dataset for training
    :param dataset_val: GNN dataset for validation
    :param dataset_test: GNN dataset for testing
    :return x_train, y_train, x_val, y_val, x_test, y_test
    """
    # Flatten graphs
    x_train, y_train, label_mask_train, center_mask_train, id_cols_train, _ = flatten(dataset_train, True)
    x_val, y_val, label_mask_val, center_mask_val, id_cols_val, usable_label_val = flatten(dataset_val, False)
    x_test, y_test, label_mask_test, center_mask_test, id_cols_test, usable_label_test = flatten(dataset_test, False)
    # Only use labeled buildings
    x_train, y_train, id_cols_train = filter_buildings_with_labels(x_train, y_train, label_mask_train, id_cols_train)
    x_val, y_val, id_cols_val = filter_buildings_with_labels(x_val, y_val, label_mask_val & usable_label_val,
                                                             id_cols_val)
    x_test, y_test, id_cols_test = filter_buildings_with_labels(x_test, y_test, label_mask_test & usable_label_test,
                                                                id_cols_test)
    return x_train, y_train, x_val, y_val, x_test, y_test


def load_data(x, y, batch_size, shuffle):
    """
    Load x and y tensors into dataloader suitable for FCNN
    :param x: features
    :param y: labels
    :param batch_size: batch size
    :param shuffle: randomly shuffle dataset?
    :return: dataloader
    """
    dataset = ds.FCNNDataset(x, y)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=0)
    return dataloader