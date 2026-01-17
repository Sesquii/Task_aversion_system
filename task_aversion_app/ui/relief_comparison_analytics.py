"""
Relief Comparison Analytics Module

This module provides detailed analysis comparing expected relief, actual relief, and net relief
to help users understand their prediction accuracy and relief patterns.
"""

from nicegui import ui
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from backend.analytics import Analytics
from backend.security_utils import escape_for_display
from ui.error_reporting import handle_error_with_ui

analytics_service = Analytics()


def register_relief_comparison_page():
    """Register the relief comparison analytics page."""
    # Page is already registered in analytics_page.py to avoid duplicate registration
    pass


def build_relief_comparison_page():
    """Build the relief comparison analytics page."""
    from backend.auth import get_current_user
    
    # Get current user for data isolation
    current_user_id = get_current_user()
    if current_user_id is None:
        ui.navigate.to('/login')
        return
    
    ui.page_title('Relief Comparison Analytics')
    
    with ui.header().classes("bg-blue-600 text-white"):
        ui.label("Relief Comparison Analytics").classes("text-2xl font-bold")
        ui.label("Compare expected vs actual relief to understand prediction accuracy and patterns").classes("text-sm")
    
    with ui.column().classes("w-full p-4 gap-4"):
        # Get data
        try:
            data = get_relief_comparison_data(user_id=current_user_id)
        except Exception as e:
            handle_error_with_ui(
                "load relief comparison data",
                e,
                user_id=current_user_id
            )
            data = {'total_tasks': 0}
        
        if not data or data['total_tasks'] == 0:
            with ui.card().classes("p-4"):
                ui.label("No relief data available yet.").classes("text-gray-500")
                ui.label("Complete some tasks with both expected and actual relief values to see comparisons.").classes("text-sm text-gray-400 mt-2")
            return
        
        # Summary statistics
        _render_summary_statistics(data)
        
        # Comparison charts
        _render_comparison_charts(data)
        
        # Pattern analysis
        _render_pattern_analysis(data)
        
        # Task-level details
        _render_task_details(data)


def get_relief_comparison_data(days: int = 90, user_id: Optional[int] = None) -> Dict:
    """Get relief comparison data from analytics service."""
    from backend.auth import get_current_user
    
    # Get user_id if not provided
    if user_id is None:
        user_id = get_current_user()
    
    df = analytics_service._load_instances(user_id=user_id)
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
    
    # Extract expected and actual relief
    def _get_expected_relief(row):
        try:
            predicted_dict = row.get('predicted_dict', {})
            if isinstance(predicted_dict, dict):
                return predicted_dict.get('expected_relief', None)
        except (KeyError, TypeError):
            pass
        return None
    
    def _get_actual_relief(row):
        try:
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return actual_dict.get('actual_relief', None)
        except (KeyError, TypeError):
            pass
        # Fallback to relief_score column
        return row.get('relief_score')
    
    completed['expected_relief'] = completed.apply(_get_expected_relief, axis=1)
    completed['actual_relief'] = completed.apply(_get_actual_relief, axis=1)
    
    # Convert to numeric
    completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
    completed['actual_relief'] = pd.to_numeric(completed['actual_relief'], errors='coerce')
    
    # Filter to rows with both expected and actual relief
    has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
    relief_data = completed[has_both].copy()
    
    if relief_data.empty:
        return {'total_tasks': 0}
    
    # Calculate net relief
    relief_data['net_relief'] = relief_data['actual_relief'] - relief_data['expected_relief']
    
    # Calculate emotional variables (factors, not standalone scores)
    relief_data['serendipity_factor'] = relief_data['net_relief'].apply(
        lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0
    )
    relief_data['disappointment_factor'] = relief_data['net_relief'].apply(
        lambda x: max(0.0, -float(x)) if pd.notna(x) else 0.0
    )
    
    # Get task names if available
    from backend.task_manager import TaskManager
    task_manager = TaskManager()
    tasks_df = task_manager.get_all(user_id=user_id)
    
    if not tasks_df.empty and 'task_name' in tasks_df.columns:
        relief_data = relief_data.merge(
            tasks_df[['task_id', 'task_name']],
            on='task_id',
            how='left'
        )
        relief_data['task_name'] = relief_data['task_name'].fillna('Unknown Task')
    else:
        relief_data['task_name'] = 'Unknown Task'
    
    # Calculate statistics
    stats = {
        'total_tasks': len(relief_data),
        'avg_expected': float(relief_data['expected_relief'].mean()),
        'avg_actual': float(relief_data['actual_relief'].mean()),
        'avg_net': float(relief_data['net_relief'].mean()),
        'std_expected': float(relief_data['expected_relief'].std()),
        'std_actual': float(relief_data['actual_relief'].std()),
        'std_net': float(relief_data['net_relief'].std()),
        'correlation': float(relief_data['expected_relief'].corr(relief_data['actual_relief'])),
        'mae': float((relief_data['net_relief'].abs()).mean()),  # Mean Absolute Error
        'rmse': float(((relief_data['net_relief'] ** 2).mean()) ** 0.5),  # Root Mean Square Error
        'avg_serendipity': float(relief_data['serendipity_factor'].mean()),
        'avg_disappointment': float(relief_data['disappointment_factor'].mean()),
        'total_serendipity': float(relief_data['serendipity_factor'].sum()),
        'total_disappointment': float(relief_data['disappointment_factor'].sum()),
    }
    
    # Categorize patterns
    relief_data['pattern'] = relief_data.apply(_categorize_relief_pattern, axis=1)
    pattern_counts = relief_data['pattern'].value_counts().to_dict()
    
    # Get recent tasks for details table
    relief_data_sorted = relief_data.sort_values('completed_at_dt', ascending=False)
    
    return {
        'stats': stats,
        'data': relief_data,
        'pattern_counts': pattern_counts,
        'recent_tasks': relief_data_sorted.head(20).to_dict('records'),
    }


def _categorize_relief_pattern(row) -> str:
    """Categorize relief pattern based on expected vs actual."""
    expected = row.get('expected_relief', 0)
    actual = row.get('actual_relief', 0)
    net = row.get('net_relief', 0)
    
    if pd.isna(expected) or pd.isna(actual):
        return 'Missing Data'
    
    # Large difference threshold
    large_diff = 20.0
    
    if abs(net) <= 5.0:
        return 'Accurate Prediction'
    elif net > large_diff:
        return 'Pleasant Surprise'
    elif net < -large_diff:
        return 'Disappointment'
    elif net > 0:
        return 'Slightly Better'
    else:
        return 'Slightly Worse'


def _render_summary_statistics(data: Dict):
    """Render summary statistics cards."""
    stats = data['stats']
    
    with ui.card().classes("p-4"):
        ui.label("Summary Statistics").classes("text-xl font-bold mb-3")
        
        with ui.row().classes("gap-4 flex-wrap"):
            with ui.card().classes("p-3 bg-blue-50 min-w-[150px]"):
                ui.label("Total Tasks").classes("text-xs text-gray-500")
                ui.label(f"{stats['total_tasks']}").classes("text-2xl font-bold")
            
            with ui.card().classes("p-3 bg-green-50 min-w-[150px]"):
                ui.label("Avg Expected Relief").classes("text-xs text-gray-500")
                ui.label(f"{stats['avg_expected']:.1f}").classes("text-2xl font-bold")
            
            with ui.card().classes("p-3 bg-purple-50 min-w-[150px]"):
                ui.label("Avg Actual Relief").classes("text-xs text-gray-500")
                ui.label(f"{stats['avg_actual']:.1f}").classes("text-2xl font-bold")
            
            with ui.card().classes("p-3 bg-yellow-50 min-w-[150px]"):
                ui.label("Avg Net Relief").classes("text-xs text-gray-500")
                color = "text-green-600" if stats['avg_net'] > 0 else "text-red-600" if stats['avg_net'] < 0 else "text-gray-600"
                ui.label(f"{stats['avg_net']:+.1f}").classes(f"text-2xl font-bold {color}")
            
            with ui.card().classes("p-3 bg-indigo-50 min-w-[150px]"):
                ui.label("Prediction Accuracy").classes("text-xs text-gray-500")
                mae = stats['mae']
                accuracy_label = "Excellent" if mae < 10 else "Good" if mae < 20 else "Fair" if mae < 30 else "Poor"
                ui.label(f"{accuracy_label}").classes("text-lg font-bold")
                ui.label(f"MAE: {mae:.1f}").classes("text-xs text-gray-500")
            
            with ui.card().classes("p-3 bg-pink-50 min-w-[150px]"):
                ui.label("Correlation").classes("text-xs text-gray-500")
                corr = stats['correlation']
                if pd.notna(corr):
                    ui.label(f"{corr:.2f}").classes("text-2xl font-bold")
                    corr_label = "Strong" if abs(corr) > 0.7 else "Moderate" if abs(corr) > 0.4 else "Weak"
                    ui.label(corr_label).classes("text-xs text-gray-500")
                else:
                    ui.label("N/A").classes("text-lg font-bold")
            
            with ui.card().classes("p-3 bg-emerald-50 min-w-[150px]"):
                ui.label("Avg Serendipity").classes("text-xs text-gray-500")
                ui.label(f"{stats['avg_serendipity']:.1f}").classes("text-2xl font-bold text-green-600")
            
            with ui.card().classes("p-3 bg-rose-50 min-w-[150px]"):
                ui.label("Avg Disappointment").classes("text-xs text-gray-500")
                ui.label(f"{stats['avg_disappointment']:.1f}").classes("text-2xl font-bold text-red-600")


def _render_comparison_charts(data: Dict):
    """Render comparison charts."""
    relief_data = data['data']
    
    with ui.card().classes("p-4"):
        ui.label("Comparison Charts").classes("text-xl font-bold mb-3")
        
        with ui.tabs().classes("w-full") as tabs:
            scatter = ui.tab("Scatter Plot")
            time_series = ui.tab("Time Series")
            distribution = ui.tab("Distribution")
        
        with ui.tab_panels(tabs, value=scatter).classes("w-full"):
            with ui.tab_panel(scatter):
                _render_scatter_plot(relief_data)
            
            with ui.tab_panel(time_series):
                _render_time_series(relief_data)
            
            with ui.tab_panel(distribution):
                _render_distribution_chart(relief_data)


def _render_scatter_plot(relief_data: pd.DataFrame):
    """Render scatter plot of expected vs actual relief."""
    fig = go.Figure()
    
    # Add perfect prediction line (y=x)
    max_val = max(relief_data['expected_relief'].max(), relief_data['actual_relief'].max())
    min_val = min(relief_data['expected_relief'].min(), relief_data['actual_relief'].min())
    fig.add_trace(go.Scatter(
        x=[min_val, max_val],
        y=[min_val, max_val],
        mode='lines',
        name='Perfect Prediction',
        line=dict(color='gray', dash='dash', width=1),
        showlegend=True
    ))
    
    # Color points by net relief
    colors = relief_data['net_relief'].apply(
        lambda x: 'green' if x > 10 else 'red' if x < -10 else 'gray'
    )
    
    fig.add_trace(go.Scatter(
        x=relief_data['expected_relief'],
        y=relief_data['actual_relief'],
        mode='markers',
        name='Tasks',
        marker=dict(
            size=8,
            color=relief_data['net_relief'],
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title="Net Relief"),
            line=dict(width=1, color='black')
        ),
        text=relief_data['task_name'].apply(escape_for_display),
        hovertemplate='<b>%{text}</b><br>Expected: %{x:.1f}<br>Actual: %{y:.1f}<br>Net: %{marker.color:.1f}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Expected vs Actual Relief",
        xaxis_title="Expected Relief",
        yaxis_title="Actual Relief",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    ui.plotly(fig)


def _render_time_series(relief_data: pd.DataFrame):
    """Render time series of expected, actual, and net relief."""
    relief_data_sorted = relief_data.sort_values('completed_at_dt')
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=relief_data_sorted['completed_at_dt'],
        y=relief_data_sorted['expected_relief'],
        mode='lines+markers',
        name='Expected Relief',
        line=dict(color='blue', width=2),
        marker=dict(size=6)
    ))
    
    fig.add_trace(go.Scatter(
        x=relief_data_sorted['completed_at_dt'],
        y=relief_data_sorted['actual_relief'],
        mode='lines+markers',
        name='Actual Relief',
        line=dict(color='green', width=2),
        marker=dict(size=6)
    ))
    
    fig.add_trace(go.Scatter(
        x=relief_data_sorted['completed_at_dt'],
        y=relief_data_sorted['net_relief'],
        mode='lines+markers',
        name='Net Relief',
        line=dict(color='orange', width=2, dash='dot'),
        marker=dict(size=6)
    ))
    
    # Add zero line for net relief
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        title="Relief Over Time",
        xaxis_title="Date",
        yaxis_title="Relief Score",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode='x unified'
    )
    
    ui.plotly(fig)


def _render_distribution_chart(relief_data: pd.DataFrame):
    """Render distribution of expected, actual, and net relief."""
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=relief_data['expected_relief'],
        name='Expected Relief',
        opacity=0.7,
        nbinsx=20
    ))
    
    fig.add_trace(go.Histogram(
        x=relief_data['actual_relief'],
        name='Actual Relief',
        opacity=0.7,
        nbinsx=20
    ))
    
    fig.add_trace(go.Histogram(
        x=relief_data['net_relief'],
        name='Net Relief',
        opacity=0.7,
        nbinsx=20
    ))
    
    fig.update_layout(
        title="Distribution of Relief Values",
        xaxis_title="Relief Score",
        yaxis_title="Frequency",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        barmode='overlay'
    )
    
    ui.plotly(fig)


def _render_pattern_analysis(data: Dict):
    """Render pattern analysis with explanations."""
    pattern_counts = data['pattern_counts']
    stats = data['stats']
    
    with ui.card().classes("p-4"):
        ui.label("Pattern Analysis").classes("text-xl font-bold mb-3")
        
        # Pattern breakdown
        with ui.row().classes("gap-4 flex-wrap mb-4"):
            for pattern, count in pattern_counts.items():
                pct = (count / stats['total_tasks']) * 100
                with ui.card().classes(f"p-3 min-w-[150px] {_get_pattern_color_class(pattern)}"):
                    ui.label(pattern).classes("text-sm font-semibold")
                    ui.label(f"{count}").classes("text-2xl font-bold")
                    ui.label(f"({pct:.1f}%)").classes("text-xs text-gray-500")
        
        # Interpretation guide
        with ui.expansion("What do these patterns mean?", icon="info").classes("w-full mt-4"):
            with ui.card().classes("p-3 bg-gray-50"):
                _render_pattern_explanations()


def _get_pattern_color_class(pattern: str) -> str:
    """Get color class for pattern."""
    color_map = {
        'Accurate Prediction': 'bg-green-50',
        'Pleasant Surprise': 'bg-blue-50',
        'Disappointment': 'bg-red-50',
        'Slightly Better': 'bg-yellow-50',
        'Slightly Worse': 'bg-orange-50',
        'Missing Data': 'bg-gray-50',
    }
    return color_map.get(pattern, 'bg-gray-50')


def _render_pattern_explanations():
    """Render explanations of what different patterns mean."""
    explanations = [
        {
            'pattern': 'Accurate Prediction',
            'description': 'Expected and actual relief are within 5 points of each other.',
            'implication': 'You have good self-awareness about how tasks will make you feel. This suggests you can trust your predictions when planning.',
            'action': 'Continue using your predictions to guide task selection and scheduling.'
        },
        {
            'pattern': 'Pleasant Surprise',
            'description': 'Actual relief exceeded expected relief by more than 20 points.',
            'implication': 'You may be underestimating the positive impact of certain tasks. These tasks might be more rewarding than you think.',
            'action': 'Consider doing more of these types of tasks, and adjust your expectations upward for similar tasks.'
        },
        {
            'pattern': 'Disappointment',
            'description': 'Actual relief fell short of expected relief by more than 20 points.',
            'implication': 'You may be overestimating how rewarding certain tasks will be. This could lead to task avoidance if you expect high relief but don\'t get it.',
            'action': 'Review these tasks - are they truly as rewarding as you think? Consider adjusting expectations downward or finding alternative approaches.'
        },
        {
            'pattern': 'Slightly Better',
            'description': 'Actual relief was 5-20 points higher than expected.',
            'implication': 'Minor positive surprises. Your predictions are generally accurate but slightly conservative.',
            'action': 'This is a healthy pattern - slight positive surprises are better than disappointments.'
        },
        {
            'pattern': 'Slightly Worse',
            'description': 'Actual relief was 5-20 points lower than expected.',
            'implication': 'Minor disappointments. Your predictions may be slightly optimistic.',
            'action': 'Consider being slightly more conservative in your relief predictions, especially for tasks you haven\'t done recently.'
        },
    ]
    
    for exp in explanations:
        with ui.card().classes("p-3 mb-2"):
            ui.label(exp['pattern']).classes("font-bold text-lg mb-1")
            ui.label(exp['description']).classes("text-sm text-gray-600 mb-2")
            with ui.row().classes("gap-2"):
                ui.label("Implication:").classes("font-semibold text-sm")
                ui.label(exp['implication']).classes("text-sm")
            with ui.row().classes("gap-2 mt-1"):
                ui.label("Action:").classes("font-semibold text-sm")
                ui.label(exp['action']).classes("text-sm")


def _render_task_details(data: Dict):
    """Render detailed task-level comparison table."""
    recent_tasks = data['recent_tasks']
    
    with ui.card().classes("p-4"):
        ui.label("Recent Task Details").classes("text-xl font-bold mb-3")
        
        if not recent_tasks:
            ui.label("No task details available.").classes("text-gray-500")
            return
        
        # Create table
        columns = [
            {'name': 'task_name', 'label': 'Task', 'field': 'task_name', 'required': True},
            {'name': 'completed_at', 'label': 'Date', 'field': 'completed_at', 'required': True},
            {'name': 'expected_relief', 'label': 'Expected', 'field': 'expected_relief', 'required': True},
            {'name': 'actual_relief', 'label': 'Actual', 'field': 'actual_relief', 'required': True},
            {'name': 'net_relief', 'label': 'Net', 'field': 'net_relief', 'required': True},
            {'name': 'serendipity_factor', 'label': 'Serendipity Factor', 'field': 'serendipity_factor', 'required': True},
            {'name': 'disappointment_factor', 'label': 'Disappointment Factor', 'field': 'disappointment_factor', 'required': True},
            {'name': 'pattern', 'label': 'Pattern', 'field': 'pattern', 'required': True},
        ]
        
        rows = []
        for task in recent_tasks:
            rows.append({
                'task_name': escape_for_display(task.get('task_name', 'Unknown')),
                'completed_at': task.get('completed_at', '')[:10] if task.get('completed_at') else '',
                'expected_relief': f"{task.get('expected_relief', 0):.1f}",
                'actual_relief': f"{task.get('actual_relief', 0):.1f}",
                'net_relief': f"{task.get('net_relief', 0):+.1f}",
                'serendipity_factor': f"{task.get('serendipity_factor', 0):.1f}",
                'disappointment_factor': f"{task.get('disappointment_factor', 0):.1f}",
                'pattern': task.get('pattern', 'Unknown'),
            })
        
        ui.table(columns=columns, rows=rows).classes("w-full").props("dense flat bordered")
