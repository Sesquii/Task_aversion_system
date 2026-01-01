"""Productivity hours goal tracking system UI.

Productivity Hours Goal Tracking system for tracking weekly productivity hours vs goals.
Access at /productivity-hours-goal-tracking
"""
from nicegui import ui
from backend.user_state import UserStateManager
from backend.productivity_tracker import ProductivityTracker
from datetime import date, timedelta
import plotly.graph_objects as go
import plotly.express as px

user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"
tracker = ProductivityTracker()


@ui.page("/goals/productivity-hours")
def productivity_goals_page():
    """Productivity hours goal tracking page."""
    
    ui.label("Productivity Hours Goal Tracking").classes("text-3xl font-bold mb-4")
    ui.label("Track weekly productivity hours vs goals with rolling 7-day or Monday-based week calculations.").classes("text-gray-600 mb-6")
    
    # Goal Settings Card
    with ui.card().classes("w-full max-w-7xl p-4 mb-4"):
        ui.label("Goal Settings").classes("text-xl font-semibold mb-4")
        
        # Load current settings
        goal_settings = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
        current_goal = goal_settings.get('goal_hours_per_week', 40.0)
        current_starting = goal_settings.get('starting_hours_per_week')
        init_method = goal_settings.get('initialization_method')
        
        with ui.row().classes("w-full gap-4 items-end"):
            goal_input = ui.number(
                label="Goal Hours Per Week",
                value=float(current_goal),
                min=0,
                max=100,
                step=0.5,
                format="%.1f"
            ).props("dense outlined").classes("flex-1")
            
            starting_input = ui.number(
                label="Starting Hours Per Week (baseline)",
                value=float(current_starting) if current_starting else None,
                min=0,
                max=100,
                step=0.5,
                format="%.1f"
            ).props("dense outlined").classes("flex-1")
            
            def save_goals():
                new_goal = float(goal_input.value or 40.0)
                new_starting = float(starting_input.value) if starting_input.value else None
                
                settings = {
                    'goal_hours_per_week': new_goal,
                    'starting_hours_per_week': new_starting,
                    'initialization_method': init_method or 'manual'
                }
                user_state.set_productivity_goal_settings(DEFAULT_USER_ID, settings)
                ui.notify("Goals saved!", color="positive")
                # Refresh the page to update displays
                ui.navigate.to("/goals/productivity-hours")
            
            ui.button("Save Goals", on_click=save_goals).classes("bg-blue-500 text-white")
        
        if init_method:
            ui.label(f"Initialization method: {init_method}").classes("text-sm text-gray-600 mt-2")
        
        # Auto-estimate button
        def estimate_starting():
            estimated = tracker.estimate_starting_hours_auto(DEFAULT_USER_ID, factor=10.0)
            if estimated:
                starting_input.set_value(estimated)
                ui.notify(f"Auto-estimated starting hours: {estimated} hours/week", color="info")
            else:
                ui.notify("Not enough data for auto-estimation. Need at least one day with completed productive tasks.", color="warning")
        
        ui.button("Auto-Estimate Starting Hours (First Day × 10)", on_click=estimate_starting).classes("mt-2")
    
    # Current Week Comparison
    with ui.card().classes("w-full max-w-7xl p-4 mb-4"):
        ui.label("Current Week Performance").classes("text-xl font-semibold mb-4")
        
        # Get week calculation mode setting
        goal_settings = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
        week_calculation_mode = goal_settings.get('week_calculation_mode', 'rolling')
        use_rolling = (week_calculation_mode == 'rolling')
        
        # Calculation mode selector
        with ui.row().classes("mb-4 gap-4 items-center"):
            ui.label("Calculation Mode:").classes("text-sm font-semibold")
            mode_select = ui.select(
                options={
                    'rolling': 'Rolling 7-Day (Last 7 Days)',
                    'monday_based': 'Monday-Based Week (with Pace)'
                },
                value=week_calculation_mode,
                label="Mode"
            ).props("dense outlined").classes("min-w-[250px]")
            
            def update_mode():
                new_mode = mode_select.value
                current_settings = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
                current_settings['week_calculation_mode'] = new_mode
                user_state.set_productivity_goal_settings(DEFAULT_USER_ID, current_settings)
                ui.navigate.to("/goals/productivity-hours")
            
            mode_select.on('update:model-value', lambda e: update_mode())
        
        comparison = tracker.compare_to_goal(DEFAULT_USER_ID, use_rolling=use_rolling)
        weekly_data = tracker.get_current_week_performance(DEFAULT_USER_ID, use_rolling=use_rolling)
        
        actual_hours = comparison.get('actual_hours', 0.0)
        goal_hours = comparison.get('goal_hours', 40.0)
        percentage = comparison.get('percentage_of_goal', 0.0)
        status = comparison.get('status', 'no_data')
        
        # Calculate pace for Monday-based mode
        pace_data = None
        if not use_rolling:
            pace_data = tracker.calculate_monday_week_pace(DEFAULT_USER_ID, goal_hours)
        
        # Calculate productivity points target
        points_target = tracker.calculate_productivity_points_target(DEFAULT_USER_ID, goal_hours)
        target_points = points_target.get('target_points', 0.0)
        avg_score_per_hour = points_target.get('avg_score_per_hour', 0.0)
        confidence = points_target.get('confidence', 'low')
        
        with ui.row().classes("w-full gap-6 items-center"):
            with ui.column().classes("flex-1"):
                ui.label("Actual Hours").classes("text-sm text-gray-600")
                ui.label(f"{actual_hours:.1f}").classes("text-3xl font-bold")
                if use_rolling:
                    ui.label("(Rolling 7-Day)").classes("text-xs text-gray-500")
                else:
                    ui.label("(This Week)").classes("text-xs text-gray-500")
            
            with ui.column().classes("flex-1"):
                ui.label("Goal Hours").classes("text-sm text-gray-600")
                ui.label(f"{goal_hours:.1f}").classes("text-3xl font-bold text-blue-600")
                if not use_rolling and pace_data:
                    projected = pace_data.get('projected_hours', 0.0)
                    ui.label(f"Projected: {projected:.1f}h").classes("text-xs text-gray-500")
            
            with ui.column().classes("flex-1"):
                ui.label("Percentage of Goal").classes("text-sm text-gray-600")
                color_class = "text-green-600" if percentage >= 100 else "text-yellow-600" if percentage >= 85 else "text-red-600"
                ui.label(f"{percentage:.1f}%").classes(f"text-3xl font-bold {color_class}")
        
        # Pace information for Monday-based mode
        if not use_rolling and pace_data:
            ui.separator().classes("my-4")
            ui.label("Weekly Pace (Monday-Based)").classes("text-lg font-semibold mb-2")
            with ui.row().classes("w-full gap-6 items-center"):
                with ui.column().classes("flex-1"):
                    ui.label("Days Elapsed").classes("text-sm text-gray-600")
                    ui.label(f"{pace_data.get('days_elapsed', 0)} / 7").classes("text-xl font-bold")
                with ui.column().classes("flex-1"):
                    ui.label("Current Pace").classes("text-sm text-gray-600")
                    pace_hours = pace_data.get('pace_hours_per_day', 0.0)
                    goal_hours_per_day = pace_data.get('goal_hours_per_day', 0.0)
                    ui.label(f"{pace_hours:.1f} h/day").classes("text-xl font-bold")
                    ui.label(f"(Goal: {goal_hours_per_day:.1f} h/day)").classes("text-xs text-gray-500")
                with ui.column().classes("flex-1"):
                    ui.label("Projected Total").classes("text-sm text-gray-600")
                    projected = pace_data.get('projected_hours', 0.0)
                    on_pace = pace_data.get('on_pace', False)
                    pace_color = "text-green-600" if on_pace else "text-yellow-600"
                    ui.label(f"{projected:.1f}h").classes(f"text-xl font-bold {pace_color}")
                    ui.label("(if pace continues)").classes("text-xs text-gray-500")
        
        # Progress bar
        progress_value = min(percentage / 100.0, 1.0) if percentage > 0 else 0.0
        progress_color = "green" if percentage >= 100 else "yellow" if percentage >= 85 else "red"
        ui.linear_progress(value=progress_value).props(f"color={progress_color}").classes("mt-4 mb-2")
        
        # Status indicator
        status_labels = {
            'above': "Above Goal",
            'on_track': "On Track",
            'below': "Below Goal",
            'no_goal': "No Goal Set",
            'no_data': "No Data Available"
        }
        status_colors = {
            'above': "text-green-600",
            'on_track': "text-blue-600",
            'below': "text-yellow-600",
            'no_goal': "text-gray-500",
            'no_data': "text-gray-400"
        }
        ui.label(f"Status: {status_labels.get(status, status)}").classes(f"text-lg font-semibold {status_colors.get(status, 'text-gray-600')}")
        
        # Productivity Points Target
        ui.separator().classes("my-4")
        ui.label("Productivity Points Target").classes("text-lg font-semibold mb-2")
        with ui.row().classes("w-full gap-6 items-center"):
            with ui.column().classes("flex-1"):
                ui.label("Target Points").classes("text-sm text-gray-600")
                ui.label(f"{target_points:.1f}").classes("text-2xl font-bold text-purple-600")
            with ui.column().classes("flex-1"):
                ui.label("Avg Score/Hour").classes("text-sm text-gray-600")
                ui.label(f"{avg_score_per_hour:.2f}").classes("text-xl font-semibold")
            with ui.column().classes("flex-1"):
                ui.label("Confidence").classes("text-sm text-gray-600")
                confidence_colors = {'high': 'text-green-600', 'medium': 'text-yellow-600', 'low': 'text-gray-500'}
                ui.label(confidence.capitalize()).classes(f"text-lg font-semibold {confidence_colors.get(confidence, 'text-gray-600')}")
        
        ui.label(
            f"Based on your recent performance ({points_target.get('weeks_used', 0)} weeks), "
            f"you average {avg_score_per_hour:.2f} productivity points per hour. "
            f"With a goal of {goal_hours:.1f} hours/week, your target is {target_points:.1f} points."
        ).classes("text-sm text-gray-600 mt-2")
        
        # Daily breakdown
        if weekly_data.get('daily_averages'):
            ui.label("Daily Breakdown").classes("text-lg font-semibold mt-4 mb-2")
            with ui.row().classes("w-full gap-2 flex-wrap"):
                for day_data in weekly_data['daily_averages']:
                    with ui.card().classes("p-2 bg-gray-50"):
                        ui.label(day_data['date']).classes("text-xs text-gray-600")
                        ui.label(f"{day_data['hours']:.1f}h").classes("text-sm font-semibold")
    
    # Record current week snapshot if needed
    tracker.get_or_record_current_week(DEFAULT_USER_ID)
    
    # Historical Trends Section
    with ui.card().classes("w-full max-w-7xl p-4 mb-4"):
        ui.label("Historical Trends (Daily)").classes("text-xl font-semibold mb-4")
        
        # Get daily productivity data (last 90 days)
        daily_data = tracker.get_daily_productivity_data(DEFAULT_USER_ID, days=90)
        
        # Get goal hours for reference line
        goal_settings = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
        goal_hours_per_week = goal_settings.get('goal_hours_per_week', 40.0)
        goal_hours_per_day = goal_hours_per_week / 7.0
        
        if daily_data:
            # Parse dates and prepare data
            dates = [date.fromisoformat(d['date']) for d in daily_data]
            hours_values = [d['hours'] for d in daily_data]
            date_labels = [d.strftime('%m/%d') for d in dates]
            
            # Hours Trend Chart (Daily)
            ui.label("Hours Trend (Daily - Last 90 Days)").classes("text-lg font-semibold mb-2")
            fig_hours = go.Figure()
            
            # Add goal line (daily goal hours)
            fig_hours.add_trace(go.Scatter(
                x=date_labels,
                y=[goal_hours_per_day] * len(date_labels),
                mode='lines',
                name='Daily Goal',
                line=dict(color='blue', dash='dash', width=2),
                marker=dict(size=4)
            ))
            
            fig_hours.add_trace(go.Scatter(
                x=date_labels,
                y=hours_values,
                mode='lines+markers',
                name='Actual Hours',
                line=dict(color='green', width=1.5),
                marker=dict(size=4)
            ))
            
            fig_hours.update_layout(
                title="Daily Productivity Hours",
                xaxis_title="Date",
                yaxis_title="Hours",
                hovermode='x unified',
                height=300,
                showlegend=True,
                font=dict(size=10),
                title_font=dict(size=12),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                legend=dict(font=dict(size=9))
            )
            
            ui.plotly(fig_hours).classes("w-full mb-6")
            
            # Productivity Metrics Trend Chart (Daily)
            ui.label("Productivity Metrics Trend (Daily - Last 90 Days)").classes("text-lg font-semibold mb-2")
            
            # Calculate 7-day rolling average for smoother trend
            rolling_avg_hours = []
            window_size = 7
            for i in range(len(hours_values)):
                start_idx = max(0, i - window_size + 1)
                window_values = hours_values[start_idx:i+1]
                if window_values:
                    rolling_avg_hours.append(sum(window_values) / len(window_values))
                else:
                    rolling_avg_hours.append(0.0)
            
            fig_metrics = go.Figure()
            
            # Add goal line
            fig_metrics.add_trace(go.Scatter(
                x=date_labels,
                y=[goal_hours_per_day] * len(date_labels),
                mode='lines',
                name='Daily Goal',
                line=dict(color='blue', dash='dash', width=2),
                marker=dict(size=4)
            ))
            
            # Add actual hours
            fig_metrics.add_trace(go.Scatter(
                x=date_labels,
                y=hours_values,
                mode='markers',
                name='Daily Hours',
                marker=dict(color='green', size=4, opacity=0.6),
                showlegend=True
            ))
            
            # Add 7-day rolling average
            fig_metrics.add_trace(go.Scatter(
                x=date_labels,
                y=rolling_avg_hours,
                mode='lines',
                name='7-Day Avg',
                line=dict(color='orange', width=2),
                marker=dict(size=4)
            ))
            
            fig_metrics.update_layout(
                title="Daily Productivity Hours with 7-Day Rolling Average",
                xaxis_title="Date",
                yaxis_title="Hours",
                hovermode='x unified',
                height=350,
                showlegend=True,
                margin=dict(l=60, r=20, t=50, b=40),
                font=dict(size=10),
                title_font=dict(size=12),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                legend=dict(font=dict(size=9))
            )
            
            ui.plotly(fig_metrics).classes("w-full")
        else:
            ui.label("No daily data yet. Data will appear as you complete productive tasks.").classes("text-gray-500")
    
    # Information Card
    with ui.card().classes("w-full max-w-7xl p-4 mb-4 bg-blue-50"):
        ui.label("How It Works").classes("text-lg font-semibold mb-2")
        ui.label(
            "• Goal Hours Per Week: Your target for weekly productive time (Work + Self Care tasks)\n"
            "• Starting Hours: Your baseline estimate (can be auto-estimated from first day × 10)\n"
            "• The system compares your actual tracked hours to your goal\n"
            "• Productivity scores are adjusted based on goal achievement (experimental)"
        ).classes("text-sm whitespace-pre-line")
    
    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4")
