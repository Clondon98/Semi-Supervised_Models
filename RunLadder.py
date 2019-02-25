import torch
from Models.Ladder import LadderNetwork
from utils import LoadData, Datasets, Arguments, KFoldSplits, SaveResults


def MNIST_train(device):

    unsupervised_dataset, supervised_dataset, validation_dataset, test_dataset = \
        LoadData.load_MNIST_data(100, 10000, 10000, 49000)

    combined_dataset = Datasets.MNISTUnsupervised(torch.cat((unsupervised_dataset.data, supervised_dataset.data), 0))

    results = []
    for i in range(5):
        ladder = LadderNetwork(784, [1000, 500, 250, 250, 250], 10, ['relu', 'relu', 'relu', 'relu', 'relu', 'softmax'],
                               0.2, [1000, 10, 0.1, 0.1, 0.1, 0.1, 0.1], device)

        print(ladder.Ladder)

        ladder.full_train(combined_dataset, supervised_dataset, validation_dataset)

        results.append(ladder.full_test(test_dataset))

    SaveResults.save_results(results, 'ladder', 'MNIST_accuracy')


def file_train(device):

    args = Arguments.parse_args()

    unsupervised_data, supervised_data, supervised_labels = LoadData.load_data_from_file(
        args.unsupervised_file, args.supervised_data_file, args.supervised_labels_file)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    ladder = LadderNetwork(784, [1000, 500, 250, 250, 250], 10, ['relu', 'relu', 'relu', 'relu', 'relu', 'softmax'],
                               0.2, [1000, 10, 0.1, 0.1, 0.1, 0.1, 0.1], device)

    test_results = []
    for test_idx, train_idx in KFoldSplits.k_fold_splits(len(supervised_data), 10):
        train_dataset = Datasets.SupervisedClassificationDataset([supervised_data[i] for i in train_idx],
                                                                 [supervised_labels[i] for i in train_idx])
        test_dataset = Datasets.SupervisedClassificationDataset([supervised_data[i] for i in test_idx],
                                                                [supervised_labels[i] for i in test_idx])

        ladder.full_train(train_dataset)

        correct_percentage = ladder.full_test(test_dataset)

        test_results.append(correct_percentage)

    SaveResults.save_results([test_results], 'ladder', 'accuracy')


if __name__ == '__main__':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    MNIST_train(device)
