from .oracle import Oracle
from .hyperband import HyperBand


class Tuner:

    def __init__(self, ongoing_trials, search_method, epochs, max_trials, max_instances_at_once, hp_space):
        self.ongoing_trials = ongoing_trials
        if search_method == "hyperband":
            self.oracle = HyperBand(space=hp_space, max_epochs=epochs, augment=False)
        elif search_method == "random":
            self.oracle = Oracle(space=hp_space, max_epochs=epochs, max_trials=max_trials)
        else:
            raise Exception('have not defined proper search_method param in configs.json')

        self.max_instances_at_once = max_instances_at_once

    def end_trial(self):
        self.oracle.update_metrics(self.ongoing_trials.trials)
        self.ongoing_trials.remove_trial()

    def add_trial(self, trial_id, hp_values, metrics, meta_checkpoint):
        self.oracle.trials[trial_id] = {'hp_values': hp_values, 'metrics': metrics, 'meta_checkpoint': meta_checkpoint}


    def search_hp(self):

        for _ in range(self.max_instances_at_once):
            trial_id, hp_values, status = self.oracle.create_trial()
            self.ongoing_trials.update_status(status)
            if status == 'STOPPED':
                break
            self.ongoing_trials.update_trial_hp(trial_id, hp_values=hp_values)

    @property
    def trials(self):
        return self.oracle.trials #TODO pop deleted last round hyperband models from trials

    def get_sorted_trial_ids(self):
        sorted_trial_ids = sorted(self.oracle.trials.keys(), key=lambda x: self.oracle.trials[x]['metrics']['val_accuracy'], reverse=True)
        return sorted_trial_ids