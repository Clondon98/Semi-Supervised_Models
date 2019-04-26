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
parser.add_argument('--imputation_type', type=str, choices=[i.name.lower() for i in ImputationType],
                    default='drop_samples')
args = parser.parse_args()

model_name = args.model
model_func = model_func_dict[model_name]
imputation_string = args.imputation_type.upper()
imputation_type = ImputationType[imputation_string]
dataset_name = 'tcga'
num_labelled = args.num_labelled
num_folds = args.num_folds
max_epochs = 200
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
(data, labels), (input_size, num_classes) = load_tcga_data(imputation_type)
str_drop = 'drop_samples' if imputation_type == ImputationType.DROP_SAMPLES else 'no_drop'
folds, labelled_indices, val_test_split = pickle.load(open('./data/tcga/{}_labelled_{}_folds_{}.p'
                                                           .format(num_labelled, num_folds, str_drop), 'rb'))

results_dict = {}
pickle.dump(results_dict, open('{}/{}_{}_test_results.p'.format(results_path, imputation_string, num_labelled), 'wb'))

for i, (train_indices, test_val_indices) in enumerate(folds):
    print('Validation Fold {}'.format(i))
    results_dict = pickle.load(open('{}/{}_{}_test_results.p'.format(results_path, imputation_string, num_labelled),
                                    'rb'))

    normalizer = RangeNormalizeTensors()
    train_data = normalizer.apply_train(data[train_indices])
    train_labels = labels[train_indices]
    labelled_data = train_data[labelled_indices[i]]
    labelled_labels = train_labels[labelled_indices[i]]

    s_d = TensorDataset(labelled_data, labelled_labels)
    u_d = TensorDataset(train_data, -1 * torch.ones(train_labels.size(0)))

    test_val_data = normalizer.apply_test(data[test_val_indices])
    test_val_labels = labels[test_val_indices]

    val_indices, test_indices = val_test_split[i]

    v_d = TensorDataset(test_val_data[val_indices], test_val_labels[val_indices])
    t_d = TensorDataset(test_val_data[test_indices], test_val_labels[test_indices])

    u_dl = DataLoader(u_d, batch_size=100, shuffle=True)
    s_dl = DataLoader(s_d, batch_size=100, shuffle=True)
    v_dl = DataLoader(v_d, batch_size=v_d.__len__())
    t_dl = DataLoader(t_d, batch_size=t_d.__len__())

    dataloaders = (u_dl, s_dl, v_dl, t_dl)

    model_name, result = model_func(i, state_path, results_path, dataset_name, dataloaders, input_size, num_classes,
                                    max_epochs, device)

    results_dict[model_name] = result

    print('===Saving Results===')
    pickle.dump(results_dict, open('{}/{}_{}_test_results.p'.format(results_path, imputation_string, num_labelled), 'wb'))
