import os
import math
import pandas as pd
import numpy as np

from generator import DataGenerator
import preprocess_utils.session2vec as sess2vec
from sklearn.preprocessing import MinMaxScaler

## ======= Datasets - Base class ======= ##

class Dataset(object):
    """ Base class containing all info about a dataset """

    def __init__(self, dataset_path):
        # load the dataset config file
        import utils.datasetconfig as datasetconfig
        data = datasetconfig.load_config(dataset_path)
        if data is None:
            return

        self.dataset_path = dataset_path
        self.mode = data['mode']
        self.cluster = data['cluster']
        # file names
        self.Xtrain_name = data['Xtrain_name']
        self.Ytrain_name = data['Ytrain_name']
        self.Xtest_name = data['Xtest_name']
        # data shapes
        self.train_len = data['train_len']
        self.test_len = data['test_len']
        self.rows_per_sample = data['rows_per_sample']
        # sparsity info
        self.X_sparse_columns = data['X_sparse_columns']
        self.Y_sparse_columns = data['Y_sparse_columns']
    
        # paths
        self.X_train_path = os.path.join(self.dataset_path, self.Xtrain_name)
        self.Y_train_path = os.path.join(self.dataset_path, self.Ytrain_name)
        self.X_test_path = os.path.join(self.dataset_path, self.Xtest_name)
    
    # load data

    def load_Xtrain(self):
        return pd.read_csv(self.X_train_path).values

    def load_Ytrain(self):
        return pd.read_csv(self.Y_train_path).values

    def load_Xtest(self):
        return pd.read_csv(self.X_test_path).values

    def get_train_validation_generator(self, validation_percentage=0.15):
        pass
    
    def get_test_generator(self):
        pass



## ======= Datasets ======= ##

class SequenceDataset(Dataset):

    def _preprocess_x_df(self, X_df, partial, fillNaN=0, return_indices=False):
        """ Preprocess the loaded data (X)
        partial (bool): True if X_df is a chunk of the entire file
        return_indices (bool): True to return the indices of the rows (useful at prediction time)
        """
        X_df = X_df.fillna(fillNaN)

        # add day of year column
        X_df.timestamp = pd.to_datetime(X_df.timestamp, unit='s')
        X_df['dayofyear'] = X_df.timestamp.dt.dayofyear

        cols_to_drop_in_X = ['user_id','session_id','timestamp','step','platform','city','current_filters']
        
        # scale the dataframe
        if partial:
            X_df.dayofyear /= 365
            X_df.impression_price /= 3000
        else:
            scaler = MinMaxScaler()
            X_df.loc[:,~X_df.columns.isin(cols_to_drop_in_X)] = scaler.fit_transform(
                X_df.drop(cols_to_drop_in_X, axis=1).values)

        return sess2vec.sessions2tensor(X_df, drop_cols=cols_to_drop_in_X, return_index=return_indices)

    def _preprocess_y_df(self, Y_df, fillNaN=0):
        """ Preprocess the loaded data (Y) """
        Y_df = Y_df.fillna(fillNaN)
        cols_to_drop_in_Y = ['session_id','user_id','timestamp','step']
        return sess2vec.sessions2tensor(Y_df, drop_cols=cols_to_drop_in_Y)


    def load_Xtrain(self):
        X_train_df = pd.read_csv(self.X_train_path, index_col=0)
        X_train_df = self._preprocess_x_df(X_train_df, partial=False)
        print('X_train:', X_train_df.shape)
        return X_train_df

    def load_Ytrain(self):
        Y_train_df = pd.read_csv(self.Y_train_path, index_col=0)
        Y_train_df = self._preprocess_y_df(Y_train_df)
        print('Y_train:', Y_train_df.shape)
        return Y_train_df

    def load_Xtest(self):
        X_test_df = pd.read_csv(self.X_test_path, index_col=0)
        X_test_df, indices = self._preprocess_x_df(X_test_df, partial=False, return_indices=True)
        print('X_test:', X_test_df.shape)
        return X_test_df, indices

    def get_train_validation_generator(self, validation_percentage=0.15, sessions_per_batch=500, use_weights=True):
        # return the generator for the train and optionally the one for validation (set to 0 to skip validation)
        def prefit(Xchunk_df, Ychunk_df, index):
            """ Preprocess a chunk of the sequence dataset """
            Xchunk_df = self._preprocess_x_df(Xchunk_df, partial=True)
            Ychunk_df = self._preprocess_y_df(Ychunk_df)
            
            if use_weights:
                # weight only the last interaction (clickout item)
                weights = np.zeros(Xchunk_df.shape[:2])
                weights[:,-1] = 1
                return Xchunk_df, Ychunk_df, weights
            else:
                return Xchunk_df, Ychunk_df

        tot_sessions = int(self.train_len / self.rows_per_sample)
        number_of_validation_sessions = int(tot_sessions * validation_percentage)
        number_of_train_sessions = tot_sessions - number_of_validation_sessions
        validation_rows = number_of_validation_sessions * self.rows_per_sample

        batches_in_train = math.ceil(number_of_train_sessions / sessions_per_batch)
        batches_in_val = math.ceil(number_of_validation_sessions / sessions_per_batch)

        train_gen = DataGenerator(self.dataset_path, pre_fit_fn=prefit, samples_per_batch=sessions_per_batch,
                                 batches_per_epoch=batches_in_train)
        val_gen = DataGenerator(self.dataset_path, pre_fit_fn=prefit, samples_per_batch=sessions_per_batch,
                                batches_per_epoch=batches_in_val, skip_rows=validation_rows)

        return train_gen, val_gen


    def get_test_generator(self):
        # return the generator for the test
        def prefit(Xchunk_df, index):
            """ Preprocess a chunk of the sequence dataset """
            Xchunk_df = self._preprocess_x_df(Xchunk_df, partial=True)
            
            return Xchunk_df

        return DataGenerator(self.dataset_path, for_train=False, pre_fit_fn=prefit)
