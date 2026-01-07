from nicegui import ui
import pandas as pd
import plotly.express as px
import time
import json

from backend.analytics import Analytics
from backend.task_schema import TASK_ATTRIBUTES

analytics_service = Analytics()

# Attribute options for trends / correlations
NUMERIC_ATTRIBUTE_OPTIONS = [
    {'label': attr.label, 'value': attr.key}
    for attr in TASK_ATTRIBUTES
    if attr.dtype == 'numeric'
]

CALCULATED_METRICS = [
    {'label': 'Stress Level', 'value': 'stress_level'},
    {'label': 'Relief Score (Actual)', 'value': 'relief_score'},
    {'label': 'Expected Relief', 'value': 'expected_relief'},
    {'label': 'Net Relief (Actual - Expected)', 'value': 'net_relief'},
    {'label': 'Serendipity Factor', 'value': 'serendipity_factor'},
    {'label': 'Disappointment Factor', 'value': 'disappointment_factor'},
    {'label': 'Net Wellbeing', 'value': 'net_wellbeing'},
    {'label': 'Net Wellbeing (Normalized)', 'value': 'net_wellbeing_normalized'},
    {'label': 'Stress Efficiency', 'value': 'stress_efficiency'},
    {'label': 'Stress-Relief Correlation Score', 'value': 'stress_relief_correlation_score'},
    {'label': 'Productivity Score', 'value': 'productivity_score'},
    {'label': 'Daily Productivity Score (8h Idle Refresh)', 'value': 'daily_productivity_score_idle_refresh'},
    {'label': 'Grit Score', 'value': 'grit_score'},
    {'label': "Today's self care tasks", 'value': 'daily_self_care_tasks'},
    {'label': 'Work Time (minutes)', 'value': 'work_time'},
    {'label': 'Play Time (minutes)', 'value': 'play_time'},
    {'label': 'Thoroughness Score', 'value': 'thoroughness_score'},
    {'label': 'Thoroughness Factor', 'value': 'thoroughness_factor'},
    {'label': 'Execution Score', 'value': 'execution_score'},
]

ATTRIBUTE_OPTIONS = NUMERIC_ATTRIBUTE_OPTIONS + CALCULATED_METRICS
ATTRIBUTE_LABELS = {opt['value']: opt['label'] for opt in ATTRIBUTE_OPTIONS}
ATTRIBUTE_OPTIONS_DICT = {opt['value']: opt['label'] for opt in ATTRIBUTE_OPTIONS}


def register_analytics_page():
    @ui.page('/analytics')
    def analytics_dashboard():
        build_analytics_page()
    
    @ui.page('/analytics/emotional-flow')
    def emotional_flow_page():
        build_emotional_flow_page()
    
    @ui.page('/analytics/factors-comparison')
    def factors_comparison_page():
        from ui.factors_comparison_analytics import build_factors_comparison_page
        build_factors_comparison_page()


def build_analytics_page():
    ui.add_head_html("<style>.analytics-grid { gap: 1rem; }</style>")
    ui.label("Analytics Studio").classes("text-2xl font-bold mb-2")
    ui.label("Explore how task qualities evolve and prototype recommendation filters.").classes(
        "text-gray-500 mb-4"
    )
    
    # Analytics Module Navigation
    with ui.card().classes("p-4 mb-4 bg-blue-50 border border-blue-200"):
        ui.label("Analytics Modules").classes("text-lg font-semibold mb-2")
        ui.label("Explore specialized analytics views for different aspects of your task data.").classes("text-sm text-gray-600 mb-3")
        with ui.row().classes("gap-3 flex-wrap"):
            ui.button("📊 Emotional Flow", on_click=lambda: ui.navigate.to('/analytics/emotional-flow')).classes("bg-purple-500 text-white")
            ui.label("Track emotion changes and patterns").classes("text-xs text-gray-500 self-center")
            ui.button("🔄 Relief Comparison", on_click=lambda: ui.navigate.to('/analytics/relief-comparison')).classes("bg-green-500 text-white")
            ui.label("Compare expected vs actual relief").classes("text-xs text-gray-500 self-center")
            ui.button("⚙️ Factors Comparison", on_click=lambda: ui.navigate.to('/analytics/factors-comparison')).classes("bg-teal-500 text-white")
            ui.label("Analyze factors that influence scores").classes("text-xs text-gray-500 self-center")
            ui.button("📋 Cancelled Tasks", on_click=lambda: ui.navigate.to('/cancelled-tasks')).classes("bg-orange-500 text-white")
            ui.label("View cancelled task patterns and statistics").classes("text-xs text-gray-500 self-center")
            ui.button("📈 Summary", on_click=lambda: ui.navigate.to('/summary')).classes("bg-indigo-500 text-white")
            ui.label("View overall performance score").classes("text-xs text-gray-500 self-center")
            ui.button("📚 Analytics Glossary", on_click=lambda: ui.navigate.to('/analytics/glossary')).classes("bg-gray-500 text-white")
            ui.label("Learn about metrics and formulas").classes("text-xs text-gray-500 self-center")
    
    # Composite Score Summary
    from backend.user_state import UserStateManager
    user_state = UserStateManager()
    DEFAULT_USER_ID = "default_user"
    
    current_weights = user_state.get_score_weights(DEFAULT_USER_ID) or {}
    
    # Composite Score section - load asynchronously to avoid timeout
    composite_container = ui.card().classes("p-4 mb-4 bg-indigo-50 border border-indigo-200")
    with composite_container:
        loading_label = ui.label("Loading composite score...").classes("text-sm text-gray-500")
        with ui.row().classes("items-center gap-4 w-full").style("display: none;") as composite_row:
            ui.label("Composite Score").classes("text-lg font-semibold")
            with ui.card().classes("p-3 bg-white border-2 border-indigo-300") as score_card:
                score_label = ui.label("--").classes("text-3xl font-bold text-indigo-700")
                ui.label("/ 100").classes("text-sm text-indigo-600")
            ui.button("View Details", on_click=lambda: ui.navigate.to('/summary')).classes("bg-indigo-500 text-white")
            ui.button("Configure Weights", on_click=lambda: ui.navigate.to('/settings')).classes("bg-gray-500 text-white")
    
    def load_composite_score():
        """Load composite score asynchronously."""
        try:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H5', 'location': 'analytics_page.py:load_composite', 'message': 'calling get_all_scores_for_composite', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
            except: pass
            # #endregion
            
            get_scores_start = time.perf_counter()
            all_scores = analytics_service.get_all_scores_for_composite(days=7)
            get_scores_duration = (time.perf_counter() - get_scores_start) * 1000
            
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H5', 'location': 'analytics_page.py:load_composite', 'message': 'get_all_scores_for_composite completed', 'data': {'duration_ms': get_scores_duration, 'score_count': len(all_scores)}, 'timestamp': int(time.time() * 1000)}) + '\n')
            except: pass
            # #endregion
            
            composite_result = analytics_service.calculate_composite_score(
                components=all_scores,
                weights=current_weights,
                normalize_components=True
            )
            
            # Update UI
            loading_label.style("display: none;")
            composite_row.style("display: flex;")
            score_label.text = f"{composite_result['composite_score']:.1f}"
        except Exception as e:
            loading_label.text = f"Error loading composite score: {str(e)}"
            loading_label.classes("text-red-500")
    
    # Load composite score asynchronously
    ui.timer(0.1, load_composite_score, once=True)

    # Get all main analytics data in one batched call (Phase 2 optimization)
    page_data = analytics_service.get_analytics_page_data(days=7)
    metrics = page_data['dashboard_metrics']
    relief_summary = page_data['relief_summary']
    tracking_data = page_data['time_tracking']
    
    # Time Tracking Consistency Section
    with ui.card().classes("p-4 mb-4 bg-teal-50 border border-teal-200"):
        ui.label("Time Tracking Consistency").classes("text-xl font-bold mb-2")
        ui.label("Measures how well you track your time. Sleep up to 8 hours is rewarded. Untracked time is penalized.").classes(
            "text-sm text-gray-600 mb-3"
        )
        
        with ui.row().classes("gap-4 flex-wrap"):
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Tracking Score").classes("text-xs text-gray-500")
                ui.label(f"{tracking_data['tracking_consistency_score']:.1f}").classes(
                    "text-2xl font-bold"
                )
                ui.label("/ 100").classes("text-xs text-gray-600")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Avg Tracked Time").classes("text-xs text-gray-500")
                tracked_hours = tracking_data['avg_tracked_time_minutes'] / 60.0
                ui.label(f"{tracked_hours:.1f} hrs").classes("text-lg font-semibold")
                ui.label(f"({tracking_data['avg_tracked_time_minutes']:.0f} min)").classes(
                    "text-xs text-gray-600"
                )
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Avg Untracked Time").classes("text-xs text-gray-500")
                untracked_hours = tracking_data['avg_untracked_time_minutes'] / 60.0
                ui.label(f"{untracked_hours:.1f} hrs").classes("text-lg font-semibold text-orange-600")
                ui.label(f"({tracking_data['avg_untracked_time_minutes']:.0f} min)").classes(
                    "text-xs text-gray-600"
                )
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Avg Sleep Time").classes("text-xs text-gray-500")
                sleep_hours = tracking_data['avg_sleep_time_minutes'] / 60.0
                ui.label(f"{sleep_hours:.1f} hrs").classes("text-lg font-semibold")
                ui.label(f"({tracking_data['avg_sleep_time_minutes']:.0f} min)").classes(
                    "text-xs text-gray-600"
                )
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Tracking Coverage").classes("text-xs text-gray-500")
                coverage_pct = tracking_data['tracking_coverage'] * 100.0
                ui.label(f"{coverage_pct:.1f}%").classes("text-lg font-semibold")
                ui.label("of day tracked").classes("text-xs text-gray-600")
        
        ui.separator().classes("my-3")
        ui.label(
            "Note: Sleep up to 8 hours is rewarded. Untracked time is penalized. "
            "Higher tracking consistency means more of your day is logged."
        ).classes("text-sm text-gray-600")
    
    life_balance = metrics.get('life_balance', {})
    with ui.row().classes("gap-3 flex-wrap mb-4"):
        for title, value in [
            ("Active", metrics['counts']['active']),
            ("Completed 7d", metrics['counts']['completed_7d']),
            ("Completion Rate", f"{metrics['counts']['completion_rate']}%"),
            ("Today's self care tasks", metrics['counts']['daily_self_care_tasks']),
            ("Avg Daily Self Care Tasks", f"{metrics['counts']['avg_daily_self_care_tasks']:.1f}"),
            ("Time Est. Accuracy", f"{metrics['time']['estimation_accuracy']:.2f}x" if metrics['time']['estimation_accuracy'] > 0 else "N/A"),
            ("Avg Relief", metrics['quality']['avg_relief']),
            ("Avg Mental Energy", metrics['quality'].get('avg_mental_energy_needed', metrics['quality'].get('avg_cognitive_load', 'N/A'))),
            ("Avg Difficulty", metrics['quality'].get('avg_task_difficulty', metrics['quality'].get('avg_cognitive_load', 'N/A'))),
            ("Avg Stress Level", metrics['quality']['avg_stress_level']),
            ("Avg Net Wellbeing", metrics['quality']['avg_net_wellbeing']),
            ("Avg Net Wellbeing (Norm)", metrics['quality']['avg_net_wellbeing_normalized']),
            ("Adjusted Wellbeing", f"{metrics['quality'].get('adjusted_wellbeing', 0.0):.1f}"),
            ("Adjusted Wellbeing (Norm)", f"{metrics['quality'].get('adjusted_wellbeing_normalized', 50.0):.1f}"),
            ("Avg Stress Efficiency", metrics['quality']['avg_stress_efficiency'] if metrics['quality']['avg_stress_efficiency'] is not None else "N/A"),
            ("Avg Aversion", f"{metrics['quality'].get('avg_aversion', 0.0):.1f}"),
            ("General Aversion Score", f"{metrics.get('aversion', {}).get('general_aversion_score', 0.0):.1f}"),
            ("Avg Relief Score (No Mult)", f"{relief_summary.get('avg_relief_score_no_mult', 0.0):.1f}"),
            ("Avg Relief Score (With Mult)", f"{relief_summary.get('avg_relief_duration_score', 0.0):.1f}"),
            ("Total Relief Score (No Mult)", f"{relief_summary.get('total_relief_score_no_mult', 0.0):.1f}"),
            ("Total Relief Score (With Mult)", f"{relief_summary.get('total_relief_score', 0.0):.1f}"),
            ("Weekly Relief (Base)", f"{relief_summary.get('weekly_relief_score', 0.0):.1f}"),
            ("Weekly Relief + Bonus (Robust)", f"{relief_summary.get('weekly_relief_score_with_bonus_robust', 0.0):.1f}"),
            ("Weekly Relief + Bonus (Sensitive)", f"{relief_summary.get('weekly_relief_score_with_bonus_sensitive', 0.0):.1f}"),
            ("Total Productivity Score", f"{relief_summary.get('total_productivity_score', 0.0):.1f}"),
            ("Weekly Productivity Score", f"{relief_summary.get('weekly_productivity_score', 0.0):.1f}"),
            ("Total Grit Score", f"{relief_summary.get('total_grit_score', 0.0):.1f}"),
            ("Weekly Grit Score", f"{relief_summary.get('weekly_grit_score', 0.0):.1f}"),
            ("Thoroughness Score", f"{metrics['quality'].get('thoroughness_score', 50.0):.1f}"),
            ("Thoroughness Factor", f"{metrics['quality'].get('thoroughness_factor', 1.0):.3f}x"),
        ]:
            with ui.card().classes("p-3 min-w-[150px]"):
                ui.label(title).classes("text-xs text-gray-500")
                ui.label(value).classes("text-xl font-bold")
                # Add link to thoroughness glossary for thoroughness metrics
                if title in ["Thoroughness Score", "Thoroughness Factor"]:
                    ui.button("📚 Learn More", 
                            on_click=lambda: ui.navigate.to('/analytics/glossary/thoroughness_factor')).classes(
                        "text-xs bg-teal-500 text-white mt-1"
                    )
    
    # Get target hours from settings for display
    from backend.user_state import UserStateManager
    user_state = UserStateManager()
    goal_settings = user_state.get_productivity_goal_settings("default_user")
    goal_hours_per_week = goal_settings.get('goal_hours_per_week', 30.0)
    target_hours_per_day = goal_hours_per_week / 5.0  # Assume 5 work days
    
    # Productivity Volume Section
    productivity_volume = metrics.get('productivity_volume', {})
    with ui.card().classes("p-4 mb-4"):
        ui.label("Productivity Volume Analysis").classes("text-xl font-bold mb-2")
        ui.label("Metrics that account for both efficiency and total work volume").classes("text-sm text-gray-500 mb-3")
        ui.label(f"Goal: {goal_hours_per_week:.1f} hours/week ({target_hours_per_day:.1f} hours/day)").classes("text-xs text-blue-600 font-semibold mb-2")
        
        with ui.row().classes("gap-4 flex-wrap"):
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Avg Daily Work Time").classes("text-xs text-gray-500")
                avg_work_time = productivity_volume.get('avg_daily_work_time', 0.0)
                ui.label(f"{avg_work_time:.1f} min").classes("text-lg font-semibold")
                ui.label(f"({avg_work_time/60:.1f} hours)").classes("text-xs text-gray-600")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Work Volume Score").classes("text-xs text-gray-500")
                volume_score = productivity_volume.get('work_volume_score', 0.0)
                ui.label(f"{volume_score:.1f}").classes("text-lg font-semibold")
                ui.label("(0-100 scale)").classes("text-xs text-gray-600")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Work Consistency").classes("text-xs text-gray-500")
                consistency = productivity_volume.get('work_consistency_score', 50.0)
                ui.label(f"{consistency:.1f}").classes("text-lg font-semibold")
                ui.label("(0-100 scale)").classes("text-xs text-gray-600")
            
            with ui.card().classes("p-3 min-w-[200px] border-2 border-blue-300"):
                ui.label("Productivity Potential").classes("text-xs text-gray-500 font-semibold")
                potential = productivity_volume.get('productivity_potential_score', 0.0)
                ui.label(f"{potential:.1f}").classes("text-2xl font-bold text-blue-600")
                ui.label(f"If you worked {target_hours_per_day:.1f} hrs/day (Volumetric)").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px] border-2 border-orange-300"):
                ui.label("Work Volume Gap").classes("text-xs text-gray-500 font-semibold")
                gap = productivity_volume.get('work_volume_gap', 0.0)
                ui.label(f"{gap:.1f} hours").classes("text-2xl font-bold text-orange-600")
                ui.label(f"Gap to {target_hours_per_day:.1f} hrs/day target").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px] border-2 border-green-300"):
                ui.label("Composite Productivity").classes("text-xs text-gray-500 font-semibold")
                composite = productivity_volume.get('composite_productivity_score', 0.0)
                ui.label(f"{composite:.1f}").classes("text-2xl font-bold text-green-600")
                ui.label("Efficiency + Volume + Consistency").classes("text-xs text-gray-400")
        
        # Add glossary link
        with ui.row().classes("mt-2"):
            ui.button("View Volumetric Productivity Glossary", 
                     on_click=lambda: ui.navigate.to('/analytics/glossary/volumetric_productivity')).classes(
                "text-xs bg-blue-500 text-white"
            )
        
        # New Volumetric Productivity Section
        ui.separator().classes("my-4")
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.label("Volumetric Productivity (Volume-Integrated)").classes("text-lg font-semibold")
            ui.button("View Glossary", 
                     on_click=lambda: ui.navigate.to('/analytics/glossary/volumetric_productivity')).classes(
                "text-xs bg-green-500 text-white"
            )
        
        ui.label("Productivity score that integrates volume factor to provide more accurate measurements.").classes("text-sm text-gray-500 mb-3")
        
        with ui.row().classes("gap-4 flex-wrap"):
            with ui.card().classes("p-3 min-w-[200px] bg-gray-50"):
                ui.label("Base Productivity (Avg)").classes("text-xs text-gray-500 font-semibold")
                base_prod = productivity_volume.get('avg_base_productivity', 0.0)
                ui.label(f"{base_prod:.1f}").classes("text-lg font-semibold")
                ui.label("Per-task average").classes("text-xs text-gray-400 italic")
            
            with ui.card().classes("p-3 min-w-[200px] bg-green-100 border-2 border-green-300"):
                ui.label("Volumetric Productivity").classes("text-xs text-gray-700 font-bold")
                volumetric = productivity_volume.get('volumetric_productivity_score', 0.0)
                ui.label(f"{volumetric:.1f}").classes("text-2xl font-bold text-green-700")
                ui.label("Base × Volume Factor").classes("text-xs text-gray-600 italic")
            
            with ui.card().classes("p-3 min-w-[200px] bg-blue-100 border-2 border-blue-300"):
                ui.label("Volumetric Potential").classes("text-xs text-gray-700 font-bold")
                volumetric_pot = productivity_volume.get('volumetric_potential_score', 0.0)
                ui.label(f"{volumetric_pot:.1f}").classes("text-2xl font-bold text-blue-700")
                ui.label(f"At target volume ({target_hours_per_day:.1f} hrs/day)").classes("text-xs text-gray-600 italic")
    
    # Show warning if efficiency is high but volume is low
    avg_efficiency = metrics.get('quality', {}).get('avg_stress_efficiency')
    if avg_efficiency is not None and volume_score < 50 and avg_efficiency > 2.0:
        with ui.card().classes("p-3 mb-4 bg-yellow-50 border-2 border-yellow-300"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("warning", size="md").classes("text-yellow-600")
                ui.label("High efficiency but low work volume detected").classes("font-semibold text-yellow-800")
            ui.label(f"You're highly efficient (efficiency: {avg_efficiency:.2f}) but only working {avg_work_time/60:.1f} hours/day on average.").classes("text-sm text-yellow-700 mt-1")
            ui.label(f"Working more could significantly increase your productivity. Gap: {gap:.1f} hours/day to reach {target_hours_per_day:.1f} hours/day target.").classes("text-sm text-yellow-700")
    
    # Life Balance Section
    with ui.card().classes("p-4 mb-4"):
        ui.label("Life Balance").classes("text-xl font-bold mb-2")
        ui.label("Comparison of Work vs Play task amounts").classes("text-sm text-gray-500 mb-3")
        
        balance_score = life_balance.get('balance_score', 50.0)
        work_count = life_balance.get('work_count', 0)
        play_count = life_balance.get('play_count', 0)
        self_care_count = life_balance.get('self_care_count', 0)
        work_time = life_balance.get('work_time_minutes', 0.0)
        play_time = life_balance.get('play_time_minutes', 0.0)
        self_care_time = life_balance.get('self_care_time_minutes', 0.0)
        
        with ui.row().classes("gap-4 flex-wrap"):
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Balance Score").classes("text-xs text-gray-500")
                ui.label(f"{balance_score:.1f}").classes("text-2xl font-bold")
                ui.label("(50 = balanced)").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Work Tasks").classes("text-xs text-gray-500")
                ui.label(f"{work_count} tasks").classes("text-lg font-semibold")
                ui.label(f"{work_time:.1f} min").classes("text-sm text-gray-600")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Play Tasks").classes("text-xs text-gray-500")
                ui.label(f"{play_count} tasks").classes("text-lg font-semibold")
                ui.label(f"{play_time:.1f} min").classes("text-sm text-gray-600")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Self Care Tasks").classes("text-xs text-gray-500")
                ui.label(f"{self_care_count} tasks").classes("text-lg font-semibold")
                ui.label(f"{self_care_time:.1f} min").classes("text-sm text-gray-600")
    
    # Obstacles Overcome Section
    with ui.card().classes("p-4 mb-4"):
        ui.label("Overcoming Obstacles").classes("text-xl font-bold mb-2")
        ui.label("Tracking spontaneous aversion spikes and rewards for overcoming them").classes("text-sm text-gray-500 mb-3")
        
        total_obstacles_robust = relief_summary.get('total_obstacles_score_robust', 0.0)
        total_obstacles_sensitive = relief_summary.get('total_obstacles_score_sensitive', 0.0)
        max_spike_robust = relief_summary.get('max_obstacle_spike_robust', 0.0)
        max_spike_sensitive = relief_summary.get('max_obstacle_spike_sensitive', 0.0)
        bonus_mult_robust = relief_summary.get('weekly_obstacles_bonus_multiplier_robust', 1.0)
        bonus_mult_sensitive = relief_summary.get('weekly_obstacles_bonus_multiplier_sensitive', 1.0)
        
        with ui.row().classes("gap-4 flex-wrap"):
            with ui.card().classes("p-3 min-w-[200px] border-2 border-blue-300"):
                ui.label("Total Obstacles Score (Robust)").classes("text-xs text-gray-500 font-semibold")
                ui.label(f"{total_obstacles_robust:.1f}").classes("text-2xl font-bold text-blue-600")
                ui.label("Median-based baseline").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px] border-2 border-purple-300"):
                ui.label("Total Obstacles Score (Sensitive)").classes("text-xs text-gray-500 font-semibold")
                ui.label(f"{total_obstacles_sensitive:.1f}").classes("text-2xl font-bold text-purple-600")
                ui.label("Trimmed mean baseline").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Max Obstacle Spike (Robust)").classes("text-xs text-gray-500")
                ui.label(f"{max_spike_robust:.1f}").classes("text-xl font-semibold")
                ui.label("This week").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Max Obstacle Spike (Sensitive)").classes("text-xs text-gray-500")
                ui.label(f"{max_spike_sensitive:.1f}").classes("text-xl font-semibold")
                ui.label("This week").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px] bg-green-50"):
                ui.label("Weekly Bonus Multiplier (Robust)").classes("text-xs text-gray-500")
                ui.label(f"{bonus_mult_robust:.2f}x").classes("text-xl font-bold text-green-600")
                if bonus_mult_robust > 1.0:
                    bonus_pct = (bonus_mult_robust - 1.0) * 100
                    ui.label(f"+{bonus_pct:.0f}% bonus").classes("text-xs text-green-600")
                else:
                    ui.label("No bonus").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px] bg-green-50"):
                ui.label("Weekly Bonus Multiplier (Sensitive)").classes("text-xs text-gray-500")
                ui.label(f"{bonus_mult_sensitive:.2f}x").classes("text-xl font-bold text-green-600")
                if bonus_mult_sensitive > 1.0:
                    bonus_pct = (bonus_mult_sensitive - 1.0) * 100
                    ui.label(f"+{bonus_pct:.0f}% bonus").classes("text-xs text-green-600")
                else:
                    ui.label("No bonus").classes("text-xs text-gray-400")
    
    # Aversion Analytics Section - Multiple Formula Comparison
    with ui.card().classes("p-4 mb-4"):
        ui.label("Aversion Analytics").classes("text-xl font-bold mb-2")
        ui.label("Comparing different obstacles score formulas to understand how net relief and relief expectations affect scoring").classes("text-sm text-gray-500 mb-3")
        
        # Formula descriptions
        formula_descriptions = {
            'expected_only': 'Uses expected relief (decision-making context)',
            'actual_only': 'Uses actual relief (outcome-based)',
            'minimum': 'Uses min(expected, actual) - most conservative',
            'average': 'Uses (expected + actual) / 2 - balanced',
            'net_penalty': 'Uses expected, bonus if actual < expected (disappointment factor)',
            'net_bonus': 'Uses expected, reduced if actual > expected (surprise benefit)',
            'net_weighted': 'Uses expected, weighted by net relief factor'
        }
        
        # Display scores in a grid
        with ui.row().classes("gap-3 flex-wrap"):
            score_variants = ['expected_only', 'actual_only', 'minimum', 'average', 'net_penalty', 'net_bonus', 'net_weighted']
            
            for variant in score_variants:
                robust_key = f'total_obstacles_{variant}_robust'
                sensitive_key = f'total_obstacles_{variant}_sensitive'
                
                robust_score = relief_summary.get(robust_key, 0.0)
                sensitive_score = relief_summary.get(sensitive_key, 0.0)
                
                with ui.card().classes("p-3 min-w-[220px] border border-gray-200"):
                    # Variant name (formatted)
                    variant_label = variant.replace('_', ' ').title()
                    ui.label(variant_label).classes("text-xs font-semibold text-gray-700 mb-1")
                    
                    # Description
                    ui.label(formula_descriptions.get(variant, '')).classes("text-xs text-gray-500 mb-2")
                    
                    # Scores
                    with ui.row().classes("gap-2 items-center"):
                        ui.label("Robust:").classes("text-xs text-gray-600")
                        ui.label(f"{robust_score:.1f}").classes("text-sm font-bold text-blue-600")
                    
                    with ui.row().classes("gap-2 items-center"):
                        ui.label("Sensitive:").classes("text-xs text-gray-600")
                        ui.label(f"{sensitive_score:.1f}").classes("text-sm font-bold text-purple-600")

    # Get all chart data in one batched call (Phase 2 optimization)
    chart_data = analytics_service.get_chart_data()
    
    with ui.row().classes("analytics-grid flex-wrap w-full"):
        _render_time_chart(chart_data['trend_series'])
        _render_attribute_box(chart_data['attribute_distribution'])

    _render_trends_section()
    _render_stress_metrics_section(chart_data['stress_dimension_data'])
    
    # Get all rankings data in one batched call (Phase 2 optimization)
    rankings_data = analytics_service.get_rankings_data(top_n=5, leaderboard_n=10)
    
    _render_task_rankings(rankings_data)
    _render_stress_efficiency_leaderboard(rankings_data['stress_efficiency_leaderboard'])
    _render_metric_comparison(metrics)
    _render_correlation_explorer()


def _render_time_chart(df=None):
    """Render time chart. If df is provided, use it (batched), otherwise fetch."""
    if df is None:
        df = analytics_service.trend_series()
    with ui.card().classes("p-3 grow"):
        ui.label("Total relief trend").classes("font-bold text-md mb-2")
        if df.empty:
            ui.label("No completed instances yet.").classes("text-xs text-gray-500")
            return
        fig = px.line(
            df,
            x='completed_at',
            y='cumulative_relief_score',
            markers=True,
            title="Total relief score over time (cumulative)",
        )
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        ui.plotly(fig)


def _render_attribute_box(df=None):
    """Render attribute box chart. If df is provided, use it (batched), otherwise fetch."""
    if df is None:
        df = analytics_service.attribute_distribution()
    with ui.card().classes("p-3 grow"):
        ui.label("Attribute distribution").classes("font-bold text-md mb-2")
        if df.empty:
            ui.label("Need more data before plotting distributions.").classes("text-xs text-gray-500")
            return
        fig = px.box(
            df,
            x='attribute',
            y='value',
            color='attribute',
            title="Spread across wellbeing metrics",
        )
        fig.update_layout(showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
        ui.plotly(fig)


def _render_trends_section():
    with ui.card().classes("p-3 w-full"):
        ui.label("Trends").classes("font-bold text-lg mb-2")
        ui.label("View daily trends for any attribute or calculated metric.").classes("text-xs text-gray-500 mb-2")

        with ui.row().classes("gap-3 flex-wrap"):
            default_attrs = []
            for key in ['net_wellbeing', 'stress_level']:
                if key in ATTRIBUTE_OPTIONS_DICT:
                    default_attrs.append(key)
            if not default_attrs and ATTRIBUTE_OPTIONS_DICT:
                default_attrs = [next(iter(ATTRIBUTE_OPTIONS_DICT))]

            attr_select = ui.select(
                options=ATTRIBUTE_OPTIONS_DICT,
                value=default_attrs,
                label="Attributes",
                multiple=True,
            ).props("dense outlined use-chips clearable")

            agg_select = ui.select(
                options={
                    'mean': 'Mean',
                    'sum': 'Sum',
                    'median': 'Median',
                    'min': 'Min',
                    'max': 'Max',
                    'count': 'Count',
                },
                value='sum',
                label="Aggregation",
            ).props("dense outlined")

            days_select = ui.select(
                options={
                    30: '30 days',
                    60: '60 days',
                    90: '90 days',
                },
                value=90,
                label="Range",
            ).props("dense outlined")

            normalize_switch = ui.switch("Normalize series (0-1)").props("dense")

        chart_area = ui.column().classes("mt-3 w-full")

        def update_chart():
            chart_area.clear()
            attrs = attr_select.value or []
            aggregation = agg_select.value or 'mean'
            days = int(days_select.value) if days_select.value else 90
            normalize = bool(normalize_switch.value)

            if not attrs:
                with chart_area:
                    ui.label("Select at least one attribute to plot.").classes("text-xs text-gray-500")
                return

            trends = analytics_service.get_multi_attribute_trends(
                attribute_keys=attrs,
                aggregation=aggregation,
                days=days,
                normalize=normalize,
            )

            rows = []
            for key, data in trends.items():
                dates = data.get('dates') or []
                values = data.get('values') or []
                if not dates or not values:
                    continue
                label = ATTRIBUTE_LABELS.get(key, key)
                for d, v in zip(dates, values):
                    rows.append({'date': d, 'value': v, 'attribute': label})

            if not rows:
                with chart_area:
                    ui.label("No trend data yet for the selected attributes.").classes("text-xs text-gray-500")
                return

            df = pd.DataFrame(rows)
            fig = px.line(df, x='date', y='value', color='attribute', markers=True, title="Daily trends")
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), legend_title_text="Attribute")
            with chart_area:
                ui.plotly(fig)

        attr_select.on('update:model-value', lambda e: update_chart())
        agg_select.on('update:model-value', lambda e: update_chart())
        days_select.on('update:model-value', lambda e: update_chart())
        normalize_switch.on('update:model-value', lambda e: update_chart())

        update_chart()


def _render_stress_metrics_section(stress_data=None):
    """Render stress dimension metrics with bar charts and line graphs.
    
    Args:
        stress_data: Optional pre-fetched stress dimension data (for batching)
    """
    ui.separator().classes("my-4")
    with ui.card().classes("p-4 w-full"):
        ui.label("Stress Metrics").classes("text-xl font-bold mb-2")
        ui.label("Separate visualization of cognitive, emotional, and physical stress dimensions").classes(
            "text-sm text-gray-500 mb-3"
        )
        
        # Helper function to calculate daily average
        def calc_daily_avg(daily_list):
            if not daily_list:
                return 0.0
            values = [item['value'] for item in daily_list if item.get('value') is not None]
            return sum(values) / len(values) if values else 0.0
        
        # Get stress dimension data if not provided
        if stress_data is None:
            stress_data = analytics_service.get_stress_dimension_data()
        
        # Calculate daily averages (overall, not just 7-day)
        cognitive_daily_avg = calc_daily_avg(stress_data.get('cognitive', {}).get('daily', []))
        emotional_daily_avg = calc_daily_avg(stress_data.get('emotional', {}).get('daily', []))
        physical_daily_avg = calc_daily_avg(stress_data.get('physical', {}).get('daily', []))
        
        # Separate bar charts for each metric type
        with ui.row().classes("gap-4 flex-wrap mb-4"):
            # Comparison bar chart - Totals
            with ui.card().classes("p-3 flex-1 min-w-[300px]"):
                ui.label("Total Stress by Dimension").classes("font-bold text-md mb-2")
                if not stress_data or all(v['total'] == 0.0 for v in stress_data.values()):
                    ui.label("No data yet").classes("text-xs text-gray-500")
                else:
                    comparison_df = pd.DataFrame({
                        'Dimension': ['Cognitive', 'Emotional', 'Physical'],
                        'Total': [
                            stress_data['cognitive']['total'],
                            stress_data['emotional']['total'],
                            stress_data['physical']['total']
                        ]
                    })
                    fig = px.bar(
                        comparison_df,
                        x='Dimension',
                        y='Total',
                        color='Dimension',
                        color_discrete_map={
                            'Cognitive': '#3498db',
                            'Emotional': '#e74c3c',
                            'Physical': '#2ecc71'
                        },
                        title="Total Stress Accumulated"
                    )
                    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), showlegend=False)
                    ui.plotly(fig)
            
            # Comparison bar chart - 7-day average
            with ui.card().classes("p-3 flex-1 min-w-[300px]"):
                ui.label("7-Day Average by Dimension").classes("font-bold text-md mb-2")
                if not stress_data or all(v['avg_7d'] == 0.0 for v in stress_data.values()):
                    ui.label("No data yet").classes("text-xs text-gray-500")
                else:
                    avg_7d_df = pd.DataFrame({
                        'Dimension': ['Cognitive', 'Emotional', 'Physical'],
                        '7-Day Average': [
                            stress_data['cognitive']['avg_7d'],
                            stress_data['emotional']['avg_7d'],
                            stress_data['physical']['avg_7d']
                        ]
                    })
                    fig = px.bar(
                        avg_7d_df,
                        x='Dimension',
                        y='7-Day Average',
                        color='Dimension',
                        color_discrete_map={
                            'Cognitive': '#3498db',
                            'Emotional': '#e74c3c',
                            'Physical': '#2ecc71'
                        },
                        title="7-Day Average Stress"
                    )
                    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), showlegend=False)
                    ui.plotly(fig)
            
            # Comparison bar chart - Daily average
            with ui.card().classes("p-3 flex-1 min-w-[300px]"):
                ui.label("Daily Average by Dimension").classes("font-bold text-md mb-2")
                if cognitive_daily_avg == 0.0 and emotional_daily_avg == 0.0 and physical_daily_avg == 0.0:
                    ui.label("No data yet").classes("text-xs text-gray-500")
                else:
                    daily_avg_df = pd.DataFrame({
                        'Dimension': ['Cognitive', 'Emotional', 'Physical'],
                        'Daily Average': [
                            cognitive_daily_avg,
                            emotional_daily_avg,
                            physical_daily_avg
                        ]
                    })
                    fig = px.bar(
                        daily_avg_df,
                        x='Dimension',
                        y='Daily Average',
                        color='Dimension',
                        color_discrete_map={
                            'Cognitive': '#3498db',
                            'Emotional': '#e74c3c',
                            'Physical': '#2ecc71'
                        },
                        title="Daily Average Stress"
                    )
                    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), showlegend=False)
                    ui.plotly(fig)
        
        # Line graphs showing values over time
        with ui.card().classes("p-3 w-full mt-4"):
            ui.label("Stress Dimensions Over Time").classes("font-bold text-md mb-2")
            
            # Prepare data for time series
            cognitive_daily = stress_data.get('cognitive', {}).get('daily', [])
            emotional_daily = stress_data.get('emotional', {}).get('daily', [])
            physical_daily = stress_data.get('physical', {}).get('daily', [])
            
            if not cognitive_daily and not emotional_daily and not physical_daily:
                ui.label("No time series data yet. Complete some tasks to see trends.").classes("text-xs text-gray-500")
            else:
                # Combine all daily data into a single dataframe
                time_series_rows = []
                
                for item in cognitive_daily:
                    time_series_rows.append({
                        'date': item['date'],
                        'value': item['value'],
                        'dimension': 'Cognitive'
                    })
                
                for item in emotional_daily:
                    time_series_rows.append({
                        'date': item['date'],
                        'value': item['value'],
                        'dimension': 'Emotional'
                    })
                
                for item in physical_daily:
                    time_series_rows.append({
                        'date': item['date'],
                        'value': item['value'],
                        'dimension': 'Physical'
                    })
                
                if time_series_rows:
                    ts_df = pd.DataFrame(time_series_rows)
                    ts_df['date'] = pd.to_datetime(ts_df['date'])
                    ts_df = ts_df.sort_values('date')
                    
                    fig = px.line(
                        ts_df,
                        x='date',
                        y='value',
                        color='dimension',
                        markers=True,
                        color_discrete_map={
                            'Cognitive': '#3498db',
                            'Emotional': '#e74c3c',
                            'Physical': '#2ecc71'
                        },
                        title="Daily Average Stress by Dimension"
                    )
                    fig.update_layout(
                        margin=dict(l=20, r=20, t=40, b=20),
                        legend_title_text="Dimension",
                        xaxis_title="Date",
                        yaxis_title="Stress Level"
                    )
                    ui.plotly(fig)
                else:
                    ui.label("No time series data available").classes("text-xs text-gray-500")
        
        # Summary statistics
        with ui.row().classes("gap-4 flex-wrap mt-4"):
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Cognitive Stress").classes("text-xs text-gray-500 font-semibold")
                ui.label(f"Total: {stress_data['cognitive']['total']:.1f}").classes("text-sm")
                ui.label(f"7-Day Avg: {stress_data['cognitive']['avg_7d']:.1f}").classes("text-sm")
                ui.label(f"Daily Avg: {cognitive_daily_avg:.1f}").classes("text-sm")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Emotional Stress").classes("text-xs text-gray-500 font-semibold")
                ui.label(f"Total: {stress_data['emotional']['total']:.1f}").classes("text-sm")
                ui.label(f"7-Day Avg: {stress_data['emotional']['avg_7d']:.1f}").classes("text-sm")
                ui.label(f"Daily Avg: {emotional_daily_avg:.1f}").classes("text-sm")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Physical Stress").classes("text-xs text-gray-500 font-semibold")
                ui.label(f"Total: {stress_data['physical']['total']:.1f}").classes("text-sm")
                ui.label(f"7-Day Avg: {stress_data['physical']['avg_7d']:.1f}").classes("text-sm")
                ui.label(f"Daily Avg: {physical_daily_avg:.1f}").classes("text-sm")


def _render_metric_comparison(metrics=None):
    """Render a flexible metric comparison tool with scatter plots.
    
    Args:
        metrics: Optional pre-fetched dashboard metrics (for batching)
    """
    ui.separator().classes("my-4")
    with ui.card().classes("p-4 w-full"):
        ui.label("Metric Comparison").classes("text-xl font-bold mb-2")
        ui.label("Compare any two metrics with interactive scatter plots. Perfect for analyzing relationships like Productivity vs Grit.").classes(
            "text-sm text-gray-500 mb-3"
        )
        
        with ui.row().classes("gap-3 flex-wrap"):
            x_select = ui.select(
                options=ATTRIBUTE_OPTIONS_DICT,
                value='productivity_score' if 'productivity_score' in ATTRIBUTE_OPTIONS_DICT else (next(iter(ATTRIBUTE_OPTIONS_DICT)) if ATTRIBUTE_OPTIONS_DICT else None),
                label="X-Axis Metric",
            ).props("dense outlined clearable").classes("min-w-[200px]")
            
            y_select = ui.select(
                options=ATTRIBUTE_OPTIONS_DICT,
                value='grit_score' if 'grit_score' in ATTRIBUTE_OPTIONS_DICT else (next(iter(ATTRIBUTE_OPTIONS_DICT)) if ATTRIBUTE_OPTIONS_DICT else None),
                label="Y-Axis Metric",
            ).props("dense outlined clearable").classes("min-w-[200px]")
            
            show_trendline = ui.switch("Show trendline", value=True).props("dense")
            show_efficiency = ui.switch("Show efficiency metrics", value=True).props("dense")
        
        chart_area = ui.column().classes("mt-3 w-full gap-3")
        stats_area = ui.column().classes("mt-3 w-full gap-2")
        
        def render_comparison():
            # Get metrics if not provided
            nonlocal metrics
            if metrics is None:
                metrics = analytics_service.get_dashboard_metrics()
            chart_area.clear()
            stats_area.clear()
            
            x_attr = x_select.value
            y_attr = y_select.value
            
            if not x_attr or not y_attr:
                with chart_area:
                    ui.label("Select both X and Y metrics to compare.").classes("text-xs text-gray-500")
                return
            
            if x_attr == y_attr:
                with chart_area:
                    ui.label("Choose two different metrics to compare.").classes("text-xs text-gray-500")
                return
            
            # Get scatter data
            scatter = analytics_service.get_scatter_data(x_attr, y_attr)
            stats = analytics_service.calculate_correlation(x_attr, y_attr, method='pearson')
            
            label_x = ATTRIBUTE_LABELS.get(x_attr, x_attr)
            label_y = ATTRIBUTE_LABELS.get(y_attr, y_attr)
            
            if scatter.get('n', 0) == 0:
                with chart_area:
                    ui.label("Not enough data to plot. Complete some tasks first.").classes("text-xs text-gray-500")
                return
            
            # Create scatter plot
            scatter_df = pd.DataFrame({
                'x': scatter['x'],
                'y': scatter['y']
            })
            
            # Check if statsmodels is available for trendline
            use_trendline = False
            if show_trendline.value:
                try:
                    import statsmodels.api as sm  # noqa: F401
                    use_trendline = True
                except ImportError:
                    pass  # statsmodels not available, skip trendline
            
            fig = px.scatter(
                scatter_df,
                x='x',
                y='y',
                labels={'x': label_x, 'y': label_y},
                title=f"{label_x} vs {label_y}",
                trendline='ols' if use_trendline else None,
            )
            fig.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode='closest'
            )
            
            with chart_area:
                ui.plotly(fig)
            
            # Show statistics
            with stats_area:
                corr = stats.get('correlation')
                p_val = stats.get('p_value')
                r_sq = stats.get('r_squared')
                n = stats.get('n')
                
                with ui.card().classes("p-3"):
                    ui.label("Correlation Statistics").classes("font-semibold text-sm mb-2")
                    with ui.column().classes("gap-1"):
                        if corr is not None:
                            ui.label(f"Correlation (r): {corr:.3f}").classes("text-sm")
                            # Interpret correlation strength
                            if abs(corr) >= 0.7:
                                strength = "Strong"
                                color = "text-green-600"
                            elif abs(corr) >= 0.4:
                                strength = "Moderate"
                                color = "text-yellow-600"
                            elif abs(corr) >= 0.2:
                                strength = "Weak"
                                color = "text-orange-600"
                            else:
                                strength = "Very Weak"
                                color = "text-gray-600"
                            ui.label(f"Strength: {strength}").classes(f"text-xs {color}")
                        else:
                            ui.label("Correlation: N/A").classes("text-sm")
                        
                        if r_sq is not None:
                            ui.label(f"R²: {r_sq:.3f} ({r_sq*100:.1f}% variance explained)").classes("text-sm")
                        
                        if p_val is not None:
                            significance = "Significant" if p_val < 0.05 else "Not Significant"
                            ui.label(f"p-value: {p_val:.4f} ({significance})").classes("text-sm")
                        
                        ui.label(f"Sample size: {n}").classes("text-xs text-gray-500")
                
                # Efficiency analysis for various metric combinations
                if show_efficiency.value:
                    # Define disclaimers for problematic combinations
                    disclaimers = {
                        # Productivity score already factors time efficiency
                        ('duration_minutes', 'productivity_score'): "⚠️ Note: Productivity Score already incorporates time efficiency (rewards completing faster than estimated). This ratio shows absolute productivity density, not efficiency relative to estimates.",
                        ('productivity_score', 'duration_minutes'): "⚠️ Note: Productivity Score already incorporates time efficiency (rewards completing faster than estimated). This ratio shows absolute productivity density, not efficiency relative to estimates.",
                        # Stress efficiency is already relief/stress
                        ('stress_level', 'stress_efficiency'): "⚠️ Note: Stress Efficiency is already calculated as Relief/Stress. This comparison may be redundant.",
                        ('stress_efficiency', 'stress_level'): "⚠️ Note: Stress Efficiency is already calculated as Relief/Stress. This comparison may be redundant.",
                        ('relief_score', 'stress_efficiency'): "⚠️ Note: Stress Efficiency is already calculated as Relief/Stress. This comparison may be redundant.",
                        ('stress_efficiency', 'relief_score'): "⚠️ Note: Stress Efficiency is already calculated as Relief/Stress. This comparison may be redundant.",
                    }
                    
                    # Define efficiency analysis configurations
                    # Format: (x_attr, y_attr): (ratio_formula, description, interpretation_thresholds, label, use_time_efficiency)
                    efficiency_configs = {
                        # Productivity vs Grit
                        ('productivity_score', 'grit_score'): (
                            lambda x, y: x / y if y > 0 else None,
                            "Productivity per unit of Grit",
                            {'high': 2.0, 'moderate': 0.5},
                            "Higher ratio = more productivity with less grit investment",
                            False
                        ),
                        ('grit_score', 'productivity_score'): (
                            lambda x, y: y / x if x > 0 else None,
                            "Productivity per unit of Grit",
                            {'high': 2.0, 'moderate': 0.5},
                            "Higher ratio = more productivity with less grit investment",
                            False
                        ),
                        # Work Time vs Play Time
                        ('work_time', 'play_time'): (
                            lambda x, y: x / y if y > 0 else None,
                            "Work Time per unit of Play Time",
                            {'high': 2.0, 'moderate': 0.5},
                            "Ratio shows work-play balance (1.0 = balanced)",
                            False
                        ),
                        ('play_time', 'work_time'): (
                            lambda x, y: x / y if y > 0 else None,
                            "Play Time per unit of Work Time",
                            {'high': 0.5, 'moderate': 0.2},
                            "Ratio shows play-work balance (1.0 = balanced)",
                            False
                        ),
                        # Stress vs Relief (Stress Efficiency)
                        ('stress_level', 'relief_score'): (
                            lambda x, y: y / x if x > 0 else None,
                            "Relief per unit of Stress (Stress Efficiency)",
                            {'high': 2.0, 'moderate': 1.0},
                            "Higher ratio = more relief for less stress. Note: This is the same calculation as the Stress Efficiency metric.",
                            False
                        ),
                        ('relief_score', 'stress_level'): (
                            lambda x, y: x / y if y > 0 else None,
                            "Relief per unit of Stress (Stress Efficiency)",
                            {'high': 2.0, 'moderate': 1.0},
                            "Higher ratio = more relief for less stress. Note: This is the same calculation as the Stress Efficiency metric.",
                            False
                        ),
                        # Time vs Productivity - Use new time efficiency metric
                        ('duration_minutes', 'productivity_score'): (
                            None,  # Will use time efficiency calculation instead
                            "Time Efficiency (Estimate/Actual)",
                            {'high': 1.2, 'moderate': 1.0},
                            "Higher ratio = completed faster than estimated. 1.0 = on time, >1.0 = faster, <1.0 = slower.",
                            True
                        ),
                        ('productivity_score', 'duration_minutes'): (
                            None,  # Will use time efficiency calculation instead
                            "Time Efficiency (Estimate/Actual)",
                            {'high': 1.2, 'moderate': 1.0},
                            "Higher ratio = completed faster than estimated. 1.0 = on time, >1.0 = faster, <1.0 = slower.",
                            True
                        ),
                        # Stress vs Net Wellbeing
                        ('stress_level', 'net_wellbeing'): (
                            lambda x, y: y / x if x > 0 else None,
                            "Net Wellbeing per unit of Stress",
                            {'high': 1.0, 'moderate': 0.5},
                            "Higher ratio = better wellbeing despite stress",
                            False
                        ),
                        ('net_wellbeing', 'stress_level'): (
                            lambda x, y: x / y if y > 0 else None,
                            "Net Wellbeing per unit of Stress",
                            {'high': 1.0, 'moderate': 0.5},
                            "Higher ratio = better wellbeing despite stress",
                            False
                        ),
                        # Relief vs Net Wellbeing
                        ('relief_score', 'net_wellbeing'): (
                            lambda x, y: y / x if x > 0 else None,
                            "Net Wellbeing per unit of Relief",
                            {'high': 1.5, 'moderate': 1.0},
                            "Higher ratio = wellbeing exceeds relief (positive impact)",
                            False
                        ),
                        ('net_wellbeing', 'relief_score'): (
                            lambda x, y: x / y if y > 0 else None,
                            "Net Wellbeing per unit of Relief",
                            {'high': 1.5, 'moderate': 1.0},
                            "Higher ratio = wellbeing exceeds relief (positive impact)",
                            False
                        ),
                        # Time vs Relief
                        ('duration_minutes', 'relief_score'): (
                            lambda x, y: y / x if x > 0 else None,
                            "Relief per minute",
                            {'high': 0.5, 'moderate': 0.2},
                            "Higher ratio = more relief per time invested",
                            False
                        ),
                        ('relief_score', 'duration_minutes'): (
                            lambda x, y: x / y if y > 0 else None,
                            "Relief per minute",
                            {'high': 0.5, 'moderate': 0.2},
                            "Higher ratio = more relief per time invested",
                            False
                        ),
                    }
                    
                    # Check if current combination has efficiency analysis
                    key = (x_attr, y_attr)
                    if key in efficiency_configs:
                        config = efficiency_configs[key]
                        use_time_efficiency = config[4] if len(config) > 4 else False
                        
                        if use_time_efficiency:
                            # Use new time efficiency metric based on estimates
                            ratio_func, description, thresholds, interpretation_label, _ = config
                            
                            with ui.card().classes("p-3 bg-blue-50"):
                                ui.label("Time Efficiency Analysis").classes("font-semibold text-sm mb-2 text-blue-700")
                                
                                # Show disclaimer if applicable
                                if key in disclaimers:
                                    with ui.row().classes("mb-2"):
                                        ui.icon("info", size="sm").classes("text-yellow-600 mt-0.5")
                                        ui.label(disclaimers[key]).classes("text-xs text-yellow-700")
                                
                                # Get time data from scatter
                                time_data = scatter.get('time_data')
                                if time_data and 'time_estimate' in time_data and 'time_actual' in time_data:
                                    time_estimates = time_data['time_estimate']
                                    time_actuals = time_data['time_actual']
                                    
                                    # Calculate time efficiency: estimate/actual (higher = faster than estimated)
                                    efficiency_ratios = []
                                    for est, actual in zip(time_estimates, time_actuals):
                                        if est is not None and actual is not None and est > 0 and actual > 0:
                                            ratio = est / actual  # >1.0 means faster than estimated
                                            efficiency_ratios.append(ratio)
                                    
                                    if efficiency_ratios:
                                        avg_efficiency = sum(efficiency_ratios) / len(efficiency_ratios)
                                        
                                        with ui.column().classes("gap-1"):
                                            ui.label(f"Average Time Efficiency: {avg_efficiency:.3f}").classes("text-sm")
                                            ui.label(f"({description})").classes("text-xs text-gray-600")
                                            
                                            # Interpretation
                                            high_threshold = thresholds.get('high', 1.0)
                                            moderate_threshold = thresholds.get('moderate', 1.0)
                                            
                                            if avg_efficiency >= high_threshold:
                                                interpretation = "Highly Efficient (Faster than Estimated)"
                                                color = "text-green-600"
                                            elif avg_efficiency >= moderate_threshold:
                                                interpretation = "On Time or Moderately Efficient"
                                                color = "text-yellow-600"
                                            else:
                                                interpretation = "Less Efficient (Slower than Estimated)"
                                                color = "text-orange-600"
                                            
                                            ui.label(f"Interpretation: {interpretation}").classes(f"text-xs font-semibold {color}")
                                            ui.label(interpretation_label).classes("text-xs text-gray-500 mt-1")
                                            
                                            # Add volume context warning if efficiency is high but volume is low
                                            # Use already-loaded metrics from page_data to avoid duplicate call
                                            volume_metrics = metrics.get('productivity_volume', {})
                                            volume_score = volume_metrics.get('work_volume_score', 0.0)
                                            avg_work_time = volume_metrics.get('avg_daily_work_time', 0.0)
                                            
                                            if avg_efficiency >= high_threshold and volume_score < 50:
                                                with ui.row().classes("mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded"):
                                                    ui.icon("info", size="sm").classes("text-yellow-600 mt-0.5")
                                                    with ui.column().classes("gap-0"):
                                                        ui.label("Volume Context").classes("text-xs font-semibold text-yellow-800")
                                                        ui.label(f"High efficiency ({avg_efficiency:.2f}) but low work volume ({avg_work_time/60:.1f} hrs/day).").classes("text-xs text-yellow-700")
                                                        ui.label("Working more could significantly increase total productivity.").classes("text-xs text-yellow-700")
                                    else:
                                        ui.label("Insufficient time estimate data for efficiency calculation").classes("text-xs text-gray-500")
                                else:
                                    ui.label("Time estimate data not available. Complete tasks with time estimates to see efficiency analysis.").classes("text-xs text-gray-500")
                        else:
                            # Standard efficiency calculation
                            ratio_func, description, thresholds, interpretation_label, _ = config
                            
                            with ui.card().classes("p-3 bg-blue-50"):
                                ui.label("Efficiency Analysis").classes("font-semibold text-sm mb-2 text-blue-700")
                                
                                # Show disclaimer if applicable
                                if key in disclaimers:
                                    with ui.row().classes("mb-2"):
                                        ui.icon("info", size="sm").classes("text-yellow-600 mt-0.5")
                                        ui.label(disclaimers[key]).classes("text-xs text-yellow-700")
                                
                                x_vals = scatter['x']
                                y_vals = scatter['y']
                                
                                # Calculate efficiency ratios
                                efficiency_ratios = []
                                for x, y in zip(x_vals, y_vals):
                                    if x is not None and y is not None:
                                        ratio = ratio_func(x, y)
                                        if ratio is not None:
                                            efficiency_ratios.append(ratio)
                                
                                if efficiency_ratios:
                                    avg_efficiency = sum(efficiency_ratios) / len(efficiency_ratios)
                                    
                                    with ui.column().classes("gap-1"):
                                        ui.label(f"Average Efficiency Ratio: {avg_efficiency:.3f}").classes("text-sm")
                                        ui.label(f"({description})").classes("text-xs text-gray-600")
                                        
                                        # Interpretation based on thresholds
                                        high_threshold = thresholds.get('high', 1.0)
                                        moderate_threshold = thresholds.get('moderate', 0.5)
                                        
                                        if avg_efficiency >= high_threshold:
                                            interpretation = "Highly Efficient"
                                            color = "text-green-600"
                                        elif avg_efficiency >= moderate_threshold:
                                            interpretation = "Moderately Efficient"
                                            color = "text-yellow-600"
                                        else:
                                            interpretation = "Less Efficient"
                                            color = "text-orange-600"
                                        
                                        ui.label(f"Interpretation: {interpretation}").classes(f"text-xs font-semibold {color}")
                                        ui.label(interpretation_label).classes("text-xs text-gray-500 mt-1")
                                        
                                        # Add volume context warning if efficiency is high but volume is low
                                        # Use already-loaded metrics from page_data to avoid duplicate call
                                        volume_metrics = metrics.get('productivity_volume', {})
                                        volume_score = volume_metrics.get('work_volume_score', 0.0)
                                        avg_work_time = volume_metrics.get('avg_daily_work_time', 0.0)
                                        
                                        if avg_efficiency >= high_threshold and volume_score < 50:
                                            with ui.row().classes("mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded"):
                                                ui.icon("info", size="sm").classes("text-yellow-600 mt-0.5")
                                                with ui.column().classes("gap-0"):
                                                    ui.label("Volume Context").classes("text-xs font-semibold text-yellow-800")
                                                    ui.label(f"High efficiency ({avg_efficiency:.2f}) but low work volume ({avg_work_time/60:.1f} hrs/day).").classes("text-xs text-yellow-700")
                                                    ui.label("Working more could significantly increase total productivity.").classes("text-xs text-yellow-700")
                                else:
                                    ui.label("Insufficient data for efficiency calculation").classes("text-xs text-gray-500")
        
        # Set up event handlers
        x_select.on('update:model-value', lambda e: render_comparison())
        y_select.on('update:model-value', lambda e: render_comparison())
        show_trendline.on('update:model-value', lambda e: render_comparison())
        show_efficiency.on('update:model-value', lambda e: render_comparison())
        
        # Initial render
        render_comparison()


def _render_correlation_explorer():
    ui.separator().classes("my-4")
    with ui.expansion("Developer Tools: Correlation Explorer", icon="science", value=False):
        with ui.card().classes("p-3 w-full"):
            ui.label("Explore relationships between attributes.").classes("text-xs text-gray-500 mb-2")
            with ui.row().classes("gap-3 flex-wrap"):
                x_select = ui.select(
                    options=ATTRIBUTE_OPTIONS_DICT,
                    value=next(iter(ATTRIBUTE_OPTIONS_DICT)) if ATTRIBUTE_OPTIONS_DICT else None,
                    label="Independent (X)",
                ).props("dense outlined clearable")
                y_select = ui.select(
                    options=ATTRIBUTE_OPTIONS_DICT,
                    value=next(iter(ATTRIBUTE_OPTIONS_DICT)) if ATTRIBUTE_OPTIONS_DICT else None,
                    label="Dependent (Y)",
                ).props("dense outlined clearable")
                method_select = ui.select(
                    options={
                        'pearson': 'Pearson',
                        'spearman': 'Spearman',
                    },
                    value='pearson',
                    label="Method",
                ).props("dense outlined")
                ui.label("Bins for threshold analysis").classes("text-xs text-gray-500 mt-1")
                bin_slider = ui.slider(
                    min=3,
                    max=15,
                    value=8,
                    step=1,
                ).props("dense")

            chart_area = ui.column().classes("mt-3 w-full gap-3")

            def render_correlation():
                chart_area.clear()
                x_attr = x_select.value
                y_attr = y_select.value
                method = method_select.value or 'pearson'
                bins = int(bin_slider.value) if bin_slider.value else 8

                if not x_attr or not y_attr:
                    with chart_area:
                        ui.label("Select both X and Y attributes.").classes("text-xs text-gray-500")
                    return
                if x_attr == y_attr:
                    with chart_area:
                        ui.label("Choose two different attributes to compare.").classes("text-xs text-gray-500")
                    return

                scatter = analytics_service.get_scatter_data(x_attr, y_attr)
                stats = analytics_service.calculate_correlation(x_attr, y_attr, method=method)
                thresholds = analytics_service.find_threshold_relationships(
                    dependent_var=y_attr,
                    independent_var=x_attr,
                    bins=bins,
                )

                label_x = ATTRIBUTE_LABELS.get(x_attr, x_attr)
                label_y = ATTRIBUTE_LABELS.get(y_attr, y_attr)

                # Scatter plot
                with chart_area:
                    if scatter.get('n', 0) == 0:
                        ui.label("Not enough data to plot a scatter yet.").classes("text-xs text-gray-500")
                    else:
                        scatter_df = pd.DataFrame({'x': scatter['x'], 'y': scatter['y']})
                        fig = px.scatter(
                            scatter_df,
                            x='x',
                            y='y',
                            labels={'x': label_x, 'y': label_y},
                            title=f"{label_x} vs {label_y}",
                        )
                        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                        ui.plotly(fig)

                # Correlation summary
                with chart_area:
                    corr = stats.get('correlation')
                    p_val = stats.get('p_value')
                    r_sq = stats.get('r_squared')
                    n = stats.get('n')
                    meta = stats.get('meta') or {}
                    summary_lines = [
                        f"Method: {meta.get('name', method.title())}",
                        f"r: {corr:.3f}" if corr is not None else "r: N/A",
                        f"p-value: {p_val:.4f}" if p_val is not None else "p-value: N/A",
                        f"r²: {r_sq:.3f}" if r_sq is not None else "r²: N/A",
                        f"Samples: {n}",
                    ]
                    ui.label("Correlation summary").classes("font-semibold text-sm mt-2")
                    ui.markdown("\n".join([f"- {line}" for line in summary_lines])).classes("text-xs")

                # Threshold analysis
                with chart_area:
                    bins_data = thresholds.get('bins') or []
                    if not bins_data:
                        ui.label("No threshold insights yet.").classes("text-xs text-gray-500")
                    else:
                        ui.label("Threshold analysis (Y avg per X bin)").classes("font-semibold text-sm mt-2")
                        for item in bins_data:
                            ui.label(f"{item['range']}: {item['dependent_avg']} (n={item['count']})").classes("text-xs")
                        best_max = thresholds.get('best_max')
                        best_min = thresholds.get('best_min')
                        if best_max:
                            ui.label(f"Highest average: {best_max['range']} → {best_max['dependent_avg']} (n={best_max['count']})").classes("text-xs text-green-600")
                        if best_min:
                            ui.label(f"Lowest average: {best_min['range']} → {best_min['dependent_avg']} (n={best_min['count']})").classes("text-xs text-red-600")

            x_select.on('update:model-value', lambda e: render_correlation())
            y_select.on('update:model-value', lambda e: render_correlation())
            method_select.on('update:model-value', lambda e: render_correlation())
            bin_slider.on('update:model-value', lambda e: render_correlation())

            render_correlation()


def _render_task_rankings(rankings_data=None):
    """Render task performance rankings.
    
    Args:
        rankings_data: Optional pre-fetched rankings data (for batching)
    """
    ui.separator()
    ui.label("Task Performance Rankings").classes("text-xl font-semibold mt-4")
    
    # Get rankings data if not provided
    if rankings_data is None:
        rankings_data = analytics_service.get_rankings_data(top_n=5, leaderboard_n=10)
    
    with ui.row().classes("gap-4 flex-wrap mt-2"):
        # Top tasks by relief
        top_relief = rankings_data['relief_ranking']
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Tasks by Relief").classes("font-bold text-md mb-2")
            if not top_relief:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in top_relief:
                    ui.label(f"{task['task_name']}: {task['metric_value']} (n={task['count']})").classes("text-sm")
        
        # Top tasks by stress efficiency
        top_efficiency = rankings_data['stress_efficiency_ranking']
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Tasks by Stress Efficiency").classes("font-bold text-md mb-2")
            if not top_efficiency:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in top_efficiency:
                    ui.label(f"{task['task_name']}: {task['metric_value']:.2f} (n={task['count']})").classes("text-sm")
        
        # Top tasks by behavioral score
        top_behavioral = rankings_data['behavioral_score_ranking']
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Tasks by Behavioral Score").classes("font-bold text-md mb-2")
            if not top_behavioral:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in top_behavioral:
                    ui.label(f"{task['task_name']}: {task['metric_value']} (n={task['count']})").classes("text-sm")
        
        # Lowest stress tasks
        low_stress = rankings_data['stress_level_ranking']
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Lowest Stress Tasks").classes("font-bold text-md mb-2")
            if not low_stress:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in low_stress:
                    ui.label(f"{task['task_name']}: {task['metric_value']} (n={task['count']})").classes("text-sm")


def _render_stress_efficiency_leaderboard(leaderboard=None):
    """Render stress efficiency leaderboard.
    
    Args:
        leaderboard: Optional pre-fetched leaderboard data (for batching)
    """
    ui.separator()
    ui.label("Stress Efficiency Leaderboard").classes("text-xl font-semibold mt-4")
    ui.label("Tasks that give you the most relief per unit of stress").classes("text-sm text-gray-500 mb-2")
    
    if leaderboard is None:
        leaderboard = analytics_service.get_stress_efficiency_leaderboard(top_n=10)
    
    if not leaderboard:
        ui.label("No data yet. Complete some tasks to see your stress efficiency leaders.").classes("text-xs text-gray-500")
        return
    
    with ui.card().classes("p-3 w-full"):
        # Simple table using cards for better compatibility
        with ui.column().classes("w-full gap-1"):
            # Header
            with ui.row().classes("w-full font-bold text-sm border-b pb-1"):
                ui.label("#").classes("w-8")
                ui.label("Task").classes("flex-1")
                ui.label("Efficiency").classes("w-24 text-right")
                ui.label("Relief").classes("w-20 text-right")
                ui.label("Stress").classes("w-20 text-right")
                ui.label("Count").classes("w-16 text-right")
            # Rows
            for i, task in enumerate(leaderboard):
                with ui.row().classes("w-full text-sm py-1 border-b border-gray-100"):
                    ui.label(str(i+1)).classes("w-8")
                    ui.label(task['task_name']).classes("flex-1")
                    ui.label(f"{task['stress_efficiency']:.2f}").classes("w-24 text-right")
                    ui.label(f"{task['avg_relief']:.1f}").classes("w-20 text-right")
                    ui.label(f"{task['avg_stress']:.1f}").classes("w-20 text-right")
                    ui.label(str(task['count'])).classes("w-16 text-right")


def build_emotional_flow_page():
    """Emotional Flow Analytics - tracks emotion changes and patterns."""
    ui.add_head_html("<style>.analytics-grid { gap: 1rem; }</style>")
    
    # Navigation
    with ui.row().classes("gap-2 mb-4"):
        ui.button("← Back to Analytics", on_click=lambda: ui.navigate.to('/analytics')).props("outlined")
        ui.label("Emotional Flow Analytics").classes("text-2xl font-bold")
    
    ui.label("Track how your emotions change from task start to completion, and discover patterns in your emotional responses.").classes(
        "text-gray-500 mb-4"
    )
    
    # Get emotional flow data
    flow_data = analytics_service.get_emotional_flow_data()
    
    # Summary metrics
    with ui.row().classes("gap-3 flex-wrap mb-4"):
        for title, value in [
            ("Avg Emotional Load", f"{flow_data.get('avg_emotional_load', 0):.1f}"),
            ("Avg Relief", f"{flow_data.get('avg_relief', 0):.1f}"),
            ("Emotional Spikes", flow_data.get('spike_count', 0)),
            ("Emotion-Relief Ratio", f"{flow_data.get('emotion_relief_ratio', 0):.2f}"),
        ]:
            with ui.card().classes("p-3 min-w-[150px]"):
                ui.label(title).classes("text-xs text-gray-500")
                ui.label(value).classes("text-xl font-bold")
    
    # Emotion transition chart (initialization → completion)
    _render_emotion_transitions(flow_data)
    
    # Emotional load vs relief scatter
    _render_emotional_load_vs_relief(flow_data)
    
    # Expected vs actual emotional load
    _render_expected_vs_actual_emotional(flow_data)
    
    # Emotion trends over time
    _render_emotion_trends(flow_data)
    
    # Emotional spikes analysis
    _render_emotional_spikes(flow_data)
    
    # Emotion correlations
    _render_emotion_correlations(flow_data)


def _render_emotion_transitions(flow_data):
    """Show how emotions change from initialization to completion."""
    with ui.card().classes("p-4 w-full mb-4"):
        ui.label("Emotion Transitions").classes("text-xl font-bold mb-2")
        ui.label("How your emotions change from task start to completion").classes("text-sm text-gray-500 mb-3")
        
        transitions = flow_data.get('transitions', [])
        if not transitions:
            ui.label("No emotion transition data yet. Complete tasks with emotion tracking to see patterns.").classes("text-xs text-gray-500")
            return
        
        # Create transition visualization
        # Group by emotion and show average initial vs final values
        emotion_data = {}
        for trans in transitions:
            emotion = trans.get('emotion')
            if not emotion:
                continue
            if emotion not in emotion_data:
                emotion_data[emotion] = {'initial': [], 'final': []}
            
            initial = trans.get('initial_value')
            final = trans.get('final_value')
            if initial is not None:
                emotion_data[emotion]['initial'].append(initial)
            if final is not None:
                emotion_data[emotion]['final'].append(final)
        
        # Calculate averages
        transition_df_data = []
        for emotion, values in emotion_data.items():
            avg_initial = sum(values['initial']) / len(values['initial']) if values['initial'] else 0
            avg_final = sum(values['final']) / len(values['final']) if values['final'] else 0
            transition_df_data.append({
                'emotion': emotion,
                'initial': avg_initial,
                'final': avg_final,
                'change': avg_final - avg_initial
            })
        
        if transition_df_data:
            df = pd.DataFrame(transition_df_data)
            df = df.sort_values('change', ascending=False)
            
            # Bar chart showing initial vs final
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df['emotion'],
                y=df['initial'],
                name='Initial (Start)',
                marker_color='#3498db'
            ))
            fig.add_trace(go.Bar(
                x=df['emotion'],
                y=df['final'],
                name='Final (Completion)',
                marker_color='#e74c3c'
            ))
            fig.update_layout(
                title="Average Emotion Intensity: Start vs Completion",
                xaxis_title="Emotion",
                yaxis_title="Intensity (0-100)",
                barmode='group',
                margin=dict(l=20, r=20, t=40, b=20)
            )
            ui.plotly(fig)
            
            # Show change summary
            with ui.row().classes("gap-3 flex-wrap mt-3"):
                increased = df[df['change'] > 5]
                decreased = df[df['change'] < -5]
                
                if not increased.empty:
                    with ui.card().classes("p-3 bg-red-50 border border-red-200"):
                        ui.label("Emotions That Increased").classes("text-xs font-semibold text-red-700 mb-1")
                        for _, row in increased.iterrows():
                            ui.label(f"{row['emotion']}: +{row['change']:.1f}").classes("text-xs text-red-600")
                
                if not decreased.empty:
                    with ui.card().classes("p-3 bg-green-50 border border-green-200"):
                        ui.label("Emotions That Decreased").classes("text-xs font-semibold text-green-700 mb-1")
                        for _, row in decreased.iterrows():
                            ui.label(f"{row['emotion']}: {row['change']:.1f}").classes("text-xs text-green-600")


def _render_emotional_load_vs_relief(flow_data):
    """Scatter plot of emotional load vs relief."""
    with ui.card().classes("p-4 w-full mb-4"):
        ui.label("Emotional Load vs Relief").classes("text-xl font-bold mb-2")
        ui.label("How emotional intensity relates to relief after completion").classes("text-sm text-gray-500 mb-3")
        
        scatter_data = flow_data.get('load_relief_scatter', {})
        if not scatter_data or not scatter_data.get('x'):
            ui.label("No data yet. Complete tasks to see emotional load vs relief patterns.").classes("text-xs text-gray-500")
            return
        
        df = pd.DataFrame({
            'emotional_load': scatter_data['x'],
            'relief': scatter_data['y'],
            'task_name': scatter_data.get('task_names', [])
        })
        
        fig = px.scatter(
            df,
            x='emotional_load',
            y='relief',
            hover_data=['task_name'],
            labels={'emotional_load': 'Emotional Load (0-100)', 'relief': 'Relief (0-100)'},
            title="Emotional Load vs Relief"
        )
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        ui.plotly(fig)
        
        # Add interpretation
        with ui.card().classes("p-3 mt-3 bg-blue-50"):
            ui.label("Interpretation").classes("text-xs font-semibold text-blue-700 mb-1")
            ui.label("• High emotional load + High relief = Meaningful accomplishment despite difficulty").classes("text-xs text-blue-600")
            ui.label("• High emotional load + Low relief = Tasks that were stressful but not rewarding").classes("text-xs text-blue-600")
            ui.label("• Low emotional load + High relief = Easy wins that feel good").classes("text-xs text-blue-600")


def _render_expected_vs_actual_emotional(flow_data):
    """Compare expected vs actual emotional load."""
    with ui.card().classes("p-4 w-full mb-4"):
        ui.label("Expected vs Actual Emotional Load").classes("text-xl font-bold mb-2")
        ui.label("How well you predict emotional intensity").classes("text-sm text-gray-500 mb-3")
        
        comparison_data = flow_data.get('expected_actual_comparison', {})
        if not comparison_data or not comparison_data.get('expected'):
            ui.label("No comparison data yet.").classes("text-xs text-gray-500")
            return
        
        df = pd.DataFrame({
            'expected': comparison_data['expected'],
            'actual': comparison_data['actual'],
            'task_name': comparison_data.get('task_names', [])
        })
        
        # Scatter plot
        fig = px.scatter(
            df,
            x='expected',
            y='actual',
            hover_data=['task_name'],
            labels={'expected': 'Expected Emotional Load', 'actual': 'Actual Emotional Load'},
            title="Expected vs Actual Emotional Load"
        )
        # Add diagonal line (perfect prediction)
        import plotly.graph_objects as go
        fig.add_trace(go.Scatter(
            x=[0, 100],
            y=[0, 100],
            mode='lines',
            name='Perfect Prediction',
            line=dict(dash='dash', color='gray')
        ))
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        ui.plotly(fig)
        
        # Calculate prediction accuracy
        if len(df) > 0:
            df['difference'] = abs(df['actual'] - df['expected'])
            avg_error = df['difference'].mean()
            
            with ui.row().classes("gap-3 mt-3"):
                with ui.card().classes("p-3"):
                    ui.label("Average Prediction Error").classes("text-xs text-gray-500")
                    ui.label(f"{avg_error:.1f} points").classes("text-lg font-bold")
                
                spikes = len(df[df['actual'] > df['expected'] + 30])
                with ui.card().classes("p-3"):
                    ui.label("Unexpected Emotional Spikes").classes("text-xs text-gray-500")
                    ui.label(f"{spikes} tasks").classes("text-lg font-bold")


def _render_emotion_trends(flow_data):
    """Time series of specific emotions."""
    with ui.card().classes("p-4 w-full mb-4"):
        ui.label("Emotion Trends Over Time").classes("text-xl font-bold mb-2")
        ui.label("Track how specific emotions evolve across tasks").classes("text-sm text-gray-500 mb-3")
        
        trends = flow_data.get('emotion_trends', {})
        if not trends:
            ui.label("No emotion trend data yet.").classes("text-xs text-gray-500")
            return
        
        # Get available emotions
        available_emotions = list(trends.keys())
        if not available_emotions:
            ui.label("No emotion data available.").classes("text-xs text-gray-500")
            return
        
        # Emotion selector
        emotion_select = ui.select(
            options={emotion: emotion.title() for emotion in available_emotions},
            value=available_emotions[0] if available_emotions else None,
            label="Select Emotion"
        ).props("dense outlined").classes("mb-3")
        
        chart_area = ui.column().classes("mt-3")
        
        def update_trend_chart():
            chart_area.clear()
            selected = emotion_select.value
            if not selected or selected not in trends:
                return
            
            trend_data = trends[selected]
            dates = trend_data.get('dates', [])
            values = trend_data.get('values', [])
            
            if not dates or not values:
                with chart_area:
                    ui.label("No trend data for this emotion.").classes("text-xs text-gray-500")
                return
            
            df = pd.DataFrame({
                'date': pd.to_datetime(dates),
                'intensity': values
            })
            df = df.sort_values('date')
            
            fig = px.line(
                df,
                x='date',
                y='intensity',
                markers=True,
                labels={'intensity': 'Intensity (0-100)', 'date': 'Date'},
                title=f"{selected.title()} Over Time"
            )
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
            with chart_area:
                ui.plotly(fig)
        
        emotion_select.on('update:model-value', lambda e: update_trend_chart())
        update_trend_chart()


def _render_emotional_spikes(flow_data):
    """Show tasks with unexpected emotional spikes."""
    with ui.card().classes("p-4 w-full mb-4"):
        ui.label("Emotional Spikes").classes("text-xl font-bold mb-2")
        ui.label("Tasks where emotional load was unexpectedly high").classes("text-sm text-gray-500 mb-3")
        
        spikes = flow_data.get('spikes', [])
        if not spikes:
            ui.label("No emotional spikes detected yet.").classes("text-xs text-gray-500")
            return
        
        # Show top spikes
        with ui.column().classes("gap-2"):
            for spike in spikes[:10]:  # Top 10
                with ui.card().classes("p-3 border-l-4 border-red-400"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(spike.get('task_name', 'Unknown Task')).classes("font-semibold")
                        ui.label(f"Expected: {spike.get('expected', 0):.0f}").classes("text-xs text-gray-500")
                        ui.label(f"Actual: {spike.get('actual', 0):.0f}").classes("text-xs text-red-600 font-bold")
                        ui.label(f"Spike: +{spike.get('spike_amount', 0):.0f}").classes("text-xs text-red-700")
                    if spike.get('completed_at'):
                        ui.label(f"Completed: {spike['completed_at']}").classes("text-xs text-gray-400")


def _render_emotion_correlations(flow_data):
    """Show how emotions correlate with other metrics."""
    with ui.card().classes("p-4 w-full mb-4"):
        ui.label("Emotion Correlations").classes("text-xl font-bold mb-2")
        ui.label("How emotions relate to relief, difficulty, and other metrics").classes("text-sm text-gray-500 mb-3")
        
        correlations = flow_data.get('correlations', {})
        if not correlations:
            ui.label("No correlation data yet. More data needed for meaningful correlations.").classes("text-xs text-gray-500")
            return
        
        # Display correlation info
        with ui.row().classes("gap-3 flex-wrap"):
            for emotion, corr_data in correlations.items():
                with ui.card().classes("p-3 min-w-[200px]"):
                    ui.label(emotion.title()).classes("text-sm font-semibold mb-2")
                    for metric, value in corr_data.items():
                        ui.label(f"{metric}: {value:.2f}").classes("text-xs")

