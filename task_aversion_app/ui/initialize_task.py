from typing import Optional
from nicegui import ui
from datetime import datetime
import json
import time

from fastapi import Request
from backend.instance_manager import InstanceManager
from backend.user_state import UserStateManager
from backend.popup_dispatcher import PopupDispatcher
from backend.performance_logger import get_perf_logger
from ui.popup_modal import show_popup_modal

im = InstanceManager()
popup_dispatcher = PopupDispatcher()
user_state = UserStateManager()
perf_logger = get_perf_logger()


def initialize_task_page(task_manager, emotion_manager):

    @ui.page('/initialize-task')
    def page(request: Request):
        page_start_time = time.perf_counter()
        perf_logger.log_event("initialize_task_page_load_start", instance_id=request.query_params.get("instance_id"))
        
        params = request.query_params  # ✅

        instance_id = params.get("instance_id")
        edit_mode = params.get("edit", "false").lower() == "true"

        if not instance_id:
            ui.notify("Error: no instance_id provided", color='negative')
            ui.navigate.to('/')
            return

        # Get current user for data isolation
        from backend.auth import get_current_user
        current_user_id = get_current_user()
        if current_user_id is None:
            ui.navigate.to('/login')
            return
        
        with perf_logger.operation("get_instance", instance_id=instance_id):
            instance = im.get_instance(instance_id, user_id=current_user_id)
        
        if not instance:
            ui.notify("Instance not found", color='negative')
            ui.navigate.to('/')
            return

        task_id = instance.get('task_id')
        
        # Check if this is a completed task being edited
        is_completed_task = instance.get('completed_at') or instance.get('is_completed') in ('True', True, 'true')
        
        with perf_logger.operation("get_task", task_id=task_id):
            task = task_manager.get_task(task_id, user_id=current_user_id)
        
        predicted_raw = instance.get('predicted') or '{}'
        try:
            predicted_data = json.loads(predicted_raw) if predicted_raw else {}
        except json.JSONDecodeError:
            predicted_data = {}
        default_estimate = predicted_data.get('time_estimate_minutes') \
            or predicted_data.get('estimate') \
            or (task.get('default_estimate_minutes') if task else 0) \
            or 0
        try:
            default_estimate = int(default_estimate)
        except (TypeError, ValueError):
            default_estimate = 0
        
        # Get previous averages for this task
        with perf_logger.operation("get_previous_task_averages", task_id=task_id):
            previous_averages = im.get_previous_task_averages(task_id, user_id=current_user_id) if task_id else {}
        
        # Get initial aversion (first time doing the task) and previous aversion
        with perf_logger.operation("get_initial_aversion", task_id=task_id):
            initial_aversion = im.get_initial_aversion(task_id, user_id=current_user_id) if task_id else None
        previous_aversion = previous_averages.get('expected_aversion')
        
        # Check if task has been completed at least once
        with perf_logger.operation("has_completed_task", task_id=task_id):
            has_completed = im.has_completed_task(task_id, user_id=current_user_id) if task_id else False
        
        page_load_duration = (time.perf_counter() - page_start_time) * 1000
        perf_logger.log_timing("initialize_task_page_load_total", page_load_duration, instance_id=instance_id, task_id=task_id)
        
        # Check if task has a default_initial_aversion from template
        template_default_aversion = None
        if task:
            template_aversion_str = task.get('default_initial_aversion', '').strip()
            if template_aversion_str:
                try:
                    template_default_aversion = int(float(template_aversion_str))
                    # Ensure it's in valid range
                    if template_default_aversion < 0 or template_default_aversion > 100:
                        template_default_aversion = None
                except (ValueError, TypeError):
                    template_default_aversion = None
        
        # Helper to get default value, scaling from 0-10 to 0-100 if needed
        # When editing a completed task, always use existing values from predicted_data
        def get_default_value(key, default=50):
            # If editing a completed task, always use existing predicted values (even if 0)
            if edit_mode and is_completed_task:
                val = predicted_data.get(key)
                if val is not None:
                    try:
                        num_val = float(val)
                        # Scale from 0-10 to 0-100 if value is <= 10
                        if num_val <= 10 and num_val >= 0:
                            num_val = num_val * 10
                        return int(round(num_val))
                    except (ValueError, TypeError):
                        pass
            # First check if current instance has a value
            val = predicted_data.get(key)
            if val is not None:
                try:
                    num_val = float(val)
                    # Scale from 0-10 to 0-100 if value is <= 10
                    if num_val <= 10 and num_val >= 0:
                        num_val = num_val * 10
                    return int(round(num_val))
                except (ValueError, TypeError):
                    pass
            # Then check previous averages
            if key in previous_averages:
                return previous_averages[key]
            return default
        
        # Default aversion logic:
        # 1. If not first time, use previous average
        # 2. If first time and template has default_initial_aversion, use that
        # 3. Otherwise default to 0
        is_first_time = initial_aversion is None
        if previous_aversion is not None:
            default_aversion = previous_aversion
        elif is_first_time and template_default_aversion is not None:
            default_aversion = template_default_aversion
        else:
            default_aversion = 0
        default_relief = get_default_value('expected_relief', 50)
        # Get defaults for new cognitive components (with backward compatibility)
        default_mental_energy = get_default_value('expected_mental_energy', None)
        if default_mental_energy is None:
            default_mental_energy = get_default_value('expected_cognitive_load', 50)  # Fallback to old field
        default_difficulty = get_default_value('expected_difficulty', None)
        if default_difficulty is None:
            default_difficulty = get_default_value('expected_cognitive_load', 50)  # Fallback to old field
        default_physical = get_default_value('expected_physical_load', 50)
        default_emotional = get_default_value('expected_emotional_load', 50)
        default_motivation = get_default_value('motivation', 50)

        with ui.column().classes("w-full gap-4"):

            # Page title
            title_text = "Edit Task Initialization" if (edit_mode and is_completed_task) else "Initialize Task"
            ui.label(title_text).classes("text-3xl font-bold mb-4")
            
            # Show edit mode notice
            if edit_mode and is_completed_task:
                with ui.card().classes("w-full p-3 bg-blue-50 border border-blue-200 mb-4"):
                    ui.label("[EDIT MODE] You are editing a completed task. Changes will be saved as edited version.").classes("text-sm text-blue-800 font-semibold")
                    ui.label("You can navigate to the completion page to edit completion data as well.").classes("text-xs text-blue-600 mt-1")
                    
                    def go_to_completion_edit():
                        ui.navigate.to(f"/complete_task?instance_id={instance_id}&edit=true")
                    
                    ui.button("Edit Completion Data →", on_click=go_to_completion_edit).classes("mt-2 bg-blue-500 text-white")

            description_field = ui.textarea(
                label="Task Specifics (optional)",
                value=predicted_data.get('description', '') if (edit_mode and is_completed_task) else '',
            )

            # Aversion slider - always show so it can be adjusted for future instances
            ui.label("Aversion (0-100)").classes("text-lg font-semibold")
            
            # Create a container for the slider with marker
            aversion_container = ui.column().classes("w-full gap-2")
            
            with aversion_container:
                # Slider - always visible, defaults to 0 if not marked as aversive, or 50 if marked
                aversion_slider = ui.slider(min=0, max=100, step=1, value=default_aversion)
                
                # Show initial aversion marker and previous aversion info
                if initial_aversion is not None:
                    ui.label(f"Initial aversion: {initial_aversion}").classes("text-xs text-blue-600 font-semibold")
                
                if previous_aversion is not None:
                    if previous_aversion != default_aversion:
                        ui.label(f"Previous average: {previous_aversion} (current: {default_aversion})").classes("text-xs text-gray-500")
                    else:
                        ui.label(f"Previous average: {previous_aversion}").classes("text-xs text-gray-500")
            
            # Add visual marker for initial aversion on the slider using CSS
            if initial_aversion is not None:
                # Create a custom style to show the initial aversion marker
                ui.add_head_html(f"""
                    <style>
                        .aversion-slider-container {{
                            position: relative;
                        }}
                        .aversion-marker {{
                            position: absolute;
                            left: {initial_aversion}%;
                            top: -5px;
                            width: 2px;
                            height: 20px;
                            background-color: #3b82f6;
                            pointer-events: none;
                            z-index: 10;
                        }}
                    </style>
                """)
                # Note: NiceGUI sliders don't easily support visual markers, so we'll show it in text for now

            # Cognitive load slider (NiceGUI 1.x → no label)
            ui.label("Predicted relief").classes("text-lg font-semibold")
            predicted_relief = ui.slider(min=0, max=100, step=1, value=default_relief)
            # Show previous value indicator if available
            if 'expected_relief' in previous_averages:
                prev_val = previous_averages['expected_relief']
                if prev_val != default_relief:
                    ui.label(f"Previous average: {prev_val} (current: {default_relief})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")

            ui.label("Mental Energy Needed").classes("text-lg font-semibold")
            ui.label("How much mental effort is required to understand and process this task?").classes("text-xs text-gray-500")
            mental_energy = ui.slider(min=0, max=100, step=1, value=default_mental_energy)
            if 'expected_mental_energy' in previous_averages:
                prev_val = previous_averages['expected_mental_energy']
                if prev_val != default_mental_energy:
                    ui.label(f"Previous average: {prev_val} (current: {default_mental_energy})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")
            elif 'expected_cognitive_load' in previous_averages:
                # Backward compatibility: show old cognitive_load average
                prev_val = previous_averages['expected_cognitive_load']
                ui.label(f"Previous average (from old data): {prev_val}").classes("text-xs text-gray-500")
            
            ui.label("Task Difficulty").classes("text-lg font-semibold")
            ui.label("How inherently difficult or complex is this task?").classes("text-xs text-gray-500")
            task_difficulty = ui.slider(min=0, max=100, step=1, value=default_difficulty)
            if 'expected_difficulty' in previous_averages:
                prev_val = previous_averages['expected_difficulty']
                if prev_val != default_difficulty:
                    ui.label(f"Previous average: {prev_val} (current: {default_difficulty})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")
            elif 'expected_cognitive_load' in previous_averages:
                # Backward compatibility: show old cognitive_load average
                prev_val = previous_averages['expected_cognitive_load']
                ui.label(f"Previous average (from old data): {prev_val}").classes("text-xs text-gray-500")
            
            ui.label("Expected Distress").classes("text-lg font-semibold")
            ui.label("How much stress or emotional activation do you expect?").classes("text-xs text-gray-500")
            emotional_load = ui.slider(min=0, max=100, step=1, value=default_emotional)
            if 'expected_emotional_load' in previous_averages:
                prev_val = previous_averages['expected_emotional_load']
                if prev_val != default_emotional:
                    ui.label(f"Previous average: {prev_val} (current: {default_emotional})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")
            ui.label("Expected Physical Load").classes("text-lg font-semibold")
            physical_load = ui.slider(min=0, max=100, step=1, value=default_physical)
            if 'expected_physical_load' in previous_averages:
                prev_val = previous_averages['expected_physical_load']
                if prev_val != default_physical:
                    ui.label(f"Previous average: {prev_val} (current: {default_physical})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")

            ui.label("Current Emotional State").classes("text-lg font-semibold")

            # Emotion loading logic:
            # - When editing: use task-specific emotions from predicted_data
            # - When initializing new task: use persistent emotions (current emotional state)
            if edit_mode:
                # Editing: load task-specific emotions from predicted data
                emotion_values_dict = predicted_data.get('emotion_values', {})
                if isinstance(emotion_values_dict, str):
                    try:
                        emotion_values_dict = json.loads(emotion_values_dict)
                    except json.JSONDecodeError:
                        emotion_values_dict = {}
                if not isinstance(emotion_values_dict, dict):
                    # Handle backward compatibility: if emotions is a list, create dict with default 50
                    if isinstance(emotion_values_dict, list):
                        emotion_values_dict = {emotion: 50 for emotion in emotion_values_dict}
                    else:
                        # Also check if there's an old 'emotions' list field
                        old_emotions = predicted_data.get('emotions', [])
                        if isinstance(old_emotions, list):
                            emotion_values_dict = {emotion: 50 for emotion in old_emotions}
                        else:
                            emotion_values_dict = {}
            else:
                # New initialization: use persistent emotions (current emotional state)
                # This ensures emotions continuously update across pages
                emotion_values_dict = user_state.get_persistent_emotions()

            # Single text input for emotions (comma-separated or one at a time)
            existing_emotions = list(emotion_values_dict.keys()) if emotion_values_dict else []
            emotions_input = ui.input(
                label="Emotions (comma-separated)",
                value=", ".join(existing_emotions) if existing_emotions else ""
            )

            def parse_emotions_input():
                raw = emotions_input.value or ''
                # Allow commas or semicolons as separators
                parts = [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
                # Preserve order while removing duplicates
                seen = set()
                ordered = []
                for p in parts:
                    if p.lower() not in seen:
                        seen.add(p.lower())
                        ordered.append(p)
                        # Persist to emotion store for future sessions
                        emotion_manager.add_emotion(p)
                return ordered

            # Container for emotion sliders
            emotion_sliders_container = ui.column().classes("w-full gap-2")

            # Dictionary to store emotion sliders
            emotion_sliders = {}

            def update_emotion_sliders():
                """Update the emotion sliders based on selected emotions"""
                # Clear existing sliders
                emotion_sliders_container.clear()
                emotion_sliders.clear()

                selected_emotions = parse_emotions_input()
                
                if not selected_emotions:
                    return
                
                for emotion in selected_emotions:
                    # Get default value from existing data or default to 50
                    default_value = emotion_values_dict.get(emotion, 50)
                    try:
                        default_value = int(float(default_value))
                        if default_value < 0 or default_value > 100:
                            default_value = 50
                    except (ValueError, TypeError):
                        default_value = 50
                    
                    with emotion_sliders_container:
                        ui.label(emotion).classes("text-sm")
                        slider = ui.slider(min=0, max=100, step=1, value=default_value)
                        emotion_sliders[emotion] = slider
                        ui.label(f"Value: {default_value}").bind_text_from(slider, 'value', lambda v: f"Value: {v}").classes("text-xs text-gray-500")

            def apply_emotion_input():
                update_emotion_sliders()

            ui.button("Update emotions", on_click=apply_emotion_input)

            # Initialize sliders if emotions are already selected
            if emotion_values_dict:
                update_emotion_sliders()

            ui.label("Physical Context").classes("text-lg font-semibold")
            physical_context_value = predicted_data.get('physical_context', 'None') if (edit_mode and is_completed_task) else None
            physical_context = ui.select(
                ["None", "Home", "Work", "Gym", "Outdoors", "Errands", "Custom..."],
                value=physical_context_value if physical_context_value and physical_context_value in ["None", "Home", "Work", "Gym", "Outdoors", "Errands"] else None
            )

            custom_physical = ui.input(placeholder="Custom Physical Context")
            if physical_context_value == "Custom..." or (physical_context_value and physical_context_value not in ["None", "Home", "Work", "Gym", "Outdoors", "Errands"]):
                custom_physical.set_value(physical_context_value if physical_context_value != "Custom..." else "")
                custom_physical.set_visibility(True)
                if physical_context.value != "Custom...":
                    physical_context.set_value("Custom...")
            else:
                custom_physical.set_visibility(False)

            def physical_changed(e):
                custom_physical.set_visibility(e.args == "Custom...")

            physical_context.on("update:model-value", physical_changed)

            ui.label("Motivation Level").classes("text-lg font-semibold")
            motivation = ui.slider(min=0, max=100, step=1, value=default_motivation)
            if 'motivation' in previous_averages:
                prev_val = previous_averages['motivation']
                if prev_val != default_motivation:
                    ui.label(f"Previous average: {prev_val} (current: {default_motivation})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")

            estimate_input = ui.number(
                label="Estimated Time to Complete (minutes)",
                value=default_estimate,
                min=0
            )

            def save():
                # Check if sliders were adjusted (compare current values to defaults)
                sliders_adjusted = False
                
                # Check aversion slider
                current_aversion = max(0, int(aversion_slider.value or 0))
                if current_aversion != default_aversion:
                    sliders_adjusted = True
                
                # Check relief slider
                current_relief = int(predicted_relief.value) if predicted_relief.value is not None else 0
                if current_relief != default_relief:
                    sliders_adjusted = True
                
                # Check mental energy slider
                current_mental_energy = int(mental_energy.value) if mental_energy.value is not None else 0
                if current_mental_energy != default_mental_energy:
                    sliders_adjusted = True
                
                # Check difficulty slider
                current_difficulty = int(task_difficulty.value) if task_difficulty.value is not None else 0
                if current_difficulty != default_difficulty:
                    sliders_adjusted = True
                
                # Check emotional slider
                current_emotional = int(emotional_load.value) if emotional_load.value is not None else 0
                if current_emotional != default_emotional:
                    sliders_adjusted = True
                
                # Check physical slider
                current_physical = int(physical_load.value) if physical_load.value is not None else 0
                if current_physical != default_physical:
                    sliders_adjusted = True
                
                # Check motivation slider
                current_motivation = int(motivation.value) if motivation.value is not None else 0
                if current_motivation != default_motivation:
                    sliders_adjusted = True
                
                # Check emotion sliders
                for emotion in emotion_sliders.keys():
                    current_val = int(emotion_sliders[emotion].value)
                    default_val = emotion_values_dict.get(emotion, 50)
                    try:
                        default_val = int(float(default_val))
                        if default_val < 0 or default_val > 100:
                            default_val = 50
                    except (ValueError, TypeError):
                        default_val = 50
                    if current_val != default_val:
                        sliders_adjusted = True
                        break
                
                # Skip popup evaluation if editing a completed task
                if edit_mode and is_completed_task:
                    # Directly save without popup
                    do_save()
                    return
                
                # Evaluate popup triggers (only for new initializations)
                initialization_context = {
                    'event_type': 'initialize',
                    'instance_id': instance_id,
                    'task_id': task_id,
                    'sliders_adjusted': sliders_adjusted
                }
                
                perf_logger.log_event("popup_evaluation_start", 
                                    instance_id=instance_id, 
                                    task_id=task_id,
                                    sliders_adjusted=sliders_adjusted)
                popup_eval_start = time.perf_counter()
                
                popup = popup_dispatcher.evaluate_triggers(
                    completion_context=initialization_context,
                    user_id='default'
                )
                
                popup_eval_duration = (time.perf_counter() - popup_eval_start) * 1000
                perf_logger.log_timing("popup_evaluation", popup_eval_duration,
                                     instance_id=instance_id,
                                     task_id=task_id,
                                     sliders_adjusted=sliders_adjusted,
                                     popup_shown=popup is not None)
                
                # If popup should show, display it and handle response
                if popup:
                    def handle_popup_response(response_value: str, helpful: Optional[bool], comment: Optional[str]):
                        # Log response
                        popup_dispatcher.handle_popup_response(
                            trigger_id=popup['trigger_id'],
                            response_value=response_value,
                            helpful=helpful,
                            comment=comment,
                            task_id=task_id,
                            user_id='default'
                        )
                        
                        if response_value == 'edit':
                            # User wants to edit sliders, don't save
                            ui.notify("Please adjust your sliders before initializing", color='info')
                            return
                        elif response_value == 'continue':
                            # User wants to continue, proceed with save
                            do_save()
                    
                    show_popup_modal(popup, on_response=handle_popup_response)
                    return  # Don't save yet, wait for popup response
                
                # No popup, proceed with save
                do_save()
            
            def do_save():
                """Internal function that actually performs the save."""
                save_start_time = time.perf_counter()
                perf_logger.log_event("do_save_start", instance_id=instance_id, task_id=task_id)
                
                emotion_list = parse_emotions_input()
                physical_value = (
                    custom_physical.value if physical_context.value == "Custom..." else physical_context.value
                ) or "None"
                try:
                    estimate_val = int(estimate_input.value or 0)
                except (TypeError, ValueError):
                    estimate_val = 0

                # Collect emotion values from sliders
                # Check all emotions that have sliders (even if not in emotion_list)
                # This ensures we capture emotions that were in persistent state but removed from input
                # Filter out emotions with 0 values (0 means emotion is not present/not being tracked)
                # This keeps the data clean: if an emotion is set to 0, it's effectively removed from tracking
                # The emotions list is still stored separately for backward compatibility
                emotion_values = {}
                # Check all emotions that have sliders (including ones that might have been removed from input)
                for emotion in emotion_sliders.keys():
                    value = int(emotion_sliders[emotion].value)
                    # Only store non-zero values (0 means emotion is not present and should be removed)
                    if value > 0:
                        emotion_values[emotion] = value
                
                # Also include emotions in emotion_list that don't have sliders yet (new emotions)
                for emotion in emotion_list:
                    if emotion not in emotion_sliders:
                        # If slider doesn't exist, use default 50 (but only if > 0)
                        # This shouldn't happen in normal flow, but handle it gracefully
                        emotion_values[emotion] = 50
                
                # Save emotions to persistent state so they carry over to other tasks
                # Setting to 0 removes the emotion from persistent state
                with perf_logger.operation("set_persistent_emotions"):
                    user_state.set_persistent_emotions(emotion_values)

                # Determine if this is the first time doing the task
                # Check if there are any other initialized instances for this task
                is_first_time = initial_aversion is None
                
                # Get aversion value: always use slider value (slider is now always shown)
                # Ensure it's at least 0 (or 1 if using 1-100 scale - but we use 0-100, so 0 is fine)
                current_aversion = max(0, int(aversion_slider.value or 0))
                
                # If this is the first time, set initial_aversion; otherwise use expected_aversion
                predicted_payload = {
                    "time_estimate_minutes": estimate_val,
                    "emotions": emotion_list,  # Keep for backward compatibility
                    "emotion_values": emotion_values,  # New: dictionary of emotion -> value
                    "expected_relief": predicted_relief.value,
                    "expected_mental_energy": mental_energy.value,
                    "expected_difficulty": task_difficulty.value,
                    "expected_physical_load": physical_load.value,
                    "expected_emotional_load": emotional_load.value,  # Keep internal name for formulas
                    "physical_context": physical_value,
                    "motivation": motivation.value,
                    "description": description_field.value or '',
                    "expected_aversion": current_aversion,  # Current aversion value (always saved, minimum 0)
                    # Backward compatibility: also include old cognitive_load field
                    "expected_cognitive_load": (mental_energy.value + task_difficulty.value) / 2,
                }
                
                # If this is the first time doing the task, set initial_aversion
                if is_first_time:
                    predicted_payload["initial_aversion"] = current_aversion
                
                # Always store the initialization value separately so it can be preserved
                # This allows the completion page to always show the original initialization value
                predicted_payload["initialization_expected_aversion"] = current_aversion

                entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "instance_id": instance_id,
                    "task": instance.get('task_id'),
                    "emotions": ",".join(emotion_list),
                    "expected_mental_energy": mental_energy.value,
                    "expected_difficulty": task_difficulty.value,
                    "expected_physical_load": physical_load.value,
                    "expected_emotional_load": emotional_load.value,
                    "physical_context": physical_value,
                    "motivation": motivation.value,
                    "description": description_field.value or '',
                    "estimate_minutes": estimate_val,
                    "initialized": True,
                    "completed": False,
                    # Backward compatibility
                    "expected_cognitive_load": (mental_energy.value + task_difficulty.value) / 2,
                }

                try:
                    # This will set initialized_at if not already set
                    with perf_logger.operation("add_prediction_to_instance", instance_id=instance_id):
                        im.add_prediction_to_instance(instance_id, predicted_payload, user_id=current_user_id)
                    
                    # If editing a completed task, mark it as edited
                    if edit_mode and is_completed_task:
                        from ui.task_editing_manager import mark_instance_as_edited
                        mark_instance_as_edited(instance_id)
                except Exception as exc:
                    perf_logger.log_error("add_prediction_to_instance failed", exc, instance_id=instance_id)
                    ui.notify(f"Failed to save instance: {exc}", color='negative')
                    return

                # Only save initialization entry if not editing (to avoid duplicate entries)
                if not (edit_mode and is_completed_task):
                    with perf_logger.operation("save_initialization_entry", instance_id=instance_id):
                        task_manager.save_initialization_entry(entry)
                
                save_duration = (time.perf_counter() - save_start_time) * 1000
                perf_logger.log_timing("do_save_total", save_duration, instance_id=instance_id, task_id=task_id)
                
                navigation_start = time.perf_counter()
                perf_logger.log_event("navigation_start", instance_id=instance_id, task_id=task_id)
                
                if edit_mode and is_completed_task:
                    ui.notify("Task initialization updated!", color='positive')
                    # Navigate back to task editing manager
                    ui.navigate.to('/task-editing-manager')
                else:
                    ui.notify("Task initialized!", color='positive')
                    ui.navigate.to('/')
                
                # Log navigation time (this happens asynchronously, so we log it immediately)
                navigation_duration = (time.perf_counter() - navigation_start) * 1000
                perf_logger.log_timing("navigation_triggered", navigation_duration, instance_id=instance_id, task_id=task_id)

            button_text = "Save Changes" if (edit_mode and is_completed_task) else "Save Initialization"
            ui.button(button_text, on_click=save).classes("mt-4")
