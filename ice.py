import logging
import os

import pandas as pd
from dataset.malware_dataset import MalwareDataset
from sklearn.model_selection import train_test_split
from transcend.classifiers.random_forest import RandomForestNCMClassifier

import transcend.calibration as calibration
import transcend.data as data
import transcend.scores as scores
import transcend.utils as utils


def main():
    # ---------------------------------------- #
    # 0. Prelude                               #
    # ---------------------------------------- #

    args = utils.parse_args()
    utils.configure_logger()

    logging.info("This is ICE - only compute test pvals with cal ncms")
    base_path = "/home/luca/ml-malware-concept-drift/src/notebooks/"

    # Load Full Dataset with Malware Static Features
    malware_dataset = MalwareDataset(
        split=pd.Timestamp("2021-09-03 13:47:49"),
        truncated_fam_path="truncated_samples_per_family.csv",
        truncated_threshold=7,
    )

    logging.info("Loading malw-static-features training features...")
    full_dataset_path = base_path + "clustering/1_preprocessing/X_nontrunc_norm.pickle"
    X = data.load_cached_data(full_dataset_path)

    X_train, X_test = (
        X.loc[malware_dataset.training_dataset["sha256"]],
        X.loc[malware_dataset.testing_dataset["sha256"]],
    )

    y_train, y_test = (
        malware_dataset.training_dataset["family"],
        malware_dataset.testing_dataset["family"],
    )

    all_labels = pd.concat([y_train, y_test]).unique()
    y_train = pd.Categorical(y_train, categories=all_labels).codes

    del X
    del X_test, y_test

    # Convert family labels to integers (needed for RF NCM)

    logging.info("Loaded: {}".format(X_train.shape, y_train.shape))

    test_size = 0.34

    # saved_data_folder = os.path.join('models', '{}-fold'.format(args.folds))
    saved_data_folder = os.path.join("models", "ice-malw-static-features")

    # ---------------------------------------- #
    # 1. Calibration                           #
    # ---------------------------------------- #

    logging.info("Training calibration set...")

    X_proper_train, X_cal, y_proper_train, y_cal = train_test_split(
        X_train, y_train, test_size=test_size, random_state=3
    )

    cal_results_dict = calibration.train_calibration_ice(
        X_proper_train=X_proper_train,
        X_cal=X_cal,
        y_proper_train=y_proper_train,
        y_cal=y_cal,
        fold_index="ice_{}".format(test_size),
        saved_data_folder=saved_data_folder,
    )

    cal_results_name = os.path.join(saved_data_folder, "cal_results.p")
    data.cache_data(cal_results_dict, cal_results_name)

    # ---------------------------------------- #
    # 3. Generate 'Full' Model for Deployment  #
    # ---------------------------------------- #

    # logging.info("Beginning TEST phase.")
    #
    # logging.info("Training model on full training set...")
    #
    # model_name = "rf_ice_full_train_deploy.p"
    # # --> model_name = "rf_cal_fold_ice_{}.p".format(test_size)
    #
    # model_name = os.path.join(saved_data_folder, model_name)
    #
    # rf = RandomForestNCMClassifier()
    # rf.fit(X_train, y_train)
    # data.cache_data(rf, model_name)
    #
    # # ------------------------------------------------------------------- #
    # # 4. Computing Credibility and Confidence for Concept drift detection #
    # # ------------------------------------------------------------------- #
    #
    # logging.info("Computing p-values for test ...")
    # y_test_pred = rf.predict(X_test)
    #
    # saved_data_name = "p_vals_ncms_rf_full_test.p"
    # saved_data_name = os.path.join(saved_data_folder, saved_data_name)
    #
    # # if True:
    # #     if args.pval_consider == "full-train":
    #
    # logging.info("Getting NCMs for train")
    # ncms_train = scores.get_rf_ncms(rf, X_train, y_train)
    #
    # logging.info("Getting NCMs for test")
    # ncms_test = scores.get_rf_ncms(rf, X_test, y_test_pred)
    #
    # p_val_test_dict = scores.compute_p_values_cred_and_conf(
    #     clf=rf,
    #     train_ncms=ncms_train,
    #     groundtruth_train=y_train,
    #     test_ncms=ncms_test,
    #     y_test=y_test_pred,
    #     X_test=X_test,
    # )
    # data.cache_data(p_val_test_dict, saved_data_name)


def package_cred_conf(cred_values, conf_values, criteria):
    package = {}

    if "cred" in criteria:
        package["cred"] = cred_values
    if "conf" in criteria:
        package["conf"] = conf_values

    return package


def print_thresholds(binary_thresholds):
    # Display per-class thresholds
    if "cred" in binary_thresholds:
        s = "Cred thresholds: mw {:.6f}, gw {:.6f}".format(
            binary_thresholds["cred"]["mw"], binary_thresholds["cred"]["gw"]
        )
    if "conf" in binary_thresholds:
        s = "Conf thresholds: mw {:.6f}, gw {:.6f}".format(
            binary_thresholds["conf"]["mw"], binary_thresholds["conf"]["gw"]
        )
    logging.info(s)
    return s


if __name__ == "__main__":
    main()
