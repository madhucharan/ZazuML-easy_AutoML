import os
# sys.path.insert(1, os.path.dirname(__file__))
from .model_trainer import ModelTrainer
from predictor.pred_utils import detect, detect_single_image

from copy import deepcopy
import random
import time
import hashlib
import torch
import logging

logger = logging.getLogger(__name__)


def generate_trial_id():
    s = str(time.time()) + str(random.randint(1, 1e7))
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:32]


class TrialAdapter(ModelTrainer):

    def _unpack_trial_checkpoint(self, trial_checkpoint):
        self.hp_values = trial_checkpoint['hp_values'] if 'hp_values' in trial_checkpoint else {}
        self.hp_values['hyperparameter_tuner/initial_epoch'] = trial_checkpoint[
            'epoch'] if 'model_fn' and 'epoch' in trial_checkpoint else self.hp_values[
            'hyperparameter_tuner/initial_epoch']
        self.annotation_type = trial_checkpoint['annotation_type']
        self.model_fn = trial_checkpoint['model_fn']
        trial_checkpoint['training_configs'].update(self.hp_values)
        self.configs = trial_checkpoint['training_configs']


        new_trial_id = self.configs['hyperparameter_tuner/new_trial_id']
        past_trial_id = self.configs[
            'hyperparameter_tuner/past_trial_id'] if 'hyperparameter_tuner/past_trial_id' in self.configs else None
        self.data_path = trial_checkpoint['home_path']
        checkpoint = None
        if 'model' in trial_checkpoint:
            checkpoint = deepcopy(trial_checkpoint)
            for x in ['model_fn', 'training_configs', 'data', 'hp_values', 'epoch']:
                checkpoint.pop(x)
        # return checkpoint with just
        return new_trial_id, past_trial_id, checkpoint

    def load(self, checkpoint_path='checkpoint.pt'):
        # the only necessary keys for load are ['model_specs']
        trial_checkpoint = torch.load(checkpoint_path)
        new_trial_id, past_trial_id, checkpoint = self._unpack_trial_checkpoint(trial_checkpoint)
        super().load(self.data_path, new_trial_id, past_trial_id, checkpoint)

    def train(self):
        super().preprocess(augment_policy=self.configs['augment_policy'],
                           dataset=self.annotation_type,
                           resize=self.configs['input_size'],
                           batch=self.configs['batch'])

        super().build(model=self.model_fn,
                      depth=self.configs['depth'],
                      learning_rate=self.configs['learning_rate'],
                      ratios=self.configs['anchor_ratios'],
                      scales=self.configs['anchor_scales'])

        super().train(epochs=self.configs['hyperparameter_tuner/epochs'],
                      init_epoch=self.configs['hyperparameter_tuner/initial_epoch'])

    def get_checkpoint_metadata(self):
        logger.info('getting best checkpoint')
        checkpoint = super().get_best_checkpoint()
        logging.info('got best checkpoint')
        checkpoint['hp_values'] = self.hp_values
        checkpoint['model_fn'] = self.model_fn
        checkpoint['training_configs'] = self.configs
        checkpoint['data_path'] = self.data_path
        checkpoint['annotation_type'] = self.annotation_type
        checkpoint['checkpoint_path'] = self.save_best_checkpoint_path
        checkpoint.pop('model')
        logging.info('checkpoint keys: ' + str(checkpoint.keys()))
        return checkpoint

    @property
    def checkpoint_path(self):
        return super().save_best_checkpoint_path

    def load_inference(self, checkpoint_path):
        if torch.cuda.is_available():
            logger.info('cuda available')
            self.inference_checkpoint = torch.load(checkpoint_path)
        else:
            logger.info('run on cpu')
            self.inference_checkpoint = torch.load(checkpoint_path, map_location=torch.device('cpu'))
        return self.inference_checkpoint

    def predict_single_image(self, image_path, checkpoint_path='checkpoint.pt'):
        if hasattr(self, 'inference_checkpoint'):
            return detect_single_image(self.inference_checkpoint, image_path)
        else:
            self.load_inference(checkpoint_path)
            return detect_single_image(self.inference_checkpoint, image_path)

    def predict_items(self, items, checkpoint_path, with_upload=True, model_name='object_detection'):
        for item in items:
            dirname = self.predict_item(item, checkpoint_path, with_upload, model_name)

        return dirname

