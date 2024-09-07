"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Load GNN dataset into RAM
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
from torch_geometric.utils import k_hop_subgraph


def split_train_val_test(center_mask):
    """
    Split the center nodes into train/val/test set
    """
    true_indices = torch.nonzero(center_mask, as_tuple=True)[0]
    shuffled_true_indices = true_indices[torch.randperm(len(true_indices))]
    num_true = len(shuffled_true_indices)
    train_end = int(0.7 * num_true)
    val_end = int(0.85 * num_true)

    train_indices = shuffled_true_indices[:train_end]
    val_indices = shuffled_true_indices[train_end:val_end]
    test_indices = shuffled_true_indices[val_end:]

    train_mask = torch.zeros_like(center_mask, dtype=torch.bool)
    val_mask = torch.zeros_like(center_mask, dtype=torch.bool)
    test_mask = torch.zeros_like(center_mask, dtype=torch.bool)

    train_mask[train_indices] = True
    val_mask[val_indices] = True
    test_mask[test_indices] = True
    return train_mask, val_mask, test_mask


def label_masks_train_val_test(data, train_mask, val_mask, test_mask, type, hops=4):
    """
    In case labels are used for surrounding nodes, label masks have to be different for train/val/test set due to
    overlapping nodes. Create these label masks
    """
    already_considered_idx = set()

    def collect_nodes_in_subgraphs(data, hops, mask_1, mask_2, mask_3):
        """
        Given masks of center nodes, follow edges in graph to get all nodes in subgraphs
        """
        if type == 'n_hop':
            subset_1, _, _, _ = k_hop_subgraph(torch.nonzero(mask_1, as_tuple=True)[0], hops, data.edge_index,
                                                   relabel_nodes=False)
            subset_2, _, _, _ = k_hop_subgraph(torch.nonzero(mask_2, as_tuple=True)[0], hops, data.edge_index,
                                                 relabel_nodes=False)
            subset_3, _, _, _ = k_hop_subgraph(torch.nonzero(mask_3, as_tuple=True)[0], hops, data.edge_index,
                                                  relabel_nodes=False)
            mask_1 = torch.zeros_like(data.id, dtype=torch.bool)
            mask_1[subset_1] = True
            mask_2 = torch.zeros_like(data.id, dtype=torch.bool)
            mask_2[subset_2] = True
            mask_3 = torch.zeros_like(data.id, dtype=torch.bool)
            mask_3[subset_3] = True
        elif type == 'circ':
            # Get original IDs of center nodes
            id_orig_train = data.id_orig[torch.nonzero(mask_1, as_tuple=True)[0]]
            id_orig_val = data.id_orig[torch.nonzero(mask_2, as_tuple=True)[0]]
            id_orig_test = data.id_orig[torch.nonzero(mask_3, as_tuple=True)[0]]
            # Collect all nodes that in the subgraphs
            mask_1 = torch.isin(data.center_id, id_orig_train)
            mask_2 = torch.isin(data.center_id, id_orig_val)
            mask_3 = torch.isin(data.center_id, id_orig_test)
        # Only keep the subgraph nodes that have labels
        mask_1 = mask_1 & data.label_mask
        mask_2 = mask_2 & data.label_mask
        mask_3 = mask_3 & data.label_mask
        subset_1 = torch.nonzero(mask_1, as_tuple=True)[0]
        subset_2 = torch.nonzero(mask_2, as_tuple=True)[0]
        subset_3 = torch.nonzero(mask_3, as_tuple=True)[0]
        return subset_1, subset_2, subset_3

    def distribute_nodes_3_sets(label_mask_1, label_mask_2, label_mask_3, subset_1, subset_2, subset_3):
        """
        Some nodes are present in all three sets (training, validation, testing).
        Distribute them randomly in a way that all sets still contain the desired ratio of labels (70/15/15)
        """
        # Get node indices that are in all three sets. Delete all labels for these nodes
        if type == 'n_hop':
            mask = label_mask_1 & label_mask_2 & label_mask_3
            nodes = torch.nonzero(mask, as_tuple=True)[0]
            label_mask_1[nodes] = False
            label_mask_2[nodes] = False
            label_mask_3[nodes] = False
        if type == 'circ':
            # Get original IDs of all labeled nodes in subgraphs
            id_orig_train = set(data.id_orig[subset_1].tolist())
            id_orig_val = set(data.id_orig[subset_2].tolist())
            id_orig_test = set(data.id_orig[subset_3].tolist())
            nodes_set = id_orig_train & id_orig_val & id_orig_test
            already_considered_idx.update(nodes_set)
            nodes = torch.tensor(list(nodes_set), dtype=torch.int64)
            mask = torch.isin(data.id_orig, nodes)
            indices = torch.nonzero(mask, as_tuple=True)[0]
            label_mask_1[indices] = False
            label_mask_2[indices] = False
            label_mask_3[indices] = False
        # Distribute indices present in all three sets to training, validation and test set
        shuffled_nodes = nodes[torch.randperm(len(nodes.tolist()))]
        num_indices = len(shuffled_nodes.tolist())
        train_end = round(1.0 * num_indices)
        val_end = round(1.0 * num_indices)
        train_indices = shuffled_nodes[:train_end]
        val_indices = shuffled_nodes[train_end:val_end]
        test_indices = shuffled_nodes[val_end:]
        # For circular buffers, map original node IDs to new node IDs
        if type == 'circ':
            mask = torch.isin(data.id_orig, train_indices)
            train_indices = torch.nonzero(mask, as_tuple=True)[0]
            mask = torch.isin(data.id_orig, val_indices)
            val_indices = torch.nonzero(mask, as_tuple=True)[0]
            mask = torch.isin(data.id_orig, test_indices)
            test_indices = torch.nonzero(mask, as_tuple=True)[0]
        # Adjust label mask according to random distribution
        label_mask_1[train_indices] = True
        label_mask_2[val_indices] = True
        label_mask_3[test_indices] = True
        return label_mask_1, label_mask_2, label_mask_3

    def distribute_nodes_2_sets(label_mask_1, label_mask_2, subset_train_1, subset_train_2, threshold):
        """
        Some nodes are present in two sets (e.g. training and validation).
        Distribute them randomly in a way that both sets still contain the desired ratio of labels.
        """
        if type == 'n_hop':
            mask = label_mask_1 & label_mask_2
            nodes = torch.nonzero(mask, as_tuple=True)[0]
            label_mask_1[nodes] = False
            label_mask_2[nodes] = False
        elif type == 'circ':
            id_orig_1 = set(data.id_orig[subset_train_1].tolist())
            id_orig_2 = set(data.id_orig[subset_train_2].tolist())
            current_idx = id_orig_1 & id_orig_2
            # The nodes in `already_considered_idx` are present in all 3 sets.
            # We do not consider them at this point anymore.
            current_idx.difference_update(already_considered_idx)
            nodes = torch.tensor(list(current_idx), dtype=torch.int64)
            mask = torch.isin(data.id_orig, nodes)
            indices = torch.nonzero(mask, as_tuple=True)[0]
            label_mask_1[indices] = False
            label_mask_2[indices] = False
        shuffled_nodes = nodes[torch.randperm(len(nodes.tolist()))]
        num_indices = len(shuffled_nodes.tolist())
        border = round(threshold * num_indices)
        indices_1 = shuffled_nodes[:border]
        indices_2 = shuffled_nodes[border:]
        if type == 'circ':
            mask = torch.isin(data.id_orig, indices_1)
            indices_1 = torch.nonzero(mask, as_tuple=True)[0]
            mask = torch.isin(data.id_orig, indices_2)
            indices_2 = torch.nonzero(mask, as_tuple=True)[0]
        label_mask_1[indices_1] = True
        label_mask_2[indices_2] = True
        return label_mask_1, label_mask_2

    def assign_center_nodes(label_mask_train, label_mask_val, label_mask_test, train_mask, val_mask, test_mask):
        """
        Center nodes must belong to correct set
        """
        label_mask_train[train_mask] = True
        label_mask_val[train_mask] = False
        label_mask_test[train_mask] = False
        label_mask_val[val_mask] = True
        label_mask_train[val_mask] = False
        label_mask_test[val_mask] = False
        label_mask_test[test_mask] = True
        label_mask_train[test_mask] = False
        label_mask_val[test_mask] = False
        return label_mask_train, label_mask_val, label_mask_test

    # Create masks
    label_mask_train = torch.zeros_like(data.label_mask, dtype=torch.bool)
    label_mask_val = torch.zeros_like(data.label_mask, dtype=torch.bool)
    label_mask_test = torch.zeros_like(data.label_mask, dtype=torch.bool)
    # Collect nodes in subgraphs
    subset_train, subset_val, subset_test = collect_nodes_in_subgraphs(data, hops, train_mask, val_mask, test_mask)
    # Add nodes in subgraphs to masks
    label_mask_train[subset_train] = True
    label_mask_val[subset_val] = True
    label_mask_test[subset_test] = True
    # Distribute nodes that are present in training, validation and test set
    label_mask_train, label_mask_val, label_mask_test = distribute_nodes_3_sets(label_mask_train, label_mask_val, label_mask_test,
                                                                                subset_train, subset_val, subset_test)
    # Distribute nodes that are present in training and validation set
    label_mask_train, label_mask_val = distribute_nodes_2_sets(label_mask_train, label_mask_val, subset_train,
                                                               subset_val, 1.0)
    # Distribute nodes that are present in training and test set
    label_mask_train, label_mask_test = distribute_nodes_2_sets(label_mask_train, label_mask_test, subset_train,
                                                                subset_test, 1.0)
    # Distribute nodes that are present in validation and test set
    label_mask_val, label_mask_test = distribute_nodes_2_sets(label_mask_val, label_mask_test, subset_val, subset_test,
                                                              1.0)
    label_mask_train, label_mask_val, label_mask_test = assign_center_nodes(label_mask_train, label_mask_val,
                                                                            label_mask_test, train_mask, val_mask,
                                                                            test_mask)
    return label_mask_train, label_mask_val, label_mask_test
