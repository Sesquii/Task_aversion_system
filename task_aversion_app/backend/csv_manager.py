# backend/csv_manager.py
import os
import pandas as pd
from datetime import datetime
from typing import Optional

class CSVManager:
    """
    Responsible for reading/writing logs and tasks CSV files.
    Ensures CSVs exist and uses pandas for easy manipulation.
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        base_path: path to the project root (folder that contains 'data' subfolder)
        If None, use the folder two levels up from this file (assumes package layout).
        """
        if base_path:
            self.base_path = os.path.abspath(base_path)
        else:
            # Assumes project structure: <project>/backend/csv_manager.py
            self.base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        self.data_path = os.path.join(self.base_path, "data")
        os.makedirs(self.data_path, exist_ok=True)

        self.logs_file = os.path.join(self.data_path, "logs.csv")
        self.tasks_file = os.path.join(self.data_path, "tasks.csv")

        self._ensure_files()

    def _ensure_files(self):
        # Default headers for logs.csv
        if not os.path.exists(self.logs_file):
            with open(self.logs_file, "w", encoding="utf-8") as f:
                f.write(
                    "timestamp,task,aversion_level,relief_prediction,relief_actual,"
                    "completion_percent,perceived_overextension,time_estimate_minutes,"
                    "time_actual_minutes,comment,blocker_type\n"
                )

        # Default headers for tasks.csv
        if not os.path.exists(self.tasks_file):
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                f.write("task,category,times_logged,avg_aversion,avg_relief,last_logged\n")

    # -------------------------
    # Logs helpers
    # -------------------------
    def read_logs(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.logs_file, parse_dates=["timestamp"])
        except Exception:
            df = pd.DataFrame(
                columns=[
                    "timestamp", "task", "aversion_level", "relief_prediction", "relief_actual",
                    "completion_percent", "perceived_overextension", "time_estimate_minutes",
                    "time_actual_minutes", "comment", "blocker_type"
                ]
            )
        return df

    def append_log(self, row: dict):
        """
        row: dict with keys matching the logs.csv headers (timestamp will be filled if absent).
        """
        df = self.read_logs()
        if "timestamp" not in row or row.get("timestamp") is None:
            row["timestamp"] = datetime.now().isoformat(sep=" ", timespec="seconds")
        # Append safely using pandas
        new_df = pd.DataFrame([row])
        new_df.to_csv(self.logs_file, mode="a", header=False, index=False)

    # -------------------------
    # Tasks helpers
    # -------------------------
    def read_tasks(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.tasks_file, parse_dates=["last_logged"])
        except Exception:
            df = pd.DataFrame(columns=["task", "category", "times_logged", "avg_aversion", "avg_relief", "last_logged"])
        return df

    def write_tasks(self, df: pd.DataFrame):
        df.to_csv(self.tasks_file, index=False)

    def upsert_task(self, task_name: str, category: str = "", times_logged: int = 0, avg_aversion: float = 0.0, avg_relief: float = 0.0, last_logged: Optional[str] = None):
        df = self.read_tasks()
        if task_name in df["task"].values:
            df.loc[df["task"] == task_name, ["category", "times_logged", "avg_aversion", "avg_relief", "last_logged"]] = [
                category, times_logged, avg_aversion, avg_relief, last_logged
            ]
        else:
            new_row = {
                "task": task_name,
                "category": category,
                "times_logged": times_logged,
                "avg_aversion": avg_aversion,
                "avg_relief": avg_relief,
                "last_logged": last_logged
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self.write_tasks(df)
