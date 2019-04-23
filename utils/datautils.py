import os
import csv
import torch
import numpy as np
from torch.utils.data import TensorDataset
from torchvision import datasets
import pandas as pd
from enum import Enum
from math import ceil
from sklearn.model_selection import StratifiedKFold


class GaussianNormalizeTensors:
    def __init__(self):
        self.means = None
        self.stds = None

    def apply_train(self, data):
        self.means = data.mean(dim=0, keepdim=True)
        self.stds = data.std(dim=0, unbiased=False, keepdim=True)

        norm_data = (data - self.means) / (1e-7 + self.stds)

        return norm_data

    def apply_test(self, data):
        norm_data = (data - self.means) / (1e-7 + self.stds)

        return norm_data


class RangeNormalizeTensors:
    def __init__(self):
        self.maxs = None
        self.mins = None

    def apply_train(self, data):
        self.maxs = data.max(dim=0)[0]
        self.mins = data.min(dim=0)[0]

        norm_data = (data - self.mins) / (self.maxs - self.mins)

        return norm_data

    def apply_test(self, data):
        norm_data = (data - self.mins) / (self.maxs - self.mins)
        norm_data = torch.clamp(norm_data, min=0, max=1)

        return norm_data


def stratified_k_fold(data, labels, num_folds=5):
    skf = StratifiedKFold(num_folds)

    return skf.split(data, labels)


def labelled_split(data, labels, num_labelled, stratified=True):
    unique_labels, counts = np.unique(labels.numpy(), return_counts=True)
    total_samples = labels.size(0)
    num_classes = len(unique_labels)

    assert (num_labelled > num_classes)

    # shuffle tensors
    # shuffled = torch.randperm(total_samples)
    # data = data[shuffled]
    # labels = labels[shuffled]

    label_index_dict = {}

    # unstratified won't return as many labelled as expected if labelled_per_class is bigger than smallest class
    labelled_per_class = ceil(num_labelled/num_classes)
    for lab, count in zip(unique_labels, counts):
        relative = ceil((count/total_samples) * num_labelled) if stratified else labelled_per_class
        lab_indexes = (labels == lab).nonzero().squeeze(1)

        label_index_dict[lab] = lab_indexes[:relative]

    labelled_samples_len = sum(tens.size(0) for tens in label_index_dict.values())

    for i in range(labelled_samples_len - num_labelled):
        # remove one from the maximum each time
        max_key = max(label_index_dict, key=lambda x: label_index_dict[x].size(0))
        label_index_dict[max_key] = label_index_dict[max_key][:-1]

    labelled_indices = torch.cat(list(label_index_dict.values()))
    np.random.shuffle(labelled_indices.numpy())
    labelled_data = data[labelled_indices]
    labelled_labels = labels[labelled_indices]

    supervised_dataset = TensorDataset(labelled_data, labelled_labels)
    unsupervised_dataset = TensorDataset(data, -1 * torch.ones(labels.size(0)))

    return supervised_dataset, unsupervised_dataset


class ImputationType(Enum):
    DROP_SAMPLES = 1
    DROP_GENES = 2
    MEAN_VALUE = 3
    ZERO = 4


def load_tcga_data(imputation_type=ImputationType.DROP_SAMPLES):
    rnaseq_df = pd.read_csv('data/tcga/rnaseq_data_with_labels.csv', index_col=0)

    if imputation_type == ImputationType.DROP_SAMPLES:
        rnaseq_df = rnaseq_df.dropna(axis=0, how='any')
    elif imputation_type == ImputationType.DROP_GENES:
        rnaseq_df = rnaseq_df.dropna(axis=1, how='any')
    elif imputation_type == ImputationType.MEAN_VALUE:
        col_means = rnaseq_df.mean()
        rnaseq_df = rnaseq_df.fillna(col_means)
    else:
        rnaseq_df = rnaseq_df.fillna(0)

    label_count_map = dict(rnaseq_df['DISEASE'].value_counts())
    remove_labels = [k for k, v in label_count_map.items() if v < 50]

    rnaseq_df = rnaseq_df[~rnaseq_df['DISEASE'].isin(remove_labels)]

    unique_labels = rnaseq_df['DISEASE'].unique()
    string_int_label_map = dict(zip(unique_labels, range(len(unique_labels))))

    labels = torch.tensor([string_int_label_map[d] for d in rnaseq_df['DISEASE'].values]).long()
    data = torch.tensor(rnaseq_df.loc[rnaseq_df.index].drop('DISEASE', axis=1).values).float()

    # rand = torch.randperm(labels.size(0))
    # labels = labels[rand]
    # data = data[rand]

    num_classes = len(unique_labels)
    input_size = data.size(1)

    return (data, labels), input_size, num_classes


def load_MNIST_data():
    mnist_train = datasets.MNIST(root='data/MNIST', train=True, download=True, transform=None)
    mnist_test = datasets.MNIST(root='data/MNIST', train=False, download=True, transform=None)

    train_data = mnist_train.data
    train_labels = mnist_train.targets

    test_data = mnist_test.data
    test_labels = mnist_test.targets

    train_data = train_data.view(-1, 784)
    train_data = 1./255. * train_data.float()
    test_data = test_data.view(-1, 784)
    test_data = 1./255. * test_data.float()

    return (train_data, train_labels), (test_data, test_labels)


def save_results(results_list, dataset_directory, model_directory, filename):
    if not os.path.exists('results'):
        os.mkdir('results')
    if not os.path.exists('results/{}'.format(dataset_directory)):
        os.mkdir('results/{}'.format(dataset_directory))
    if not os.path.exists('results/{}/{}'.format(dataset_directory, model_directory)):
        os.mkdir('results/{}/{}'.format(dataset_directory, model_directory))

    # if os.path.exists('results/{}/{}/{}.csv'.format(dataset_directory, model_directory, filename)):
    #     os.remove('results/{}/{}/{}.csv'.format(dataset_directory, model_directory, filename))

    file = open('results/{}/{}/{}.csv'.format(dataset_directory, model_directory, filename), 'w')
    writer = csv.writer(file)

    if not isinstance(results_list, list):
        raise ValueError

    if isinstance(results_list[0], list):
        for row in results_list:
            writer.writerow(row)
    else:
        writer.writerow(results_list)

    file.close()
