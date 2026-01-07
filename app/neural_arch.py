import torch
import torch.nn as nn

class NeuralPredictor(nn.Module):
    def __init__(self, input_dim):
        super(NeuralPredictor, self).__init__()
        # Matches Kaggle Architecture v3.1 (GPU Trained)
        self.layer_1 = nn.Linear(input_dim, 256)
        self.batchnorm1 = nn.BatchNorm1d(256)
        self.layer_2 = nn.Linear(256, 128)
        self.batchnorm2 = nn.BatchNorm1d(128)
        self.layer_3 = nn.Linear(128, 64)
        self.batchnorm3 = nn.BatchNorm1d(64)
        self.layer_out = nn.Linear(64, 1)
        
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=0.3) 

    def forward(self, x):
        x = self.layer_1(x)
        # Handle batch norm during inference with batch_size=1
        if x.shape[0] > 1: x = self.batchnorm1(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer_2(x)
        if x.shape[0] > 1: x = self.batchnorm2(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer_3(x)
        if x.shape[0] > 1: x = self.batchnorm3(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer_out(x)
        return torch.sigmoid(x)
