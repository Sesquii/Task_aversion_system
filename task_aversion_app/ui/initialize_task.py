# ui/initialize_task.py
from nicegui import ui
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.emotion_manager import EmotionManager
import json
from urllib.parse import urlparse, parse_qs

tm = TaskManager()
im = InstanceManager()
em = EmotionManager()

def initialize_task_page():
    @ui.page('/initialize_task')
    def page():
        ui.label("Initialize Task (Prediction)").classes("text-xl font-bold")
        # read instance_id if passed
        params = ui.get_query()
        instance_id = params.get('instance_id') if params else None

        # if instance_id present show predicted values, else allow choosing a task to create instance for
        task_select = ui.select(options=tm.list_tasks(), label='Choose task')
        new_task = ui.input(label='Or type new task name (optional)')

        prod_label = ui.label("Prediction inputs")
        # sliders and fields
        aversion = ui.slider(min=0, max=10, value=5, label='Aversion (predicted)')
        excitement = ui.slider(min=0, max=10, value=5, label='Excitement (predicted)')
        expected_relief = ui.slider(min=0, max=10, value=5, label='Expected Relief')
        cognitive = ui.slider(min=0, max=10, value=5, label='Expected Cognitive Demand')
        emotional = ui.slider(min=0, max=10, value=5, label='Expected Emotional Demand')
        time_est = ui.number(label='Estimated minutes', value=15)

        # emotions multi-select
        emotions = ui.select(options=em.list_emotions(), multiple=True, label='Emotions (predicted)')

        def submit_prediction():
            # decide task name or create
            name = new_task.value.strip() if new_task.value and new_task.value.strip() else task_select.value
            if not name:
                ui.notify("Please choose or type a task name", color='negative')
                return
            task = tm.find_by_name(name)
            if not task:
                tid = tm.create_task(name)
                task = tm.find_by_name(name)
            predicted = {
                'aversion': int(aversion.value),
                'excitement': int(excitement.value),
                'expected_relief': int(expected_relief.value),
                'cognitive_expected': int(cognitive.value),
                'emotional_expected': int(emotional.value),
                'time_estimate_minutes': int(time_est.value),
                'emotions': emotions.value or []
            }
            inst_id = im.create_instance(task['task_id'], task['name'], task_version=task.get('version') or 1, predicted=predicted)
            ui.notify(f"Initialized {name} → instance {inst_id}", color='positive')
            ui.navigate.to(f'/initialize_task?instance_id={inst_id}')

        ui.button("Initialize & Create Instance", on_click=submit_prediction)
