"""
 |---------------------------------------------------------------------------------------------------------------------|
 | FCNN classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch.nn as nn
import torch.nn.functional as F


class FullyConnectedNN(nn.Module):
    def __init__(self, input_layer_size, config, output_layer_size):
        """
        :param input_layer_size: number of neurons in the first layer
        :param config: various hyperparameters
        :param output_layer_size: number of last layer/number of classes
        """
        super().__init__()
        self.dropout_rate = config.dropout_rate
        self.num_layers = config.num_layers
        self.config = config
        self.activation_fun = F.relu
        self.layers = nn.ModuleList([])

        for i in range(self.num_layers):
            if i == 0:
                self.layers.append(nn.Linear(input_layer_size, config.hidden_size))
            elif i == self.num_layers - 1:
                self.layers.append(nn.Linear(config.hidden_size, output_layer_size))
            else:
                self.layers.append(nn.Linear(config.hidden_size, config.hidden_size))

    def forward(self, x):
        for i, layer in enumerate(self.layers):
            x = layer(x)
            if i != self.num_layers - 1:
                x = self.activation_fun(x)
                x = F.dropout(x, p=self.dropout_rate, training=self.training)
        return F.log_softmax(x, dim=1)


def weight_initialization(model):
    """
    Use He-initialization to initialize the weights of the model
    :param model: FCNN model
    """
    def weights_init(m):
        if isinstance(m, nn.Linear):
            nn.init.kaiming_normal_(m.weight.data, nonlinearity='relu')
    model.apply(weights_init)


def initialize_model(config, device):
    """
    Initialized model and performs weight initialization
    :param config: various hyperparameters
    :param device: CPU or GPU
    :return: initialized model
    """
    model = FullyConnectedNN(69, config, 9).to(device)
    # Weight initialization
    weight_initialization(model)
    return model