"""
Factors Comparison Analytics Module

This module provides analysis and comparison of factors used in analytical formulas.
Currently focuses on emotional factors (serendipity and disappointment) as a foundation
for understanding how factors influence scores.

[NOTE: This is a new feature - functionality will be expanded over time]
"""

from nicegui import ui
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from backend.analytics import Analytics

analytics_service = Analytics()


def register_factors_comparison_page():
    """Register the factors comparison analytics page."""
    # Page is already registered in analytics_page.py to avoid duplicate registration
    pass


def build_factors_comparison_page():
    """Build the factors comparison analytics page."""
    ui.page_title('Factors Comparison Analytics')
    
    with ui.header().classes("bg-indigo-600 text-white"):
        ui.label("Factors Comparison Analytics").classes("text-2xl font-bold")
        ui.label("Compare and analyze factors that influence scores in formulas").classes("text-sm")
    
    # New Feature Notice
    with ui.card().classes("p-4 mb-4 bg-yellow-50 border border-yellow-200"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("info", size="lg").classes("text-yellow-600")
            with ui.column().classes("flex-1"):
                ui.label("New Feature").classes("font-bold text-yellow-800")
                ui.label("This is a new analytics module. Additional functionality and factor types will be added over time.").classes("text-sm text-yellow-700")
    
    # Factors Explanation
    with ui.card().classes("p-4 mb-4 bg-blue-50 border border-blue-200"):
        ui.label("Understanding Emotional Factors").classes("text-lg font-bold mb-2")
        with ui.column().classes("gap-2"):
            ui.label("What are Emotional Factors?").classes("font-semibold")
            ui.label("Emotional factors measure the difference between expected and actual relief. They help understand prediction accuracy and emotional patterns.").classes("text-sm")
            
            with ui.row().classes("gap-4 mt-2"):
                with ui.column().classes("flex-1"):
                    ui.label("Serendipity Factor").classes("font-semibold text-green-700")
                    ui.label("Measures pleasant surprise when actual relief exceeds expectations.").classes("text-sm")
                    ui.label("• Range: 0-100 (0 = no surprise, 100 = maximum surprise)").classes("text-xs text-gray-600")
                    ui.label("• Healthy: Moderate amounts (5-20) indicate good self-awareness with occasional positive surprises").classes("text-xs text-gray-600")
                    ui.label("• Acceptable: Up to 30 points - pleasant surprises are beneficial for motivation").classes("text-xs text-gray-600")
                
                with ui.column().classes("flex-1"):
                    ui.label("Disappointment Factor").classes("font-semibold text-red-700")
                    ui.label("Measures disappointment when actual relief falls short of expectations.").classes("text-sm")
                    ui.label("• Range: 0-100 (0 = no disappointment, 100 = maximum disappointment)").classes("text-xs text-gray-600")
                    ui.label("• Healthy: Low amounts (<10) indicate accurate predictions and realistic expectations").classes("text-xs text-gray-600")
                    ui.label("• Acceptable: Up to 15 points - occasional disappointments are normal, but frequent high disappointment (>20) may indicate unrealistic expectations").classes("text-xs text-gray-600")
            
            ui.separator().classes("my-2")
            
            ui.label("Expected Variation").classes("font-semibold mt-2")
            with ui.column().classes("gap-1"):
                ui.label("• Normal variation: ±5-10 points is typical and indicates good prediction accuracy").classes("text-sm")
                ui.label("• Moderate variation: ±10-20 points is acceptable and shows some prediction error").classes("text-sm")
                ui.label("• High variation: ±20+ points suggests significant prediction errors or changing task characteristics").classes("text-sm")
                ui.label("• Mental health: A balance of serendipity (pleasant surprises) with minimal disappointment is ideal for maintaining motivation and realistic expectations").classes("text-sm")
    
    with ui.column().classes("w-full p-4 gap-4"):
        # Debug Section
        with ui.card().classes("p-3 mb-4 bg-gray-100 border border-gray-300"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("bug_report", size="md").classes("text-gray-600")
                ui.label("Debug Tools").classes("font-semibold text-gray-700")
            with ui.row().classes("gap-2 mt-2"):
                debug_output = ui.textarea().classes("w-full").props("rows=15").style("font-family: monospace; font-size: 11px;")
                debug_output.set_value("Debug output will appear here when you click 'Run Debug'...")
                
                def run_debug():
                    """Run debug analysis and print results."""
                    import sys
                    from io import StringIO
                    
                    # Capture print output
                    old_stdout = sys.stdout
                    sys.stdout = captured_output = StringIO()
                    
                    try:
                        print("=" * 70)
                        print("FACTORS COMPARISON DEBUG ANALYSIS")
                        print("=" * 70)
                        print()
                        
                        # Step 1: Load instances
                        print("STEP 1: Loading instances from analytics service...")
                        df = analytics_service._load_instances()
                        print(f"  ✓ Loaded {len(df)} total instances")
                        print(f"  ✓ Columns: {list(df.columns)}")
                        print()
                        
                        # Step 2: Filter completed
                        print("STEP 2: Filtering completed instances...")
                        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                        print(f"  ✓ Found {len(completed)} completed instances")
                        print()
                        
                        # Step 3: Check for factor columns
                        print("STEP 3: Checking for factor columns...")
                        has_serendipity = 'serendipity_factor' in completed.columns
                        has_disappointment = 'disappointment_factor' in completed.columns
                        has_net_relief = 'net_relief' in completed.columns
                        print(f"  ✓ serendipity_factor column exists: {has_serendipity}")
                        print(f"  ✓ disappointment_factor column exists: {has_disappointment}")
                        print(f"  ✓ net_relief column exists: {has_net_relief}")
                        print()
                        
                        if has_serendipity:
                            serendipity_values = pd.to_numeric(completed['serendipity_factor'], errors='coerce')
                            print(f"  ✓ serendipity_factor stats:")
                            print(f"    - Non-null values: {serendipity_values.notna().sum()}")
                            print(f"    - Null values: {serendipity_values.isna().sum()}")
                            print(f"    - Mean: {serendipity_values.mean():.2f}")
                            print(f"    - Max: {serendipity_values.max():.2f}")
                            print(f"    - Min: {serendipity_values.min():.2f}")
                            print(f"    - Sample values: {serendipity_values.dropna().head(5).tolist()}")
                        else:
                            print("  ✗ serendipity_factor column NOT FOUND")
                        print()
                        
                        if has_disappointment:
                            disappointment_values = pd.to_numeric(completed['disappointment_factor'], errors='coerce')
                            print(f"  ✓ disappointment_factor stats:")
                            print(f"    - Non-null values: {disappointment_values.notna().sum()}")
                            print(f"    - Null values: {disappointment_values.isna().sum()}")
                            print(f"    - Mean: {disappointment_values.mean():.2f}")
                            print(f"    - Max: {disappointment_values.max():.2f}")
                            print(f"    - Min: {disappointment_values.min():.2f}")
                            print(f"    - Sample values: {disappointment_values.dropna().head(5).tolist()}")
                        else:
                            print("  ✗ disappointment_factor column NOT FOUND")
                        print()
                        
                        # Step 4: Get factors comparison data
                        print("STEP 4: Calling get_factors_comparison_data()...")
                        data = get_factors_comparison_data()
                        print(f"  ✓ Returned data keys: {list(data.keys())}")
                        print(f"  ✓ total_tasks: {data.get('total_tasks', 'N/A')}")
                        print()
                        
                        if 'stats' in data:
                            stats = data['stats']
                            print(f"  ✓ Stats keys: {list(stats.keys())}")
                            print(f"  ✓ avg_serendipity: {stats.get('avg_serendipity', 'N/A')}")
                            print(f"  ✓ avg_disappointment: {stats.get('avg_disappointment', 'N/A')}")
                        print()
                        
                        if 'data' in data:
                            factors_data = data['data']
                            if isinstance(factors_data, pd.DataFrame):
                                print(f"  ✓ factors_data DataFrame:")
                                print(f"    - Shape: {factors_data.shape}")
                                print(f"    - Columns: {list(factors_data.columns)}")
                                if 'serendipity_factor' in factors_data.columns:
                                    sf_col = pd.to_numeric(factors_data['serendipity_factor'], errors='coerce')
                                    print(f"    - serendipity_factor: {sf_col.notna().sum()} non-null, mean={sf_col.mean():.2f}")
                                if 'disappointment_factor' in factors_data.columns:
                                    df_col = pd.to_numeric(factors_data['disappointment_factor'], errors='coerce')
                                    print(f"    - disappointment_factor: {df_col.notna().sum()} non-null, mean={df_col.mean():.2f}")
                                print(f"    - First 3 rows:")
                                print(factors_data.head(3).to_string())
                        print()
                        
                        # Step 5: Test chart generation
                        print("STEP 5: Testing chart generation...")
                        if 'data' in data and isinstance(data['data'], pd.DataFrame):
                            factors_data = data['data']
                            if not factors_data.empty:
                                try:
                                    # Test time series
                                    print("  Testing time series chart...")
                                    if 'completed_at_dt' in factors_data.columns:
                                        time_data = factors_data[factors_data['completed_at_dt'].notna()].copy()
                                        print(f"    - Rows with dates: {len(time_data)}")
                                        if len(time_data) > 0:
                                            print(f"    - Date range: {time_data['completed_at_dt'].min()} to {time_data['completed_at_dt'].max()}")
                                            if 'serendipity_factor' in time_data.columns:
                                                sf_vals = pd.to_numeric(time_data['serendipity_factor'], errors='coerce')
                                                print(f"    - Serendipity values: {sf_vals.notna().sum()} non-null")
                                            if 'disappointment_factor' in time_data.columns:
                                                df_vals = pd.to_numeric(time_data['disappointment_factor'], errors='coerce')
                                                print(f"    - Disappointment values: {df_vals.notna().sum()} non-null")
                                    else:
                                        print("    ✗ completed_at_dt column NOT FOUND")
                                except Exception as e:
                                    print(f"    ✗ ERROR: {e}")
                                    import traceback
                                    traceback.print_exc()
                        print()
                        
                        print("=" * 70)
                        print("DEBUG COMPLETE")
                        print("=" * 70)
                        
                    except Exception as e:
                        print(f"\n✗ ERROR during debug: {e}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        sys.stdout = old_stdout
                        output_text = captured_output.getvalue()
                        debug_output.set_value(output_text)
                
                ui.button("Run Debug", on_click=run_debug).classes("bg-blue-500 text-white")
        
        # Get data
        data = get_factors_comparison_data()
        
        # Check for data - total_tasks is in stats, not at top level
        stats = data.get('stats', {})
        total = stats.get('total_tasks', 0) if stats else 0
        factors_data = data.get('data', pd.DataFrame())
        
        print(f"[DEBUG build_factors_comparison_page] Data check: total_tasks={total}, factors_data shape={factors_data.shape if isinstance(factors_data, pd.DataFrame) else 'Not DataFrame'}")
        
        if not data or total == 0 or (isinstance(factors_data, pd.DataFrame) and factors_data.empty):
            with ui.card().classes("p-4"):
                ui.label("No factor data available yet.").classes("text-gray-500")
                ui.label("Complete some tasks with both expected and actual relief values to see factor comparisons.").classes("text-sm text-gray-400 mt-2")
                ui.label("Note: You need to set both 'expected relief' when initializing a task and 'actual relief' when completing it.").classes("text-xs text-gray-500 mt-2")
            return
        
        # Debug: Show data count (can be removed later)
        if total > 0:
            with ui.card().classes("p-2 mb-2 bg-gray-50 text-xs"):
                ui.label(f"Loaded {total} tasks with factor data").classes("text-gray-600")
        
        # Summary statistics
        _render_factors_summary(data)
        
        # Factor comparison charts
        _render_factors_comparison_charts(data)
        
        # Factor impact analysis (stub)
        _render_factor_impact_analysis(data)
        
        # Task-level details
        _render_factors_task_details(data)


def get_factors_comparison_data(days: int = 90) -> Dict:
    """Get factors comparison data from analytics service.
    
    Uses pre-calculated factors from _load_instances() which already computes
    serendipity_factor and disappointment_factor based on net_relief.
    """
    # Use _load_instances() which already calculates factors
    df = analytics_service._load_instances()
    completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
    
    if completed.empty:
        return {'total_tasks': 0}
    
    # Filter by date range
    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
    completed = completed[completed['completed_at_dt'].notna()]
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        completed = completed[completed['completed_at_dt'] >= cutoff]
    
    if completed.empty:
        return {'total_tasks': 0}
    
    # Always calculate factors from expected/actual relief for reliability
    # Extract expected and actual relief from JSON or columns
    def _get_expected_relief(row):
        # Try predicted_dict first
        try:
            predicted_dict = row.get('predicted_dict', {})
            if isinstance(predicted_dict, dict):
                val = predicted_dict.get('expected_relief', None)
                if val is not None:
                    return val
        except (KeyError, TypeError):
            pass
        # Try predicted JSON string
        try:
            if 'predicted' in row and isinstance(row['predicted'], str):
                import json
                pred = json.loads(row['predicted'] or '{}')
                val = pred.get('expected_relief', None)
                if val is not None:
                    return val
        except (KeyError, TypeError, json.JSONDecodeError):
            pass
        return None
    
    def _get_actual_relief(row):
        # Try actual_dict first
        try:
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                val = actual_dict.get('actual_relief', None)
                if val is not None:
                    return val
        except (KeyError, TypeError):
            pass
        # Try actual JSON string
        try:
            if 'actual' in row and isinstance(row['actual'], str):
                import json
                act = json.loads(row['actual'] or '{}')
                val = act.get('actual_relief', None)
                if val is not None:
                    return val
        except (KeyError, TypeError, json.JSONDecodeError):
            pass
        # Fallback to relief_score column
        return row.get('relief_score')
    
    completed['expected_relief'] = completed.apply(_get_expected_relief, axis=1)
    completed['actual_relief'] = completed.apply(_get_actual_relief, axis=1)
    
    # Convert to numeric and scale if needed (0-10 to 0-100)
    def _normalize_relief(val):
        if pd.isna(val):
            return None
        val = float(val)
        if 0 <= val <= 10:
            return val * 10.0
        return val
    
    completed['expected_relief'] = completed['expected_relief'].apply(_normalize_relief)
    completed['actual_relief'] = completed['actual_relief'].apply(_normalize_relief)
    completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
    completed['actual_relief'] = pd.to_numeric(completed['actual_relief'], errors='coerce')
    
    # Filter to rows with both expected and actual relief
    has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
    factors_data = completed[has_both].copy()
    
    if factors_data.empty:
        return {'total_tasks': 0}
    
    # Use stored net_relief if available, otherwise calculate
    if 'net_relief' in factors_data.columns:
        factors_data['net_relief'] = pd.to_numeric(factors_data['net_relief'], errors='coerce')
    else:
        factors_data['net_relief'] = None
    
    # Fill missing net_relief by calculating from expected/actual relief
    missing_net_relief = factors_data['net_relief'].isna()
    if missing_net_relief.any():
        factors_data.loc[missing_net_relief, 'net_relief'] = (
            factors_data.loc[missing_net_relief, 'actual_relief'] - 
            factors_data.loc[missing_net_relief, 'expected_relief']
        )
    
    # Use stored factors from database (preferred) - they're already calculated and stored
    # Only recalculate if stored values are missing (NaN)
    print(f"[DEBUG get_factors_comparison_data] Checking stored factors...")
    
    # Check if stored factors exist
    has_stored_serendipity = 'serendipity_factor' in factors_data.columns
    has_stored_disappointment = 'disappointment_factor' in factors_data.columns
    
    if has_stored_serendipity:
        factors_data['serendipity_factor'] = pd.to_numeric(factors_data['serendipity_factor'], errors='coerce')
        stored_serendipity_count = factors_data['serendipity_factor'].notna().sum()
        print(f"[DEBUG get_factors_comparison_data] Stored serendipity_factor: {stored_serendipity_count} non-null values")
    else:
        factors_data['serendipity_factor'] = None
        stored_serendipity_count = 0
        print(f"[DEBUG get_factors_comparison_data] No stored serendipity_factor column found")
    
    if has_stored_disappointment:
        factors_data['disappointment_factor'] = pd.to_numeric(factors_data['disappointment_factor'], errors='coerce')
        stored_disappointment_count = factors_data['disappointment_factor'].notna().sum()
        print(f"[DEBUG get_factors_comparison_data] Stored disappointment_factor: {stored_disappointment_count} non-null values")
    else:
        factors_data['disappointment_factor'] = None
        stored_disappointment_count = 0
        print(f"[DEBUG get_factors_comparison_data] No stored disappointment_factor column found")
    
    # Only recalculate if stored values are missing (NaN)
    missing_serendipity = factors_data['serendipity_factor'].isna()
    missing_disappointment = factors_data['disappointment_factor'].isna()
    
    if missing_serendipity.any() or missing_disappointment.any():
        print(f"[DEBUG get_factors_comparison_data] Some factors missing, recalculating from expected/actual relief...")
        print(f"[DEBUG get_factors_comparison_data] Missing serendipity: {missing_serendipity.sum()}, Missing disappointment: {missing_disappointment.sum()}")
        
        # Ensure net_relief is calculated for recalculation
        if 'net_relief' not in factors_data.columns or factors_data['net_relief'].isna().any():
            factors_data['net_relief'] = factors_data['actual_relief'] - factors_data['expected_relief']
        
        # Recalculate only missing factors
        if missing_serendipity.any():
            factors_data.loc[missing_serendipity, 'serendipity_factor'] = factors_data.loc[missing_serendipity, 'net_relief'].apply(
                lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0
            )
            print(f"[DEBUG get_factors_comparison_data] Recalculated {missing_serendipity.sum()} missing serendipity_factor values")
        
        if missing_disappointment.any():
            factors_data.loc[missing_disappointment, 'disappointment_factor'] = factors_data.loc[missing_disappointment, 'net_relief'].apply(
                lambda x: max(0.0, -float(x)) if pd.notna(x) else 0.0
            )
            print(f"[DEBUG get_factors_comparison_data] Recalculated {missing_disappointment.sum()} missing disappointment_factor values")
    else:
        print(f"[DEBUG get_factors_comparison_data] Using stored factors (all values present, no recalculation needed)")
        # Ensure net_relief exists for reference (but don't overwrite if it exists)
        if 'net_relief' not in factors_data.columns:
            factors_data['net_relief'] = factors_data['actual_relief'] - factors_data['expected_relief']
    
    # Ensure all values are properly typed (non-negative for factors)
    factors_data['serendipity_factor'] = factors_data['serendipity_factor'].fillna(0.0)
    factors_data['serendipity_factor'] = factors_data['serendipity_factor'].apply(lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0)
    factors_data['disappointment_factor'] = factors_data['disappointment_factor'].fillna(0.0)
    factors_data['disappointment_factor'] = factors_data['disappointment_factor'].apply(lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0)
    
    print(f"[DEBUG get_factors_comparison_data] Final factor stats:")
    print(f"[DEBUG get_factors_comparison_data]   serendipity_factor: min={factors_data['serendipity_factor'].min():.2f}, max={factors_data['serendipity_factor'].max():.2f}, mean={factors_data['serendipity_factor'].mean():.2f}, non-zero={((factors_data['serendipity_factor'] > 0).sum())}")
    print(f"[DEBUG get_factors_comparison_data]   disappointment_factor: min={factors_data['disappointment_factor'].min():.2f}, max={factors_data['disappointment_factor'].max():.2f}, mean={factors_data['disappointment_factor'].mean():.2f}, non-zero={((factors_data['disappointment_factor'] > 0).sum())}")
    
    # Ensure all numeric fields are properly typed
    factors_data['net_relief'] = pd.to_numeric(factors_data['net_relief'], errors='coerce').fillna(0.0)
    factors_data['expected_relief'] = pd.to_numeric(factors_data['expected_relief'], errors='coerce')
    factors_data['actual_relief'] = pd.to_numeric(factors_data['actual_relief'], errors='coerce')
    factors_data['relief_score'] = pd.to_numeric(factors_data.get('relief_score', factors_data['actual_relief']), errors='coerce')
    
    # Get task names if available
    from backend.task_manager import TaskManager
    task_manager = TaskManager()
    tasks_df = task_manager.get_all()
    
    if not tasks_df.empty and 'task_name' in tasks_df.columns:
        factors_data = factors_data.merge(
            tasks_df[['task_id', 'task_name']],
            on='task_id',
            how='left'
        )
        factors_data['task_name'] = factors_data['task_name'].fillna('Unknown Task')
    else:
        factors_data['task_name'] = 'Unknown Task'
    
    # Calculate statistics
    stats = {
        'total_tasks': len(factors_data),
        'avg_serendipity': float(factors_data['serendipity_factor'].mean()),
        'avg_disappointment': float(factors_data['disappointment_factor'].mean()),
        'max_serendipity': float(factors_data['serendipity_factor'].max()),
        'max_disappointment': float(factors_data['disappointment_factor'].max()),
        'std_serendipity': float(factors_data['serendipity_factor'].std()) if len(factors_data) > 1 else 0.0,
        'std_disappointment': float(factors_data['disappointment_factor'].std()) if len(factors_data) > 1 else 0.0,
        'total_serendipity': float(factors_data['serendipity_factor'].sum()),
        'total_disappointment': float(factors_data['disappointment_factor'].sum()),
        'serendipity_tasks': int((factors_data['serendipity_factor'] > 0).sum()),
        'disappointment_tasks': int((factors_data['disappointment_factor'] > 0).sum()),
        'neutral_tasks': int(((factors_data['serendipity_factor'] == 0) & (factors_data['disappointment_factor'] == 0)).sum()),
        'high_serendipity_tasks': int((factors_data['serendipity_factor'] > 20).sum()),  # Significant pleasant surprise
        'high_disappointment_tasks': int((factors_data['disappointment_factor'] > 20).sum()),  # Significant disappointment
    }
    
    # Get recent tasks for details table
    factors_data_sorted = factors_data.sort_values('completed_at_dt', ascending=False)
    
    # Ensure completed_at_dt is available for time series
    if 'completed_at_dt' not in factors_data.columns:
        factors_data['completed_at_dt'] = pd.to_datetime(factors_data.get('completed_at', ''), errors='coerce')
    
    # Convert DataFrame to dict, but convert Timestamp objects to strings for JSON serialization
    # NiceGUI can't serialize pandas Timestamp objects to JSON
    recent_tasks_df = factors_data_sorted.head(20).copy()
    
    # Convert Timestamp columns to strings
    for col in recent_tasks_df.columns:
        if recent_tasks_df[col].dtype.name.startswith('datetime'):
            recent_tasks_df[col] = recent_tasks_df[col].apply(
                lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else None
            )
        elif recent_tasks_df[col].dtype == 'object':
            # Check if values are Timestamps
            sample_val = recent_tasks_df[col].dropna().iloc[0] if not recent_tasks_df[col].dropna().empty else None
            if isinstance(sample_val, pd.Timestamp):
                recent_tasks_df[col] = recent_tasks_df[col].apply(
                    lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) and isinstance(x, pd.Timestamp) else x
                )
    
    return {
        'stats': stats,
        'data': factors_data,
        'recent_tasks': recent_tasks_df.to_dict('records'),
    }


def _render_factors_summary(data: Dict):
    """Render summary statistics for factors with health indicators."""
    stats = data.get('stats', {})
    
    with ui.card().classes("p-4"):
        ui.label("Factors Summary").classes("text-xl font-bold mb-3")
        
        # Health indicators
        avg_serendipity = stats.get('avg_serendipity', 0.0)
        avg_disappointment = stats.get('avg_disappointment', 0.0)
        
        # Determine health status
        serendipity_status = "Excellent" if 5 <= avg_serendipity <= 20 else "Good" if avg_serendipity < 30 else "High"
        disappointment_status = "Excellent" if avg_disappointment < 10 else "Good" if avg_disappointment < 15 else "High" if avg_disappointment < 25 else "Very High"
        
        serendipity_color = "text-green-600" if serendipity_status in ["Excellent", "Good"] else "text-yellow-600"
        disappointment_color = "text-green-600" if disappointment_status == "Excellent" else "text-yellow-600" if disappointment_status == "Good" else "text-orange-600" if disappointment_status == "High" else "text-red-600"
        
        with ui.row().classes("gap-4 flex-wrap"):
            total_tasks = stats.get('total_tasks', 0)
            
            with ui.card().classes("p-3 bg-blue-50 min-w-[150px]"):
                ui.label("Total Tasks").classes("text-xs text-gray-500")
                ui.label(f"{total_tasks}").classes("text-2xl font-bold")
            
            with ui.card().classes(f"p-3 bg-emerald-50 min-w-[150px] border-2 {serendipity_color.replace('text-', 'border-')}"):
                ui.label("Avg Serendipity Factor").classes("text-xs text-gray-500")
                ui.label(f"{avg_serendipity:.1f}").classes(f"text-2xl font-bold {serendipity_color}")
                ui.label(f"Status: {serendipity_status}").classes(f"text-xs {serendipity_color} font-semibold")
                max_serendipity = stats.get('max_serendipity', 0.0)
                ui.label(f"Max: {max_serendipity:.1f}").classes("text-xs text-gray-500")
                std_serendipity = stats.get('std_serendipity', 0.0)
                ui.label(f"Std Dev: {std_serendipity:.1f}").classes("text-xs text-gray-500")
            
            with ui.card().classes(f"p-3 bg-rose-50 min-w-[150px] border-2 {disappointment_color.replace('text-', 'border-')}"):
                ui.label("Avg Disappointment Factor").classes("text-xs text-gray-500")
                ui.label(f"{avg_disappointment:.1f}").classes(f"text-2xl font-bold {disappointment_color}")
                ui.label(f"Status: {disappointment_status}").classes(f"text-xs {disappointment_color} font-semibold")
                max_disappointment = stats.get('max_disappointment', 0.0)
                ui.label(f"Max: {max_disappointment:.1f}").classes("text-xs text-gray-500")
                std_disappointment = stats.get('std_disappointment', 0.0)
                ui.label(f"Std Dev: {std_disappointment:.1f}").classes("text-xs text-gray-500")
            
            with ui.card().classes("p-3 bg-green-50 min-w-[150px]"):
                ui.label("Serendipity Tasks").classes("text-xs text-gray-500")
                serendipity_tasks = stats.get('serendipity_tasks', 0)
                ui.label(f"{serendipity_tasks}").classes("text-2xl font-bold")
                pct = (serendipity_tasks / total_tasks * 100) if total_tasks > 0 else 0
                ui.label(f"({pct:.1f}%)").classes("text-xs text-gray-500")
            
            with ui.card().classes("p-3 bg-red-50 min-w-[150px]"):
                ui.label("Disappointment Tasks").classes("text-xs text-gray-500")
                disappointment_tasks = stats.get('disappointment_tasks', 0)
                ui.label(f"{disappointment_tasks}").classes("text-2xl font-bold")
                pct = (disappointment_tasks / total_tasks * 100) if total_tasks > 0 else 0
                ui.label(f"({pct:.1f}%)").classes("text-xs text-gray-500")
            
            with ui.card().classes("p-3 bg-gray-50 min-w-[150px]"):
                ui.label("Neutral Tasks").classes("text-xs text-gray-500")
                neutral_tasks = stats.get('neutral_tasks', 0)
                ui.label(f"{neutral_tasks}").classes("text-2xl font-bold")
                pct = (neutral_tasks / total_tasks * 100) if total_tasks > 0 else 0
                ui.label(f"({pct:.1f}%)").classes("text-xs text-gray-500")
            
            with ui.card().classes("p-3 bg-yellow-50 min-w-[150px]"):
                ui.label("High Serendipity (>20)").classes("text-xs text-gray-500")
                high_serendipity = stats.get('high_serendipity_tasks', 0)
                ui.label(f"{high_serendipity}").classes("text-2xl font-bold text-green-600")
                pct = (high_serendipity / total_tasks * 100) if total_tasks > 0 else 0
                ui.label(f"({pct:.1f}%)").classes("text-xs text-gray-500")
            
            with ui.card().classes("p-3 bg-orange-50 min-w-[150px]"):
                ui.label("High Disappointment (>20)").classes("text-xs text-gray-500")
                high_disappointment = stats.get('high_disappointment_tasks', 0)
                ui.label(f"{high_disappointment}").classes("text-2xl font-bold text-red-600")
                pct = (high_disappointment / total_tasks * 100) if total_tasks > 0 else 0
                ui.label(f"({pct:.1f}%)").classes("text-xs text-gray-500")


def _render_factors_comparison_charts(data: Dict):
    """Render comparison charts for factors."""
    factors_data = data.get('data', pd.DataFrame())
    
    print(f"[DEBUG _render_factors_comparison_charts] Called with factors_data shape: {factors_data.shape if isinstance(factors_data, pd.DataFrame) else 'Not DataFrame'}")
    print(f"[DEBUG _render_factors_comparison_charts] factors_data type: {type(factors_data)}")
    
    if isinstance(factors_data, pd.DataFrame):
        print(f"[DEBUG _render_factors_comparison_charts] DataFrame columns: {list(factors_data.columns)}")
        if 'serendipity_factor' in factors_data.columns:
            sf_vals = pd.to_numeric(factors_data['serendipity_factor'], errors='coerce')
            print(f"[DEBUG _render_factors_comparison_charts] serendipity_factor: {sf_vals.notna().sum()} non-null, {sf_vals.isna().sum()} null, non-zero: {(sf_vals > 0).sum()}")
        if 'disappointment_factor' in factors_data.columns:
            df_vals = pd.to_numeric(factors_data['disappointment_factor'], errors='coerce')
            print(f"[DEBUG _render_factors_comparison_charts] disappointment_factor: {df_vals.notna().sum()} non-null, {df_vals.isna().sum()} null, non-zero: {(df_vals > 0).sum()}")
    
    with ui.card().classes("p-4"):
        ui.label("Factors Comparison Charts").classes("text-xl font-bold mb-3")
        
        with ui.tabs().classes("w-full") as tabs:
            time_series = ui.tab("Time Series")
            scatter = ui.tab("Factor Scatter")
            distribution = ui.tab("Distribution")
        
        with ui.tab_panels(tabs, value=time_series).classes("w-full"):
            with ui.tab_panel(time_series):
                print(f"[DEBUG _render_factors_comparison_charts] Rendering time series chart...")
                _render_factors_time_series(factors_data)
            
            with ui.tab_panel(scatter):
                print(f"[DEBUG _render_factors_comparison_charts] Rendering scatter plot...")
                _render_factors_scatter_plot(factors_data)
            
            with ui.tab_panel(distribution):
                print(f"[DEBUG _render_factors_comparison_charts] Rendering distribution chart...")
                _render_factors_distribution(factors_data)


def _render_factors_scatter_plot(factors_data: pd.DataFrame):
    """Render scatter plot comparing serendipity vs disappointment factors."""
    fig = go.Figure()
    
    # Add diagonal line (theoretical maximum where one factor is max and other is zero)
    max_val = max(factors_data['serendipity_factor'].max(), factors_data['disappointment_factor'].max())
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[max_val, 0],
        mode='lines',
        name='Theoretical Maximum',
        line=dict(color='gray', dash='dash', width=1),
        showlegend=True
    ))
    
    # Color points by net relief
    fig.add_trace(go.Scatter(
        x=factors_data['serendipity_factor'],
        y=factors_data['disappointment_factor'],
        mode='markers',
        name='Tasks',
        marker=dict(
            size=8,
            color=factors_data['net_relief'],
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title="Net Relief"),
            line=dict(width=1, color='black')
        ),
        text=factors_data['task_name'],
        hovertemplate='<b>%{text}</b><br>Serendipity: %{x:.1f}<br>Disappointment: %{y:.1f}<br>Net Relief: %{marker.color:.1f}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Serendipity Factor vs Disappointment Factor",
        xaxis_title="Serendipity Factor",
        yaxis_title="Disappointment Factor",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    print("[DEBUG _render_factors_scatter_plot] Rendering Plotly chart...")
    ui.plotly(fig).classes("w-full h-96")
    print("[DEBUG _render_factors_scatter_plot] Chart rendered successfully!")


def _render_factors_time_series(factors_data: pd.DataFrame):
    """Render time series of factors over time using plotly."""
    print(f"[DEBUG _render_factors_time_series] Called with DataFrame shape: {factors_data.shape}")
    print(f"[DEBUG _render_factors_time_series] Columns: {list(factors_data.columns)}")
    
    if factors_data.empty:
        print("[DEBUG _render_factors_time_series] DataFrame is empty!")
        ui.label("No data available for time series.").classes("text-gray-500")
        return
    
    print(f"[DEBUG _render_factors_time_series] DataFrame is not empty, proceeding...")
    
    # Ensure we have the date column
    if 'completed_at_dt' not in factors_data.columns:
        print("[DEBUG _render_factors_time_series] completed_at_dt not in columns, creating from 'completed_at'")
        factors_data['completed_at_dt'] = pd.to_datetime(factors_data.get('completed_at', ''), errors='coerce')
    else:
        print("[DEBUG _render_factors_time_series] completed_at_dt already exists")
    
    # Filter out rows without valid dates
    factors_data = factors_data[factors_data['completed_at_dt'].notna()].copy()
    print(f"[DEBUG _render_factors_time_series] Rows with valid dates: {len(factors_data)}")
    
    if factors_data.empty:
        print("[DEBUG _render_factors_time_series] No valid date data after filtering!")
        ui.label("No valid date data for time series.").classes("text-gray-500")
        return
    
    # Sort by date
    factors_data_sorted = factors_data.sort_values('completed_at_dt')
    print(f"[DEBUG _render_factors_time_series] Sorted by date, date range: {factors_data_sorted['completed_at_dt'].min()} to {factors_data_sorted['completed_at_dt'].max()}")
    
    # Check factor columns before conversion
    print(f"[DEBUG _render_factors_time_series] Checking factor columns...")
    print(f"[DEBUG _render_factors_time_series] serendipity_factor in columns: {'serendipity_factor' in factors_data_sorted.columns}")
    print(f"[DEBUG _render_factors_time_series] disappointment_factor in columns: {'disappointment_factor' in factors_data_sorted.columns}")
    
    if 'serendipity_factor' in factors_data_sorted.columns:
        serendipity_raw = factors_data_sorted['serendipity_factor']
        print(f"[DEBUG _render_factors_time_series] serendipity_factor raw: {serendipity_raw.notna().sum()} non-null, {serendipity_raw.isna().sum()} null")
        print(f"[DEBUG _render_factors_time_series] serendipity_factor sample: {serendipity_raw.head(5).tolist()}")
    else:
        print("[DEBUG _render_factors_time_series] WARNING: serendipity_factor column NOT FOUND!")
    
    if 'disappointment_factor' in factors_data_sorted.columns:
        disappointment_raw = factors_data_sorted['disappointment_factor']
        print(f"[DEBUG _render_factors_time_series] disappointment_factor raw: {disappointment_raw.notna().sum()} non-null, {disappointment_raw.isna().sum()} null")
        print(f"[DEBUG _render_factors_time_series] disappointment_factor sample: {disappointment_raw.head(5).tolist()}")
    else:
        print("[DEBUG _render_factors_time_series] WARNING: disappointment_factor column NOT FOUND!")
    
    # Ensure factors are numeric
    factors_data_sorted['serendipity_factor'] = pd.to_numeric(factors_data_sorted['serendipity_factor'], errors='coerce').fillna(0.0)
    factors_data_sorted['disappointment_factor'] = pd.to_numeric(factors_data_sorted['disappointment_factor'], errors='coerce').fillna(0.0)
    
    print(f"[DEBUG _render_factors_time_series] After conversion:")
    print(f"[DEBUG _render_factors_time_series] serendipity_factor: min={factors_data_sorted['serendipity_factor'].min():.2f}, max={factors_data_sorted['serendipity_factor'].max():.2f}, mean={factors_data_sorted['serendipity_factor'].mean():.2f}")
    print(f"[DEBUG _render_factors_time_series] disappointment_factor: min={factors_data_sorted['disappointment_factor'].min():.2f}, max={factors_data_sorted['disappointment_factor'].max():.2f}, mean={factors_data_sorted['disappointment_factor'].mean():.2f}")
    
    print("[DEBUG _render_factors_time_series] Creating Plotly figure...")
    fig = go.Figure()
    
    # Convert Timestamp objects to strings for JSON serialization
    # Plotly can handle datetime strings, but not pandas Timestamp objects
    def convert_timestamp(ts):
        """Convert pandas Timestamp to string or Python datetime."""
        if pd.isna(ts):
            return None
        if isinstance(ts, pd.Timestamp):
            return ts.to_pydatetime()  # Convert to Python datetime
        return ts
    
    # Add serendipity factor trace
    serendipity_vals = factors_data_sorted['serendipity_factor'].tolist()
    serendipity_dates = [convert_timestamp(ts) for ts in factors_data_sorted['completed_at_dt'].tolist()]
    print(f"[DEBUG _render_factors_time_series] Adding serendipity trace with {len(serendipity_vals)} points")
    print(f"[DEBUG _render_factors_time_series] Serendipity values range: {min(serendipity_vals):.2f} to {max(serendipity_vals):.2f}")
    print(f"[DEBUG _render_factors_time_series] Date type: {type(serendipity_dates[0]) if serendipity_dates else 'None'}")
    
    fig.add_trace(go.Scatter(
        x=serendipity_dates,
        y=serendipity_vals,
        mode='lines+markers',
        name='Serendipity Factor',
        line=dict(color='#10b981', width=2.5),  # Green
        marker=dict(size=8, color='#10b981', symbol='circle'),
        hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Value: %{y:.1f}<extra></extra>'
    ))
    
    # Add disappointment factor trace
    disappointment_vals = factors_data_sorted['disappointment_factor'].tolist()
    disappointment_dates = [convert_timestamp(ts) for ts in factors_data_sorted['completed_at_dt'].tolist()]
    print(f"[DEBUG _render_factors_time_series] Adding disappointment trace with {len(disappointment_vals)} points")
    print(f"[DEBUG _render_factors_time_series] Disappointment values range: {min(disappointment_vals):.2f} to {max(disappointment_vals):.2f}")
    
    fig.add_trace(go.Scatter(
        x=disappointment_dates,
        y=disappointment_vals,
        mode='lines+markers',
        name='Disappointment Factor',
        line=dict(color='#ef4444', width=2.5),  # Red
        marker=dict(size=8, color='#ef4444', symbol='circle'),
        hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Value: %{y:.1f}<extra></extra>'
    ))
    
    print("[DEBUG _render_factors_time_series] Traces added, configuring layout...")
    
    # Add zero reference line
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray",
        opacity=0.3,
        annotation_text="Zero baseline"
    )
    
    # Add health zone indicators (optional visual guides)
    fig.add_hrect(
        y0=5, y1=20,
        fillcolor="green",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="Healthy Serendipity Zone",
        annotation_position="top left"
    )
    
    fig.add_hrect(
        y0=0, y1=10,
        fillcolor="green",
        opacity=0.1,
        layer="below",
        line_width=0,
        annotation_text="Healthy Disappointment Zone",
        annotation_position="bottom left"
    )
    
    fig.update_layout(
        title="Emotional Factors Over Time",
        xaxis_title="Date",
        yaxis_title="Factor Value (0-100)",
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            range=[0, max(100, factors_data_sorted['serendipity_factor'].max() * 1.1, factors_data_sorted['disappointment_factor'].max() * 1.1)]
        )
    )
    
    print("[DEBUG _render_factors_time_series] Rendering Plotly chart...")
    print(f"[DEBUG _render_factors_time_series] Figure has {len(fig.data)} traces")
    if len(fig.data) > 0:
        print(f"[DEBUG _render_factors_time_series] First trace has {len(fig.data[0].x)} x values and {len(fig.data[0].y)} y values")
        print(f"[DEBUG _render_factors_time_series] First trace y values sample: {list(fig.data[0].y[:5])}")
    
    try:
        chart_element = ui.plotly(fig).classes("w-full h-96")
        print("[DEBUG _render_factors_time_series] Chart element created successfully!")
        print(f"[DEBUG _render_factors_time_series] Chart element type: {type(chart_element)}")
    except Exception as e:
        print(f"[DEBUG _render_factors_time_series] ERROR creating chart: {e}")
        import traceback
        traceback.print_exc()
        ui.label(f"Error rendering chart: {e}").classes("text-red-500")


def _render_factors_distribution(factors_data: pd.DataFrame):
    """Render distribution of factors."""
    if factors_data.empty or 'serendipity_factor' not in factors_data.columns:
        ui.label("No data available for distribution chart.").classes("text-gray-500")
        return
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=factors_data['serendipity_factor'],
        name='Serendipity Factor',
        opacity=0.7,
        nbinsx=20
    ))
    
    fig.add_trace(go.Histogram(
        x=factors_data['disappointment_factor'],
        name='Disappointment Factor',
        opacity=0.7,
        nbinsx=20
    ))
    
    fig.update_layout(
        title="Distribution of Factor Values",
        xaxis_title="Factor Value",
        yaxis_title="Frequency",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        barmode='overlay'
    )
    
    ui.plotly(fig)


def _render_factor_impact_analysis(data: Dict):
    """Render factor impact analysis with health recommendations."""
    stats = data.get('stats', {})
    factors_data = data.get('data', pd.DataFrame())
    
    with ui.card().classes("p-4"):
        ui.label("Factor Health Analysis").classes("text-xl font-bold mb-3")
        
        if factors_data.empty:
            with ui.card().classes("p-3 bg-gray-50 border border-gray-200"):
                ui.label("No data available for analysis.").classes("text-gray-500")
            return
        
        # Calculate health metrics
        avg_serendipity = stats.get('avg_serendipity', 0.0)
        avg_disappointment = stats.get('avg_disappointment', 0.0)
        total_tasks = stats.get('total_tasks', 0)
        high_disappointment_pct = (stats.get('high_disappointment_tasks', 0) / total_tasks * 100) if total_tasks > 0 else 0
        high_serendipity_pct = (stats.get('high_serendipity_tasks', 0) / total_tasks * 100) if total_tasks > 0 else 0
        
        # Health assessment
        with ui.card().classes("p-3 mb-3"):
            ui.label("Overall Health Assessment").classes("font-semibold mb-2")
            
            # Serendipity assessment
            if 5 <= avg_serendipity <= 20:
                serendipity_assessment = "Excellent - Good balance of pleasant surprises"
                serendipity_color = "text-green-600"
            elif avg_serendipity < 5:
                serendipity_assessment = "Low - Few pleasant surprises, may indicate conservative expectations"
                serendipity_color = "text-yellow-600"
            elif avg_serendipity <= 30:
                serendipity_assessment = "Moderate - Some pleasant surprises, generally positive"
                serendipity_color = "text-green-600"
            else:
                serendipity_assessment = "High - Many pleasant surprises, may indicate consistently underestimating relief"
                serendipity_color = "text-yellow-600"
            
            # Disappointment assessment
            if avg_disappointment < 10:
                disappointment_assessment = "Excellent - Low disappointment, accurate predictions"
                disappointment_color = "text-green-600"
            elif avg_disappointment < 15:
                disappointment_assessment = "Good - Occasional disappointments, generally realistic expectations"
                disappointment_color = "text-yellow-600"
            elif avg_disappointment < 25:
                disappointment_assessment = "Moderate - Some disappointments, may need to adjust expectations"
                disappointment_color = "text-orange-600"
            else:
                disappointment_assessment = "High - Frequent disappointments, likely unrealistic expectations"
                disappointment_color = "text-red-600"
            
            with ui.column().classes("gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle" if avg_serendipity >= 5 and avg_disappointment < 15 else "warning", size="md").classes(serendipity_color if avg_serendipity >= 5 and avg_disappointment < 15 else "text-yellow-600")
                    ui.label(f"Serendipity: {serendipity_assessment}").classes(f"text-sm {serendipity_color}")
                
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle" if avg_disappointment < 10 else "warning" if avg_disappointment < 15 else "error", size="md").classes(disappointment_color)
                    ui.label(f"Disappointment: {disappointment_assessment}").classes(f"text-sm {disappointment_color}")
        
        # Recommendations
        with ui.card().classes("p-3 bg-blue-50 border border-blue-200"):
            ui.label("Recommendations").classes("font-semibold mb-2")
            recommendations = []
            
            if avg_disappointment > 20:
                recommendations.append("• Consider adjusting expectations downward - frequent high disappointment suggests unrealistic predictions")
            elif avg_disappointment > 15:
                recommendations.append("• Review tasks with high disappointment - identify patterns that lead to overestimation")
            
            if high_disappointment_pct > 30:
                recommendations.append(f"• {high_disappointment_pct:.1f}% of tasks have high disappointment (>20) - this may impact motivation and wellbeing")
            
            if avg_serendipity < 5:
                recommendations.append("• Low serendipity suggests very conservative expectations - consider being slightly more optimistic")
            
            if high_serendipity_pct > 40:
                recommendations.append(f"• {high_serendipity_pct:.1f}% of tasks have high serendipity (>20) - you may consistently underestimate relief")
            
            if not recommendations:
                recommendations.append("• Your factor patterns look healthy - good balance of accurate predictions with occasional pleasant surprises")
            
            for rec in recommendations:
                ui.label(rec).classes("text-sm")
        
        # Variation analysis
        std_serendipity = stats.get('std_serendipity', 0.0)
        std_disappointment = stats.get('std_disappointment', 0.0)
        
        with ui.card().classes("p-3 bg-gray-50 border border-gray-200 mt-3"):
            ui.label("Variation Analysis").classes("font-semibold mb-2")
            with ui.column().classes("gap-1"):
                ui.label(f"Serendipity variation (std dev): {std_serendipity:.1f}").classes("text-sm")
                if std_serendipity < 10:
                    ui.label("  → Low variation: Consistent prediction accuracy").classes("text-xs text-gray-600")
                elif std_serendipity < 20:
                    ui.label("  → Moderate variation: Some variation in prediction accuracy").classes("text-xs text-gray-600")
                else:
                    ui.label("  → High variation: Significant variation in prediction accuracy").classes("text-xs text-gray-600")
                
                ui.label(f"Disappointment variation (std dev): {std_disappointment:.1f}").classes("text-sm")
                if std_disappointment < 10:
                    ui.label("  → Low variation: Consistent disappointment levels").classes("text-xs text-gray-600")
                elif std_disappointment < 20:
                    ui.label("  → Moderate variation: Some variation in disappointment").classes("text-xs text-gray-600")
                else:
                    ui.label("  → High variation: Significant variation in disappointment - may indicate inconsistent expectations").classes("text-xs text-gray-600")


def _render_factors_task_details(data: Dict):
    """Render detailed task-level comparison table."""
    recent_tasks = data.get('recent_tasks', [])
    
    with ui.card().classes("p-4"):
        ui.label("Recent Task Factors").classes("text-xl font-bold mb-3")
        
        if not recent_tasks:
            ui.label("No task details available.").classes("text-gray-500")
            return
        
        # Create table
        columns = [
            {'name': 'task_name', 'label': 'Task', 'field': 'task_name', 'required': True},
            {'name': 'completed_at', 'label': 'Date', 'field': 'completed_at', 'required': True},
            {'name': 'expected_relief', 'label': 'Expected', 'field': 'expected_relief', 'required': True},
            {'name': 'actual_relief', 'label': 'Actual', 'field': 'actual_relief', 'required': True},
            {'name': 'net_relief', 'label': 'Net Relief', 'field': 'net_relief', 'required': True},
            {'name': 'serendipity_factor', 'label': 'Serendipity', 'field': 'serendipity_factor', 'required': True},
            {'name': 'disappointment_factor', 'label': 'Disappointment', 'field': 'disappointment_factor', 'required': True},
        ]
        
        rows = []
        for task in recent_tasks:
            rows.append({
                'task_name': task.get('task_name', 'Unknown'),
                'completed_at': task.get('completed_at', '')[:10] if task.get('completed_at') else '',
                'expected_relief': f"{task.get('expected_relief', 0):.1f}",
                'actual_relief': f"{task.get('actual_relief', 0):.1f}",
                'net_relief': f"{task.get('net_relief', 0):+.1f}",
                'serendipity_factor': f"{task.get('serendipity_factor', 0):.1f}",
                'disappointment_factor': f"{task.get('disappointment_factor', 0):.1f}",
            })
        
        ui.table(columns=columns, rows=rows).classes("w-full").props("dense flat bordered")
