import numpy as np
import implicit
from recommenders.recommender_base import RecommenderBase
import scipy.sparse as sps
import data
from tqdm import tqdm
import os
import utils.check_folder as cf


class AlternatingLeastSquare(RecommenderBase):
    """
    Reference: http://yifanhu.net/PUB/collaborative_filtering.pdf (PAPER)
               https://medium.com/radon-dev/als-implicit-collaborative-filtering-5ed653ba39fe (SIMPLE EXPLANATION)

    Implementation of Alternating Least Squares with implicit data. We iteratively
    compute the user (x_u) and item (y_i) vectors using the following formulas:

    x_u = ((Y.T*Y + Y.T*(Cu - I) * Y) + lambda*I)^-1 * (X.T * Cu * p(u))
    y_i = ((X.T*X + X.T*(Ci - I) * X) + lambda*I)^-1 * (Y.T * Ci * p(i))

    [link text](http://www.example.com)
    """

    def __init__(self, mode, urm_name, factors, regularization, iterations, alpha):
        os.environ['MKL_NUM_THREADS'] = '1'
        name = 'ALS urm_name: {}\n factors: {}\n regularization: {}\n ' \
                    'iterations: {}\n alpha: {}'.format(urm_name, factors, regularization, iterations, alpha)
        super(AlternatingLeastSquare, self).__init__(mode, name)

        self.factors = factors
        self.regularization = regularization
        self.iterations = iterations
        self.alpha = alpha

        self.targetids = data.target_urm_rows(self.mode)
        self.urm = data.urm(mode=mode, urm_name=urm_name)
        self.user_vecs = None
        self.item_vecs = None
        self._model = None
        self.R_hat = None

        self.fixed_params_dict = {
            'mode': mode,
            'urm_name': urm_name
        }

        self.hyperparameters_dict = {
            'factors': (50, 200),
            'regularization': (0, 1),
            'iterations': (1, 250),
            'alpha': (15, 45)
        }

    def get_r_hat(self):
        """
        compute the r_hat for the model filled with zeros in playlists not target
        :return  r_hat
        """

        if self.R_hat is None:
            print('computing the R_hat...')
            self.R_hat = np.dot(self.user_vecs[self.targetids], self.item_vecs.T)

        return self.R_hat

    def fit(self):
        """
        train the model finding the two matrices U and V: U*V.T=R  (R is the extimated URM)

        Parameters
        ----------
        :param (csr) urm: The URM matrix of shape (number_users, number_items).
        :param (int) factors: How many latent features we want to compute.
        :param (float) regularization: lambda_val regularization value
        :param (int) iterations: How many times we alternate between fixing and updating our user and item vectors
        :param (int) alpha: The rate in which we'll increase our confidence in a preference with more interactions.

        Returns
        -------
        :return (csr_matrix) user_vecs: matrix N_user x factors
        :return (csr_matrix) item_vecs: matrix N_item x factors
        """

        sparse_item_user = self.urm.T

        # Initialize the als model and fit it using the sparse item-user matrix
        os.environ['OPENBLAS_NUM_THREADS'] = '1'
        self._model = implicit.als.AlternatingLeastSquares(factors=self.factors,
                                                           regularization=self.regularization,
                                                           iterations=self.iterations)

        # Calculate the confidence by multiplying it by our alpha value.
        data_conf = (sparse_item_user * self.alpha).astype('double')

        # Fit the model
        self._model.fit(data_conf)

        # set the user and item vectors for our model R = user_vecs * item_vecs.T
        self.user_vecs = self._model.user_factors
        self.item_vecs = self._model.item_factors

    def recommend_batch(self):
        print('recommending batch')

        df_handle = data.handle_df(mode=self.mode)
        dict_col = data.dictionary_col(mode=self.mode)

        R_hat = self.get_r_hat()

        predictions = dict()

        for index, row in tqdm(df_handle.iterrows()):
            impr = list(map(int, row['impressions'].split('|')))
            # get ratings
            l = [[i, R_hat[index, dict_col[i]]] for i in impr]
            l.sort(key=lambda tup: tup[1], reverse=True)
            p = [e[0] for e in l]
            predictions[row["session_id"]] = p
        return predictions

    def save_r_hat(self):
        base_save_path = 'dataset/matrices/{}/r_hat_matrices'.format(self.mode)
        cf.check_folder(base_save_path)
        print('saving r_hat...')
        sps.save_npz('{}/{}'.format(base_save_path, self.name), self.get_r_hat())
        print('r_hat saved succesfully !')

if __name__ == '__main__':
    model = AlternatingLeastSquare(mode='small', urm_name='urm_lin', factors=250, regularization=0.3,
                                   iterations=100, alpha=25)
    model.evaluate()

