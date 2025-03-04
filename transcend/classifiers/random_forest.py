import numpy as np
from tqdm import tqdm
from sklearn.ensemble import RandomForestClassifier
from multiprocessing import Pool, shared_memory
from transcend.classifiers.ncm_classifier import NCMClassifier
from transcend.utils import alloc_shm, close_and_unlink_shm, load_existing_shm, close_shm

eps = np.finfo(np.float64).eps


def parall_prox(args):
    (shm_tuple, (example_idx, end_idx)) = args
    (t_leaves_shm_t, leaves_shm_t) = shm_tuple

    t_leaves = load_existing_shm(*t_leaves_shm_t)
    leaves = load_existing_shm(*leaves_shm_t)

    try:
        proximity = np.mean(
            leaves[..., np.newaxis]
            == t_leaves[:, example_idx:end_idx][np.newaxis, ...],
            axis=1,
        )
    finally:
        close_shm(t_leaves_shm_t[0])
        close_shm(leaves_shm_t[0])
        
    return proximity


class RandomForestNCMClassifier(NCMClassifier, RandomForestClassifier):
    def __init__(self, **kwargs):
        RandomForestClassifier.__init__(self, **kwargs)
        NCMClassifier.__init__(self)
        self.proximity = None
        self.train_leaves = None
        self.X_train = None
        self.y_train = None

    def __compute_proximity(self, leaves, step_size=100):
        """
        Computes the proximity between each pair of examples.
        :param leaves: A matrix of shape [num_example, num_tree] where the value [i,j] is
          the index of the leaf reached by example "i" in the tree "j".
        :param step_size: Size of the block of examples for the computation of the
          proximity. Does not impact the results.
        :return: The example pair-wise proximity matrix of shape [n,n] with "n" the number of
        examples.
        """
        example_idx = 0
        num_examples = len(self.X_train)

        t_leaves = np.transpose(self.train_leaves)
        # proximities = []

        # Instead of computing the proximity in between all the examples at the same
        # time, we compute the similarity in blocks of "step_size" examples. This
        # makes the code more efficient with the the numpy broadcast.

        ex_end_idxs = []

        while example_idx < num_examples:
            end_idx = min(example_idx + step_size, num_examples)
            ex_end_idxs.append((example_idx, end_idx))
            example_idx = end_idx

        t_leaves_shm_t = alloc_shm(t_leaves)
        leaves_shm_t = alloc_shm(leaves)

        shm_tuple = (t_leaves_shm_t, leaves_shm_t)
        with Pool(32) as p:
            try:
                proximities = p.map(parall_prox, [(shm_tuple, ex_end_idx) for ex_end_idx in ex_end_idxs])
            finally:
                close_and_unlink_shm(t_leaves_shm_t[0])
                close_and_unlink_shm(leaves_shm_t[0])

        # train_ncms_shm.name, groundtruth_train.shape, train_ncms.dtype

        # while example_idx < num_examples:
        #         end_idx = min(example_idx + step_size, num_examples)
        #         proximities.append(
        #             np.mean(
        #                 leaves[..., np.newaxis]
        #                 == t_leaves[:, example_idx:end_idx][np.newaxis, ...],
        #                 axis=1,
        #             )
        #         )
        #         example_idx = end_idx
        return np.concatenate(proximities, axis=1)

    def fit(self, X_train, y_train):
        super().fit(X_train, y_train)
        self.X_train = X_train
        self.y_train = y_train
        self.train_leaves = self.apply(X_train)
        self.proximity = self.__compute_proximity(self.train_leaves)

    def ncm(self, X, y):
        if np.array_equal(X, self.X_train):
            proximity = self.proximity
        else:
            leaves = self.apply(X)
            proximity = self.__compute_proximity(leaves)

        def single_ncm(i):
            avg_prox_diff = np.mean(np.sort(proximity[i, self.y_train != y[i]])[-5:])
            avg_prox_eq = np.mean(np.sort(proximity[i, self.y_train == y[i]])[-5:])
            return avg_prox_diff / (avg_prox_eq + eps)

        return np.array(
            [single_ncm(i) for i in tqdm(range(len(y)), total=len(y), desc="rf ncm")]
        )
