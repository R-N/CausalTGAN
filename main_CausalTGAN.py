import os
import torch
import pickle
import argparse

from CausalTGAN.model.causalTGAN import CausalTGAN
from CausalTGAN.helper.feature_info import FeatureINFO
from CausalTGAN.configuration import TrainingOptions, CausalTGANConfig, CondGANConfig
from CausalTGAN.helper.utils import data_transform, load_data_graph, create_folder_for_run
from CausalTGAN.helper.trainer import train_full_knowledge, train_partial_knowledge, train_no_knowledge

def main():
    parser = argparse.ArgumentParser(description='Causal-TGAN-BN')
    parser.add_argument('--data_name', '-dn', default='adult', type=str, help='The name of dataset.')
    parser.add_argument('--device_idx', '-gpu', default=1, type=int, help='CUDA idx')

    parser.add_argument('--batch_size', '-b', default=500, type=int, help='The batch size.')
    parser.add_argument('--epochs', '-e', default=10, type=int, help='Number of epochs to run the simulation.')
    parser.add_argument('--runs_folder', '-sf', default=os.path.join('.', 'Testing'), type=str,help='The root folder where data about experiments are stored.')
    parser.add_argument('--pac_num', '-pc', default=1, type=int, help='Number of sample in one pac in pac gan')
    parser.add_argument('--z_dim', '-z', default=2, type=int, help='The length in random sample noise - exogenous variable size')
    parser.add_argument('--d_iter', '-di', default=5, type=int, help='The length in random sample noise - confounder size')
    parser.add_argument('--transformer_type', '-tt', default='ctgan', type=str, help='Type of data transformer', choices=['ctgan', 'plain', 'general'])

    parser.set_defaults()
    args = parser.parse_args()

    device = torch.device('cuda:{}'.format(args.device_idx)) if torch.cuda.is_available() else torch.device('cpu')
    exp_name = 'CausalTGAN_runs_{}'.format(args.data_name)
    this_run_folder = create_folder_for_run(args.runs_folder, exp_name)

    data, col_names, discrete_cols, causal_graph = load_data_graph(args.data_name)

    train_options = TrainingOptions(
        batch_size=args.batch_size,
        number_of_epochs=args.epochs,
        runs_folder=this_run_folder,
        experiment_name=exp_name)

    gan_config = CausalTGANConfig(causal_graph=causal_graph, z_dim=args.z_dim,
                                  pac_num=args.pac_num, D_iter=args.d_iter)

    transform_data, transformer, data_dims = data_transform(args.transformer_type, args.data_name, data, discrete_cols)
    full_feature_info = FeatureINFO(col_names, discrete_cols, data_dims)

    with open(os.path.join(this_run_folder, 'options-and-config.pickle'), 'wb+') as f:
        pickle.dump(train_options, f)
        pickle.dump(gan_config, f)

    with open(os.path.join(this_run_folder, 'causal_graph.pickle'), 'wb') as f:
        pickle.dump(causal_graph, f)

    with open(os.path.join(this_run_folder, 'transformer.pickle'), 'wb') as f:
        pickle.dump(transformer, f)

    full_knowledge_flag = True if len(causal_graph) == len(col_names) else False

    if full_knowledge_flag: # samples generated fully from CausalTGAN
        feature_info = full_feature_info
        trainer = CausalTGAN(device, gan_config, feature_info, transformer)
        train_full_knowledge(train_options, transform_data, trainer)
    else:
        if len(causal_graph) == 0: # samples generated fully from GAN
            feature_info = None
            condGAN_config = CondGANConfig(causal_graph, col_names, data_dims)

            with open(os.path.join(this_run_folder, 'condGAN-config.pickle'), 'wb') as f:
                pickle.dump(condGAN_config, f)

            trainer = CausalTGAN(device, gan_config, feature_info, transformer)
            train_no_knowledge(train_options, condGAN_config, transform_data, trainer)

        else: # samples generated by hybrid of CausalTGAN and CondGAN
            causalGAN_features = [item[0] for item in causal_graph]
            causalGAN_features_pos = full_feature_info.get_position_by_name(causalGAN_features)
            transform_data_causalGAN = transform_data[:, causalGAN_features_pos]

            col_names_partial = causalGAN_features
            discrete_cols_partial = [item for item in discrete_cols if item in causalGAN_features]
            data_dims_partial = [data_dims[i] for i in range(len(col_names)) if col_names[i] in causalGAN_features]

            feature_info = FeatureINFO(col_names_partial, discrete_cols_partial, data_dims_partial)

            condGAN_config = CondGANConfig(causal_graph, col_names, data_dims)

            with open(os.path.join(this_run_folder, 'condGAN-config.pickle'), 'wb') as f:
                pickle.dump(condGAN_config, f)

            trainer = CausalTGAN(device, gan_config, feature_info, transformer)
            train_partial_knowledge(train_options, condGAN_config, transform_data, transform_data_causalGAN, trainer)


    with open(os.path.join(this_run_folder, 'featureInfo.pickle'), 'wb') as f:
        pickle.dump(feature_info, f)


if __name__ == '__main__':
    main()
