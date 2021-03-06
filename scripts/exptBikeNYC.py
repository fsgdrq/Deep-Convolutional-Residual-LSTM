# -*- coding: utf-8 -*-
""" 
Usage:
    THEANO_FLAGS="device=gpu0" python exptBikeNYC.py
"""

import os
import pickle
import numpy as np
import math

import h5py
import keras
from keras.optimizers import Adam
from keras import losses
from keras.callbacks import EarlyStopping, ModelCheckpoint
from deepst.models.STResCNNLSTMNet3 import stresnet
from deepst.config import Config
import deepst.metrics as metrics
from deepst.datasets import BikeNYC3

np.random.seed(1337)  # for reproducibility

# parameters
# data path, you may set your own data path with the global envirmental
# variable DATAPATH
DATAPATH = Config().DATAPATH
nb_epoch = 200  # number of epoch at training stage
nb_epoch_cont = 10  # number of epoch at training (cont) stage
batch_size = 32  # batch size
T = 24  # number of time intervals in one day

lr = 0.0002  # learning rate
len_closeness = 5  # length of closeness dependent sequence
len_period = 2  # length of peroid dependent sequence
len_trend = 2  # length of trend dependent sequence
len_y = 3
nb_residual_unit = 2  # number of residual units

nb_flow = 2  # there are two types of flows: new-flow and end-flow
# divide data into two subsets: Train & Test, of which the test set is the
# last 10 days
days_test = 10
len_test = T * days_test
map_height, map_width = 16, 8  # grid size
# For NYC Bike data, there are 81 available grid-based areas, each of
# which includes at least ONE bike station. Therefore, we modify the final
# RMSE by multiplying the following factor (i.e., factor).
nb_area = 81
m_factor = math.sqrt(1. * map_height * map_width / nb_area)
print('factor: ', m_factor)
path_result = 'RET'
path_model = 'MODEL'

if os.path.isdir(path_result) is False:
    os.mkdir(path_result)
if os.path.isdir(path_model) is False:
    os.mkdir(path_model)


def build_model(external_dim):
    c_conf = (len_closeness, nb_flow, map_height,
              map_width) if len_closeness > 0 else None
    p_conf = (len_period, nb_flow, map_height,
              map_width) if len_period > 0 else None
    t_conf = (len_trend, nb_flow, map_height,
              map_width) if len_trend > 0 else None

    model = stresnet(c_conf=c_conf, p_conf=p_conf, t_conf=t_conf, len_y=len_y,
                     external_dim=external_dim, nb_residual_unit=nb_residual_unit)
    adam = Adam(lr=lr)

    model.compile(loss=losses.mean_squared_error, optimizer=adam,
                  metrics=[metrics.rmse])
    model.summary()
    # from keras.utils.visualize_util import plot
    # plot(model, to_file='model.png', show_shapes=True)
    return model


def cache(fname, X_train, Y_train, X_test, Y_test, external_dim, timestamp_train, timestamp_test):
    h5 = h5py.File(fname, 'w')
    h5.create_dataset('num', data=len(X_train))

    for i, data in enumerate(X_train):
        h5.create_dataset('X_train_%i' % i, data=data)
    # for i, data in enumerate(Y_train):
    for i, data in enumerate(X_test):
        h5.create_dataset('X_test_%i' % i, data=data)
    h5.create_dataset('Y_train', data=Y_train)
    h5.create_dataset('Y_test', data=Y_test)
    external_dim = -1 if external_dim is None else int(external_dim)
    h5.create_dataset('external_dim', data=external_dim)
    h5.create_dataset('T_train', data=timestamp_train)
    h5.create_dataset('T_test', data=timestamp_test)
    h5.close()


def read_cache(fname):
    mmn = pickle.load(open('preprocessing.pkl', 'rb'))
    f = h5py.File(fname, 'r')
    num = int(f['num'].value)
    X_train, Y_train, X_test, Y_test = [], [], [], []
    for i in range(num):
        X_train.append(f['X_train_%i' % i].value)
        X_test.append(f['X_test_%i' % i].value)
    Y_train = f['Y_train'].value
    Y_test = f['Y_test'].value
    external_dim = f['external_dim'].value
    timestamp_train = f['T_train'].value
    timestamp_test = f['T_test'].value
    f.close()
    return X_train, Y_train, X_test, Y_test, mmn, external_dim, timestamp_train, timestamp_test

def main():
    # load data
    print("loading data...")

    DATAPATH = 'E:\Pycharm_Worker\keras\DeepST-master\data\BikeNYC\CACHE'
    fname = os.path.join(DATAPATH, 'bike3_C{}_P{}_T{}.h5'.format(
        len_closeness, len_period, len_trend))
    if os.path.exists(fname) and True:
        X_train, Y_train, X_test, Y_test, mmn, external_dim, timestamp_train, timestamp_test=read_cache(fname)
    else:
        X_train, Y_train, X_test, Y_test, mmn, external_dim, timestamp_train, timestamp_test = BikeNYC3.load_data(
            T=T, nb_flow=nb_flow, len_closeness=len_closeness, len_period=len_period, len_trend=len_trend, len_y=len_y,
            len_test=len_test,
            preprocess_name='preprocessing.pkl', meta_data=True)
        cache(fname, X_train, Y_train, X_test, Y_test,
          external_dim, timestamp_train, timestamp_test)

    print("\n days (test): ", [v[:8] for v in timestamp_test[0::T]])

    # import sys
    # sys.exit(0)


    print('=' * 10)
    print("compiling model...")
    print(
        "**at the first time, it takes a few minites to compile if you use [Theano] as the backend**")
    model = build_model(external_dim)
    hyperparams_name = 'c{}.p{}.t{}.y{}.resunit{}.lr{}'.format(
        len_closeness, len_period, len_trend, len_y, nb_residual_unit, lr)
    fname_param = os.path.join('MODEL', '{}.best.h5'.format(hyperparams_name))

    early_stopping = EarlyStopping(monitor='val_rmse', patience=7, mode='min')
    model_checkpoint = ModelCheckpoint(
        fname_param, monitor='val_rmse', verbose=0, save_best_only=True, mode='min')



    print('=' * 10)
    print("training model...")
    cnm=[0]
    print(type(X_train[0]))
    print(len(X_train))
    X_train = list(X_train[0])
    print(len(X_train))
    print(X_train[0].shape)
    X_test = list(X_test[0])
    history = model.fit(X_train, Y_train,
                        nb_epoch=nb_epoch,
                        batch_size=batch_size,
                        validation_split=0.1,
                        callbacks=[early_stopping, model_checkpoint],
                        verbose=1)
    model.save_weights(os.path.join(
        'MODEL', '{}.h5'.format(hyperparams_name)), overwrite=True)
    pickle.dump((history.history), open(os.path.join(
        path_result, '{}.history.pkl'.format(hyperparams_name)), 'wb'))

    print('=' * 10)
    print('evaluating using the model that has the best loss on the valid set')

    model.load_weights(fname_param)
    score = model.evaluate(X_train, Y_train, batch_size=Y_train.shape[
                                                            0] // 48, verbose=0)
    print('Train score: %.6f rmse (norm): %.6f rmse (real): %.6f' %
          (score[0], score[1], score[1] * (mmn._max - mmn._min) / 2. * m_factor))

    score = model.evaluate(
        X_test, Y_test, batch_size=Y_test.shape[0], verbose=0)
    print('Test score: %.6f rmse (norm): %.6f rmse (real): %.6f' %
          (score[0], score[1], score[1] * (mmn._max - mmn._min) / 2. * m_factor))

    print('=' * 10)
    print("training model (cont)...")
    fname_param = os.path.join(
        'MODEL', '{}.cont.best.h5'.format(hyperparams_name))
    model_checkpoint = ModelCheckpoint(
        fname_param, monitor='rmse', verbose=0, save_best_only=True, mode='min')
    history = model.fit(X_train, Y_train, nb_epoch=nb_epoch_cont, verbose=1, batch_size=batch_size, callbacks=[
        model_checkpoint], validation_data=(X_test, Y_test))
    pickle.dump((history.history), open(os.path.join(
        path_result, '{}.cont.history.pkl'.format(hyperparams_name)), 'wb'))
    model.save_weights(os.path.join(
        'MODEL', '{}_cont.h5'.format(hyperparams_name)), overwrite=True)

    print('=' * 10)
    print('evaluating using the final model')
    score = model.evaluate(X_train, Y_train, batch_size=Y_train.shape[
                                                            0] // 48, verbose=0)
    print('Train score: %.6f rmse (norm): %.6f rmse (real): %.6f' %
          (score[0], score[1], score[1] * (mmn._max - mmn._min) / 2. * m_factor))

    score = model.evaluate(
        X_test, Y_test, batch_size=Y_test.shape[0], verbose=0)
    print('Test score: %.6f rmse (norm): %.6f rmse (real): %.6f' %
          (score[0], score[1], score[1] * (mmn._max - mmn._min) / 2. * m_factor))


if __name__ == '__main__':
    main()
