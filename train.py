import os
import time

import scipy
import numpy as np
import tensorflow as tf
import pandas as pd
from sklearn.model_selection import train_test_split

from logger import logger
from model.unet import UNet
from data_io import read_images, ImageFileName
from image_op import save_image


######################################
#  Global Parameters Definition
######################################
PROJECT_HOME = '/home/rlan/projects/Kaggle/Carnava/kaggle-carvana-semantic-segmentation-unet'
CHECKPOINT_DIR = os.path.join(PROJECT_HOME, 'checkpoints')
INPUT_DIR = os.path.join(PROJECT_HOME, 'input')
TRAIN_DATA_DIR = os.path.join(INPUT_DIR, 'train')
TRAIN_MASK_DIR = os.path.join(INPUT_DIR, 'train_masks')

EPOCHS_ACCUMULATE_EACH_SAVING = 10
MAX_EPOCH = 50
LEARNING_RATE = 1e-4
NUM_CLASSES = 2
BATCH_SIZE = 16
INPUT_SHAPE = 512

######################################
#  Prepare Train / Validation Data
######################################
df = pd.read_csv(os.path.join(INPUT_DIR, 'train_masks.csv'))
fnames = [ImageFileName(f.split('.')[0]) for f in df['img'].tolist()]
fnames_train, fnames_validation = train_test_split(fnames, test_size=0.2, random_state=233)

cur_checkpoint_path = os.path.join(CHECKPOINT_DIR, '{:.0f}'.format(time.time()))
if not os.path.exists(cur_checkpoint_path):
    os.makedirs(cur_checkpoint_path)

######################################
#  Build Graph and Evaluation
######################################
with tf.Session() as sess:
    unet = UNet(num_classes=NUM_CLASSES, input_shape=INPUT_SHAPE, learning_rate=LEARNING_RATE)
    unet.build()
    init = tf.global_variables_initializer()
    sess.run(init)
    saver = tf.train.Saver(tf.global_variables(), max_to_keep=5)

    for epoch in range(MAX_EPOCH):
        ##############
        #   Train
        ##############
        start_time = time.time()
        train_data = read_images(TRAIN_DATA_DIR, batch_size=BATCH_SIZE, as_shape=INPUT_SHAPE, mask_dir=TRAIN_MASK_DIR,
                                 file_names=fnames_train)
        for batch, (X_batch, y_batch) in enumerate(train_data):
            _, loss, pred = sess.run([unet.train_op, unet.loss, unet.pred],
                                     feed_dict={unet.is_training: True, unet.X_train: X_batch, unet.y_train: y_batch})
            logger.info('[epoch {}, batch {}] training error: {}'.format(epoch, batch, loss))

        logger.info('==== epoch {} took {:.0f} seconds to train. ===='.format(epoch, time.time() - start_time))

        ##########################
        #   Eval Validation set
        ##########################
        start_time = time.time()
        val_data = read_images(TRAIN_DATA_DIR, batch_size=BATCH_SIZE, as_shape=INPUT_SHAPE, mask_dir=TRAIN_MASK_DIR,
                               file_names=fnames_validation)
        losses = []
        for batch, (X_batch, y_batch) in enumerate(val_data):
            loss, pred = sess.run([unet.loss, unet.pred],
                                  feed_dict={unet.is_training: False, unet.X_train: X_batch, unet.y_train: y_batch})
            losses.append(loss)

        logger.info('==== average validation error: {} ===='.format(np.average(losses)))
        logger.info('==== epoch {} took {:.0f} seconds to evaluate the validation set. ===='.format(epoch, time.time() - start_time))

        last_image = np.argmax(pred[pred.shape[0] - 1, :, :, :], axis=2) * 255
        save_image(last_image, os.path.join(PROJECT_HOME, 'sample_results', 'val', 'epoch_{}.png'.format(epoch)))

        if (epoch > 0 and epoch % EPOCHS_ACCUMULATE_EACH_SAVING == 0) or epoch == MAX_EPOCH - 1:
            saver.save(sess, os.path.join(cur_checkpoint_path, 'unet-{}'.format(INPUT_SHAPE)), global_step=epoch)
