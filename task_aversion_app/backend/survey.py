import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


DATA_DIR = os.path.join(Path(__file__).resolve().parent.parent, "data")
os.makedirs(DATA_DIR, exist_ok=True)

RESP_FILE = os.path.join(DATA_DIR, "survey_responses.csv")


class SurveyManager:
    """Lightweight CSV-backed survey storage."""

    def __init__(self, resp_file: Optional[str] = None):
        self.file = resp_file or RESP_FILE
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        self._ensure_file()
        self._reload()

    def _ensure_file(self):
        if not os.path.exists(self.file):
            with open(self.file, "w", encoding="utf-8") as f:
                f.write("user_id,response_id,question_category,question_id,response_value,response_text,timestamp\n")

    def _reload(self):
        try:
            self.df = pd.read_csv(self.file, dtype=str).fillna("")
        except Exception:
            self.df = pd.DataFrame(
                columns=[
                    "user_id",
                    "response_id",
                    "question_category",
                    "question_id",
                    "response_value",
                    "response_text",
                    "timestamp",
                ]
            )

    def _save(self):
        self.df.to_csv(self.file, index=False)
        self._reload()

    def _next_id(self) -> str:
        return f"srv-{int(datetime.utcnow().timestamp()*1000)}"

    def record_response(
        self,
        user_id: str,
        question_category: str,
        question_id: str,
        response_value: Optional[str] = "",
        response_text: Optional[str] = "",
    ) -> str:
        self._reload()
        rid = self._next_id()
        row = {
            "user_id": user_id,
            "response_id": rid,
            "question_category": question_category,
            "question_id": question_id,
            "response_value": response_value or "",
            "response_text": response_text or "",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save()
        return rid

    def record_bulk(
        self, user_id: str, responses: List[Dict[str, Any]], question_category: str
    ) -> List[str]:
        ids = []
        for resp in responses:
            ids.append(
                self.record_response(
                    user_id=user_id,
                    question_category=question_category,
                    question_id=resp.get("question_id", ""),
                    response_value=str(resp.get("response_value", "")),
                    response_text=str(resp.get("response_text", "")),
                )
            )
        return ids

    def get_responses_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        self._reload()
        rows = self.df[self.df["user_id"] == user_id]
        return rows.to_dict(orient="records")

