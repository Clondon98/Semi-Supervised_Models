import torch
from torch import nn
from torch.utils.data import DataLoader
from utils import Datasets, LoadData


class Classifier(nn.Module):
    def __init__(self, data_dim, hidden_dimensions, num_classes, activation):
        super(Classifier, self).__init__()
        self.fc_layers = []
        self.activation = activation
        self.fc_layers.append(nn.Linear(data_dim, hidden_dimensions[0]))

        for i in range(1, len(hidden_dimensions)):
            self.layers.append(nn.Linear(hidden_dimensions[i - 1], hidden_dimensions[i]))

        self.classification_layer = nn.Linear(hidden_dimensions[-1], num_classes)
        self.discriminator_layer = nn.Sequential(
            nn.Linear(hidden_dimensions[-1], 1),
            nn.Sigmoid(),
        )

    # TODO: return features somehow
    # maybe don't have the separation of validity? K+1 classes
    def forward(self, x):
        for layer in self.fc_layers:
            x = self.activation(layer(x))

        return self.discriminator_layer(x), self.classification_layer(x)


class Generator(nn.Module):
    def __init__(self, latent_dim, hidden_dimensions, data_dim, activation):
        super(Generator, self).__init__()

        self.fc_layers = []
        self.activation = activation
        self.fc_layers.append(nn.Linear(latent_dim, hidden_dimensions[0]))

        for i in range(1, len(hidden_dimensions)):
            self.layers.append(nn.Linear(hidden_dimensions[i - 1], hidden_dimensions[i]))

        self.output_layer = nn.Sequential(
            nn.Linear(hidden_dimensions[-1], data_dim),
            nn.Sigmoid(),
        )

        # sigmoid as assume other data has been normalized

    def forward(self, x):
        for layer in self.fc_layers:
            x = self.activation(layer(x))

        return self.output_layer(x)


class SS_GAN:
    def __init__(self, gen_hidden_dimensions, dis_hidden_dimensions, data_size, latent_size, num_classes, activation,
                 device):
        self.G = Generator(latent_size, gen_hidden_dimensions, data_size, activation).to(device)
        self.D = Classifier(data_size, dis_hidden_dimensions, num_classes, activation).to(device)
        self.G_optimizer = torch.optim.Adam(self.G.parameters(), lr=1e-3)
        self.D_optimizer = torch.optim.Adam(self.D.parameters(), lr=1e-3)
        self.num_classes = num_classes
        self.device = device
        self.latent_dim = latent_size

    def classifier_loss(self, classification_logits, real_labels):
        # loss for (xi, yi) is -log(q(xi)(j)) where yi(j) == 1 (only one element in label vector)
        # safely ignore the fake label for real supervised loss
        return nn.CrossEntropyLoss(reduction='sum')(classification_logits, real_labels)

    def discriminator_real_loss(self, prob_fake):
        # labels are 0 because we want no probability for K+1 here
        return nn.BCELoss(reduction='sum')(prob_fake, torch.zeros(prob_fake.size()))

    def discriminator_fake_loss(self, prob_fake):
        # labels are 1 because discriminator should put all these in K+1)

        # Loss function if switch back to K+1 classes
        # probs = nn.Softmax(logits)
        # return nn.BCELoss(probs[:, self.num_classes], torch.ones(probs[:, 0].size()))

        return nn.BCELoss(reduction='sum')(prob_fake, torch.ones(prob_fake.size()))

    def simple_generator_loss(self, prob_fake):
        # only calculated for fake data batches
        # labels are 0 even though data is fake as loss for generator is higher when discriminator classifies correctly
        return nn.BCELoss(reduction='sum')(prob_fake, torch.zeros(prob_fake.size()))

    def feature_matching_loss(self, real_features, fake_features):
        # not sure why they do mean then do distance
        # L = ||E_real[f(x)] - E_fake[f(x)]||**2
        real_expectation = torch.mean(real_features, dim=0)
        fake_expectation = torch.mean(fake_features, dim=0)
        distance = torch.sum((real_expectation - fake_expectation) ** 2)

        return distance

    def train_one_epoch(self, supervised_dataloader, unsupervised_dataloader):
        total_supervised_loss = 0
        total_unsupervised_loss = 0
        total_gen_loss = 0

        supervised_samples = 0
        unsupervised_samples = 0
        gen_samples = 0

        # any additional batches in the supervised or unsupervised dataloader will be ignored
        # num_batches = min(supervised_batches, unsupervised_batches)
        for i, (labeled_data, unlabeled_data) in enumerate(zip(supervised_dataloader, unsupervised_dataloader)):
            # ----------------------
            # Discriminator training
            # ----------------------
            labeled_data.to(self.device)
            unlabeled_data.to(self.device)

            self.D.train()
            self.D_optimizer.zero_grad()

            labeled_inputs, labeled_outputs = labeled_data

            supervised_samples += len(labeled_inputs)

            _, labeled_pred = self.D(labeled_inputs)

            supervised_loss = self.classifier_loss(labeled_pred, labeled_outputs)
            supervised_loss.backward()

            total_supervised_loss += supervised_loss.item()

            unsupervised_samples += len(unlabeled_data)

            unsupervised_valid, _ = self.D(unlabeled_data)

            discriminator_real_loss = self.discriminator_real_loss(unsupervised_valid)
            discriminator_real_loss.backward()

            # Half of the data is fake (same amount as supervised+unsupervised)
            gen_input = torch.randn(len(unlabeled_data) + len(labeled_inputs), 50, device=self.device)

            gen_samples += len(gen_input)

            fake = self.G(gen_input)

            fake_valid, _ = self.D(fake.detach())

            discriminator_fake_loss = self.discriminator_fake_loss(fake_valid)
            discriminator_fake_loss.backward()

            unsupervised_loss = discriminator_real_loss + discriminator_fake_loss

            total_unsupervised_loss += unsupervised_loss.item()

            self.D_optimizer.step()

            # ------------------
            # Generator training
            # ------------------

            self.G.train()
            self.G_optimizer.zero_grad()

            validity, _ = self.D(fake)

            generator_loss = self.simple_generator_loss(validity)
            generator_loss.backward()

            total_gen_loss += generator_loss.item()

            self.G_optimizer.step()

        return total_supervised_loss/supervised_samples, total_unsupervised_loss/unsupervised_samples, \
               total_gen_loss/gen_samples

    def validation(self, supervised_dataloader):
        model = self.D

        model.eval()
        validation_loss = 0

        with torch.no_grad():
            for batch_idx, (data, labels) in enumerate(supervised_dataloader):
                data.to(self.device)
                labels.to(self.device)

                _, predictions = model(data)

                loss = self.classifier_loss(predictions, labels)

                validation_loss += loss.item()

        return validation_loss/len(supervised_dataloader.dataset)

    def test(self, dataloader):
        model = self.SDAE

        model.eval()

        correct = 0

        with torch.no_grad():
            for batch_idx, (data, labels) in enumerate(dataloader):
                _, outputs = model(data)
                _, predicted = torch.max(outputs.data, 1)
                correct += (predicted == labels).sum().item()

        return correct/len(dataloader.dataset)

    def full_train(self, unsupervised_dataset, train_dataset, validation_dataset):

        # TODO: don't use arbitrary values for batch size
        unsupervised_dataloader = DataLoader(dataset=unsupervised_dataset, batch_size=256, shuffle=True)
        supervised_dataloader = DataLoader(dataset=train_dataset, batch_size=64, shuffle=True)
        validation_dataloader = DataLoader(dataset=validation_dataset, batch_size=validation_dataset.__len__())

        # simple early stopping employed (can change later)

        validation_result = float("inf")
        for epoch in range(50):

            self.train_one_epoch(supervised_dataloader, unsupervised_dataloader)
            val = self.validation(validation_dataloader)

            if val > validation_result:
                break

            validation_result = val

    def full_test(self, test_dataset):
        test_dataloader = DataLoader(dataset=test_dataset, batch_size=test_dataset.__len__())

        return self.test(test_dataloader)
