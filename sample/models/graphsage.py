"""
 |---------------------------------------------------------------------------------------------------------------------|
 | GCN classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv


class GraphSAGE(torch.nn.Module):
    def __init__(self, input_layer_size, config, output_layer_size):
        """
        :param input_layer_size: number of neurons in the first layer
        :param config: various hyperparameters
        :param output_layer_size: number of last layer/number of classes
        """
        super().__init__()
        self.dropout_rate = config.dropout_rate
        self.num_gnn_layers = config.num_gnn_layers
        self.fcnn_after = config.fcnn_after
        self.fcnn_before = config.fcnn_before
        self.config = config
        self.activation_fun = F.relu
        # Define suitable input and output layer sizes depending on whether FCNN layers are used or not
        if config.fcnn_before:
            i = config.hidden_size
        else:
            i = input_layer_size
        if config.fcnn_after:
            o = config.hidden_size
        else:
            o = output_layer_size
        # Input FCNN layer
        if config.fcnn_before:
            self.linear_before = nn.Linear(input_layer_size, config.hidden_size)
        # Graph convolutional layers
        self.conv_layers = nn.ModuleList([SAGEConv(i, config.hidden_size, aggr=config.aggr, normalize=config.normalize,
                                                   project=config.project, root_weight=config.root_weight)])
        if self.num_gnn_layers > 2:
            self.conv_layers.extend([SAGEConv(config.hidden_size, config.hidden_size, aggr=config.aggr, normalize=config.normalize,
                                                   project=config.project, root_weight=config.root_weight)
                                     for _ in range(2, self.num_gnn_layers)])
        self.conv_layers.append(SAGEConv(config.hidden_size, o, aggr=config.aggr, normalize=config.normalize,
                                                   project=config.project, root_weight=config.root_weight))
        if self.fcnn_after:
            self.linear_after = nn.Linear(config.hidden_size, output_layer_size)

    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        if self.fcnn_before:
            x = self.linear_before(x)
            x = self.activation_fun(x)
            x = F.dropout(x, p=self.dropout_rate, training=self.training)
        # Convolutional graph layers
        for i, conv_layer in enumerate(self.conv_layers):
            x = conv_layer(x, edge_index)
            if i < len(self.conv_layers) - 1:
                # Apply activation function and dropout after all conv layers except for the last one
                x = self.activation_fun(x)
                x = F.dropout(x, p=self.dropout_rate, training=self.training)
        if self.fcnn_after:
            x = self.activation_fun(x)
            x = F.dropout(x, p=self.dropout_rate, training=self.training)
            x = self.linear_after(x)
        # Convert logits to log probabilities
        return F.log_softmax(x, dim=1)
