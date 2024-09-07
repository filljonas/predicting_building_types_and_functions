"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Create FCNN dataset
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
from torch.utils.data import DataLoader


class FCNNDataset(torch.utils.data.Dataset):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.n_samples = x.shape[0]

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]


def load_data(x, y, batch_size, shuffle):
    """
    Load x and y tensors into dataloader suitable for FCNN
    :param x: features
    :param y: labels
    :param batch_size: batch size
    :param shuffle: randomly shuffle dataset?
    :return: dataloader
    """
    dataset = FCNNDataset(x, y)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=0)
    return dataloader