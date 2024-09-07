"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Functions for evaluating the classifiers
 |---------------------------------------------------------------------------------------------------------------------|
"""

import torch
import numpy as np
import sklearn.metrics as metrics
import tqdm

import sample.util.class_names as cn


def evaluate_and_log(dataloader, model, device, loss_fn, all, epoch,
                     model_type, mode, config):
    """
    Evaluate classifier and log results
    :param dataloader: dataloader for evaluation
    :param model: classifier model
    :param device: CPU or GPU
    :param loss_fn: loss function
    :param all: true -> log all metrics, false -> log most important metrics
    :param epoch: current epoch
    :param model_type: which kind of classifier? (ex. GAT)
    :param mode: `train`: training, `val`: validation, `test`: test
    :param config: various hyperparameters
    :return: model predictions, validation loss
    """
    if model_type == 'fcnn':
        evaluate_fun = evaluate_fcnn
    elif model_type in ['gcn', 'gat', 'transformer', 'sage']:
        evaluate_fun = evaluate_gnn
    elif model_type in ['dt', 'rf']:
        evaluate_fun = evaluate_tree
    # Get model predictions
    y_predict, y, loss_val = evaluate_fun(dataloader, model, device, loss_fn, mode, config)
    # During training, only compute the most important metrics to get an understanding of the validation performance.
    # After training, compute detailed performance metrics (ex. F1 score per individual class).
    compute_and_log_metrics(y_predict, y, epoch, loss_val, all, model_type, mode)
    return y_predict, loss_val


def evaluate_tree(dataloader, model, device, loss_fn, mode, config):
    """
    Evaluate tree-base classifier
    :param dataloader: dataloader for evaluation
    :param model: classifier model
    :param device: CPU or GPU
    :param loss_fn: loss function
    :param mode: `val`: validation, `test`: test
    :param config: various hyperparameters
    :return: model predictions, ground truth, _
    """
    x, y = dataloader
    y_predict = model.predict(x)
    return y_predict.tolist(), y.tolist(), None


def evaluate_fcnn(dataloader, model, device, loss_fn, mode, config):
    """
    Evaluate FCNN classifier
    :param dataloader: dataloader for evaluation
    :param model: classifier model
    :param device: CPU or GPU
    :param loss_fn: loss function
    :param mode: `val`: validation, `test`: test
    :param config: various hyperparameters
    :return: model predictions, ground truth, test loss
    """
    num_batches = len(dataloader)
    # Switch on evaluation mode of the model (in evaluation model, dropout is deactivated)
    model.eval()
    test_loss, correct = 0, 0
    y_predict_all = []
    y_all = []
    with torch.no_grad():
        for x, y in dataloader:
            x, y = x.to(device), y.to(device)
            # Get predictions of current batch
            y_pred = model(x)
            # Compute loss of current barch
            test_loss += loss_fn(y_pred, y).item()
            y_predict_all.extend(y_pred.argmax(1).tolist())
            y_all.extend(y.tolist())
    test_loss /= num_batches
    return y_predict_all, y_all, test_loss


def evaluate_gnn(dataloader, model, device, loss_fn, mode, config):
    """
    Evaluate GNN classifier
    :param dataloader: dataloader for evaluation
    :param model: classifier model
    :param device: CPU or GPU
    :param loss_fn: loss function
    :param mode: `val`: validation, `test`: test
    :param config: various hyperparameters
    :return: model predictions, ground truth, test loss
    """
    num_batches = len(dataloader)
    # Switch on evaluation mode of the model (in evaluation model, dropout is deactivated)
    model.eval()
    test_loss, correct = 0, 0
    y_predict_all = []
    y_all = []
    with torch.no_grad():
        for batch in dataloader:
            batch = batch.to(device)
            # Get predictions of current batch
            y_pred = model(batch)
            # Compute loss of current batch
            if config.only_center_labels:
                mask = torch.zeros(batch.label_mask.size(0), dtype=torch.bool)
                mask[:batch.batch_size] = True
            else:
                if mode == 'train':
                    mask = batch.label_mask_train
                elif mode == 'val':
                    mask = batch.label_mask_val
                elif mode == 'test':
                    mask = batch.label_mask_test
            test_loss += loss_fn(y_pred[mask], batch.y[mask]).item()
            y_predict_all.extend(y_pred[mask].argmax(1).tolist())
            y_all.extend(batch.y[mask].tolist())
    test_loss /= num_batches
    return y_predict_all, y_all, test_loss


def compute_metrics(y, y_predict, all):
    """
    Compute performance metrics out of model predictions and ground truth data
    :param y: ground truth
    :param y_predict: model predictions
    :param all: true -> log all metrics, false -> log most important metrics
    :return:
    """
    accuracy_score = metrics.accuracy_score(y, y_predict)
    macro_f1_score = metrics.f1_score(y, y_predict, average='macro')
    if all:
        cohen_kappa = metrics.cohen_kappa_score(y, y_predict)
        matthews_corrcoef = metrics.matthews_corrcoef(y, y_predict)
        precision_scores = metrics.precision_score(y, y_predict, average=None)
        recall_scores = metrics.recall_score(y, y_predict, average=None)
        f1_scores = metrics.f1_score(y, y_predict, average=None)
        cm = metrics.confusion_matrix(y, y_predict)
        return accuracy_score, cohen_kappa, matthews_corrcoef, macro_f1_score, precision_scores, recall_scores, \
            f1_scores, cm
    else:
        return accuracy_score, macro_f1_score


def compute_and_log_metrics(y_predict, y, epoch, loss_val, all, model_type, mode):
    """
    Compute evaluation metrics for different class distinctions
    :param y_predict: model predictions
    :param y: ground truth
    :param epoch: current epoch
    :param loss_val: loss
    :param all: true -> log all metrics, false -> log most important metrics
    :param model_type: which kind of classifier? (ex. GAT)
    :param mode: training or validation mode?
    """
    # Convert lists to NumPy arrays to be able to create masks
    y_predict = np.array(y_predict)
    y = np.array(y)
    if all:
        compute_and_log_metrics_all_classes(y, y_predict)
        compute_and_log_metrics_res_nonres(y, y_predict)
        compute_and_log_metrics_restypes_nonres(y, y_predict)
    else:
        if model_type in ['fcnn', 'gcn', 'gat', 'transformer', 'sage']:
            if mode == 'train':
                long_mode = 'Training'
            elif mode == 'val':
                long_mode = 'Validation'
            # Compute evaluation metrics
            accuracy_score, macro_f1_score = compute_metrics(y, y_predict, all)
            print(f'{long_mode} Metrics: Avg loss: {loss_val:>8f}, Accuracy score: {accuracy_score}, '
                  f'Macro F1 score: {macro_f1_score} \n')
        elif model_type in ['dt', 'rf']:
            accuracy_score, macro_f1_score = compute_metrics(y, y_predict, all)
            print(f'Accuracy score train: {accuracy_score}')
            print(f'Macro F1 score train: {macro_f1_score}')


def compute_and_log_metrics_all_classes(y, y_predict):
    """
    Compute evaluation metrics for all classes
    :param y: ground truth
    :param y_predict: model predictions
    :return: performance metrics
    """
    # Compute evaluation metrics
    accuracy_score, cohen_kappa, matthews_corrcoef, \
        macro_f1_score, precision_scores, recall_scores, f1_scores, cm = compute_metrics(y, y_predict, True)
    print(f'Accuracy score (all): {accuracy_score}')
    print(f'Cohen\'s Kappa Coefficient (all): {cohen_kappa}')
    print(f'Matthew\'s Correlation Coefficient (all): {matthews_corrcoef}')
    print(f'Macro F1-score (all): {macro_f1_score}')
    for i in range(len(precision_scores)):
        print(f'Precision score ({cn.class_names_all[i]}): {precision_scores[i]}')
        print(f'Recall score ({cn.class_names_all[i]}): {recall_scores[i]}')
        print(f'F1-score ({cn.class_names_all[i]}): {f1_scores[i]}')
    return accuracy_score, cohen_kappa, matthews_corrcoef, \
        macro_f1_score, precision_scores, recall_scores, f1_scores, cm


def compute_and_log_metrics_res_nonres(y, y_predict):
    """
    Compute evaluation metrics for res/nonres distinction
    :param y: ground truth
    :param y_predict: model predictions
    :return: performance metrics
    """
    # Res/nonres distinction
    mask = y_predict > 3
    y_predict_res_nonres = y_predict.copy()
    y_predict_res_nonres[mask] = 1
    y_predict_res_nonres[~mask] = 0

    mask = y > 3
    y_val_res_nonres = y.copy()
    y_val_res_nonres[mask] = 1
    y_val_res_nonres[~mask] = 0

    accuracy_score, cohen_kappa, matthews_corrcoef, macro_f1_score, precision_scores, recall_scores, f1_scores, cm = compute_metrics(
        y_val_res_nonres, y_predict_res_nonres, True)
    print(f'Accuracy score (res/nonres): {accuracy_score}')
    print(f'Cohen\'s Kappa Coefficient (res/nonres): {cohen_kappa}')
    print(f'Matthew\'s Correlation Coefficient (res/nonres): {matthews_corrcoef}')
    print(f'Macro F1-score (res/nonres): {macro_f1_score}')
    print(f'Precision score (res): {precision_scores[0]}')
    print(f'Recall score (res): {recall_scores[0]}')
    print(f'F1-score (res): {f1_scores[0]}')
    print(f'Precision score (nonres): {precision_scores[1]}')
    print(f'Recall score (nonres): {recall_scores[1]}')
    print(f'F1-score (nonres): {f1_scores[1]}')
    return accuracy_score, cohen_kappa, matthews_corrcoef, \
        macro_f1_score, precision_scores, recall_scores, f1_scores, cm


def compute_and_log_metrics_restypes_nonres(y, y_predict):
    """
    Compute evaluation metrics for residential typology prediction
    :param y: ground truth
    :param y_predict: model predictions
    :return: performance metrics
    """
    # Restypes/nonres distinction
    mask = y_predict > 3
    y_predict_restypes_nonres = y_predict.copy()
    y_predict_restypes_nonres[mask] = 4

    mask = y > 3
    y_val_restypes_nonres = y.copy()
    y_val_restypes_nonres[mask] = 4

    accuracy_score, cohen_kappa, matthews_corrcoef, macro_f1_score, precision_scores, recall_scores, f1_scores, cm = compute_metrics(
        y_val_restypes_nonres, y_predict_restypes_nonres, True)
    print(f'Accuracy score (res. typology): {accuracy_score}')
    print(f'Cohen\'s Kappa Coefficient (res. typology): {cohen_kappa}')
    print(f'Matthew\'s Correlation Coefficient (res. typology): {matthews_corrcoef}')
    print(f'Macro F1-score (res. typology): {macro_f1_score}')
    return accuracy_score, cohen_kappa, matthews_corrcoef, \
        macro_f1_score, precision_scores, recall_scores, f1_scores, cm


def inference_gnn(dataloader, model, device):
    """
    Just perform inference without evaluation
    :param dataloader: dataloader for evaluation
    :param model: classifier model
    :param device: CPU or GPU
    :return: model predictions, auxiliary columns
    """
    # Switch on evaluation mode of the model (in evaluation model, dropout is deactivated)
    model.eval()
    y_predict_all = []
    id_cols_all = []
    # Set up progress bar
    loop = tqdm.tqdm(dataloader)
    loop.set_description(f'Inference')
    with torch.no_grad():
        for _, batch in enumerate(loop):
            batch = batch.to(device)
            # Get predictions of current batch
            y_pred = model(batch)
            y_predict_all.extend(y_pred.argmax(1).tolist())
            id_cols_all.extend(batch.id_cols.tolist())
    return y_predict_all, id_cols_all