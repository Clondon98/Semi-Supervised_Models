import os
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
import argparse
from utils.datautils import *
from Models import *
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
state_path = './Models/state'
results_path = './results'

hyperparameter_fns = {
    'simple': simple_hyperparameter_loop,
    'sdae': sdae_hyperparameter_loop,
    'ladder': ladder_hyperparameter_loop,
}

construction_fns = {
    'simple': simple_constructor,
    'sdae': sdae_constructor,
    'ladder': ladder_constructor,
}


def main():
    parser = argparse.ArgumentParser(description='Take arguments to construct model')
    parser.add_argument('model', type=str,
                        choices=['simple', 'pretraining', 'sdae', 'simple_m1', 'm1', 'm2', 'ladder'],
                        help="Choose which model to run"
                        )
    parser.add_argument('dataset', type=str, choices=['mnist', 'tcga', 'metabric'], help='Dataset to run on')
    parser.add_argument('num_labelled', type=int)
    parser.add_argument('--num_folds', type=int, default=5)

    args = parser.parse_args()

    model_name = args.model
    hyperparameter_optimizer = hyperparameter_fns[model_name]
    constructor = construction_fns[model_name]

    if not os.path.exists(state_path):
        os.mkdir(state_path)
    if not os.path.exists('{}/{}'.format(state_path, model_name)):
        os.mkdir('{}/{}'.format(state_path, model_name))
    if not os.path.exists(results_path):
        os.mkdir(results_path)
    if not os.path.exists('{}/{}'.format(results_path, model_name)):
        os.mkdir('{}/{}'.format(results_path, model_name))

    dataset_name = args.dataset
    num_folds = args.num_folds
    fold_accuracies = []

    if dataset_name == 'mnist':
        open('./results/{}/{}_{}labelled_hyperparameter_train.csv'.format(model_name, dataset_name, args.num_labelled),
             'w').close()

        for i in range(num_folds):
            u_d, s_d, v_d, t_d = load_MNIST_data(args.num_labelled, 50000, True, True)

            u_dl = DataLoader(u_d, batch_size=100, shuffle=True)
            s_dl = DataLoader(s_d, batch_size=100, shuffle=True)
            v_dl = DataLoader(v_d, batch_size=v_d.__len__())
            t_dl = DataLoader(t_d, batch_size=t_d.__len__())

            accuracies, parameter_dict = hyperparameter_optimizer(dataset_name, (u_dl, s_dl, v_dl), 784, 10, device)

            index = accuracies.index(max(accuracies))

            model = constructor(parameter_dict[index])

            model.train_model(100, (u_dl, s_dl, v_dl), False)

            fold_accuracies.append(model.test_model(t_dl))

    elif dataset_name == 'tcga':
        (data, labels), input_size, num_classes = load_tcga_data()

        open('./results/{}/{}_{}labelled_hyperparameter_train.csv'.format(model_name, dataset_name, args.num_labelled),
             'w').close()

        for train_indices, val_and_test_indices in stratified_k_fold(data, labels, num_folds=num_folds):
            s_d, u_d = \
                labelled_split(data[train_indices], labels([train_indices]), num_labelled=args.num_labelled)

            val_and_test_data = data[val_and_test_indices]
            val_and_test_labels = labels[val_and_test_indices]
            val_indices, test_indices = next(stratified_k_fold(val_and_test_data, val_and_test_labels,
                                                               num_folds=2))
            v_d = TensorDataset(val_and_test_data[val_indices], val_and_test_labels[val_indices])
            t_d = TensorDataset(val_and_test_data[test_indices], val_and_test_labels[test_indices])

            u_dl = DataLoader(u_d, batch_size=100, shuffle=True)
            s_dl = DataLoader(s_d, batch_size=100, shuffle=True)
            v_dl = DataLoader(v_d, batch_size=v_d.__len__())
            t_dl = DataLoader(t_d, batch_size=t_d.__len__())

            accuracies, parameter_dict = hyperparameter_optimizer(dataset_name, (u_dl, s_dl, v_dl), input_size,
                                                                  num_classes, device)

            index = accuracies.index(max(accuracies))

            model = constructor(parameter_dict[index])

            model.train_model(100, (u_dl, s_dl, v_dl), False)

            fold_accuracies.append(model.test_model(t_dl))

    save_results(fold_accuracies, dataset_name, model_name, '{}_fold_accuracies'.format(num_folds))


if __name__ == '__main__':
    main()
