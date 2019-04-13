import torch
from torch import nn
from Models.BuildingBlocks import Classifier
from Models.Model import Model
from utils.trainingutils import accuracy, EarlyStopping
import csv


class SimpleNetwork(Model):
    def __init__(self, input_size, hidden_dimensions, num_classes, lr, dataset_name, device):
        super(SimpleNetwork, self).__init__(dataset_name, device)

        self.Classifier = Classifier(input_size, hidden_dimensions, num_classes).to(device)
        self.optimizer = torch.optim.Adam(self.Classifier.parameters(), lr=1e-3)
        self.criterion = nn.CrossEntropyLoss()

        self.model_name = 'simple'

    def train_classifier(self, max_epochs, train_dataloader, validation_dataloader, comparison):
        epochs = []
        train_losses = []
        validation_accs = []

        early_stopping = EarlyStopping('{}/{}.pt'.format(self.model_name, self.dataset_name))

        print(accuracy(self.Classifier, validation_dataloader, self.device))
        for epoch in range(max_epochs):
            if early_stopping.early_stop:
                break

            for batch_idx, (data, labels) in enumerate(train_dataloader):
                self.Classifier.train()

                data = data.to(self.device)
                labels = labels.to(self.device)

                self.optimizer.zero_grad()

                preds = self.Classifier(data)

                loss = self.criterion(preds, labels)

                loss.backward()
                self.optimizer.step()

                if comparison:
                    epochs.append(epoch)
                    train_losses.append(loss.item())
                    validation_accs.append(accuracy(self.Classifier, validation_dataloader, self.device))

            val = accuracy(self.Classifier, validation_dataloader, self.device)

            print('Supervised Epoch: {} Validation acc: {}'.format(epoch, val))

            early_stopping(1 - val, self.Classifier)

        if early_stopping.early_stop:
            early_stopping.load_checkpoint(self.Classifier)

        return epochs, train_losses, validation_accs

    def train_model(self, max_epochs, dataloaders, comparison):
        supervised_dataloader, validation_dataloader = dataloaders

        epochs, losses, validation_accs = self.train_classifier(max_epochs, supervised_dataloader,
                                                                validation_dataloader, comparison)

        return epochs, losses, validation_accs

    def test_model(self, test_dataloader):
        return accuracy(self.Classifier, test_dataloader, self.device)

    def classify(self, data):
        self.Classifier.eval()

        return self.forward(data)

    def forward(self, data):
        return self.Classifier(data.to(self.device))


def hyperparameter_loop(dataset_name, dataloaders, input_size, output_size, device):
    learning_rates = [0.1, 0.01, 0.001]
    hidden_layer_size = max(1024, (input_size + output_size)//2)
    hidden_layers = range(1, 4)
    unsupervised, supervised, validation, test = dataloaders
    num_labelled = len(supervised.dataset)

    f = open('./results/simple/{}_{}labelled_hyperparameter_train.csv'.format(dataset_name, num_labelled), 'a')
    writer = csv.writer(f)

    for lr in learning_rates:
        for h in hidden_layers:
            model = SimpleNetwork(input_size, [hidden_layer_size] * h, output_size, lr, dataset_name, device)
            model.train_model(100, (supervised, validation), False)
            test_result = model.test_model(test)

            writer.writerow([lr, hidden_layer_size, h, test_result])

    f.close()
