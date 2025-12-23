# ui/complete_task.py
from nicegui import ui
from fastapi import Request
from backend.instance_manager import InstanceManager
from backend.user_state import UserStateManager
import json

im = InstanceManager()
user_state = UserStateManager()

def complete_task_page(task_manager, emotion_manager):

    @ui.page('/complete_task')
    def page(request: Request):   # <-- Request injected here (IMPORTANT)

        print("[complete_task] Entered /complete_task page")
        print("[complete_task] Request headers:", request.headers)
        print("[complete_task] Query params:", request.query_params)

        ui.label("Complete Task").classes("text-3xl font-bold mb-4")

        params = dict(request.query_params)
        instance_id = params.get("instance_id")
        print("[complete_task] instance_id from URL:", instance_id)

        # Get instance and predicted values if instance_id is available
        instance = None
        predicted_data = {}
        current_actual_data = {}
        task_id = None
        
        if instance_id:
            instance = im.get_instance(instance_id)
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

        # Helper to get default value from predicted (initialization) values, scaling from 0-10 to 0-100 if needed
        # IMPORTANT: This function copies initialization values even if they are zero. No fallback to task creation.
        def get_default_value(actual_key, predicted_key, default=0):
            # First check if current instance already has actual values (for editing)
            if actual_key in current_actual_data:
                val = current_actual_data[actual_key]
                try:
                    num_val = float(val)
                    # Scale from 0-10 to 0-100 if value is <= 10
                    if num_val <= 10 and num_val >= 0:
                        num_val = num_val * 10
                    return int(round(num_val))
                except (ValueError, TypeError):
                    pass
            # Then use predicted values from initialization as baseline
            # Check if key exists (even if value is 0) - use 'in' operator to distinguish missing key from 0 value
            if predicted_key in predicted_data:
                val = predicted_data[predicted_key]
                try:
                    num_val = float(val)
                    # Scale from 0-10 to 0-100 if value is <= 10
                    if num_val <= 10 and num_val >= 0:
                        num_val = num_val * 10
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
        
        # Process the value: scale if needed and convert to int
        # Handle 0 as a valid value (0 is not None, so we check if the key exists)
        current_expected_aversion = 0
        if 'initialization_expected_aversion' in predicted_data:
            # Key exists, so process the value (even if it's 0)
            try:
                current_expected_aversion = float(initialization_aversion)
                # Scale from 0-10 to 0-100 if needed
                if current_expected_aversion <= 10 and current_expected_aversion >= 0:
                    current_expected_aversion = current_expected_aversion * 10
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
        if 'expected_relief' in predicted_data:
            pred_val = predicted_data.get('expected_relief')
            try:
                pred_num = float(pred_val)
                if pred_num <= 10 and pred_num >= 0:
                    pred_num = pred_num * 10
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
                if pred_num <= 10 and pred_num >= 0:
                    pred_num = pred_num * 10
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
                if pred_num <= 10 and pred_num >= 0:
                    pred_num = pred_num * 10
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
                if pred_num <= 10 and pred_num >= 0:
                    pred_num = pred_num * 10
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
                if pred_num <= 10 and pred_num >= 0:
                    pred_num = pred_num * 10
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
                if pred_num <= 10 and pred_num >= 0:
                    pred_num = pred_num * 10
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
                if pred_num <= 10 and pred_num >= 0:
                    pred_num = pred_num * 10
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
        
        # If no initial emotions from this task, load persistent emotions
        if not initial_emotion_values:
            initial_emotion_values = user_state.get_persistent_emotions()
        
        # Load actual emotion values if they exist (for editing)
        actual_emotion_values = current_actual_data.get('emotion_values', {})
        if isinstance(actual_emotion_values, str):
            try:
                actual_emotion_values = json.loads(actual_emotion_values)
            except json.JSONDecodeError:
                actual_emotion_values = {}
        if not isinstance(actual_emotion_values, dict):
            actual_emotion_values = {}
        
        # Get all emotions that were tracked initially, plus any new ones added
        initial_emotions = list(initial_emotion_values.keys())
        actual_emotions = list(actual_emotion_values.keys())
        all_emotions = list(set(initial_emotions + actual_emotions))
        
        # Container for emotion sliders
        emotion_sliders_container = ui.column().classes("w-full gap-2")
        emotion_sliders = {}
        
        def get_emotion_default_value(emotion):
            """Get default value for an emotion: actual value if exists, else initial value, else 50
            
            Note: If an emotion was initialized but is not in actual_emotion_values, it means
            it was either never set or was set to 0 (and filtered out). We default to showing
            the initial value so the user can see what it was and adjust if needed.
            """
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
        
        # Single input for emotions (comma-separated)
        ui.label("Track emotions by listing them (comma-separated)").classes("text-xs text-gray-500 mt-4")
        emotions_input = ui.input(
            label="Emotions",
            value=", ".join(all_emotions) if all_emotions else "",
            placeholder="e.g., Excitement, Anxiety, Relief"
        )

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

        ui.button("Update emotions", on_click=apply_emotion_input).classes("mb-4")

        ui.label("Completion %").classes("text-lg font-semibold")
        ui.label("Enter percentage completed. Use values > 100% if you completed more work than expected.").classes("text-xs text-gray-500 mb-2")
        completion_pct = ui.number(
            label="Completion Percentage",
            value=100,
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
            if started_at:
                # Calculate duration from start time to now
                from datetime import datetime
                import pandas as pd
                try:
                    started = pd.to_datetime(started_at)
                    now = datetime.now()
                    default_duration = (now - started).total_seconds() / 60.0
                except Exception:
                    pass
            else:
                # Default to expected duration from predicted data
                predicted_raw = instance.get('predicted') or '{}'
                try:
                    predicted_data = json.loads(predicted_raw) if predicted_raw else {}
                    default_duration = float(predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0)
                except (ValueError, TypeError, json.JSONDecodeError):
                    pass

        ui.label("Actual Time (minutes)").classes("text-lg font-semibold")
        actual_time = ui.number(value=int(default_duration) if default_duration > 0 else 0)

        notes = ui.textarea(label='Notes (optional)')

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
            
            # Combine notes with over-completion note if provided
            combined_notes = notes.value or ""
            if over_completion_note.value and over_completion_note.value.strip():
                if combined_notes:
                    combined_notes += "\n\nOver-completion: " + over_completion_note.value.strip()
                else:
                    combined_notes = "Over-completion: " + over_completion_note.value.strip()
            
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
                'notes': combined_notes,
                'emotion_values': emotion_values,  # Store actual emotion values
                # Backward compatibility: also include old cognitive field
                'actual_cognitive': int((mental_energy_val + difficulty_val) / 2),
            }

            print("[complete_task] actual payload:", actual)

            try:
                result = im.complete_instance(iid, actual)
                print("[complete_task] complete_instance result:", result)
                
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

            ui.notify("Instance completed", color='positive')
            ui.navigate.to('/')

        ui.button("Submit Completion", on_click=submit_completion)
