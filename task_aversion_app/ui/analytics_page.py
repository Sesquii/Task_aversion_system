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
    {'label': 'Relief Duration Score', 'value': 'relief_duration_score'},
    {'label': 'Daily Self Care Tasks', 'value': 'daily_self_care_tasks'},
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
            ("Daily Self Care Tasks", metrics['counts']['daily_self_care_tasks']),
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
        ]:
            with ui.card().classes("p-3 min-w-[150px]"):
                ui.label(title).classes("text-xs text-gray-500")
                ui.label(value).classes("text-xl font-bold")
    
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
    _render_task_rankings()
    _render_stress_efficiency_leaderboard()
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

