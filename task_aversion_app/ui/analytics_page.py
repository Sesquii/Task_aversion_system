from nicegui import ui
import pandas as pd
import plotly.express as px

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
    {'label': 'Net Wellbeing', 'value': 'net_wellbeing'},
    {'label': 'Net Wellbeing (Normalized)', 'value': 'net_wellbeing_normalized'},
    {'label': 'Stress Efficiency', 'value': 'stress_efficiency'},
    {'label': 'Productivity Score', 'value': 'productivity_score'},
    {'label': 'Grit Score', 'value': 'grit_score'},
    {'label': 'Relief Duration Score', 'value': 'relief_duration_score'},
    {'label': "Today's self care tasks", 'value': 'daily_self_care_tasks'},
    {'label': 'Work Time (minutes)', 'value': 'work_time'},
    {'label': 'Play Time (minutes)', 'value': 'play_time'},
]

ATTRIBUTE_OPTIONS = NUMERIC_ATTRIBUTE_OPTIONS + CALCULATED_METRICS
ATTRIBUTE_LABELS = {opt['value']: opt['label'] for opt in ATTRIBUTE_OPTIONS}
ATTRIBUTE_OPTIONS_DICT = {opt['value']: opt['label'] for opt in ATTRIBUTE_OPTIONS}


def register_analytics_page():
    @ui.page('/analytics')
    def analytics_dashboard():
        build_analytics_page()


def build_analytics_page():
    ui.add_head_html("<style>.analytics-grid { gap: 1rem; }</style>")
    ui.label("Analytics Studio").classes("text-2xl font-bold mb-2")
    ui.label("Explore how task qualities evolve and prototype recommendation filters.").classes(
        "text-gray-500 mb-4"
    )

    metrics = analytics_service.get_dashboard_metrics()
    relief_summary = analytics_service.get_relief_summary()
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
        ]:
            with ui.card().classes("p-3 min-w-[150px]"):
                ui.label(title).classes("text-xs text-gray-500")
                ui.label(value).classes("text-xl font-bold")
    
    # Productivity Volume Section
    productivity_volume = metrics.get('productivity_volume', {})
    with ui.card().classes("p-4 mb-4"):
        ui.label("Productivity Volume Analysis").classes("text-xl font-bold mb-2")
        ui.label("Metrics that account for both efficiency and total work volume").classes("text-sm text-gray-500 mb-3")
        
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
                ui.label("If you worked 6 hrs/day").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px] border-2 border-orange-300"):
                ui.label("Work Volume Gap").classes("text-xs text-gray-500 font-semibold")
                gap = productivity_volume.get('work_volume_gap', 0.0)
                ui.label(f"{gap:.1f} hours").classes("text-2xl font-bold text-orange-600")
                ui.label("Gap to 6 hrs/day target").classes("text-xs text-gray-400")
            
            with ui.card().classes("p-3 min-w-[200px] border-2 border-green-300"):
                ui.label("Composite Productivity").classes("text-xs text-gray-500 font-semibold")
                composite = productivity_volume.get('composite_productivity_score', 0.0)
                ui.label(f"{composite:.1f}").classes("text-2xl font-bold text-green-600")
                ui.label("Efficiency + Volume + Consistency").classes("text-xs text-gray-400")
    
    # Show warning if efficiency is high but volume is low
    avg_efficiency = metrics.get('quality', {}).get('avg_stress_efficiency')
    if avg_efficiency is not None and volume_score < 50 and avg_efficiency > 2.0:
        with ui.card().classes("p-3 mb-4 bg-yellow-50 border-2 border-yellow-300"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("warning", size="md").classes("text-yellow-600")
                ui.label("High efficiency but low work volume detected").classes("font-semibold text-yellow-800")
            ui.label(f"You're highly efficient (efficiency: {avg_efficiency:.2f}) but only working {avg_work_time/60:.1f} hours/day on average.").classes("text-sm text-yellow-700 mt-1")
            ui.label(f"Working more could significantly increase your productivity. Gap: {gap:.1f} hours/day to reach 6 hours/day target.").classes("text-sm text-yellow-700")
    
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

    with ui.row().classes("analytics-grid flex-wrap w-full"):
        _render_time_chart()
        _render_attribute_box()

    _render_trends_section()
    _render_stress_metrics_section()
    _render_task_rankings()
    _render_stress_efficiency_leaderboard()
    _render_metric_comparison()
    _render_correlation_explorer()


def _render_time_chart():
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


def _render_attribute_box():
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


def _render_stress_metrics_section():
    """Render stress dimension metrics with bar charts and line graphs."""
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
        
        # Get stress dimension data
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


def _render_metric_comparison():
    """Render a flexible metric comparison tool with scatter plots."""
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
                                            volume_metrics = analytics_service.get_dashboard_metrics().get('productivity_volume', {})
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
                                        volume_metrics = analytics_service.get_dashboard_metrics().get('productivity_volume', {})
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


def _render_task_rankings():
    ui.separator()
    ui.label("Task Performance Rankings").classes("text-xl font-semibold mt-4")
    
    with ui.row().classes("gap-4 flex-wrap mt-2"):
        # Top tasks by relief
        top_relief = analytics_service.get_task_performance_ranking('relief', top_n=5)
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Tasks by Relief").classes("font-bold text-md mb-2")
            if not top_relief:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in top_relief:
                    ui.label(f"{task['task_name']}: {task['metric_value']} (n={task['count']})").classes("text-sm")
        
        # Top tasks by stress efficiency
        top_efficiency = analytics_service.get_task_performance_ranking('stress_efficiency', top_n=5)
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Tasks by Stress Efficiency").classes("font-bold text-md mb-2")
            if not top_efficiency:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in top_efficiency:
                    ui.label(f"{task['task_name']}: {task['metric_value']:.2f} (n={task['count']})").classes("text-sm")
        
        # Top tasks by behavioral score
        top_behavioral = analytics_service.get_task_performance_ranking('behavioral_score', top_n=5)
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Tasks by Behavioral Score").classes("font-bold text-md mb-2")
            if not top_behavioral:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in top_behavioral:
                    ui.label(f"{task['task_name']}: {task['metric_value']} (n={task['count']})").classes("text-sm")
        
        # Lowest stress tasks
        low_stress = analytics_service.get_task_performance_ranking('stress_level', top_n=5)
        with ui.card().classes("p-3 min-w-[250px]"):
            ui.label("Top 5 Lowest Stress Tasks").classes("font-bold text-md mb-2")
            if not low_stress:
                ui.label("No data yet").classes("text-xs text-gray-500")
            else:
                for task in low_stress:
                    ui.label(f"{task['task_name']}: {task['metric_value']} (n={task['count']})").classes("text-sm")


def _render_stress_efficiency_leaderboard():
    ui.separator()
    ui.label("Stress Efficiency Leaderboard").classes("text-xl font-semibold mt-4")
    ui.label("Tasks that give you the most relief per unit of stress").classes("text-sm text-gray-500 mb-2")
    
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

