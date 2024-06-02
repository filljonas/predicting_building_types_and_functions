"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Create FCNN dataset (in the format readable by PyTorch)
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch


class FCNNDataset(torch.utils.data.Dataset):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.n_samples = x.shape[0]

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]