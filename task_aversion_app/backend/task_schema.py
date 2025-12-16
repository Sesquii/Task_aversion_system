from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass(frozen=True)
class TaskAttribute:
    key: str
    label: str
    description: str
    dtype: str
    range_hint: str
    default: Any


TASK_ATTRIBUTES: List[TaskAttribute] = [
    TaskAttribute(
        key="duration_minutes",
        label="Duration (min)",
        description="Actual or expected minutes needed to finish the task instance.",
        dtype="numeric",
        range_hint="0-600",
        default=30,
    ),
    TaskAttribute(
        key="relief_score",
        label="Relief Score",
        description="How much emotional relief is felt after finishing (0-10).",
        dtype="numeric",
        range_hint="0-10",
        default=5,
    ),
    TaskAttribute(
        key="mental_energy_needed",
        label="Mental Energy Needed",
        description="Germane load: Mental effort required to understand and process the task (0-100).",
        dtype="numeric",
        range_hint="0-100",
        default=50,
    ),
    TaskAttribute(
        key="task_difficulty",
        label="Task Difficulty",
        description="Intrinsic load: Inherent difficulty/complexity of the task itself (0-100).",
        dtype="numeric",
        range_hint="0-100",
        default=50,
    ),
    TaskAttribute(
        key="emotional_load",
        label="Emotional Load",
        description="Degree of emotional activation or stress expected during the task.",
        dtype="numeric",
        range_hint="0-10",
        default=4,
    ),
    TaskAttribute(
        key="environmental_effect",
        label="Environmental Fit",
        description="How much the surrounding environment helps or harms progress.",
        dtype="numeric",
        range_hint="-5 to +5",
        default=0,
    ),
    TaskAttribute(
        key="skills_improved",
        label="Skills Improved",
        description="Comma separated capabilities practiced while executing the task.",
        dtype="list",
        range_hint="text list",
        default="",
    ),
    TaskAttribute(
        key="behavioral_score",
        label="Behavioral Score",
        description="How well you adhered to planned behaviour (0-100, 50 = neutral/perfect adherence).",
        dtype="numeric",
        range_hint="0-100",
        default=50,
    ),
]


def attribute_defaults() -> Dict[str, Any]:
    return {attr.key: attr.default for attr in TASK_ATTRIBUTES}

