import torch
from torch import nn
from torch.utils.data import DataLoader
from Models.BuildingBlocks import Autoencoder, Classifier
from Models.Model import Model
from utils.trainingutils import EarlyStopping, unsupervised_validation_loss

# --------------------------------------------------------------------------------------
# Kingma M1 model using simple autoencoder for dimensionality reduction (for comparison)
# --------------------------------------------------------------------------------------


class SimpleM1(Model):
    def __init__(self, input_size, hidden_dimensions_encoder, latent_size, hidden_dimensions_classifier,
                 num_classes, latent_activation, output_activation, device):
        super(SimpleM1, self).__init__(device)

        self.Autoencoder = Autoencoder(input_size, hidden_dimensions_encoder, latent_size, latent_activation,
                                       output_activation).to(device)
        self.Autoencoder_criterion = nn.BCELoss()
        self.Autoencoder_optim = torch.optim.Adam(self.Autoencoder.parameters(), lr=1e-3)
        self.Encoder = self.Autoencoder.encoder

        self.Classifier = Classifier(latent_size, hidden_dimensions_classifier, num_classes).to(device)
        self.Classifier_criterion = nn.CrossEntropyLoss()
        self.Classifier_optim = torch.optim.Adam(self.Classifier.parameters(), lr=1e-3)

        self.model_name = 'simple_m1'

    def train_autoencoder(self, dataset_name, train_dataloader, validation_dataloader):
        epochs = []
        train_losses = []
        validation_losses = []

        early_stopping = EarlyStopping('{}/{}_autoencoder'.format(self.model_name, dataset_name))

        epoch = 0
        while not early_stopping.early_stop:
            train_loss = 0
            validation_loss = 0
            for batch_idx, data in enumerate(train_dataloader):
                self.Autoencoder.train()

                data = data.to(self.device)

                self.Autoencoder_optim.zero_grad()

                recons = self.Autoencoder(data)

                loss = self.Autoencoder_criterion(recons, data)

                train_loss += loss.item()

                loss.backward()
                self.Autoencoder_optim.step()

                validation_loss += unsupervised_validation_loss(self.Autoencoder, validation_dataloader,
                                                                self.Autoencoder_criterion, self.device)

            train_loss /= len(train_dataloader)
            validation_loss /= len(train_dataloader)

            early_stopping(validation_loss, self.Autoencoder)

            epochs.append(epoch)
            train_losses.append(train_loss)
            validation_losses.append(validation_loss)

            print('Unsupervised Epoch: {} Loss: {} Validation loss: {}'.format(epoch, train_loss, validation_loss))

            epoch += 1

        self.Autoencoder.load_state_dict(torch.load('./Models/state/{}/{}_autoencoder.pt'
                                                    .format(self.model_name, dataset_name)))

        return epochs, train_losses, validation_losses

    def train_classifier(self, dataset_name, train_dataloader, validation_dataloader):
        epochs = []
        train_losses = []
        validation_accs = []

        early_stopping = EarlyStopping('{}/{}_classifier'.format(self.model_name, dataset_name))

        epoch = 0
        while not early_stopping.early_stop:
            for batch_idx, (data, labels) in enumerate(train_dataloader):
                self.Classifier.train()

                data = data.float().to(self.device)
                labels = labels.to(self.device)

                self.Classifier_optim.zero_grad()

                with torch.no_grad():
                    z = self.Encoder(data)

                pred = self.Classifier(z)

                loss = self.Classifier_criterion(pred, labels)

                loss.backward()
                self.Classifier_optim.step()

                validation_acc = self.accuracy(validation_dataloader)

                early_stopping(1-validation_acc, self.Classifier)

                epochs.append(epoch)
                train_losses.append(loss.item())
                validation_accs.append(validation_acc)

                print('Supervised Epoch: {} Loss: {} Validation acc: {}'.format(epoch, loss.item(), validation_acc))

            epoch += 1

        self.Classifier.load_state_dict(torch.load('./Models/state/{}/{}_classifier.pt'
                                                   .format(self.model_name, dataset_name)))

        return epochs, train_losses, validation_accs

    def accuracy(self, dataloader):
        self.Encoder.eval()
        self.Classifier.eval()

        correct = 0

        with torch.no_grad():
            for batch_idx, (data, labels) in enumerate(dataloader):
                data = data.float().to(self.device)
                labels = labels.to(self.device)

                z = self.Encoder(data)
                outputs = self.Classifier(z)
                _, predicted = torch.max(outputs.data, 1)
                correct += (predicted == labels).sum().item()

        return correct / len(dataloader.dataset)

    def train(self, dataset_name, supervised_dataloader, unsupervised_dataloader, validation_dataloader=None):
        autoencoder_epochs, autoencoder_train_losses, autoencoder_validation_losses = \
            self.train_autoencoder(dataset_name, unsupervised_dataloader, validation_dataloader)

        classifier_epochs, classifier_losses, classifier_accs = \
            self.train_classifier(dataset_name, supervised_dataloader, validation_dataloader)

        return classifier_epochs, classifier_losses, classifier_accs

    def test(self, test_dataloader):
        return self.accuracy(test_dataloader)