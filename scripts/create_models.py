#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--seed', '-s', type=str)
parser.add_argument('--dataset_backend', '-d', type=str, default='lmdb')
parser.add_argument('--crop_size', '-c', type=int, default=64)
parser.add_argument('--batch_size', '-b', type=int, default=128)
args = parser.parse_args()
print args

dataset = args.dataset_backend
crop_size = args.crop_size
batch_size = args.batch_size


def data_layer(number, bottom, object_type):
    return '''layer {{
  name: "input_data"
  type: "Data"
  top: "input_data"
  data_param {{
    backend: LMDB
    source: "../../data/mass_{object_type}/{dataset}/train_sat.lmdb"
    batch_size: {batch_size}
  }}
  include: {{ phase: TRAIN }}
}}
layer {{
  name: "input_label"
  type: "Data"
  top: "input_label"
  data_param {{
    backend: LMDB
    source: "../../data/mass_{object_type}/{dataset}/train_map.lmdb"
    batch_size: {batch_size}
  }}
  include: {{ phase: TRAIN }}
}}
layer {{
  name: "input_data"
  type: "Data"
  top: "input_data"
  data_param {{
    backend: LMDB
    source: "../../data/mass_{object_type}/{dataset}/test_sat.lmdb"
    batch_size: {batch_size}
  }}
  include: {{ phase: TEST }}
}}
layer {{
  name: "input_label"
  type: "Data"
  top: "input_label"
  data_param {{
    backend: LMDB
    source: "../../data/mass_{object_type}/{dataset}/test_map.lmdb"
    batch_size: {batch_size}
  }}
  include: {{ phase: TEST }}
}}'''.format(object_type=object_type,
             dataset=dataset,
             batch_size=batch_size)


def augment_layer(number, bottom, stddev0, stddev1, stddev2):
    return '''layer {{
  name: "augment{number}"
  type: "Augment"
  bottom: "input_data"
  bottom: "input_label"
  top: "augment{number}"
  top: "label"
  augment_param {{
    # common
    rotate: true
    flip: true
    # data
    crop_size: {crop_size}
    binarize: false
    mean_normalize: true
    divide: {stddev0}
    divide: {stddev1}
    divide: {stddev2}
    # label
    crop_size: 16
    binarize: true
  }}
  include: {{ phase: TRAIN }}
}}
layer {{
  name: "augment{number}"
  type: "Augment"
  bottom: "input_data"
  bottom: "input_label"
  top: "augment{number}"
  top: "label"
  augment_param {{
    # data
    crop_size: {crop_size}
    binarize: false
    mean_normalize: true
    divide: {stddev0}
    divide: {stddev1}
    divide: {stddev2}
    # label
    crop_size: 16
    binarize: true
  }}
  include: {{ phase: TEST }}
}}'''.format(crop_size=crop_size,
             number=number,
             stddev0=stddev0,
             stddev1=stddev1,
             stddev2=stddev2)


def predict_augment_layer(number, bottom, stddev0, stddev1, stddev2):
    return '''layer {{
  name: "augment{number}"
  type: "Augment"
  bottom: "input_data"
  top: "augment{number}"
  augment_param {{
    # data
    crop_size: {crop_size}
    binarize: false
    mean_normalize: true
    divide: {stddev0}
    divide: {stddev1}
    divide: {stddev2}
  }}
}}'''.format(crop_size=crop_size,
             number=number,
             stddev0=stddev0,
             stddev1=stddev1,
             stddev2=stddev2)


def conv_layer(number, bottom, num_output, kernel_size, stride):
    return '''layer {{
  name: "conv{number}"
  type: "Convolution"
  bottom: "{bottom}"
  top: "conv{number}"
  convolution_param {{
    num_output: {num_output}
    kernel_size: {kernel_size}
    stride: {stride}
    weight_filler {{
      type: "xavier"
    }}
    bias_filler {{
      type: "constant"
    }}
  }}
}}'''.format(number=number,
             bottom=bottom,
             num_output=num_output,
             kernel_size=kernel_size,
             stride=stride)


def maxout_layer(number, bottom):
    return '''layer {{
  name: "slice{number}"
  type: "Slice"
  bottom: "{bottom}"
  top: "slice{number}1"
  top: "slice{number}2"
  top: "slice{number}3"
  top: "slice{number}4"
  slice_param {{
    slice_dim: 1
  }}
}}
layer {{
  name: "maxout{number}"
  type: "Eltwise"
  bottom: "slice{number}1"
  bottom: "slice{number}2"
  bottom: "slice{number}3"
  bottom: "slice{number}4"
  top: "maxout{number}"
  eltwise_param {{
    operation: MAX
  }}
}}'''.format(number=number,
             bottom=bottom)


def pool_layer(number, bottom, kernel_size, stride):
    return '''layer {{
  name: "pool{number}"
  type: "Pooling"
  bottom: "{bottom}"
  top: "pool{number}"
  pooling_param {{
    pool: MAX
    kernel_size: {kernel_size}
    stride: {stride}
  }}
}}'''.format(number=number,
             bottom=bottom,
             kernel_size=kernel_size,
             stride=stride)


def bn_layer(number, bottom, scale, shift):
    return '''layer {{
  name: "bn{number}"
  type: "BN"
  bottom: "{bottom}"
  top: "bn{number}"
  param {{
    lr_mult: 1.00001
    decay_mult: 0
  }}
  param {{
    lr_mult: 1.00001
    decay_mult: 0
  }}
  bn_param {{
    scale_filler {{
      type: "constant"
      value: {scale}
    }}
    shift_filler {{
      type: "constant"
      value: {shift}
    }}
  }}
}}'''.format(number=number,
             bottom=bottom,
             scale=scale,
             shift=shift)


def fc_layer(number, bottom, num_output):
    return '''layer {{
  name: "fc{number}"
  type: "InnerProduct"
  bottom: "{bottom}"
  top: "fc{number}"
  inner_product_param {{
    num_output: {num_output}
    weight_filler {{
      type: "xavier"
    }}
    bias_filler {{
      type: "constant"
    }}
  }}
}}'''.format(number=number,
             bottom=bottom,
             num_output=num_output)


def relu_layer(number, bottom):
    return '''layer {{
  name: "relu{number}"
  type: "ReLU"
  bottom: "{bottom}"
  top: "relu{number}"
}}'''.format(number=number,
             bottom=bottom)


def dropout_layer(number, bottom):
    return '''layer {{
  name: "dropout{number}"
  type: "Dropout"
  bottom: "{bottom}"
  top: "dropout{number}"
  dropout_param {{
     dropout_ratio: 0.5
  }}
}}'''.format(number=number,
             bottom=bottom)


def reshape_layer(number, bottom, channels, height, width):
    return '''layer {{
  name: "reshape{number}"
  type: "Reshape"
  bottom: "{bottom}"
  top: "reshape{number}"
  reshape_param {{
    channels: {channels}
    height: {height}
    width: {width}
  }}
}}'''.format(number=number,
             bottom=bottom,
             channels=channels,
             height=height,
             width=width)


def loss_layer(number, bottom, loss_type, weight=1, weights=None):
    txt = '''layer {{
  name: "predict_loss"
  type: "{loss_type}CrossEntropyLoss"
  bottom: "{bottom}"
  bottom: "label"
  top: "predict_loss"
  loss_weight: {weight}
}}
layer {{
  name: "precision_recall_loss"
  type: "PrecisionRecallLoss"
  bottom: "{bottom}"
  bottom: "label"
  top: "error_rate"
  include: {{ phase: TEST }}
}}'''.format(loss_type=loss_type.upper(),
             bottom=bottom,
             weight=weight)
    if weights is not None and len(weights) == 3:
        txt = '''layer {{
  name: "predict_loss"
  type: "{loss_type}CrossEntropyLoss"
  bottom: "{bottom}"
  bottom: "label"
  top: "predict_loss"
  loss_weight: {weight}
  softmax_cross_entropy_loss_param {{
    weights: {weights0}
    weights: {weights1}
    weights: {weights2}
  }}
}}
layer {{
  name: "precision_recall_loss"
  type: "PrecisionRecallLoss"
  bottom: "{bottom}"
  bottom: "label"
  top: "error_rate"
  include: {{ phase: TEST }}
}}'''.format(loss_type=loss_type.upper(),
             bottom=bottom,
             weight=weight,
             weights0=weights[0],
             weights1=weights[1],
             weights2=weights[2])

    return txt


def predict_layer(number, bottom, loss_type):
    return '''layer {{
  name: "output"
  type: "{loss_type}"
  bottom: "{bottom}"
  top: "output"
}}'''.format(loss_type=loss_type.upper(),
             bottom=bottom)


def solver(model_name, base_lr, gamma, stepsize, max_iter):
    return '''net: "train_test.prototxt"
test_iter: 10
test_interval: 1000

solver_type: SGD
base_lr: {base_lr}
lr_policy: "step"
gamma: {gamma}
stepsize: {stepsize}
momentum: 0.9
weight_decay: 0.0002

display: 100
max_iter: {max_iter}

snapshot: 10000
snapshot_prefix: "snapshots/{model_name}"

solver_mode: GPU
device_id: 0

random_seed: 1701
'''.format(model_name=model_name,
           base_lr=base_lr,
           gamma=gamma,
           stepsize=stepsize,
           max_iter=max_iter)

if __name__ == '__main__':
    if not os.path.exists('models'):
        os.mkdir('models')

    models = json.load(open(args.seed))
    for model_name, architecture in models.iteritems():
        if not os.path.exists('models/%s' % model_name):
            os.mkdir('models/%s' % model_name)

        # save prototxt for train & test
        fp = open('models/%s/train_test.prototxt' % model_name, 'w')
        print >> fp, 'name: "%s"' % model_name
        for i, layer in enumerate(architecture):
            if layer[0] == 'solver':
                continue
            bottom = None
            if i > 1:
                bottom = '%s%d' % (architecture[i - 1][0], i - 1)
            if len(layer) > 1:
                print >> fp, globals()['%s_layer' % layer[0]](
                    i, bottom, *layer[1])
            else:
                print >> fp, globals()['%s_layer' % layer[0]](i, bottom)
        fp.close()

        # save prototxt for solver
        fp = open('models/%s/solver.prototxt' % model_name, 'w')
        print >> fp, solver(model_name, *architecture[-1][1])
        fp.close()

        # save prototxt for predict
        fp = open('models/%s/predict.prototxt' % model_name, 'w')
        print >> fp, 'name: "%s"' % model_name
        print >> fp, 'input: "input_data"'
        print >> fp, 'input_dim: 64'
        print >> fp, 'input_dim: 3'
        print >> fp, 'input_dim: %d' % crop_size
        print >> fp, 'input_dim: %d' % crop_size
        for i, layer in enumerate(architecture):
            if layer[0] == 'data':
                continue
            elif layer[0] == 'solver':
                continue

            bottom = None
            if i > 1:
                bottom = '%s%d' % (architecture[i - 1][0], i - 1)
            if len(layer) > 1:
                if layer[0] == 'augment':
                    txt = globals()['predict_%s_layer' % layer[0]](
                        i, bottom, *layer[1])
                elif layer[0] == 'loss':
                    txt = globals()['predict_layer'](i, bottom, layer[1][0])
                else:
                    txt = globals()['%s_layer' % layer[0]](
                        i, bottom, *layer[1])
                print >> fp, txt
            else:
                print >> fp, globals()['%s_layer' % layer[0]](i, bottom)
        fp.close()

        subprocess.check_output(
            ['python', '/home/ubuntu/Libraries/caffe/python/draw_net.py',
             'models/%s/train_test.prototxt' % model_name,
             'models/%s/net.png' % model_name])