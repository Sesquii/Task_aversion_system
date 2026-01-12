# ui/complete_task.py
from typing import Optional
from nicegui import ui
from fastapi import Request
from backend.instance_manager import InstanceManager
from backend.user_state import UserStateManager
from backend.popup_dispatcher import PopupDispatcher
from backend.recommendation_logger import recommendation_logger
from ui.popup_modal import show_popup_modal
import json

im = InstanceManager()
user_state = UserStateManager()
popup_dispatcher = PopupDispatcher()

def complete_task_page(task_manager, emotion_manager):

    @ui.page('/complete_task')
    def page(request: Request):   # <-- Request injected here (IMPORTANT)

        print("[complete_task] Entered /complete_task page")
        print("[complete_task] Request headers:", request.headers)
        print("[complete_task] Query params:", request.query_params)

        ui.label("Complete Task").classes("text-3xl font-bold mb-4")

        params = dict(request.query_params)
        instance_id = params.get("instance_id")
        edit_mode = params.get("edit", "false").lower() == "true"
        print("[complete_task] instance_id from URL:", instance_id)
        print("[complete_task] edit_mode:", edit_mode)

        # Get instance and predicted values if instance_id is available
        instance = None
        predicted_data = {}
        current_actual_data = {}
        task_id = None
        
        # Get current user for data isolation
        from backend.auth import get_current_user
        current_user_id = get_current_user()
        if current_user_id is None:
            ui.navigate.to('/login')
            return
        
        if instance_id:
            instance = im.get_instance(instance_id, user_id=current_user_id)
            if instance:
                task_id = instance.get('task_id')
                
                # Get predicted values from initialization (these are the baseline)
                predicted_raw = instance.get('predicted') or '{}'
                try:
                    predicted_data = json.loads(predicted_raw) if predicted_raw else {}
                except json.JSONDecodeError:
                    predicted_data = {}
                
                # Check if current instance already has actual values
                actual_raw = instance.get('actual') or '{}'
                try:
                    current_actual_data = json.loads(actual_raw) if actual_raw else {}
                except json.JSONDecodeError:
                    current_actual_data = {}
        
        # Display task description at the top if available
        task_description = predicted_data.get('description', '')
        if task_description and task_description.strip():
            ui.label("Task Description").classes("text-lg font-semibold mt-4")
            ui.label(task_description).classes("text-sm text-gray-700 mb-4 p-3 bg-gray-50 rounded border")

        inst_input = ui.input(
            label='Instance ID (or leave blank to choose)',
            value=instance_id or ''
        )

        # If no instance_id provided, show selector UI
        if not instance_id:
            active = im.list_active_instances()
            print("[complete_task] active instances:", active)

            inst_select = ui.select(
                options=[f"{r['instance_id']} | {r['task_name']}" for r in active],
                label='Pick active instance'
            )

            def on_choose(e):
                print("[complete_task] dropdown event:", e.args)
                if e.args:
                    iid = e.args[0].split('|', 1)[0]
                    print("[complete_task] picked instance_id:", iid)
                    inst_input.set_value(iid)

            inst_select.on('update:model-value', on_choose)

        # Helper to get default value from predicted (initialization) values
        # IMPORTANT: This function copies initialization values even if they are zero. No fallback to task creation.
        # Values are stored on 0-100 scale and should be used as-is (no scaling).
        def get_default_value(actual_key, predicted_key, default=0):
            # First check if current instance already has actual values (for editing)
            if actual_key in current_actual_data:
                val = current_actual_data[actual_key]
                try:
                    num_val = float(val)
                    return int(round(num_val))
                except (ValueError, TypeError):
                    pass
            # Then use predicted values from initialization as baseline
            # Check if key exists (even if value is 0) - use 'in' operator to distinguish missing key from 0 value
            if predicted_key in predicted_data:
                val = predicted_data[predicted_key]
                try:
                    num_val = float(val)
                    return int(round(num_val))
                except (ValueError, TypeError):
                    pass
            return default
        
        # Map predicted keys to actual keys for baseline
        # Use 0 as default (not 50) to ensure we copy initialization values even if zero
        default_relief = get_default_value('actual_relief', 'expected_relief', 0)
        # Get defaults for cognitive components - NO fallback to task creation values
        default_mental_energy = get_default_value('actual_mental_energy', 'expected_mental_energy', 0)
        default_difficulty = get_default_value('actual_difficulty', 'expected_difficulty', 0)
        default_emotional = get_default_value('actual_emotional', 'expected_emotional_load', 0)
        default_physical = get_default_value('actual_physical', 'expected_physical_load', 0)

        # Get the initialization aversion value (the value set when this instance was initialized)
        # Only use initialization_expected_aversion (preserved from initialization of this specific instance)
        # Do NOT use initial_aversion (first-time value for this task) or expected_aversion (may be an average)
        # Handle 0 as a valid initialization value
        
        # Only check for initialization_expected_aversion (preserved initialization value for this instance)
        # Use .get() with a sentinel value to distinguish between missing key and 0 value
        initialization_aversion = predicted_data.get('initialization_expected_aversion', None)
        
        # Process the value: convert to int (values are stored on 0-100 scale, use as-is)
        # Handle 0 as a valid value (0 is not None, so we check if the key exists)
        current_expected_aversion = 0
        if 'initialization_expected_aversion' in predicted_data:
            # Key exists, so process the value (even if it's 0)
            try:
                current_expected_aversion = float(initialization_aversion)
                current_expected_aversion = int(round(current_expected_aversion))
            except (ValueError, TypeError):
                current_expected_aversion = 0
        # If key doesn't exist, current_expected_aversion remains 0 (default)

        # ----- Aversion Update (always show so it can be adjusted) -----
        aversion_slider = None
        if instance_id:
            ui.label("Update Expected Aversion").classes("text-lg font-semibold mt-4")
            ui.label("Your aversion to this task may have changed. Update it here if needed.").classes("text-xs text-gray-500 mb-2")
            aversion_slider = ui.slider(min=0, max=100, step=1, value=current_expected_aversion)

        # ----- Actual values -----

        ui.label("Actual Relief").classes("text-lg font-semibold")
        actual_relief = ui.slider(min=0, max=100, step=1, value=default_relief)
        # Show predicted value from initialization if available
        # Values are stored on 0-100 scale and displayed as-is (no scaling)
        if 'expected_relief' in predicted_data:
            pred_val = predicted_data.get('expected_relief')
            try:
                pred_num = float(pred_val)
                pred_val = int(round(pred_num))
                if pred_val != default_relief:
                    ui.label(f"Initialized: {pred_val} (current: {default_relief})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Initialized: {pred_val}").classes("text-xs text-gray-500")
            except (ValueError, TypeError):
                pass

        ui.label("Mental Energy Needed").classes("text-lg font-semibold")
        ui.label("How much mental effort was required to understand and process this task?").classes("text-xs text-gray-500")
        actual_mental_energy = ui.slider(min=0, max=100, step=1, value=default_mental_energy)
        # Show predicted value from initialization if available
        if 'expected_mental_energy' in predicted_data:
            pred_val = predicted_data.get('expected_mental_energy')
            try:
                pred_num = float(pred_val)
                pred_val = int(round(pred_num))
                if pred_val != default_mental_energy:
                    ui.label(f"Initialized: {pred_val} (current: {default_mental_energy})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Initialized: {pred_val}").classes("text-xs text-gray-500")
            except (ValueError, TypeError):
                pass
        elif 'expected_cognitive_load' in predicted_data:
            # Backward compatibility
            pred_val = predicted_data.get('expected_cognitive_load')
            try:
                pred_num = float(pred_val)
                pred_val = int(round(pred_num))
                ui.label(f"Initialized (from old data): {pred_val}").classes("text-xs text-gray-500")
            except (ValueError, TypeError):
                pass

        ui.label("Task Difficulty").classes("text-lg font-semibold")
        ui.label("How inherently difficult or complex was this task?").classes("text-xs text-gray-500")
        actual_difficulty = ui.slider(min=0, max=100, step=1, value=default_difficulty)
        # Show predicted value from initialization if available
        if 'expected_difficulty' in predicted_data:
            pred_val = predicted_data.get('expected_difficulty')
            try:
                pred_num = float(pred_val)
                pred_val = int(round(pred_num))
                if pred_val != default_difficulty:
                    ui.label(f"Initialized: {pred_val} (current: {default_difficulty})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Initialized: {pred_val}").classes("text-xs text-gray-500")
            except (ValueError, TypeError):
                pass
        elif 'expected_cognitive_load' in predicted_data:
            # Backward compatibility
            pred_val = predicted_data.get('expected_cognitive_load')
            try:
                pred_num = float(pred_val)
                pred_val = int(round(pred_num))
                ui.label(f"Initialized (from old data): {pred_val}").classes("text-xs text-gray-500")
            except (ValueError, TypeError):
                pass

        ui.label("Actual Distress").classes("text-lg font-semibold")
        ui.label("How much stress or emotional activation did you experience?").classes("text-xs text-gray-500")
        actual_emotional = ui.slider(min=0, max=100, step=1, value=default_emotional)
        # Show predicted value from initialization if available
        if 'expected_emotional_load' in predicted_data:
            pred_val = predicted_data.get('expected_emotional_load')
            try:
                pred_num = float(pred_val)
                pred_val = int(round(pred_num))
                if pred_val != default_emotional:
                    ui.label(f"Initialized: {pred_val} (current: {default_emotional})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Initialized: {pred_val}").classes("text-xs text-gray-500")
            except (ValueError, TypeError):
                pass

        ui.label("Actual Physical Demand").classes("text-lg font-semibold")
        actual_physical = ui.slider(min=0, max=100, step=1, value=default_physical)
        # Show predicted value from initialization if available
        if 'expected_physical_load' in predicted_data:
            pred_val = predicted_data.get('expected_physical_load')
            try:
                pred_num = float(pred_val)
                pred_val = int(round(pred_num))
                if pred_val != default_physical:
                    ui.label(f"Initialized: {pred_val} (current: {default_physical})").classes("text-xs text-gray-500")
                else:
                    ui.label(f"Initialized: {pred_val}").classes("text-xs text-gray-500")
            except (ValueError, TypeError):
                pass

        # ----- Emotion Tracking -----
        ui.label("Current Emotional State").classes("text-lg font-semibold mt-4")
        
        # Load initial emotion values from predicted data (from initialization)
        # Emotion loading logic:
        # - When editing: use task-specific emotions from actual/predicted data
        # - When completing new task: use persistent emotions for sliders, but show initial values for comparison
        
        # Always load initial emotions from predicted data (for comparison display)
        initial_emotion_values = predicted_data.get('emotion_values', {})
        if isinstance(initial_emotion_values, str):
            try:
                initial_emotion_values = json.loads(initial_emotion_values)
            except json.JSONDecodeError:
                initial_emotion_values = {}
        if not isinstance(initial_emotion_values, dict):
            # Handle backward compatibility: if emotions is a list, create dict with default 50
            if isinstance(initial_emotion_values, list):
                initial_emotion_values = {emotion: 50 for emotion in initial_emotion_values}
            else:
                # Also check if there's an old 'emotions' list field
                old_emotions = predicted_data.get('emotions', [])
                if isinstance(old_emotions, list):
                    initial_emotion_values = {emotion: 50 for emotion in old_emotions}
                else:
                    initial_emotion_values = {}
        
        # Load actual emotion values if they exist (for editing)
        actual_emotion_values = current_actual_data.get('emotion_values', {})
        if isinstance(actual_emotion_values, str):
            try:
                actual_emotion_values = json.loads(actual_emotion_values)
            except json.JSONDecodeError:
                actual_emotion_values = {}
        if not isinstance(actual_emotion_values, dict):
            actual_emotion_values = {}
        
        # Determine which emotions to show and what default values to use
        if edit_mode:
            # Editing: use task-specific emotions (actual if exists, else initial)
            # Get all emotions from both initial and actual
            initial_emotions = list(initial_emotion_values.keys())
            actual_emotions = list(actual_emotion_values.keys())
            all_emotions = list(set(initial_emotions + actual_emotions))
        else:
            # New completion: use persistent emotions for sliders (current emotional state)
            # But also include initial emotions for comparison
            persistent_emotions = user_state.get_persistent_emotions()
            initial_emotions = list(initial_emotion_values.keys())
            persistent_emotion_list = list(persistent_emotions.keys())
            # Combine: initial emotions (for comparison) + persistent emotions (for current state)
            all_emotions = list(set(initial_emotions + persistent_emotion_list))
        
        # Container for emotion sliders
        emotion_sliders_container = ui.column().classes("w-full gap-2")
        emotion_sliders = {}
        
        def get_emotion_default_value(emotion):
            """Get default value for an emotion slider.
            
            Logic:
            - When editing: use actual value if exists, else initial value, else 50
            - When completing new task: use persistent emotion value (current state), 
              but fall back to initial value if persistent doesn't have it, else 50
            """
            if edit_mode:
                # Editing: prioritize actual value, then initial value
                if emotion in actual_emotion_values:
                    val = actual_emotion_values[emotion]
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        pass
                if emotion in initial_emotion_values:
                    val = initial_emotion_values[emotion]
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        pass
                return 50
            else:
                # New completion: use persistent emotions (current emotional state)
                # This ensures emotions continuously update across pages
                persistent_emotions = user_state.get_persistent_emotions()
                if emotion in persistent_emotions:
                    val = persistent_emotions[emotion]
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        pass
                # Fall back to initial value if persistent doesn't have it
                if emotion in initial_emotion_values:
                    val = initial_emotion_values[emotion]
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        pass
                return 50
        
        def update_emotion_sliders():
            """Update the emotion sliders"""
            emotion_sliders_container.clear()
            emotion_sliders.clear()
            
            if not all_emotions:
                ui.label("No emotions were tracked during initialization. Add emotions below to track how completing this task affects your feelings.").classes("text-xs text-gray-500")
                return
            
            ui.label("Compare with initial values to see how completing the task affected your emotions.").classes("text-xs text-gray-500 mb-2")
            
            for emotion in all_emotions:
                default_value = get_emotion_default_value(emotion)
                initial_value = initial_emotion_values.get(emotion, 50)
                
                with emotion_sliders_container:
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.label(emotion).classes("text-sm font-medium min-w-[120px]")
                        slider = ui.slider(min=0, max=100, step=1, value=default_value)
                        emotion_sliders[emotion] = slider
                        value_label = ui.label(f"{default_value}").classes("text-sm min-w-[40px]")
                        value_label.bind_text_from(slider, 'value', lambda v: str(v))
                    
                    # Show initial value for comparison
                    if emotion in initial_emotion_values:
                        try:
                            init_val = int(float(initial_value))
                            change = default_value - init_val
                            change_text = f"Initial: {init_val}"
                            if change != 0:
                                change_text += f" (change: {change:+d})"
                            ui.label(change_text).classes("text-xs text-gray-500 ml-[120px]")
                        except (ValueError, TypeError):
                            pass
        
        # Initialize emotion sliders
        update_emotion_sliders()
        
        # Single input for emotions (comma-separated) - disabled in edit mode
        ui.label("Track emotions by listing them (comma-separated)").classes("text-xs text-gray-500 mt-4")
        emotions_input = ui.input(
            label="Emotions",
            value=", ".join(all_emotions) if all_emotions else "",
            placeholder="e.g., Excitement, Anxiety, Relief"
        )
        # Edit mode allows full editing now

        def parse_emotions_input():
            raw = emotions_input.value or ''
            parts = [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
            seen = set()
            ordered = []
            for p in parts:
                key = p.lower()
                if key in seen:
                    continue
                seen.add(key)
                ordered.append(p)
                emotion_manager.add_emotion(p)
            return ordered

        def apply_emotion_input():
            nonlocal all_emotions
            all_emotions = parse_emotions_input()
            update_emotion_sliders()

        update_emotions_btn = ui.button("Update emotions", on_click=apply_emotion_input).classes("mb-4")
        # Edit mode allows full editing now

        ui.label("Completion %").classes("text-lg font-semibold")
        ui.label("Enter percentage completed. Use values > 100% if you completed more work than expected.").classes("text-xs text-gray-500 mb-2")
        # Load existing completion percentage if editing
        default_completion_pct = 100
        if edit_mode and instance:
            completion_pct_from_actual = current_actual_data.get('completion_percent')
            if completion_pct_from_actual is not None:
                try:
                    default_completion_pct = int(float(completion_pct_from_actual))
                except (ValueError, TypeError):
                    pass
        completion_pct = ui.number(
            label="Completion Percentage",
            value=default_completion_pct,
            min=0,
            precision=0
        )
        over_completion_note = ui.textarea(
            label="Over-completion Note (optional)",
            placeholder="If you completed more than 100%, describe what extra work you did..."
        ).classes("mt-2")

        # Calculate default duration based on whether task was started
        default_duration = 0
        if instance:
            started_at = instance.get('started_at', '')
            time_spent_before_pause = 0.0
            
            # Get time spent before pause (if task was paused and resumed)
            actual_str = instance.get('actual', '{}')
            if actual_str:
                try:
                    if isinstance(actual_str, str):
                        actual_data = json.loads(actual_str) if actual_str else {}
                    else:
                        actual_data = actual_str if isinstance(actual_str, dict) else {}
                    
                    time_before = actual_data.get('time_spent_before_pause', 0.0)
                    if isinstance(time_before, (int, float)):
                        time_spent_before_pause = float(time_before)
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
            
            if started_at:
                # Calculate duration from start time to now, plus any time from previous sessions
                from datetime import datetime
                import pandas as pd
                try:
                    started = pd.to_datetime(started_at)
                    now = datetime.now()
                    current_session_minutes = (now - started).total_seconds() / 60.0
                    default_duration = current_session_minutes + time_spent_before_pause
                except Exception:
                    # If we can't calculate current session, use time_spent_before_pause if available
                    default_duration = time_spent_before_pause
            else:
                # Task not currently started, use time_spent_before_pause if available
                if time_spent_before_pause > 0:
                    default_duration = time_spent_before_pause
                else:
                    # Default to expected duration from predicted data
                    predicted_raw = instance.get('predicted') or '{}'
                    try:
                        predicted_data = json.loads(predicted_raw) if predicted_raw else {}
                        default_duration = float(predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0)
                    except (ValueError, TypeError, json.JSONDecodeError):
                        pass

        ui.label("Actual Time (minutes)").classes("text-lg font-semibold")
        # Load existing time if editing
        default_actual_time = int(default_duration) if default_duration > 0 else 0
        if edit_mode and instance:
            time_actual_from_data = current_actual_data.get('time_actual_minutes')
            if time_actual_from_data is not None:
                try:
                    default_actual_time = int(float(time_actual_from_data))
                except (ValueError, TypeError):
                    pass
        actual_time = ui.number(value=default_actual_time)

        # Load existing completion notes (instance-specific completion notes, separate from shared instance notes)
        existing_completion_notes = current_actual_data.get('completion_notes', '') or ''
        
        # Also show shared notes if they exist (for reference, not editable here)
        shared_notes = current_actual_data.get('notes', '') or ''
        
        # Show edit mode indicator
        if edit_mode:
            with ui.card().classes("w-full p-3 bg-blue-50 border border-blue-200 mb-4"):
                ui.label("[EDIT MODE] You are editing a completed task. All values can be edited.").classes("text-sm text-blue-800 font-semibold")
                ui.label("Changes will be saved as edited version. You can navigate to the initialization page to edit initialization data as well.").classes("text-xs text-blue-600 mt-1")
                
                def go_to_init_edit():
                    ui.navigate.to(f"/initialize-task?instance_id={instance_id}&edit=true")
                
                ui.button("← Edit Initialization Data", on_click=go_to_init_edit).classes("mt-2 bg-blue-500 text-white")
        
        # Show shared notes if they exist (read-only)
        if shared_notes and not edit_mode:
            ui.label("Shared notes from active task:").classes("text-xs text-gray-600 mt-2 mb-1")
            ui.markdown(shared_notes).classes("text-xs text-gray-700 p-2 bg-gray-50 rounded border mb-2").style("max-height: 150px; overflow-y: auto; white-space: pre-wrap;")
        
        notes_label = 'Completion Notes (optional)' + (' - Instance-specific completion notes' if not edit_mode else '')
        notes = ui.textarea(label=notes_label, value=existing_completion_notes if edit_mode else '')

        def submit_completion():
            print("[complete_task] submit clicked")
            iid = (inst_input.value or "").strip()
            print("[complete_task] iid:", iid)

            if not iid:
                ui.notify("Instance ID required", color='negative')
                return
            
            # Validate that the instance exists
            instance_check = im.get_instance(iid)
            if not instance_check:
                ui.notify(f"Instance {iid} not found", color='negative')
                return

            # Check if sliders were adjusted (compare current values to defaults)
            sliders_adjusted = False
            
            # Check relief slider
            current_relief = int(actual_relief.value) if actual_relief.value is not None else 0
            if current_relief != default_relief:
                sliders_adjusted = True
            
            # Check mental energy slider
            current_mental_energy = int(actual_mental_energy.value) if actual_mental_energy.value is not None else 0
            if current_mental_energy != default_mental_energy:
                sliders_adjusted = True
            
            # Check difficulty slider
            current_difficulty = int(actual_difficulty.value) if actual_difficulty.value is not None else 0
            if current_difficulty != default_difficulty:
                sliders_adjusted = True
            
            # Check emotional slider
            current_emotional = int(actual_emotional.value) if actual_emotional.value is not None else 0
            if current_emotional != default_emotional:
                sliders_adjusted = True
            
            # Check physical slider
            current_physical = int(actual_physical.value) if actual_physical.value is not None else 0
            if current_physical != default_physical:
                sliders_adjusted = True
            
            # Check emotion sliders
            for emotion in emotion_sliders.keys():
                current_val = int(emotion_sliders[emotion].value)
                default_val = get_emotion_default_value(emotion)
                if current_val != default_val:
                    sliders_adjusted = True
                    break
            
            # Check aversion slider if it exists
            if aversion_slider is not None:
                current_aversion = int(aversion_slider.value) if aversion_slider.value is not None else 0
                if current_aversion != current_expected_aversion:
                    sliders_adjusted = True
            
            # Skip popup evaluation if editing a completed task
            if edit_mode:
                # Directly submit without popup
                do_submit_completion()
                return
            
            # Evaluate popup triggers (only for new completions)
            completion_context = {
                'event_type': 'complete',
                'instance_id': iid,
                'task_id': task_id,
                'sliders_adjusted': sliders_adjusted
            }
            
            popup = popup_dispatcher.evaluate_triggers(
                completion_context=completion_context,
                user_id='default'
            )
            
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
                        # User wants to edit sliders, don't submit
                        ui.notify("Please adjust your sliders before completing", color='info')
                        return
                    elif response_value == 'continue':
                        # User wants to continue, proceed with submission
                        do_submit_completion()
                    elif response_value == 'break':
                        # User wants to take a break, still submit but show break message
                        ui.notify("Good idea to take a break! Task will be completed.", color='positive')
                        do_submit_completion()
                    elif response_value == 'view':
                        # User wants to view scores, submit and navigate (if navigation available)
                        ui.notify("Task completed. Check your analytics dashboard for score details.", color='info')
                        do_submit_completion()
                        # TODO: Navigate to analytics/scores view if available
                    else:
                        # Default: proceed with submission
                        do_submit_completion()
                
                show_popup_modal(popup, on_response=handle_popup_response)
                return  # Don't submit yet, wait for popup response
            
            # No popup, proceed with submission
            do_submit_completion()
        
        def do_submit_completion():
            """Internal function that actually performs the submission."""
            iid = (inst_input.value or "").strip()

            # Collect emotion values from sliders
            # Check all emotions that have sliders (even if not in all_emotions)
            # This ensures we capture emotions that were in persistent state but removed from input
            # Filter out emotions with 0 values (0 means emotion is not present/not being tracked)
            # This keeps the data clean: if an emotion was initialized but set to 0 on completion,
            # it means the emotion is no longer present and won't clutter the data.
            # When loading, initialized emotions are still shown so users can see the full picture.
            emotion_values = {}
            # Check all emotions that have sliders (including ones that might have been removed from input)
            for emotion in emotion_sliders.keys():
                value = int(emotion_sliders[emotion].value)
                # Only store non-zero values (0 means emotion is not present and should be removed)
                if value > 0:
                    emotion_values[emotion] = value
            
            # Also include emotions in all_emotions that don't have sliders yet (new emotions)
            for emotion in all_emotions:
                if emotion not in emotion_sliders:
                    # Fallback to default if slider doesn't exist
                    default_val = get_emotion_default_value(emotion)
                    # Only store if > 0
                    if default_val > 0:
                        emotion_values[emotion] = default_val
            
            # Save emotions to persistent state so they carry over to other tasks
            # Setting to 0 removes the emotion from persistent state
            user_state.set_persistent_emotions(emotion_values)

            # Get completion percentage, defaulting to 100 if not provided
            completion_value = completion_pct.value if completion_pct.value is not None else 100
            completion_value = float(completion_value) if completion_value else 100.0
            
            # Completion notes are instance-specific (stored separately from task-level notes)
            # Get existing completion notes
            existing_completion_notes = current_actual_data.get('completion_notes', '') or ''
            new_completion_notes = notes.value or "" if not edit_mode else notes.value or ""
            
            # Use the new completion notes (no merging needed since they're instance-specific)
            combined_completion_notes = new_completion_notes
            
            # Add over-completion note if provided
            if over_completion_note.value and over_completion_note.value.strip():
                if combined_completion_notes:
                    combined_completion_notes += "\n\nOver-completion: " + over_completion_note.value.strip()
                else:
                    combined_completion_notes = "Over-completion: " + over_completion_note.value.strip()
            
            # Safely get slider values with fallbacks
            try:
                relief_val = int(actual_relief.value) if actual_relief.value is not None else 0
            except (AttributeError, TypeError, ValueError):
                relief_val = 0
            try:
                mental_energy_val = int(actual_mental_energy.value) if actual_mental_energy.value is not None else 0
            except (AttributeError, TypeError, ValueError):
                mental_energy_val = 0
            try:
                difficulty_val = int(actual_difficulty.value) if actual_difficulty.value is not None else 0
            except (AttributeError, TypeError, ValueError):
                difficulty_val = 0
            try:
                emotional_val = int(actual_emotional.value) if actual_emotional.value is not None else 0
            except (AttributeError, TypeError, ValueError):
                emotional_val = 0
            try:
                physical_val = int(actual_physical.value) if actual_physical.value is not None else 0
            except (AttributeError, TypeError, ValueError):
                physical_val = 0
            
            actual = {
                'actual_relief': relief_val,
                'actual_mental_energy': mental_energy_val,
                'actual_difficulty': difficulty_val,
                'actual_emotional': emotional_val,  # Keep internal name for formulas
                'actual_physical': physical_val,
                'completion_percent': int(round(completion_value)),
                'time_actual_minutes': int(actual_time.value or 0),
                'completion_notes': combined_completion_notes,  # Instance-specific completion notes
                'emotion_values': emotion_values,  # Store actual emotion values
                # Backward compatibility: also include old cognitive field
                'actual_cognitive': int((mental_energy_val + difficulty_val) / 2),
            }

            print("[complete_task] actual payload:", actual)

            try:
                # If editing, use update method instead of complete_instance to preserve completion status
                if edit_mode:
                    # Update the actual data directly
                    instance = im.get_instance(iid)
                    if instance:
                        # Update actual data
                        from ui.task_editing_manager import _update_actual_data_db, _update_actual_data_csv
                        if im.use_db:
                            _update_actual_data_db(iid, actual)
                        else:
                            _update_actual_data_csv(iid, actual)
                        
                        # Update predicted aversion if slider exists
                        if aversion_slider is not None:
                            updated_aversion = int(aversion_slider.value)
                            predicted_raw = instance.get('predicted') or '{}'
                            try:
                                predicted_dict = json.loads(predicted_raw) if predicted_raw else {}
                                predicted_dict['expected_aversion'] = updated_aversion
                                if 'initialization_expected_aversion' not in predicted_dict:
                                    original_aversion = predicted_dict.get('expected_aversion', updated_aversion)
                                    predicted_dict['initialization_expected_aversion'] = original_aversion
                                im.add_prediction_to_instance(iid, predicted_dict)
                            except json.JSONDecodeError:
                                pass
                else:
                    result = im.complete_instance(iid, actual, user_id=current_user_id)
                    print("[complete_task] complete_instance result:", result)

                    # Log recommendation outcome if this was a recommended task
                    try:
                        instance = im.get_instance(iid, user_id=current_user_id)
                        if instance:
                            task_id = instance.get('task_id')
                            task_name = instance.get('task_name', '')
                            
                            # Get predicted and actual relief scores
                            predicted_raw = instance.get('predicted') or '{}'
                            predicted_data = {}
                            try:
                                predicted_data = json.loads(predicted_raw) if predicted_raw else {}
                            except json.JSONDecodeError:
                                pass
                            
                            predicted_relief = predicted_data.get('expected_relief') or predicted_data.get('relief_score')
                            actual_relief_val = actual.get('actual_relief') or actual.get('relief_score')
                            
                            # Get duration
                            duration_minutes = actual.get('time_actual_minutes')
                            if duration_minutes is None:
                                duration_minutes = instance.get('duration_minutes')
                            
                            recommendation_logger.log_recommendation_outcome(
                                task_id=task_id,
                                instance_id=iid,
                                task_name=task_name,
                                outcome='completed',
                                completion_time_minutes=float(duration_minutes) if duration_minutes else None,
                                actual_relief=float(actual_relief_val) if actual_relief_val is not None else None,
                                predicted_relief=float(predicted_relief) if predicted_relief is not None else None,
                            )
                    except Exception as log_error:
                        # Don't fail if logging fails
                        print(f"[complete_task] Failed to log recommendation outcome: {log_error}")
                    
                    # If aversion slider exists, update the predicted aversion
                    # Note: We preserve initialization_expected_aversion so it always shows the original initialization value
                    if aversion_slider is not None:
                        updated_aversion = int(aversion_slider.value)
                        # Get current predicted data and update expected_aversion
                        instance = im.get_instance(iid)
                        if instance:
                            predicted_raw = instance.get('predicted') or '{}'
                            try:
                                predicted_dict = json.loads(predicted_raw) if predicted_raw else {}
                                # Update expected_aversion but preserve initialization_expected_aversion
                                predicted_dict['expected_aversion'] = updated_aversion
                                # Preserve initialization_expected_aversion if it exists (don't overwrite it)
                                if 'initialization_expected_aversion' not in predicted_dict:
                                    # If it doesn't exist, create it from current expected_aversion before update
                                    # This handles cases where the instance was initialized before this change
                                    original_aversion = predicted_dict.get('expected_aversion', updated_aversion)
                                    predicted_dict['initialization_expected_aversion'] = original_aversion
                                # Update the instance with new predicted data
                                im.add_prediction_to_instance(iid, predicted_dict)
                                print(f"[complete_task] Updated expected_aversion to {updated_aversion}")
                            except json.JSONDecodeError:
                                pass
                
            except Exception as e:
                print("[complete_task] ERROR:", e)
                ui.notify(str(e), color='negative')
                return

            # If editing a completed task, mark it as edited
            if edit_mode:
                from ui.task_editing_manager import mark_instance_as_edited
                mark_instance_as_edited(iid)
                ui.notify("Completion data updated!", color='positive')
                # Navigate back to task editing manager
                ui.navigate.to('/task-editing-manager')
            else:
                ui.notify("Instance completed", color='positive')
                ui.navigate.to('/')

        button_text = "Save Changes" if edit_mode else "Submit Completion"
        ui.button(button_text, on_click=submit_completion)
