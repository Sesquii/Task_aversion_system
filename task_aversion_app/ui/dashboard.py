# ui/dashboard.py
from nicegui import ui
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.emotion_manager import EmotionManager
from backend.analytics import Analytics

tm = TaskManager()
im = InstanceManager()
em = EmotionManager()
an = Analytics()

def build_dashboard(task_manager):
    ui.label("Task Aversion Dashboard").classes("text-2xl font-bold mb-4")
    with ui.row().classes('gap-6'):
        with ui.column().classes('w-1/2'):
            ui.button("➕ Create Task", on_click=lambda: ui.navigate.to('/create_task'))
            ui.button("▶ Initialize Task", on_click=lambda: ui.navigate.to('/initialize-task'))
            ui.button("✓ Complete Task", on_click=lambda: ui.navigate.to('/complete_task'))
            ui.markdown("### Active (Initialized & Not Completed)")
            active = im.list_active_instances()
            if not active:
                ui.markdown("_No active task instances._")
            else:
                for inst in active:
                    with ui.card().classes('mb-3'):
                        ui.markdown(f"**{inst.get('task_name')}** — created {inst.get('created_at')}")
                        ui.markdown(f"Predicted: {inst.get('predicted')}")
                        # show quick actions
                        with ui.row():
                            ui.button("Complete", on_click=lambda i=inst['instance_id']: go_complete(i))
                            ui.button("Start", on_click=lambda i=inst['instance_id']: start_instance(i))
                            ui.button("Details", on_click=lambda i=inst['instance_id']: show_details(i))
        with ui.column().classes('w-1/2'):
            ui.markdown("### Recommendations")
            stats = an.active_summary()
            ui.markdown(f"- Active tasks: {stats.get('active_count',0)}")
            ui.markdown(f"- Oldest active: {stats.get('oldest_active')}")
            ui.markdown("### Quick Task Templates")
            tasks = tm.get_all()
            if tasks is None or tasks.empty:
                ui.markdown("_No task templates yet._")
            else:
                rows = tasks.to_dict(orient='records')
                for r in rows[:10]:
                    with ui.card().classes('mb-2'):
                        ui.markdown(f"**{r.get('name')}** — v{r.get('version')}")
                        ui.markdown(r.get('description') or '_no description_')
                        ui.button("Init", on_click=lambda name=r.get('name'): init_quick(name))

def init_quick(task_name):
    t = tm.find_by_name(task_name)
    if not t:
        ui.notify("Task not found", color='negative')
        return
    # create instance passing default estimate
    from backend.instance_manager import InstanceManager
    im_local = InstanceManager()
    inst_id = im_local.create_instance(t['task_id'], t['name'], task_version=t.get('version') or 1, predicted={'time_estimate_minutes': t.get('default_estimate_minutes') or 0})
    ui.navigate.to(f'/initialize-task?task_id={inst_id}')

def start_instance(instance_id):
    im.start_instance(instance_id)
    ui.notify("Instance started", color='positive')

def go_complete(instance_id):
    ui.navigate.to(f'/complete_task?instance_id={instance_id}')

def show_details(instance_id):
    inst = InstanceManager.get_instance(instance_id)

    with ui.dialog() as dialog, ui.card():
        ui.label(f"Instance ID: {instance_id}")
        ui.markdown(f"```json\n{inst}\n```")
        ui.button("Close", on_click=dialog.close)

    dialog.open()
