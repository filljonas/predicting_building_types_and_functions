"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Preprocessing functions for GNN dataset
 |---------------------------------------------------------------------------------------------------------------------|
"""

import pandas as pd
import numpy as np
import json

import sample.util.feature_names as fn

import sklearn.preprocessing as sklearnpp


def one_hot_encoding(dataset, col_name, group_name):
    """
    Compute one-hot encoding for a certain input feature and the
    name of the feature group.
    :param dataset: dataframe with the dataset
    :param col_name: name of categorical feature in dataframe
    :param group_name: group name of the categorical feature, ex. 'Country indicators'
    :return: new dataframe with one hot encoding
    """
    # Extract feature that has textual features
    feature_col = dataset[col_name]
    # Retrieve all categories
    feature_names = fn.feature_groups_names[group_name]
    # Number of categories
    num_categories = len(feature_names)
    # Convert each textual features to the index of its category
    feature_col_numeric = feature_col.apply(lambda x: feature_names.index(x)).values
    # Set up one-hot-encoding matrix
    one_hot_matrix = np.eye(num_categories)[np.searchsorted(np.arange(num_categories), feature_col_numeric)]
    # Convert to pandas dataframe with categories as column names
    one_hot_df = pd.DataFrame(one_hot_matrix, columns=feature_names)
    # Add one-hot-encodings to dataset
    dataset = pd.concat([dataset, one_hot_df], axis=1)
    # Delete original column
    dataset = dataset.drop(columns=[col_name])
    return dataset


def scale_node_features(dataset, deployment, dataset_name):
    """
    Scaling for the node features
    :param dataset: dataframe with the dataset
    :param deployment: are we in deployment mode (if so, we have to use the same scaling parameters that were used
    while training the model)
    :param dataset_name: name of the dataset
    """
    features_to_normalize = fn.feature_groups_names['Building-level features'] + fn.feature_groups_names['Block-level features']
    dataset_cols_to_normalize = dataset[features_to_normalize]
    if not deployment:
        mean = []
        std = []
        var = []
        for column in dataset_cols_to_normalize.columns:
            scaler = sklearnpp.StandardScaler()
            dataset[column] = scaler.fit_transform(dataset_cols_to_normalize[column].values.reshape(-1, 1))
            mean.append(scaler.mean_[0])
            std.append(scaler.scale_[0])
            var.append(scaler.var_[0])
        # Write standardization parameters to JSON for later use during deployment
        data = {'mean': mean, 'std': std, 'var': var}
        with open(f'../scaling_parameters/{dataset_name}.json', 'w') as json_file:
            json.dump(data, json_file)
    else:
        with open('../scaling_parameters/pyg_ds.json', 'r') as json_file:
            data = json.load(json_file)
        # Extract the lists from the loaded dictionary
        mean = data['mean']
        std = data['std']
        var = data['var']
        for i, column in enumerate(dataset_cols_to_normalize.columns):
            scaler = sklearnpp.StandardScaler()
            scaler.mean_ = mean[i]
            scaler.scale_ = std[i]
            scaler.var_ = var[i]
            dataset[column] = scaler.transform(dataset_cols_to_normalize[column].values.reshape(-1, 1))


def scale_edge_weights(dataset):
    """
    Add scaled edge weights (with standardization and robust scaling)
    :param dataset: dataframe with the dataset
    :return: new dataframe with scaled edge weights
    """
    edge_weights = dataset['distance']
    scaler = sklearnpp.StandardScaler()
    dataset['distance_std'] = scaler.fit_transform(edge_weights.values.reshape(-1, 1))
    scaler = sklearnpp.RobustScaler()
    dataset['distance_rob'] = scaler.fit_transform(edge_weights.values.reshape(-1, 1))
    return dataset


def preprocess_nodes(dataset, deployment, dataset_name):
    """
    Data scaling and one-hot encoding for all node features
    :param dataset: dataframe with the dataset
    :param deployment: are we in deployment mode (if so, we have to use the same scaling parameters that were used
    while training the model)
    :param dataset_name: name of the dataset
    :return: new dataframe with scaled node features
    """
    # Compute one hot encodings for categorical input features
    dataset = one_hot_encoding(dataset, 'land_cover_ua_clc', 'Land cover indicators')
    dataset = one_hot_encoding(dataset, 'degurba', 'Urbanization indicators')
    dataset = one_hot_encoding(dataset, 'country', 'Country indicators')
    # Perform scaling for numerical input features
    scale_node_features(dataset, deployment, dataset_name)
    return dataset


def preprocess_edges(dataset):
    """
    Preprocess edge features
    :param dataset: dataframe with the dataset
    :return: new dataframe with scaled edge features
    """
    return scale_edge_weights(dataset)