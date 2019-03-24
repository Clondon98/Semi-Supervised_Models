import torch
from torch import nn
from torch.nn import functional as F
from Models.BuildingBlocks import VAE, Classifier
from Models.Model import Model
from utils.trainingutils import EarlyStopping, unsupervised_validation_loss


class M1(Model):
    def __init__(self, input_size, hidden_dimensions_encoder, latent_size, hidden_dimensions_classifier,
                 num_classes, output_activation, dataset_name, device):
        super(M1, self).__init__(dataset_name, device)

        self.VAE = VAE(input_size, hidden_dimensions_encoder, latent_size, output_activation).to(device)
        self.VAE_optim = torch.optim.Adam(self.VAE.parameters(), lr=1e-3)
        self.Encoder = self.VAE.encoder

        self.Classifier = Classifier(latent_size, hidden_dimensions_classifier, num_classes).to(device)
        self.Classifier_criterion = nn.CrossEntropyLoss(reduction='sum')
        self.Classifier_optim = torch.optim.Adam(self.Classifier.parameters(), lr=1e-3)

        self.model_name = 'm1'

    def VAE_criterion(self, batch_params, x):
        # KL divergence between two normal distributions (N(0, 1) and parameterized)
        recons, mu, logvar = batch_params

        KLD = 0.5*torch.sum(logvar.exp() + mu.pow(2) - logvar - 1, dim=1)

        # reconstruction error (use BCE because we normalize input data to [0, 1] and sigmoid output)
        BCE = F.binary_cross_entropy(recons, x, reduction='none').sum(dim=1)

        # TODO: change BCE depending on what the ouput activation is
        # if not necessarily 0-1 normalised
        # BCE = nn.MSELoss(reduction='sum')(pred_x, x)

        return (KLD + BCE).mean()

    def train_VAE(self, train_dataloader, validation_dataloader):
        epochs = []
        train_losses = []
        validation_losses = []

        early_stopping = EarlyStopping('{}/{}_autoencoder'.format(self.model_name, self.dataset_name), patience=7)

        epoch = 0
        while not early_stopping.early_stop:
            train_loss = 0
            validation_loss = 0
            for batch_idx, (data, _) in enumerate(train_dataloader):
                self.VAE.train()

                data = data.to(self.device)

                self.VAE_optim.zero_grad()

                batch_params = self.VAE(data)

                loss = self.VAE_criterion(batch_params, data)

                train_loss += loss.item()

                loss.backward()
                self.VAE_optim.step()

                validation_loss = unsupervised_validation_loss(self.VAE, validation_dataloader, self.VAE_criterion,
                                                               self.device)

            early_stopping(validation_loss, self.VAE)

            epochs.append(epoch)
            train_losses.append(train_loss)
            validation_losses.append(validation_loss)

            print('Unsupervised Epoch: {} Loss: {} Validation loss: {}'.format(epoch, train_loss, validation_loss))

            epoch += 1

        early_stopping.load_checkpoint(self.VAE)

        return epochs, train_losses, validation_losses

    def train_classifier(self, train_dataloader, validation_dataloader):
        epochs = []
        train_losses = []
        validation_accs = []

        early_stopping = EarlyStopping('{}/{}_classifier'.format(self.model_name, self.dataset_name))

        epoch = 0
        while not early_stopping.early_stop:
            for batch_idx, (data, labels) in enumerate(train_dataloader):
                self.Classifier.train()

                data = data.to(self.device)
                labels = labels.to(self.device)

                self.Classifier_optim.zero_grad()

                with torch.no_grad():
                    z, _, _ = self.Encoder(data)

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

        early_stopping.load_checkpoint(self.Classifier)

        return epochs, train_losses, validation_accs

    def accuracy(self, dataloader):
        self.Encoder.eval()
        self.Classifier.eval()

        correct = 0

        with torch.no_grad():
            for batch_idx, (data, labels) in enumerate(dataloader):
                data = data.to(self.device)
                labels = labels.to(self.device)

                z, _, _ = self.Encoder(data)
                outputs = self.Classifier(z)
                _, predicted = torch.max(outputs.data, 1)
                correct += (predicted == labels).sum().item()

        return correct / len(dataloader.dataset)

    def train(self, supervised_dataloader, unsupervised_dataloader, validation_dataloader=None):
        autoencoder_epochs, autoencoder_train_losses, autoencoder_validation_losses = \
            self.train_VAE(unsupervised_dataloader, validation_dataloader)

        classifier_epochs, classifier_losses, classifier_accs = \
            self.train_classifier(supervised_dataloader, validation_dataloader)

        return classifier_epochs, classifier_losses, classifier_accs

    def test(self, test_dataloader):
        return self.accuracy(test_dataloader)
