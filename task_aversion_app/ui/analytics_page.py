from nicegui import ui
import plotly.express as px

from backend.analytics import (
    Analytics,
    SUGGESTED_ANALYTICS_LIBRARIES,
    SUGGESTED_ML_LIBRARIES,
)
from backend.task_schema import TASK_ATTRIBUTES

analytics_service = Analytics()


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
    with ui.row().classes("gap-3 flex-wrap mb-4"):
        for title, value in [
            ("Active", metrics['counts']['active']),
            ("Completed 7d", metrics['counts']['completed_7d']),
            ("Avg Relief", metrics['quality']['avg_relief']),
            ("Avg Cognitive", metrics['quality']['avg_cognitive_load']),
            ("Avg Stress Level", metrics['quality']['avg_stress_level']),
            ("Avg Net Wellbeing", metrics['quality']['avg_net_wellbeing']),
            ("Avg Net Wellbeing (Norm)", metrics['quality']['avg_net_wellbeing_normalized']),
            ("Avg Stress Efficiency", metrics['quality']['avg_stress_efficiency'] if metrics['quality']['avg_stress_efficiency'] is not None else "N/A"),
            ("Avg Relief × Duration", relief_summary.get('avg_relief_duration_score', 0.0)),
            ("Total Relief × Duration", relief_summary.get('total_relief_duration_score', 0.0)),
            ("Total Relief Score", relief_summary.get('total_relief_score', 0.0)),
        ]:
            with ui.card().classes("p-3 min-w-[150px]"):
                ui.label(title).classes("text-xs text-gray-500")
                ui.label(value).classes("text-xl font-bold")

    with ui.row().classes("analytics-grid flex-wrap w-full"):
        _render_time_chart()
        _render_attribute_box()

    _render_recommendation_lab()
    _render_future_notes()


def _render_time_chart():
    df = analytics_service.trend_series()
    with ui.card().classes("p-3 grow"):
        ui.label("Relief trend").classes("font-bold text-md mb-2")
        if df.empty:
            ui.label("No completed instances yet.").classes("text-xs text-gray-500")
            return
        fig = px.line(
            df,
            x='completed_at',
            y='relief_score',
            markers=True,
            title="Relief over time",
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


def _render_recommendation_lab():
    ui.separator()
    ui.label("Recommendation lab").classes("text-xl font-semibold mt-4")
    filters = analytics_service.default_filters()

    with ui.row().classes("gap-3 flex-wrap mt-2"):
        max_duration = ui.number("Max duration (min)", value=filters['max_duration']).classes("w-40")

    result_area = ui.column().classes("mt-3 w-full")

    def update_filters(key, raw):
        value = raw if raw not in (None, '', 'None') else None
        if value is not None:
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = None
        filters[key] = value
        _render_recommendations(result_area, filters)

    max_duration.on('change', lambda e: update_filters('max_duration', e.value))

    _render_recommendations(result_area, filters)


def _render_recommendations(target, filters):
    target.clear()
    recs = analytics_service.recommendations(filters)
    if not recs:
        ui.label("No recommendations yet. Try relaxing the filters.").classes("text-xs text-gray-500")
        return
    with target:
        for rec in recs:
            with ui.card().classes("p-3 mb-2 w-full"):
                ui.label(rec['title']).classes("text-xs uppercase text-gray-500")
                ui.label(rec['task_name']).classes("text-lg font-semibold")
                ui.label(rec['reason']).classes("text-sm text-gray-600")
                ui.label(
                    f"Duration {rec.get('duration', '—')} min · Relief {rec.get('relief', '—')} · Cog {rec.get('cognitive_load', '—')}"
                ).classes("text-xs text-gray-500")


def _render_future_notes():
    ui.separator().classes("my-4")
    ui.label("Future ML roadmap").classes("text-xl font-semibold")

    ui.markdown("**Candidate analytics libraries:**")
    ui.markdown("\n".join([f"- {lib}" for lib in SUGGESTED_ANALYTICS_LIBRARIES]))

    ui.markdown("**ML toolchain starters:**")
    ui.markdown("\n".join([f"- {lib}" for lib in SUGGESTED_ML_LIBRARIES]))

    ui.markdown(
        """
**Assumptions & path forward:**
- Task attributes defined in the schema (duration, relief, cognitive load, emotional load, environmental effect, skills improved, behavioral deviation) are recorded per instance.
- Until organic data exists we can bootstrap synthetic rows by sampling from historical distributions or heuristics tied to task categories.
- Manual filters can be replaced by a ranking score learned via scikit-learn or LightFM as soon as per-user preference vectors are available.
"""
    )

    ui.markdown("**Attribute schema (extensible):**")
    schema_lines = "\n".join(
        [f"- `{attr.key}` / {attr.label}: {attr.description}" for attr in TASK_ATTRIBUTES]
    )
    ui.markdown(schema_lines)

