from utils.datautils import *
from torch.utils.data import DataLoader
from Models import *
import argparse
import pickle

model_func_dict = {
    'simple': simple_hyperparameter_loop,
    'm1': m1_hyperparameter_loop,
    'sdae': sdae_hyperparameter_loop,
    'm2': m2_hyperparameter_loop,
    'ladder': ladder_hyperparameter_loop,
}

parser = argparse.ArgumentParser(description='Take arguments to construct model')
parser.add_argument('model', type=str, choices=['simple', 'm1', 'sdae', 'm2', 'ladder'],
                    help="Choose which model to run")
parser.add_argument('num_labelled', type=int, help='Number of labelled examples to use')
parser.add_argument('num_folds', type=int, help='Number of folds')
parser.add_argument('mnist_name', type=str, help='Folder name output file')
args = parser.parse_args()

model_name = args.model
model_func = model_func_dict[model_name]
dataset_name = args.mnist_name
num_labelled = args.num_labelled
num_folds = args.num_folds
max_epochs = 100
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
output_path = './outputs'
results_path = '{}/{}/{}/results'.format(output_path, dataset_name, model_name)
state_path = '{}/{}/{}/state'.format(output_path, dataset_name, model_name)

if not os.path.exists(output_path):
    os.mkdir(output_path)
if not os.path.exists('{}/{}'.format(output_path, dataset_name)):
    os.mkdir('{}/{}'.format(output_path, dataset_name))
if not os.path.exists('{}/{}/{}'.format(output_path, dataset_name, model_name)):
    os.mkdir('{}/{}/{}'.format(output_path, dataset_name, model_name))
if not os.path.exists(results_path):
    os.mkdir(results_path)
if not os.path.exists(state_path):
    os.mkdir(state_path)

print('===Loading Data===')
(train_and_val_data, train_and_val_labels), (test_data, test_labels) = load_MNIST_data()
folds, label_indices = pickle.load(open('./data/MNIST/{}_labelled_{}_folds.p'.format(num_labelled, num_folds), 'rb'))
t_d = TensorDataset(test_data, test_labels)

results_dict = {}
pickle.dump(results_dict, open('{}/{}_test_results.p'.format(results_path, num_labelled), 'wb'))

for i, (train_indices, val_indices) in enumerate(folds):
    results_dict = pickle.load(open('{}/{}_test_results.p'.format(results_path, num_labelled), 'rb'))

    print('Validation Fold {}'.format(i))
    train_data = train_and_val_data[train_indices]
    train_labels = train_and_val_labels[train_indices]
    labelled_indices = label_indices[i]

    s_d = TensorDataset(train_data[labelled_indices], train_labels[labelled_indices])
    u_d = TensorDataset(train_data, train_labels)
    v_d = TensorDataset(train_and_val_data[val_indices], train_and_val_labels[val_indices])

    u_dl = DataLoader(u_d, batch_size=100, shuffle=True)
    s_dl = DataLoader(s_d, batch_size=100, shuffle=True)
    v_dl = DataLoader(v_d, batch_size=v_d.__len__())
    t_dl = DataLoader(t_d, batch_size=t_d.__len__())

    dataloaders = (u_dl, s_dl, v_dl, t_dl)

    model_name, result = model_func(i, state_path, results_path, dataset_name, dataloaders, 784, 10, max_epochs, device)

    results_dict[model_name] = result

    print('===Saving Results===')
    pickle.dump(results_dict, open('{}/{}_test_results.p'.format(results_path, num_labelled), 'wb'))
