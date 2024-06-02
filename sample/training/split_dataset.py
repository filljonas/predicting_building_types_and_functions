"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Load GNN dataset into RAM
 |---------------------------------------------------------------------------------------------------------------------|
"""

import bisect
import torch


def split_train_val_test(dataset):
    """
    Split dataset into training/validation/test set
    :param dataset: dataset to split
    :return: dataset_train, dataset_val, dataset_test
    """
    dataset = dataset.shuffle()
    limit_train_val = int(len(dataset) * 0.7)
    limit_val_test = int(len(dataset) * 0.85)
    dataset_train = []
    dataset_val = []
    dataset_test = []
    for i in range(limit_train_val):
        dataset_train.append(dataset[i])
    for i in range(limit_train_val, limit_val_test):
        dataset_val.append(dataset[i])
    for i in range(limit_val_test, len(dataset)):
        dataset_test.append(dataset[i])
    return dataset_train, dataset_val, dataset_test


def mark_overlapping_labels(dataset_train, dataset_val, dataset_test):
    """
    Labels already used during training cannot be used during validation.
    Labels already used during training/validation cannot be used during testing.
    :param dataset_train:
    :param dataset_val:
    :param dataset_test:
    :return: new datasets with added mask `train_labels`
    """
    # Collect Graph IDs from training and validation set
    all_graphs_train = []
    all_graphs_train_or_val = []
    for data in dataset_train:
        all_graphs_train.append(data.id_cols[0][0].item())
    all_graphs_train = sorted(all_graphs_train)
    len_all_graphs_train = len(all_graphs_train)
    all_graphs_train_or_val.extend(all_graphs_train)
    usable_labels_val_set = 0
    for i, data in enumerate(dataset_val):
        all_graphs_train_or_val.append(data.id_cols[0][0].item())

        own_graph_id = data.id_cols[0][0].item()
        # Mask nodes that are present in training set
        data.usable_label = torch.full((data.id_cols.shape[0],), True, dtype=torch.bool)
        for j, graph_ids in enumerate(data.graph_id_arr):
            # Only check overlap for labeled nodes
            if data.label_mask[j] and len(graph_ids) > 1:
                for graph_id in graph_ids:
                    if graph_id != own_graph_id:
                        # Check if Graph ID is present in training set using binary search
                        index = bisect.bisect_left(all_graphs_train, graph_id)
                        if index != len_all_graphs_train and all_graphs_train[index] == graph_id:
                            data.usable_label[j] = False
        usable_labels_val_set += torch.count_nonzero(data.label_mask & data.usable_label).item()
    all_graphs_train_or_val = sorted(all_graphs_train_or_val)
    len_all_graphs_train_or_val = len(all_graphs_train_or_val)
    for i, data in enumerate(dataset_test):
        own_graph_id = data.id_cols[0][0].item()
        data.usable_label = torch.full((data.id_cols.shape[0],), True, dtype=torch.bool)
        for j, graph_ids in enumerate(data.graph_id_arr):
            if data.label_mask[j] and len(graph_ids) > 1:
                for graph_id in graph_ids:
                    if graph_id != own_graph_id:
                        # Check if Graph ID is present in training set OR validation set using binary search
                        index = bisect.bisect_left(all_graphs_train_or_val, graph_id)
                        if index != len_all_graphs_train_or_val and all_graphs_train_or_val[index] == graph_id:
                            data.usable_label[j] = False
    return dataset_train, dataset_val, dataset_test