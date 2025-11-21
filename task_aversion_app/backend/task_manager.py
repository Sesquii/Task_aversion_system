import pandas as pd
from datetime import datetime

class TaskManager:
    def __init__(self, tasks_path, logs_path):
        self.tasks_path = tasks_path
        self.logs_path = logs_path

        # Load or initialize tasks file
        try:
            self.tasks = pd.read_csv(self.tasks_path)
        except FileNotFoundError:
            self.tasks = pd.DataFrame(columns=[
                "task", "category", "times_logged",
                "avg_aversion", "avg_relief", "last_logged"
            ])
            self.tasks.to_csv(self.tasks_path, index=False)

        # Load logs
        try:
            self.logs = pd.read_csv(self.logs_path)
        except FileNotFoundError:
            self.logs = pd.DataFrame(columns=[
                "timestamp", "task", "aversion_level",
                "relief_prediction", "relief_actual",
                "completion_percent", "perceived_overextension",
                "time_estimate_minutes", "time_actual_minutes",
                "comment", "blocker_type"
            ])
            self.logs.to_csv(self.logs_path, index=False)

    # -----------------------------------------
    def get_task_list(self):
        return sorted(self.tasks["task"].unique())

    # NEW: for consistency with your UI
    def get_all_tasks(self):
        return self.get_task_list()

    # -----------------------------------------
    def add_task_if_missing(self, task_name):
        if task_name not in self.tasks["task"].values:
            new_row = {
                "task": task_name,
                "category": "General",
                "times_logged": 0,
                "avg_aversion": 0,
                "avg_relief": 0,
                "last_logged": ""
            }
            self.tasks.loc[len(self.tasks)] = new_row
            self.tasks.to_csv(self.tasks_path, index=False)

    # -----------------------------------------
    def update_task_metadata(self, task_name, aversion, relief):
        row = self.tasks[self.tasks["task"] == task_name]

        if row.empty:
            return

        idx = row.index[0]

        prev_times = self.tasks.loc[idx, "times_logged"]
        prev_avg_aversion = self.tasks.loc[idx, "avg_aversion"]
        prev_avg_relief = self.tasks.loc[idx, "avg_relief"]

        new_times = prev_times + 1
        new_avg_aversion = (prev_avg_aversion * prev_times + aversion) / new_times
        new_avg_relief = (prev_avg_relief * prev_times + relief) / new_times

        self.tasks.loc[idx, "times_logged"] = new_times
        self.tasks.loc[idx, "avg_aversion"] = round(new_avg_aversion, 2)
        self.tasks.loc[idx, "avg_relief"] = round(new_avg_relief, 2)
        self.tasks.loc[idx, "last_logged"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        self.tasks.to_csv(self.tasks_path, index=False)

    # -----------------------------------------
    def save_log_entry(self, entry_dict):
        self.logs.loc[len(self.logs)] = entry_dict
        self.logs.to_csv(self.logs_path, index=False)
