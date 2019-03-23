import torch
from torch import nn
from Models.PretrainingNetwork_new import PretrainingNetwork
from utils import arguments, datautils


def MNIST_train(device):
    unsupervised_dataset, supervised_dataset, validation_dataset, test_dataset = \
        datautils.load_MNIST_data(100, 50000, True, True)

    results = []
    for i in range(5):
        deep_metabolism = PretrainingNetwork(784, [1000, 500, 250, 250, 250], 10, lambda x: x, nn.Sigmoid(), device)

        print(deep_metabolism.Autoencoder)

        deep_metabolism.train(unsupervised_dataset, supervised_dataset, validation_dataset)

        results.append(deep_metabolism.test(test_dataset))

    datautils.save_results(results, 'deep_metabolism', 'MNIST_accuracy')


def file_train(device):

    # TODO: this is all wrong
    args = arguments.parse_args()

    unsupervised_data, supervised_data, supervised_labels = datautils.load_data_from_file(
        args.unsupervised_file, args.supervised_data_file, args.supervised_labels_file)

    deep_metabolism = PretrainingNetwork(500, [200], 10, nn.ReLU(), device)

    test_results = []
    for test_idx, train_idx in datautils.k_fold_splits(len(supervised_data), 10):
        train_dataset = datautils.SupervisedClassificationDataset([supervised_data[i] for i in train_idx],
                                                                  [supervised_labels[i] for i in train_idx])
        test_dataset = datautils.SupervisedClassificationDataset([supervised_data[i] for i in test_idx],
                                                                 [supervised_labels[i] for i in test_idx])

        deep_metabolism.train(train_dataset)

        correct_percentage = deep_metabolism.test(test_dataset)

        test_results.append(correct_percentage)

    datautils.save_results([test_results], 'deep_metabolism', 'blah')


if __name__ == '__main__':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    MNIST_train(device)
