# ui/gap_handling.py
"""
Gap Handling UI Component
Allows users to choose how to handle detected data gaps.
"""

from nicegui import ui
from typing import Optional

from backend.gap_detector import GapDetector
from backend.data_archival import DataArchival


def gap_handling_page():
    """Create gap handling page with user options."""
    
    gap_detector = GapDetector()
    gap_summary = gap_detector.get_gap_summary()
    
    if not gap_summary['has_gaps']:
        ui.label("No Data Gaps Detected").classes("text-h4")
        ui.label("Your data collection appears continuous. No action needed.")
        ui.link("Return to Dashboard", "/").classes("button")
        return
    
    largest_gap = gap_summary['largest_gap']
    
    ui.label("Data Gap Detected").classes("text-h4")
    ui.label(f"We detected a {largest_gap['gap_days']:.0f}-day gap in your data collection.")
    
    with ui.card().classes("w-full"):
        ui.label("Gap Details:").classes("font-bold")
        ui.label(f"Start: {largest_gap['gap_start_str']}")
        ui.label(f"End: {largest_gap['gap_end_str']}")
        ui.label(f"Instances before gap: {largest_gap['instances_before']}")
        ui.label(f"Instances after gap: {largest_gap['instances_after']}")
    
    ui.separator()
    
    ui.label("How would you like to handle this gap?").classes("text-h5")
    ui.label(
        "This decision affects how your analytics are calculated. "
        "You can change this later in settings."
    ).classes("text-sm text-gray-600")
    
    def handle_continue_as_is():
        """Handle continue as-is choice."""
        gap_detector.set_gap_handling_preference("continue_as_is")
        ui.notify("Preference saved: Continue as-is", type="positive")
        ui.navigate.to("/")
    
    def handle_fresh_start():
        """Handle fresh start choice."""
        gap_detector.set_gap_handling_preference("fresh_start")
        
        # Trigger archival
        try:
            archival = DataArchival()
            archival.archive_pre_gap_data()
            ui.notify("Preference saved: Fresh start. Pre-gap data archived.", type="positive")
        except Exception as e:
            ui.notify(f"Error during archival: {e}", type="negative")
        
        ui.navigate.to("/")
    
    with ui.card().classes("w-full border-2 border-blue-200 bg-blue-50"):
        ui.label("Option A: Continue as-is").classes("text-h6")
        ui.label(
            "Keep all your data. The gap period will be marked and excluded "
            "from trend analysis, but all historical data remains available."
        )
        ui.label("✓ All data preserved").classes("text-sm text-green-600")
        ui.label("✓ Can compare pre-gap and post-gap patterns").classes("text-sm text-green-600")
        ui.label("⚠ Gap period excluded from trends").classes("text-sm text-orange-600")
        ui.button(
            "Choose Continue as-is",
            on_click=handle_continue_as_is
        ).classes("w-full bg-blue-500")
    
    with ui.card().classes("w-full border-2 border-green-200 bg-green-50"):
        ui.label("Option B: Fresh Start with Averages").classes("text-h6")
        ui.label(
            "Archive your pre-gap data and store only key averages. "
            "Start fresh with post-gap data for cleaner analysis."
        )
        ui.label("✓ Cleaner, more focused analysis").classes("text-sm text-green-600")
        ui.label("✓ Pre-gap averages preserved for reference").classes("text-sm text-green-600")
        ui.label("⚠ Pre-gap detailed data archived (can be restored)").classes("text-sm text-orange-600")
        ui.button(
            "Choose Fresh Start",
            on_click=handle_fresh_start
        ).classes("w-full bg-green-500")


def check_and_redirect_to_gap_handling():
    """Check if gap handling is needed and redirect if so."""
    gap_detector = GapDetector()
    
    if gap_detector.needs_gap_decision():
        ui.navigate.to("/gap-handling")
        return True
    
    return False

