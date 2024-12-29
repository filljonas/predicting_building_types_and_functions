import json

import sample.dataset.gnn_dataset as dsm
import sample.training.split_dataset as sd
import sample.training.train_and_eval_tree as tetree
import sample.training.train_and_eval_fcnn as tefcnn
import sample.training.train_and_eval_gnn as tegnn


class Config:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def train(args=None):
    model_type = args.model_type
    model_name = model_type

    with open(f'sample/training/config/{model_type}.json', 'r') as json_file:
        config_dict = json.load(json_file)
    with open(f'sample/training/config/general.json', 'r') as json_file:
        general_dict = json.load(json_file)
        config_dict['only_center_labels'] = general_dict['only_center_labels']
        config_dict['subgraph_type'] = general_dict['subgraph_type']
        config_dict['hops'] = general_dict['hops']

    path = f'./sample/dataset/{config_dict["subgraph_type"]}'
    data = dsm.GNNDataset(path, config_dict['subgraph_type'])[0]
    config = Config(**config_dict)
    data.train_mask, data.val_mask, data.test_mask = sd.split_train_val_test(data.center_mask)
    if not config_dict['only_center_labels']:
        data.label_mask_train, data.label_mask_val, data.label_mask_test = sd.label_masks_train_val_test(data,
                                                                                                         data.train_mask,
                                                                                                         data.val_mask,
                                                                                                         data.test_mask,
                                                                                                         config_dict[
                                                                                                             'subgraph_type'],
                                                                                                         config_dict[
                                                                                                             'hops'])
    # For non-GNN-based models, flatten graph
    if model_type in ['dt', 'rf', 'fcnn']:
        if config_dict['only_center_labels']:
            x_train, y_train, x_val, y_val, x_test, y_test = data.x[data.train_mask], data.y[data.train_mask], \
                data.x[data.val_mask], data.y[data.val_mask], \
                data.x[data.test_mask], data.y[data.test_mask]
        else:
            x_train, y_train, x_val, y_val, x_test, y_test = data.x[data.label_mask_train], data.y[
                data.label_mask_train], \
                data.x[data.label_mask_val], data.y[data.label_mask_val], \
                data.x[data.label_mask_test], data.y[data.label_mask_test]
    # Appropriate train/eval script for tree-based models, FCNN or GNNs
    if model_type in ['dt', 'rf']:
        tetree.train_and_eval_tree(x_train, y_train, x_val, y_val, x_test, y_test, config, model_name,
                                   model_type)
    elif model_type == 'fcnn':
        tefcnn.train_and_eval_fcnn(x_train, y_train, x_val, y_val, x_test, y_test, config, model_name,
                                   model_type)
    else:
        tegnn.train_and_eval_gnn(data, config, model_name, model_type)


def main(args) -> None:
    """
    Perform training for a given classifier
    """
    train(args=args)


if __name__ == "__main__":
    main()
