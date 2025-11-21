# ui/create_task.py
from nicegui import ui
from backend.task_manager import TaskManager
from backend.emotion_manager import EmotionManager
import json

tm = TaskManager()
em = EmotionManager()

def create_task_page():
    @ui.page('/create_task')
    def page():
        ui.label("Create Task Template").classes("text-xl font-bold")
        with ui.column().classes('w-full max-w-2xl gap-4'):
            name = ui.input(label="Task Name")
            desc = ui.textarea(label="Description (optional)")
            ttype = ui.select(options=['one-time','recurring','routine','project'], label='Type', value='one-time')
            est = ui.number(label='Default estimate minutes', value=0)
            # emotions multi-select (from emotion manager)
            emotion_opts = em.list_emotions()
            emotions = ui.select(options=emotion_opts, label='Tracked Emotions (multi)', multiple=True)
            new_em = ui.input(label="Add custom emotion")
            def add_emotion():
                val = new_em.value.strip()
                if not val:
                    ui.notify("Enter an emotion", color='negative')
                    return
                em.add_emotion(val)
                emotions.options = em.list_emotions()
                new_em.set_value('')
                ui.notify("Added emotion", color='positive')
            ui.button("Add Emotion", on_click=add_emotion)

            def save_task():
                if not name.value or not name.value.strip():
                    ui.notify("Task name required", color='negative')
                    return
                cat_json = json.dumps(emotions.value or [])
                tid = tm.create_task(name.value.strip(), description=desc.value or '', ttype=ttype.value, is_recurring=(ttype.value!='one-time'), categories=cat_json, default_estimate_minutes=int(est.value or 0))
                ui.notify(f"Task created: {tid}", color='positive')
                ui.navigate.to('/')
            ui.button("Create Task", on_click=save_task)
