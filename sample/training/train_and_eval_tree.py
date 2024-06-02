"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Training and evaluation for tree-based classifier
 |---------------------------------------------------------------------------------------------------------------------|
"""

import sample.training.train as tr
import sample.training.eval as ev

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier


def train_and_eval_tree(x_train, y_train, x_val, y_val, config, model_name, model_type):
    """
    Training and evaluation for tree-based classifier
    :param x_train: tensor with train features
    :param y_train: tensor with train labels
    :param x_val: tensor with val features
    :param y_val: tensor with val labels
    :param config: various hyperparameters
    :param model_name: name of the model
    :param model_type: which kind of classifier? (ex. DT)
    :return: model predictions
    """
    dataloader_train = x_train, y_train
    dataloader_val = x_val, y_val
    if model_type == 'dt':
        model = DecisionTreeClassifier(criterion=config.criterion, max_depth=config.max_depth,
                                       min_weight_fraction_leaf=config.min_weight_fraction_leaf,
                                       class_weight=config.class_weight)
    elif model_type == 'rf':
        model = RandomForestClassifier(n_estimators=config.n_estimators, n_jobs=config.n_jobs,
                                       criterion=config.criterion, max_depth=config.max_depth,
                                       max_features=config.max_features, class_weight=config.class_weight)
    tr.train(model, None, dataloader_train, dataloader_val,
                     None, config, model_name, model_type)
    y_predict, _ = ev.evaluate(dataloader_val, model, None, None, True, None, model_type)
    return y_predict