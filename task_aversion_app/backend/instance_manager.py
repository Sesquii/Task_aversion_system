# backend/instance_manager.py
import os
import pandas as pd
from datetime import datetime
from typing import Optional
import json

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
class InstanceManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.file = os.path.join(DATA_DIR, 'task_instances.csv')
        # fields: instance_id, task_id, task_name, task_version, created_at, initialized_at, started_at, completed_at,
        # predicted (json), actual (json), procrastination_score, proactive_score, is_completed, is_deleted, delay_minutes
        if not os.path.exists(self.file):
            pd.DataFrame(columns=[
                'instance_id','task_id','task_name','task_version','created_at','initialized_at','started_at',
                'completed_at','cancelled_at','predicted','actual','procrastination_score','proactive_score',
                'is_completed','is_deleted','status','delay_minutes'
            ]).to_csv(self.file, index=False)
        self._reload()

    def _reload(self):
        self.df = pd.read_csv(self.file, dtype=str).fillna('')
        defaults = {
            'predicted': '',
            'actual': '',
            'cancelled_at': '',
            'duration_minutes': '',
            'delay_minutes': '',
            'relief_score': '',
            'cognitive_load': '',
            'emotional_load': '',
            'environmental_effect': '',
            'skills_improved': '',
            'behavioral_score': '',
            'net_relief': '',
        }
        for col, default in defaults.items():
            if col not in self.df.columns:
                self.df[col] = default
        if 'status' not in self.df.columns:
            if 'is_completed' in self.df.columns:
                self.df['status'] = self.df['is_completed'].apply(
                    lambda v: 'completed' if str(v).lower() == 'true' else 'active'
                )
            else:
                self.df['status'] = 'active'
        else:
            fallback = (
                self.df['is_completed'].apply(lambda v: 'completed' if str(v).lower() == 'true' else 'active')
                if 'is_completed' in self.df.columns else pd.Series(['active'] * len(self.df), index=self.df.index)
            )
            self.df['status'] = self.df['status'].replace('', None)
            self.df['status'] = self.df['status'].fillna(fallback)

    def _save(self):
        self.df.to_csv(self.file, index=False)
        self._reload()

    def create_instance(self, task_id, task_name, task_version=1, predicted: dict = None):
        self._reload()
        instance_id = f"i{int(datetime.now().timestamp())}"
        row = {
            'instance_id': instance_id,
            'task_id': task_id,
            'task_name': task_name,
            'task_version': task_version,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'initialized_at': '',  # Will be set when user saves initialization form
            'started_at': '',
            'completed_at': '',
            'cancelled_at': '',
            'predicted': json.dumps(predicted or {}),
            'actual': json.dumps({}),
            'procrastination_score': '',
            'proactive_score': '',
            'is_completed': 'False',
            'is_deleted': 'False',
            'status': 'active',
            'duration_minutes': '',
            'delay_minutes': '',
            'relief_score': '',
            'cognitive_load': '',
            'emotional_load': '',
            'environmental_effect': '',
            'skills_improved': '',
            'behavioral_score': '',
            'net_relief': '',
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save()
        return instance_id

    def list_active_instances(self):
        self._reload()
        status_series = self.df['status'].str.lower()
        df = self.df[
            (self.df['is_completed'] != 'True') &
            (self.df['is_deleted'] != 'True') &
            (~status_series.isin(['completed', 'cancelled']))
        ]
        return df.to_dict(orient='records')

    def get_instance(self, instance_id):
        self._reload()
        rows = self.df[self.df['instance_id'] == instance_id]
        if rows.empty:
            return None
        row = rows.iloc[0].to_dict()
        return row

    def start_instance(self, instance_id):
        self._reload()
        idx = self.df.index[self.df['instance_id']==instance_id][0]
        self.df.at[idx,'started_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()

    def complete_instance(self, instance_id, actual: dict):
        import json, math
        self._reload()
        idx = self.df.index[self.df['instance_id']==instance_id][0]
        # set actual JSON
        self.df.at[idx,'actual'] = json.dumps(actual)
        completed_at = datetime.now()
        self.df.at[idx,'completed_at'] = completed_at.strftime("%Y-%m-%d %H:%M")
        self.df.at[idx,'is_completed'] = 'True'
        self.df.at[idx,'status'] = 'completed'
        self.df.at[idx,'cancelled_at'] = ''
        
        # Calculate duration and delay
        try:
            initialized_at_str = self.df.at[idx,'initialized_at']
            started_at_str = self.df.at[idx,'started_at']
            initialized_at = pd.to_datetime(initialized_at_str) if initialized_at_str else None
            started_at = pd.to_datetime(started_at_str) if started_at_str else None
            
            # Get duration from actual dict, or calculate from start time
            duration_minutes = actual.get('time_actual_minutes')
            if duration_minutes is None or duration_minutes == '':
                # If start button was used, calculate duration from start to completion
                if started_at:
                    duration_minutes = (completed_at - started_at).total_seconds() / 60.0
                else:
                    # Default to expected duration
                    predicted = json.loads(self.df.at[idx,'predicted'] or "{}")
                    duration_minutes = float(predicted.get('time_estimate_minutes') or predicted.get('estimate') or 0)
            
            # Store duration
            if duration_minutes is not None and duration_minutes != '':
                self.df.at[idx, 'duration_minutes'] = str(duration_minutes)
                # Also update in actual dict if not already set
                if 'time_actual_minutes' not in actual or actual.get('time_actual_minutes') == '':
                    actual['time_actual_minutes'] = duration_minutes
                    self.df.at[idx,'actual'] = json.dumps(actual)
            
            # Calculate delay: time from initialization to start (if started) or to completion minus duration (if not started)
            if initialized_at:
                if started_at:
                    # Delay = start time - initialization time
                    delay_minutes = (started_at - initialized_at).total_seconds() / 60.0
                else:
                    # Delay = completion time - duration - initialization time
                    if duration_minutes:
                        delay_minutes = (completed_at - initialized_at).total_seconds() / 60.0 - float(duration_minutes)
                    else:
                        delay_minutes = (completed_at - initialized_at).total_seconds() / 60.0
                self.df.at[idx, 'delay_minutes'] = str(round(delay_minutes, 2))
        except Exception as e:
            print(f"[InstanceManager] Error calculating duration/delay: {e}")
        
        # compute simple procrastination/proactive metrics
        try:
            created = pd.to_datetime(self.df.at[idx,'created_at'])
            started = pd.to_datetime(self.df.at[idx,'started_at']) if self.df.at[idx,'started_at'] else pd.to_datetime(self.df.at[idx,'initialized_at']) if self.df.at[idx,'initialized_at'] else created
            predicted = json.loads(self.df.at[idx,'predicted'] or "{}")
            estimate = float(predicted.get('time_estimate_minutes') or predicted.get('estimate') or 0) or 1.0
            delay = (started - created).total_seconds() / 60.0
            procrast = delay / max(estimate, 1.0)
            proactive = max(0.0, 1.0 - (delay / max(estimate*2.0,1.0)))
            self.df.at[idx,'procrastination_score'] = round(min(procrast, 10.0), 3)
            self.df.at[idx,'proactive_score'] = round(min(max(proactive*10.0,0.0), 10.0), 3)
        except Exception:
            self.df.at[idx,'procrastination_score'] = ''
            self.df.at[idx,'proactive_score'] = ''
        
        self._update_attributes_from_payload(idx, actual)
        self._save()

    def cancel_instance(self, instance_id, actual: dict):
        import json
        self._reload()
        matches = self.df.index[self.df['instance_id'] == instance_id]
        if len(matches) == 0:
            raise ValueError(f"Instance {instance_id} not found")
        idx = matches[0]
        self.df.at[idx, 'actual'] = json.dumps(actual or {})
        self.df.at[idx, 'cancelled_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.df.at[idx, 'status'] = 'cancelled'
        self.df.at[idx, 'is_completed'] = 'True'
        self.df.at[idx, 'completed_at'] = ''
        self.df.at[idx, 'procrastination_score'] = ''
        self.df.at[idx, 'proactive_score'] = ''
        self._update_attributes_from_payload(idx, actual or {})
        self._save()

    def add_prediction_to_instance(self, instance_id, predicted: dict):
        import json
        self._reload()
        idx = self.df.index[self.df['instance_id'] == instance_id][0]
        self.df.at[idx,'predicted'] = json.dumps(predicted)
        # Always set initialized_at when prediction is added (initialization happens)
        if not self.df.at[idx,'initialized_at'] or self.df.at[idx,'initialized_at'] == '':
            self.df.at[idx,'initialized_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Extract predicted values to columns (only if columns are empty)
        self._update_attributes_from_payload(idx, predicted)
        self._save()

    def ensure_instance_for_task(self, task_id, task_name, predicted: dict = None):
        # create an instance and return id
        return self.create_instance(task_id, task_name, task_version=1, predicted=predicted)



    def delete_instance(self, instance_id):
        print(f"[InstanceManager] delete_instance called with: {instance_id}")
        self._reload()
        before = len(self.df)
        self.df = self.df[self.df['instance_id'] != instance_id]
        if len(self.df) == before:
            print("[InstanceManager] No matching instance to delete.")
            return False
        self._save()
        print("[InstanceManager] Instance deleted.")
        return True

    def _update_attributes_from_payload(self, idx, payload: dict):
        """Persist wellbeing attributes if caller provided them.
        Maps both direct keys and common aliases from JSON payloads."""
        if not isinstance(payload, dict):
            return
        
        # Mapping from payload keys to CSV column names
        # Handles both direct matches and common aliases
        attribute_mappings = {
            # Direct mappings
            'duration_minutes': ['duration_minutes', 'time_actual_minutes', 'actual_time'],
            'relief_score': ['relief_score', 'actual_relief', 'expected_relief'],
            'cognitive_load': ['cognitive_load', 'actual_cognitive', 'expected_cognitive_load', 'expected_cognitive'],
            'emotional_load': ['emotional_load', 'actual_emotional', 'expected_emotional_load', 'expected_emotional'],
            'environmental_effect': ['environmental_effect', 'environmental_fit'],
            'skills_improved': ['skills_improved'],
            'behavioral_score': ['behavioral_score'],
            'net_relief': ['net_relief'],
        }
        
        # Also handle physical load if present
        if 'actual_physical' in payload or 'expected_physical_load' in payload:
            # Store in a note or additional field if needed
            pass
        
        # Extract values using mappings
        for csv_column, possible_keys in attribute_mappings.items():
            value = None
            # Try each possible key in order
            for key in possible_keys:
                if key in payload:
                    val = payload[key]
                    # Allow 0 as a valid numeric value - check if it's a number (including 0) or non-empty
                    if val is not None:
                        # For numbers, 0 is valid; for strings, must be non-empty
                        if isinstance(val, (int, float)) or (val != ''):
                            value = val
                            break
            
            # Only update if we found a value and the column is currently empty
            # Explicitly allow 0 as a valid numeric value
            if value is not None:
                # For numbers, 0 is valid; for strings, must be non-empty
                if isinstance(value, (int, float)) or (value != ''):
                    current_value = self.df.at[idx, csv_column]
                    if current_value == '' or pd.isna(current_value):
                        self.df.at[idx, csv_column] = value


    def list_recent_completed(self, limit=20):
        print(f"[InstanceManager] list_recent_completed called (limit={limit})")
        self._reload()
        df = self.df[self.df['completed_at'].astype(str).str.strip() != '']
        if df.empty:
            return []
        df = df.sort_values("completed_at", ascending=False)
        return df.head(limit).to_dict(orient="records")
    
    def backfill_attributes_from_json(self):
        """Backfill empty attribute columns from JSON data in predicted/actual columns.
        This is a migration method to fix existing data."""
        import json
        self._reload()
        updated_count = 0
        
        # Helper to check if value is empty
        def is_empty(val):
            if val is None:
                return True
            if isinstance(val, float) and pd.isna(val):
                return True
            if str(val).strip() == '':
                return True
            return False
        
        for idx in self.df.index:
            row_updated = False
            
            # Try to extract from actual JSON first (most accurate)
            actual_str = str(self.df.at[idx, 'actual'] or '{}').strip()
            if actual_str and actual_str != '{}':
                try:
                    actual_dict = json.loads(actual_str)
                    if isinstance(actual_dict, dict) and actual_dict:
                        # Update attributes from actual data
                        mappings = {
                            'duration_minutes': ['time_actual_minutes', 'actual_time', 'duration_minutes'],
                            'relief_score': ['actual_relief', 'relief_score'],
                            'cognitive_load': ['actual_cognitive', 'cognitive_load'],
                            'emotional_load': ['actual_emotional', 'emotional_load'],
                        }
                        for csv_column, possible_keys in mappings.items():
                            current_value = self.df.at[idx, csv_column]
                            if is_empty(current_value):
                                for key in possible_keys:
                                    if key in actual_dict:
                                        val = actual_dict[key]
                                        if not is_empty(val):
                                            self.df.at[idx, csv_column] = str(val)
                                            row_updated = True
                                            break
                except (json.JSONDecodeError, Exception) as e:
                    pass
            
            # If still empty, try predicted JSON
            predicted_str = str(self.df.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    predicted_dict = json.loads(predicted_str)
                    if isinstance(predicted_dict, dict) and predicted_dict:
                        mappings = {
                            'duration_minutes': ['time_estimate_minutes', 'estimate', 'duration_minutes'],
                            'relief_score': ['expected_relief', 'relief_score'],
                            'cognitive_load': ['expected_cognitive_load', 'expected_cognitive', 'cognitive_load'],
                            'emotional_load': ['expected_emotional_load', 'expected_emotional', 'emotional_load'],
                        }
                        for csv_column, possible_keys in mappings.items():
                            current_value = self.df.at[idx, csv_column]
                            if is_empty(current_value):
                                for key in possible_keys:
                                    if key in predicted_dict:
                                        val = predicted_dict[key]
                                        if not is_empty(val):
                                            self.df.at[idx, csv_column] = str(val)
                                            row_updated = True
                                            break
                except (json.JSONDecodeError, Exception) as e:
                    pass
            
            if row_updated:
                updated_count += 1
        
        if updated_count > 0:
            self._save()
            print(f"[InstanceManager] Backfilled {updated_count} instances with missing attributes")
        else:
            print(f"[InstanceManager] No instances needed backfilling (all attributes already populated or no JSON data found)")
        
        return updated_count

    def get_previous_task_averages(self, task_id: str) -> dict:
        """Get average values from previous initialized instances of the same task.
        Returns a dict with keys: expected_relief, expected_cognitive_load, 
        expected_physical_load, expected_emotional_load, motivation, expected_aversion.
        Values are scaled to 0-100 range."""
        import json
        self._reload()
        
        # Get all initialized instances for this task (completed or not)
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return {}
        
        # Extract values from predicted JSON
        relief_values = []
        cognitive_values = []
        physical_values = []
        emotional_values = []
        motivation_values = []
        aversion_values = []
        
        for idx in initialized.index:
            predicted_str = str(initialized.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        # Extract values, handling both 0-10 and 0-100 scales
                        for key, value_list in [
                            ('expected_relief', relief_values),
                            ('expected_cognitive_load', cognitive_values),
                            ('expected_physical_load', physical_values),
                            ('expected_emotional_load', emotional_values),
                            ('motivation', motivation_values),
                            ('expected_aversion', aversion_values)
                        ]:
                            val = pred_dict.get(key)
                            if val is not None:
                                try:
                                    num_val = float(val)
                                    # Scale from 0-10 to 0-100 if value is <= 10
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    value_list.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        result = {}
        if relief_values:
            result['expected_relief'] = round(sum(relief_values) / len(relief_values))
        if cognitive_values:
            result['expected_cognitive_load'] = round(sum(cognitive_values) / len(cognitive_values))
        if physical_values:
            result['expected_physical_load'] = round(sum(physical_values) / len(physical_values))
        if emotional_values:
            result['expected_emotional_load'] = round(sum(emotional_values) / len(emotional_values))
        if motivation_values:
            result['motivation'] = round(sum(motivation_values) / len(motivation_values))
        if aversion_values:
            result['expected_aversion'] = round(sum(aversion_values) / len(aversion_values))
        
        return result

    def get_previous_actual_averages(self, task_id: str) -> dict:
        """Get average values from previous completed instances of the same task.
        Returns a dict with keys: actual_relief, actual_cognitive, 
        actual_emotional, actual_physical.
        Values are scaled to 0-100 range."""
        import json
        self._reload()
        
        # Get all completed instances for this task
        completed = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['completed_at'].astype(str).str.strip() != '')
        ].copy()
        
        if completed.empty:
            return {}
        
        # Extract values from actual JSON
        relief_values = []
        cognitive_values = []
        physical_values = []
        emotional_values = []
        
        for idx in completed.index:
            actual_str = str(completed.at[idx, 'actual'] or '{}').strip()
            if actual_str and actual_str != '{}':
                try:
                    actual_dict = json.loads(actual_str)
                    if isinstance(actual_dict, dict):
                        # Extract values, handling both 0-10 and 0-100 scales
                        for key, value_list in [
                            ('actual_relief', relief_values),
                            ('actual_cognitive', cognitive_values),
                            ('actual_physical', physical_values),
                            ('actual_emotional', emotional_values)
                        ]:
                            val = actual_dict.get(key)
                            if val is not None:
                                try:
                                    num_val = float(val)
                                    # Scale from 0-10 to 0-100 if value is <= 10
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    value_list.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        result = {}
        if relief_values:
            result['actual_relief'] = round(sum(relief_values) / len(relief_values))
        if cognitive_values:
            result['actual_cognitive'] = round(sum(cognitive_values) / len(cognitive_values))
        if physical_values:
            result['actual_physical'] = round(sum(physical_values) / len(physical_values))
        if emotional_values:
            result['actual_emotional'] = round(sum(emotional_values) / len(emotional_values))
        
        return result

    def get_initial_aversion(self, task_id: str) -> Optional[float]:
        """Get the initial aversion value for a task (from the first initialized instance).
        Returns None if this is the first time doing the task.
        Values are scaled to 0-100 range."""
        import json
        self._reload()
        
        # Get all initialized instances for this task, sorted by initialized_at
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return None
        
        # Sort by initialized_at to get the first one
        initialized['initialized_at_dt'] = pd.to_datetime(initialized['initialized_at'], errors='coerce')
        initialized = initialized.sort_values('initialized_at_dt')
        
        # Get the first instance's predicted data
        first_idx = initialized.index[0]
        predicted_str = str(initialized.at[first_idx, 'predicted'] or '{}').strip()
        if predicted_str and predicted_str != '{}':
            try:
                pred_dict = json.loads(predicted_str)
                if isinstance(pred_dict, dict):
                    initial_aversion = pred_dict.get('initial_aversion')
                    if initial_aversion is not None:
                        try:
                            num_val = float(initial_aversion)
                            # Scale from 0-10 to 0-100 if value is <= 10
                            if num_val <= 10 and num_val >= 0:
                                num_val = num_val * 10
                            return round(num_val)
                        except (ValueError, TypeError):
                            pass
            except (json.JSONDecodeError, Exception):
                pass
        
        return None

    def get_previous_aversion_average(self, task_id: str) -> Optional[float]:
        """Get average aversion from previous initialized instances of the same task.
        Returns None if no previous instances exist.
        Values are scaled to 0-100 range."""
        import json
        self._reload()
        
        # Get all initialized instances for this task (completed or not)
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return None
        
        aversion_values = []
        
        for idx in initialized.index:
            predicted_str = str(initialized.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        val = pred_dict.get('expected_aversion')
                        if val is not None:
                            try:
                                num_val = float(val)
                                # Scale from 0-10 to 0-100 if value is <= 10
                                if num_val <= 10 and num_val >= 0:
                                    num_val = num_val * 10
                                aversion_values.append(num_val)
                            except (ValueError, TypeError):
                                pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        if aversion_values:
            return round(sum(aversion_values) / len(aversion_values))
        return None

    def scale_values_10_to_100(self):
        """Scale existing values from 0-10 range to 0-100 range.
        This migration updates both JSON payloads and CSV columns.
        Only scales values that are <= 10 (to avoid double-scaling)."""
        import json
        self._reload()
        updated_count = 0
        
        # Fields to scale in predicted JSON
        predicted_fields = [
            'expected_relief', 'expected_cognitive_load', 'expected_physical_load',
            'expected_emotional_load', 'motivation'
        ]
        # Fields to scale in actual JSON
        actual_fields = [
            'actual_relief', 'actual_cognitive', 'actual_emotional', 'actual_physical'
        ]
        # CSV columns to scale
        csv_columns = [
            'relief_score', 'cognitive_load', 'emotional_load'
        ]
        
        for idx in self.df.index:
            row_updated = False
            
            # Scale predicted JSON
            predicted_str = str(self.df.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        for field in predicted_fields:
                            if field in pred_dict:
                                val = pred_dict[field]
                                try:
                                    num_val = float(val)
                                    # Only scale if value is in 0-10 range
                                    if 0 <= num_val <= 10:
                                        pred_dict[field] = num_val * 10
                                        row_updated = True
                                except (ValueError, TypeError):
                                    pass
                        if row_updated:
                            self.df.at[idx, 'predicted'] = json.dumps(pred_dict)
                except (json.JSONDecodeError, Exception):
                    pass
            
            # Scale actual JSON
            actual_str = str(self.df.at[idx, 'actual'] or '{}').strip()
            if actual_str and actual_str != '{}':
                try:
                    actual_dict = json.loads(actual_str)
                    if isinstance(actual_dict, dict):
                        for field in actual_fields:
                            if field in actual_dict:
                                val = actual_dict[field]
                                try:
                                    num_val = float(val)
                                    # Only scale if value is in 0-10 range
                                    if 0 <= num_val <= 10:
                                        actual_dict[field] = num_val * 10
                                        row_updated = True
                                except (ValueError, TypeError):
                                    pass
                        if row_updated:
                            self.df.at[idx, 'actual'] = json.dumps(actual_dict)
                except (json.JSONDecodeError, Exception):
                    pass
            
            # Scale CSV columns
            for col in csv_columns:
                if col in self.df.columns:
                    val = self.df.at[idx, col]
                    if val and str(val).strip() != '':
                        try:
                            num_val = float(val)
                            # Only scale if value is in 0-10 range
                            if 0 <= num_val <= 10:
                                self.df.at[idx, col] = str(num_val * 10)
                                row_updated = True
                        except (ValueError, TypeError):
                            pass
            
            if row_updated:
                updated_count += 1
        
        if updated_count > 0:
            self._save()
            print(f"[InstanceManager] Scaled {updated_count} instances from 0-10 to 0-100 range")
        else:
            print(f"[InstanceManager] No instances needed scaling (all values already in 0-100 range or empty)")
        
        return updated_count