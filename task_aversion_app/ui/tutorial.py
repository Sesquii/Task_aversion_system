import json
import os
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional

from nicegui import ui

from backend.user_state import UserStateManager


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STEPS_FILE = DATA_DIR / "tutorial_steps.json"


def _add_highlight_styles():
    ui.add_head_html(
        """
        <style id="tas-tutorial-style">
        body.tas-tour-active * { pointer-events: none !important; }
        body.tas-tour-active .tas-tour-root,
        body.tas-tour-active .tas-tour-root * { pointer-events: auto !important; }
        body.tas-tour-active #tas-highlight-overlay,
        body.tas-tour-active #tas-highlight-spot { pointer-events: auto !important; }
        .tas-tour-root {
            position: fixed;
            inset: 0;
            z-index: 4000;
            display: none;
            align-items: flex-start;
            justify-content: center;
            padding: 32px;
            box-sizing: border-box;
        }
        .tas-tour-root.visible { display: flex !important; }
        .tas-tour-panel {
            max-width: 520px;
            width: 100%;
            pointer-events: auto !important;
        }
        .tas-highlight-overlay {
            position: fixed;
            background: rgba(0,0,0,0.45);
            backdrop-filter: blur(1px);
            inset: 0;
            z-index: 3000; /* keep below dialog (Quasar uses ~4000) */
            pointer-events: none; /* overlay blocks visuals but not clicks (handled by body class) */
        }
        .tas-highlight-spot {
            position: absolute;
            border: 2px solid #3b82f6;
            box-shadow: 0 0 0 9999px rgba(0,0,0,0.45);
            border-radius: 10px;
            pointer-events: none;
            z-index: 3001;
        }
        </style>
        """
    )


def load_tutorial_steps() -> List[Dict[str, Any]]:
    if not STEPS_FILE.exists():
        return []
    try:
        with open(STEPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _highlight_js(selector: str) -> str:
    safe_sel = selector.replace("'", "\\'")
    return f"""
    (() => {{
        const sel = '{safe_sel}';
        const target = document.querySelector(sel);
        const existing = document.getElementById('tas-highlight-spot');
        const overlay = document.getElementById('tas-highlight-overlay');
        if (!target) {{
            if (existing) existing.remove();
            if (overlay) overlay.remove();
            return;
        }}
        target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        const rect = target.getBoundingClientRect();
        let ov = overlay;
        if (!ov) {{
            ov = document.createElement('div');
            ov.id = 'tas-highlight-overlay';
            ov.className = 'tas-highlight-overlay';
            document.body.appendChild(ov);
        }}
        let spot = existing;
        if (!spot) {{
            spot = document.createElement('div');
            spot.id = 'tas-highlight-spot';
            spot.className = 'tas-highlight-spot';
            document.body.appendChild(spot);
        }}
        spot.style.top = rect.top + 'px';
        spot.style.left = rect.left + 'px';
        spot.style.width = rect.width + 'px';
        spot.style.height = rect.height + 'px';
    }})();
    """


def _clear_highlight_js() -> str:
    return """
    (() => {
        const spot = document.getElementById('tas-highlight-spot');
        const overlay = document.getElementById('tas-highlight-overlay');
        if (spot) spot.remove();
        if (overlay) overlay.remove();
    })();
    """


class TutorialWalkthrough:
    """Step-by-step walkthrough using a modal and highlight overlay."""

    def __init__(self, user_state: UserStateManager, user_id: str):
        self.user_state = user_state
        self.user_id = user_id
        self.steps = load_tutorial_steps() or [
            {
                "step_id": "welcome",
                "title": "Welcome to Task Aversion",
                "description": "This tour highlights the main areas. Click Next to continue.",
                "target_element": "#tas-dashboard-header",
                "highlight_selector": "#tas-dashboard-header",
                "position": "bottom",
            },
            {
                "step_id": "quick-actions",
                "title": "Quick Actions",
                "description": "Create or initialize tasks quickly from here.",
                "target_element": "#tas-quick-actions",
                "highlight_selector": "#tas-quick-actions",
                "position": "bottom",
            },
            {
                "step_id": "active-tasks",
                "title": "Active Tasks",
                "description": "Manage tasks that are initialized or in progress.",
                "target_element": "#tas-active-tasks",
                "highlight_selector": "#tas-active-tasks",
                "position": "left",
            },
            {
                "step_id": "analytics",
                "title": "Analytics",
                "description": "Open analytics to see trends and patterns.",
                "target_element": "#tas-analytics-link",
                "highlight_selector": "#tas-analytics-link",
                "position": "right",
            },
        ]
        self.index = 0
        _add_highlight_styles()
        self.root = ui.element('div').classes("tas-tour-root")
        with self.root:
            with ui.card().classes("tas-tour-panel").style("padding: 20px; gap: 10px;"):
                with ui.row().classes("w-full items-start justify-between"):
                    self.title_lbl = ui.label("").classes("text-xl font-bold")
                    ui.button("×", on_click=self.skip).classes("text-lg").props("flat")
                self.desc_lbl = ui.label("").classes("text-gray-600")
                self.progress_lbl = ui.label("").classes("text-sm text-gray-500")
                ui.label("Click Next to advance, Previous to go back, or Skip to exit. The rest of the page is locked while the tour runs.").classes("text-xs text-gray-500 mb-2")
                with ui.row().classes("justify-between w-full"):
                    self.prev_btn = ui.button("Previous", on_click=self.prev).props("flat")
                    self.next_btn = ui.button("Next", on_click=self.next).classes("bg-blue-500 text-white")
                    self.skip_btn = ui.button("Skip / Close", on_click=self.skip).props("outline")
        # ensure the element is hidden initially
        self.root.classes(add="hidden")

    def show_step(self, idx: int):
        if not self.steps:
            ui.notify("No tutorial steps configured yet.", color="warning")
            return
        self.index = max(0, min(idx, len(self.steps) - 1))
        step = self.steps[self.index]
        self.title_lbl.set_text(step.get("title", "Step"))
        self.desc_lbl.set_text(step.get("description", ""))
        self.progress_lbl.set_text(f"Step {self.index + 1} of {len(self.steps)}")
        selector = step.get("highlight_selector") or step.get("target_element")
        if selector:
            ui.run_javascript(f"""
                const runStep = () => {{ {_highlight_js(selector)} }};
                setTimeout(runStep, 50);
                setTimeout(runStep, 250);
                setTimeout(runStep, 600);
            """)
        else:
            ui.run_javascript(_clear_highlight_js())
        # show the overlay root
        self.root.classes(remove="hidden")
        self.root.classes(add="visible")

    def next(self):
        if self.index + 1 >= len(self.steps):
            self.finish()
        else:
            self.show_step(self.index + 1)

    def prev(self, *_):
        self.show_step(max(0, self.index - 1))

    def skip(self, *_):
        self.finish()

    def finish(self, *_):
        ui.run_javascript(_clear_highlight_js())
        ui.run_javascript("document.body.classList.remove('tas-tour-active');")
        self.root.classes(remove="visible")
        self.root.classes(add="hidden")
        self.user_state.mark_tutorial_completed(self.user_id, choice="guided")
        ui.notify("Tutorial completed. You can re-open it anytime from the tutorial button.", color="positive")

    def start(self):
        ui.run_javascript("document.body.classList.add('tas-tour-active');")
        self.root.classes(add="visible")
        self.root.classes(remove="hidden")
        self.show_step(0)


def show_tutorial_welcome(
    user_state: UserStateManager,
    user_id: str,
    on_start_walkthrough: Optional[Callable[[], None]] = None,
):
    """Two-path welcome modal."""
    dialog = ui.dialog()
    _add_highlight_styles()

    with dialog, ui.card().classes("w-full max-w-lg"):
        ui.label("Welcome!").classes("text-2xl font-bold mb-1")
        ui.label("Choose how you want to learn the app.").classes("text-gray-600 mb-3")
        dont_show = ui.checkbox("Don't show again").classes("mb-2")

        def set_auto_show():
            user_state.update_preference(user_id, "tutorial_auto_show", not dont_show.value)

        with ui.column().classes("gap-2 w-full"):
            def handle_guided():
                user_state.update_preference(user_id, "tutorial_choice", "guided")
                set_auto_show()
                dialog.close()
                if on_start_walkthrough:
                    on_start_walkthrough()

            def handle_explore():
                user_state.update_preference(user_id, "tutorial_choice", "explore")
                set_auto_show()
                dialog.close()
                ui.notify("Ctrl + Click any element to see tooltips. Tutorial can be reopened anytime.", color="positive")

            ui.button("Take Guided Tour", on_click=handle_guided).classes("w-full bg-blue-500 text-white")
            ui.button("Explore on My Own (Ctrl + Click for tips)", on_click=handle_explore).classes("w-full")

    dialog.open()
    return dialog

