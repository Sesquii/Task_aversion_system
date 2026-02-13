import json
from pathlib import Path
from typing import Dict, Any, List

from nicegui import ui

from backend.survey import SurveyManager
from ui.slider_style import progress_slider
from backend.user_state import UserStateManager
from backend.auth import get_current_user
from backend.security_utils import escape_for_display
from ui.error_reporting import handle_error_with_ui


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
QUESTIONS_FILE = DATA_DIR / "survey_questions.json"

survey_manager = SurveyManager()
user_state = UserStateManager()


def load_questions() -> Dict[str, Any]:
    if not QUESTIONS_FILE.exists():
        return {"categories": []}
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@ui.page("/survey")
def survey_page():
    try:
        questions = load_questions().get("categories", [])
    except Exception as e:
        handle_error_with_ui(
            operation="load survey questions",
            error=e,
            user_id=get_current_user(),
            context={"questions_file": str(QUESTIONS_FILE)},
            user_message="Unable to load survey questions. Please try again later.",
            show_report=True
        )
        questions = []
    state: Dict[str, Any] = {"user_id": None}
    controls: Dict[str, Any] = {}

    async def init_user():
        try:
            uid = await ui.run_javascript(UserStateManager.js_get_or_create_user_id())
            state["user_id"] = uid
            user_state.ensure_user(uid)
        except Exception as e:
            print(f"[WARNING] Failed to initialize user_id: {e}")
            # Fallback: try to get user from auth
            try:
                from backend.auth import get_current_user
                uid = get_current_user()
                if uid:
                    state["user_id"] = uid
                    user_state.ensure_user(uid)
            except Exception:
                pass

    ui.timer(0.1, init_user, once=True, immediate=True)

    ui.label("Mental Health Survey").classes("text-2xl font-bold")
    ui.label("Optional data helps improve recommendations. Required fields are clearly marked.").classes(
        "text-gray-600 mb-4"
    )

    progress = ui.linear_progress(value=0).classes("mb-4")

    def update_progress():
        total = len(questions)
        done = 0
        for cat in questions:
            for q in cat.get("questions", []):
                getter = controls.get(q["question_id"])
                if not getter:
                    continue
                val = getter()
                has_val = False
                if isinstance(val, tuple):
                    v, t = val
                    has_val = bool(v) or bool(t)
                else:
                    has_val = bool(val)
                if has_val:
                    done += 1
        if total == 0:
            progress.set_value(0)
        else:
            progress.set_value(min(1.0, done / max(1, total * 1.0)))

    def render_checkbox_group(question):
        opts = question.get("options", [])
        rows = []  # List of (checkbox, option_text) tuples
        for opt in opts:
            cb = ui.checkbox(opt)
            rows.append((cb, opt))  # Store checkbox with its option text
        other_input = None
        if question.get("allow_other"):
            other_input = ui.input(label="Other (optional)")

        def getter():
            selected = [opt_text for cb, opt_text in rows if cb.value]
            other = other_input.value.strip() if other_input else ""
            values = selected + ([other] if other else [])
            return values, ""

        controls[question["question_id"]] = getter

        def on_change(_=None):
            update_progress()

        for cb, _ in rows:
            cb.on("update:model-value", on_change)
        if other_input:
            other_input.on("update:model-value", on_change)

    def render_scale(question):
        scale_min = question.get("scale_min", 1)
        scale_max = question.get("scale_max", 10)
        slider = progress_slider(scale_min, scale_max, 1, scale_min)
        controls[question["question_id"]] = lambda: (slider.value, "")
        slider.on("update:model-value", lambda _: update_progress())

    def render_text(question):
        input_box = ui.textarea(label=question.get("question_text", ""))
        controls[question["question_id"]] = lambda: ("", input_box.value or "")
        input_box.on("update:model-value", lambda _: update_progress())

    for cat in questions:
        ui.separator()
        with ui.column().classes("gap-2"):
            title = cat.get("title", "Category")
            ui.label(escape_for_display(title)).classes("text-xl font-semibold")
            if cat.get("disclaimer"):
                ui.label(escape_for_display(cat["disclaimer"])).classes("text-sm text-amber-600")
            for q in cat.get("questions", []):
                required = q.get("required", False)
                label_text = q.get("question_text", "")
                if required:
                    label_text += " *"
                ui.label(escape_for_display(label_text)).classes("text-sm font-medium")
                qtype = q.get("type", "text")
                if qtype == "checkbox":
                    render_checkbox_group(q)
                elif qtype == "scale":
                    render_scale(q)
                else:
                    render_text(q)

    def submit():
        try:
            missing: List[str] = []
            rows: List[Dict[str, Any]] = []
            for cat in questions:
                cat_id = cat.get("id", "unknown")
                for q in cat.get("questions", []):
                    getter = controls.get(q["question_id"])
                    if not getter:
                        continue
                    val = getter()
                    response_value = ""
                    response_text = ""
                    if isinstance(val, tuple):
                        response_value, response_text = val
                    else:
                        response_value = val

                    # Convert list responses to comma-separated strings
                    if isinstance(response_value, list):
                        if response_value:
                            response_value = ", ".join(str(v) for v in response_value if v)
                        else:
                            response_value = ""  # Empty list becomes empty string
                    
                    # Ensure response_value is a string
                    if response_value is None:
                        response_value = ""
                    elif not isinstance(response_value, str):
                        response_value = str(response_value)

                    has_val = bool(response_value) or bool(response_text)
                    if q.get("required") and not has_val:
                        missing.append(escape_for_display(q.get("question_text", q["question_id"])))
                        continue

                    rows.append(
                        {
                            "question_id": q["question_id"],
                            "question_category": cat_id,
                            "response_value": response_value,
                            "response_text": response_text,
                        }
                    )

            if missing:
                ui.notify(f"Please answer required: {', '.join(missing[:3])}", color="negative")
                return

            uid = state.get("user_id")
            # Try to get user_id from auth as fallback
            if not uid or uid == "anonymous":
                try:
                    from backend.auth import get_current_user
                    uid = get_current_user()
                    if uid:
                        state["user_id"] = uid
                except Exception:
                    pass
            
            if not uid or uid == "anonymous":
                ui.notify("Error: User ID not available. Please refresh the page.", color="negative")
                return

            for row in rows:
                survey_manager.record_response(
                    user_id=uid,
                    question_category=row["question_category"],
                    question_id=row["question_id"],
                    response_value=row.get("response_value", ""),
                    response_text=row.get("response_text", ""),
                )
            user_state.mark_survey_completed(uid)
            ui.notify("Survey saved. Thank you!", color="positive")
        except Exception as e:
            handle_error_with_ui(
                'save_survey_responses',
                e,
                user_id=get_current_user()
            )

    ui.button("Submit Survey", on_click=submit).classes("mt-4 bg-blue-500 text-white")

