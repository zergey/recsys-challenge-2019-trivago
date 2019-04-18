from extract_features.feature_base import FeatureBase
import data
import pandas as pd
from tqdm.auto import tqdm
tqdm.pandas()


class SessionFilterActiveWhenClickout(FeatureBase):

    """
    filter active at the moment of the clickout:
    | user_id | session_id | filter_active_when_clickout
    filter_active_when_clickout is string, in the format: filter1 | filter2 | filter3 ...
    """

    def __init__(self, mode, cluster='no_cluster'):
        name = 'filter_active_when_clickout'
        columns_to_onehot = [('filter_active_when_clickout', 'multiple')]
        super(SessionFilterActiveWhenClickout, self).__init__(
            name=name, mode=mode, cluster=cluster)

    def extract_feature(self):

        import math
        def func(x):
            y = x[(x['action_type'] == 'clickout item')]
            if len(y) > 0:
                t = y.tail(1)
                if isinstance(t.current_filters, str):
                    return 'no_filter_active_when_clickout'
                else:
                    return t.current_filters

        train = data.train_df(mode=self.mode, cluster=self.cluster)
        test = data.test_df(mode=self.mode, cluster=self.cluster)
        df = pd.concat([train, test])
        s = df.groupby(['user_id', 'session_id']).progress_apply(func)
        return pd.DataFrame({'user_id':[x[0] for x in s.index.values], 'session_id':[x[1] for x in s.index.values], 'filter_active_when_clickout': s.values})

if __name__ == '__main__':
    c = SessionFilterActiveWhenClickout(mode='small', cluster='no_cluster')
    c.save_feature()
