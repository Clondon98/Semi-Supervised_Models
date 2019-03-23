import torch
from torch import nn
from torch.utils.data import DataLoader
from utils.trainingutils import accuracy, unsupervised_validation_loss
from Models.BuildingBlocks import Autoencoder
from Models.Model import Model


class PretrainingNetwork(Model):
    def __init__(self, input_size, hidden_dimensions, num_classes, latent_activation, output_activation, device):
        super(PretrainingNetwork, self).__init__(device)

        self.Autoencoder = Autoencoder(input_size, hidden_dimensions, num_classes, latent_activation,
                                       output_activation).to(device)
        self.Autoencoder_optim = torch.optim.Adam(self.Autoencoder.parameters(), lr=1e-3)
        self.Autoencoder_criterion = nn.MSELoss()

        self.Classifier = self.Autoencoder.encoder
        self.Classifier_optim = torch.optim.Adam(self.Classifier.parameters(), lr=1e-3)
        self.Classifier_criterion = nn.CrossEntropyLoss()

    def train_autoencoder_one_epoch(self, dataloader, validation_dataloader):
        train_loss = 0

        for batch_idx, data in enumerate(dataloader):
            self.Autoencoder.train()

            data = data.to(self.device)

            self.Autoencoder_optim.zero_grad()

            recons = self.Autoencoder(data)

            loss = self.Autoencoder_criterion(recons, data)

            train_loss += loss.item()

            loss.backward()
            self.Autoencoder_optim.step()

            # validation_loss = unsupervised_validation_loss(self.Autoencoder, validation_dataloader,
            #                                                self.Autoencoder_criterion, self.device)

        # print('Unsupervised Loss: {} Validation Loss: {}'.format(train_loss, validation_loss))
        print('Unsupervised Loss: {}'.format(train_loss))

    def train_classifier_one_epoch(self, epoch, dataloader, validation_dataloader):
        for batch_idx, (data, labels) in enumerate(dataloader):
            self.Classifier.train()

            data = data.to(self.device)
            labels = labels.to(self.device)

            self.Classifier_optim.zero_grad()

            preds = self.Classifier(data)

            loss = self.Classifier_criterion(preds, labels)

            loss.backward()
            self.Classifier_optim.step()

            print('Epoch: {} Loss: {} Validation accuracy: {}'
                  .format(epoch, loss.item(), accuracy(self.Classifier, validation_dataloader, self.device)))

    def train(self, unsupervised_dataset, train_dataset, validation_dataset=None):
        pretraining_dataloader = DataLoader(dataset=unsupervised_dataset, batch_size=100, shuffle=True)
        supervised_dataloader = DataLoader(dataset=train_dataset, batch_size=100, shuffle=True)
        validation_dataloader = DataLoader(dataset=validation_dataset, batch_size=validation_dataset.__len__())

        for epoch in range(50):
            self.train_autoencoder_one_epoch(pretraining_dataloader, validation_dataloader)

        for epoch in range(50):
            self.train_classifier_one_epoch(epoch, supervised_dataloader, validation_dataloader)

    def test(self, test_dataset):
        test_dataloader = DataLoader(dataset=test_dataset, batch_size=test_dataset.__len__())

        return accuracy(self.Classifier, test_dataloader, self.device)
