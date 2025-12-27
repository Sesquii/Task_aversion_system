"""Experimental productivity hours goal tracking system UI.

This is an experimental implementation of the productivity hours goal tracking system.
Access at /experimental/productivity-hours-goal-tracking-system
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


@ui.page("/experimental/productivity-hours-goal-tracking-system")
def productivity_goals_experimental_page():
    """Experimental productivity hours goal tracking page."""
    
    ui.label("Productivity Hours Goal Tracking (Experimental)").classes("text-3xl font-bold mb-4")
    ui.label("This is an experimental feature for tracking weekly productivity hours vs goals.").classes("text-gray-600 mb-6")
    
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
                ui.navigate.to("/experimental/productivity-hours-goal-tracking-system")
            
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
        
        comparison = tracker.compare_to_goal(DEFAULT_USER_ID)
        weekly_data = tracker.calculate_weekly_productivity_hours(DEFAULT_USER_ID)
        
        actual_hours = comparison.get('actual_hours', 0.0)
        goal_hours = comparison.get('goal_hours', 40.0)
        percentage = comparison.get('percentage_of_goal', 0.0)
        status = comparison.get('status', 'no_data')
        
        # Calculate productivity points target
        points_target = tracker.calculate_productivity_points_target(DEFAULT_USER_ID, goal_hours)
        target_points = points_target.get('target_points', 0.0)
        avg_score_per_hour = points_target.get('avg_score_per_hour', 0.0)
        confidence = points_target.get('confidence', 'low')
        
        with ui.row().classes("w-full gap-6 items-center"):
            with ui.column().classes("flex-1"):
                ui.label("Actual Hours").classes("text-sm text-gray-600")
                ui.label(f"{actual_hours:.1f}").classes("text-3xl font-bold")
            
            with ui.column().classes("flex-1"):
                ui.label("Goal Hours").classes("text-sm text-gray-600")
                ui.label(f"{goal_hours:.1f}").classes("text-3xl font-bold text-blue-600")
            
            with ui.column().classes("flex-1"):
                ui.label("Percentage of Goal").classes("text-sm text-gray-600")
                color_class = "text-green-600" if percentage >= 100 else "text-yellow-600" if percentage >= 85 else "text-red-600"
                ui.label(f"{percentage:.1f}%").classes(f"text-3xl font-bold {color_class}")
        
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
        ui.label("Historical Trends").classes("text-xl font-semibold mb-4")
        
        # Get historical data (last 12 weeks)
        history = tracker.get_productivity_history(DEFAULT_USER_ID, weeks=12)
        
        if history:
            # Parse dates and prepare data
            history_data = []
            for entry in history:
                    try:
                        week_start = date.fromisoformat(entry['week_start'])
                        history_data.append({
                            'week_start': week_start,
                            'week_label': week_start.strftime('%m/%d'),
                            'goal_hours': entry.get('goal_hours', entry.get('goal_hours_per_week', 0.0)),
                            'actual_hours': entry.get('actual_hours', 0.0),
                            'productivity_score': entry.get('productivity_score', 0.0),
                            'productivity_points': entry.get('productivity_points', 0.0)
                        })
                    except (ValueError, KeyError):
                        continue
            
            if history_data:
                # Limit to last 12 weeks for display
                history_data = sorted(history_data, key=lambda x: x['week_start'], reverse=True)[:12]
                history_data.reverse()  # Oldest to newest for chart
                
                # Hours Trend Chart
                ui.label("Hours Trend (Last 12 Weeks)").classes("text-lg font-semibold mb-2")
                fig_hours = go.Figure()
                
                goal_values = [w['goal_hours'] for w in history_data]
                actual_values = [w['actual_hours'] for w in history_data]
                week_labels = [w['week_label'] for w in history_data]
                
                fig_hours.add_trace(go.Scatter(
                    x=week_labels,
                    y=goal_values,
                    mode='lines+markers',
                    name='Goal Hours',
                    line=dict(color='blue', dash='dash', width=2),
                    marker=dict(size=6)
                ))
                
                fig_hours.add_trace(go.Scatter(
                    x=week_labels,
                    y=actual_values,
                    mode='lines+markers',
                    name='Actual Hours',
                    line=dict(color='green', width=2),
                    marker=dict(size=6)
                ))
                
                fig_hours.update_layout(
                    title="Weekly Productivity Hours",
                    xaxis_title="Week Starting",
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
                
                # Configurable Productivity Metrics Chart
                ui.label("Productivity Metrics Trend (Last 12 Weeks)").classes("text-lg font-semibold mb-2")
                
                # Chart view selector
                with ui.row().classes("mb-4 gap-4 items-center"):
                    ui.label("View:").classes("text-sm font-semibold")
                    view_select = ui.select(
                        options={
                            'points': 'Productivity Points',
                            'score': 'Productivity Score',
                            'hours': 'Hours',
                            'normalized': 'All 3 (Normalized to Goal)'
                        },
                        value='points',
                        label="Metric View"
                    ).props("dense outlined").classes("min-w-[250px]")
                
                # Chart container
                chart_area = ui.column().classes("w-full")
                
                def update_metrics_chart():
                    """Update the metrics chart based on selected view."""
                    chart_area.clear()
                    view = view_select.value or 'points'
                    
                    # Get average goal hours for normalization (use first non-zero goal, or 40 as default)
                    avg_goal_hours = 40.0
                    if history_data:
                        goal_values = [w['goal_hours'] for w in history_data if w['goal_hours'] > 0]
                        if goal_values:
                            avg_goal_hours = sum(goal_values) / len(goal_values)
                    
                    # Get average score/points for normalization (calculate from non-zero values)
                    avg_score = 1.0
                    avg_points = 1.0
                    if history_data:
                        score_values = [w['productivity_score'] for w in history_data if w['productivity_score'] > 0]
                        points_values = [w['productivity_points'] for w in history_data if w['productivity_points'] > 0]
                        if score_values:
                            avg_score = sum(score_values) / len(score_values)
                        if points_values:
                            avg_points = sum(points_values) / len(points_values)
                    
                    fig = go.Figure()
                    
                    if view == 'points':
                        points_values = [w['productivity_points'] for w in history_data]
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=points_values,
                            mode='lines+markers',
                            name='Productivity Points',
                            line=dict(color='orange', width=2),
                            marker=dict(size=6)
                        ))
                        fig.update_layout(
                            title="Weekly Productivity Points",
                            yaxis_title="Points",
                            font=dict(size=10),
                            title_font=dict(size=12),
                            xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            legend=dict(font=dict(size=9))
                        )
                        
                    elif view == 'score':
                        score_values = [w['productivity_score'] for w in history_data]
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=score_values,
                            mode='lines+markers',
                            name='Productivity Score',
                            line=dict(color='purple', width=2),
                            marker=dict(size=6)
                        ))
                        fig.update_layout(
                            title="Weekly Productivity Score",
                            yaxis_title="Score",
                            font=dict(size=10),
                            title_font=dict(size=12),
                            xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            legend=dict(font=dict(size=9))
                        )
                        
                    elif view == 'hours':
                        actual_values = [w['actual_hours'] for w in history_data]
                        goal_values = [w['goal_hours'] for w in history_data]
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=goal_values,
                            mode='lines+markers',
                            name='Goal Hours',
                            line=dict(color='blue', dash='dash', width=2),
                            marker=dict(size=6)
                        ))
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=actual_values,
                            mode='lines+markers',
                            name='Actual Hours',
                            line=dict(color='green', width=2),
                            marker=dict(size=6)
                        ))
                        fig.update_layout(
                            title="Weekly Productivity Hours",
                            yaxis_title="Hours",
                            font=dict(size=10),
                            title_font=dict(size=12),
                            xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            legend=dict(font=dict(size=9))
                        )
                        
                    elif view == 'normalized':
                        # Normalize all three metrics to their respective goals/averages
                        # Hours normalized to goal hours, Score and Points normalized to their averages
                        normalized_hours = []
                        normalized_scores = []
                        normalized_points = []
                        
                        for w in history_data:
                            goal_h = w['goal_hours'] if w['goal_hours'] > 0 else avg_goal_hours
                            normalized_hours.append(w['actual_hours'] / goal_h if goal_h > 0 else 0)
                            
                            avg_s = avg_score if avg_score > 0 else 1.0
                            normalized_scores.append(w['productivity_score'] / avg_s if avg_s > 0 else 0)
                            
                            avg_p = avg_points if avg_points > 0 else 1.0
                            normalized_points.append(w['productivity_points'] / avg_p if avg_p > 0 else 0)
                        
                        # Add goal line at 1.0 (100%)
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=[1.0] * len(week_labels),
                            mode='lines',
                            name='Goal (100%)',
                            line=dict(color='gray', dash='dash', width=1),
                            showlegend=True
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=normalized_hours,
                            mode='lines+markers',
                            name='Hours (normalized)',
                            line=dict(color='green', width=2),
                            marker=dict(size=6)
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=normalized_scores,
                            mode='lines+markers',
                            name='Score (normalized)',
                            line=dict(color='purple', width=2),
                            marker=dict(size=6)
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=week_labels,
                            y=normalized_points,
                            mode='lines+markers',
                            name='Points (normalized)',
                            line=dict(color='orange', width=2),
                            marker=dict(size=6)
                        ))
                        
                        fig.update_layout(
                            title="All Metrics Normalized to Goal/Average",
                            yaxis_title="Ratio (1.0 = Goal/Average)",
                            font=dict(size=10),
                            title_font=dict(size=12),
                            xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                            legend=dict(font=dict(size=9))
                        )
                    
                    # Common layout settings
                    fig.update_layout(
                        xaxis_title="Week Starting",
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
                    
                    with chart_area:
                        ui.plotly(fig).classes("w-full")
                
                # Set up event handler for view selector
                view_select.on('update:model-value', lambda e: update_metrics_chart())
                
                # Initial render
                update_metrics_chart()
            else:
                ui.label("No valid historical data available.").classes("text-gray-500")
        else:
            ui.label("No historical data yet. Historical tracking will begin after you complete tasks this week.").classes("text-gray-500")
    
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
