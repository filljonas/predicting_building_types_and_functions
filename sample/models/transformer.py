"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Graph Transformer classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import torch.nn.functional as F
import torch.nn as nn
from torch_geometric.nn import TransformerConv


class GraphTransformer(torch.nn.Module):
    def __init__(self, input_layer_size, config, output_layer_size):
        """
        :param input_layer_size: number of neurons in the first layer
        :param config: various hyperparameters
        :param output_layer_size: number of last layer/number of classes
        """
        super().__init__()
        self.dropout_rate = config.dropout_rate
        self.dropout_rate_trans = config.dropout_rate_trans
        self.num_gnn_layers = config.num_gnn_layers
        self.fcnn_after = config.fcnn_after
        self.fcnn_before = config.fcnn_before
        self.config = config
        # We use the distance between buildings as an edge features.
        # Therefore, the dimension of the edge features is 1.
        self.edge_dim = 1
        self.activation_fun = F.relu
        # Define suitable input and output layer sizes depending on whether FCNN layers are used or not
        if config.fcnn_before:
            i = config.hidden_size
        else:
            i = input_layer_size
        if config.fcnn_after:
            o = config.hidden_size // config.heads
            concat = True
        else:
            o = output_layer_size
            concat = False
        # Input FCNN layer
        if config.fcnn_before:
            self.linear_before = nn.Linear(input_layer_size, config.hidden_size)
        # Graph convolutional layers
        self.conv_layers = nn.ModuleList([TransformerConv(i, config.hidden_size // config.heads, edge_dim=self.edge_dim,
                               heads=config.heads, beta=config.beta,
                               dropout=self.dropout_rate_trans)])
        if self.num_gnn_layers > 2:
            self.conv_layers.extend([TransformerConv(config.hidden_size, config.hidden_size // config.heads, edge_dim=self.edge_dim,
                                   heads=config.heads, beta=config.beta,
                                   dropout=self.dropout_rate_trans) for _ in range(2, self.num_gnn_layers)])

        self.conv_layers.append(TransformerConv(config.hidden_size, o,
                                   edge_dim=self.edge_dim, heads=config.heads, beta=config.beta,
                                   dropout=self.dropout_rate_trans, concat=concat))
        self.norms = nn.ModuleList([nn.LayerNorm(config.hidden_size) for _ in range(self.num_gnn_layers)])
        # Output FCNN layer
        if self.fcnn_after:
            self.linear_after = nn.Linear(config.hidden_size, output_layer_size)

    def forward(self, data):
        if self.config.scaler_dist == 'std':
            x, edge_index, distance = data.x, data.edge_index, data.distance_std
        elif self.config.scaler_dist == 'minmax':
            x, edge_index, distance = data.x, data.edge_index, data.distance
            distance = 1 - (distance / self.config.minmax_threshold)
        if self.fcnn_before:
            x = self.linear_before(x)
            x = self.activation_fun(x)
            x = F.dropout(x, p=self.dropout_rate, training=self.training)
        # Convolutional graph layers
        for i, conv_layer in enumerate(self.conv_layers):
            x = conv_layer(x, edge_index, edge_attr=distance)
            if i < len(self.conv_layers) - 1:
                # Apply layer normalization, activation function and dropout after all conv layers except for the last one
                x = self.norms[i](x)
                x = self.activation_fun(x)
                x = F.dropout(x, p=self.dropout_rate, training=self.training)
        if self.fcnn_after:
            x = self.norms[-1](x)
            x = self.activation_fun(x)
            x = F.dropout(x, p=self.dropout_rate, training=self.training)
            x = self.linear_after(x)
        # Convert logits to log probabilities
        return F.log_softmax(x, dim=1)
