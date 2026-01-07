from nicegui import ui


def register_known_issues_page():
    @ui.page('/known-issues')
    def known_issues_page():
        build_known_issues_page()


def build_known_issues_page():
    """Build the Known Issues and Bugs page."""
    ui.label("Known Issues & Bugs").classes("text-3xl font-bold mb-4")
    ui.label("This page documents known limitations, bugs, and issues in the current version.").classes("text-gray-600 mb-6")
    
    # Design Limitations Section
    with ui.card().classes("w-full max-w-4xl mb-4"):
        ui.label("Design Limitations").classes("text-2xl font-bold mb-3 text-blue-600")
        
        with ui.column().classes("gap-3"):
            with ui.card().classes("p-4 bg-blue-50 border-l-4 border-blue-400"):
                ui.label("Score Accuracy").classes("text-lg font-semibold mb-2")
                ui.label("Scores do NOT necessarily 100% accurately reflect reality. They are an attempt at converting real experiences into data-driven analysis and are inherently prone to miscalibration for outlier situations.").classes("text-sm")
            
            with ui.card().classes("p-4 bg-blue-50 border-l-4 border-blue-400"):
                ui.label("Local-Only System").classes("text-lg font-semibold mb-2")
                ui.label("The system is currently not integrated into a website, so new user data cannot be used to enhance existing features. All improvements must be made manually through code updates.").classes("text-sm")
    
    # Release 0.2 Caveats Section
    with ui.card().classes("w-full max-w-4xl mb-4"):
        ui.label("Release 0.2 Caveats").classes("text-2xl font-bold mb-3 text-orange-600")
        
        with ui.column().classes("gap-3"):
            with ui.card().classes("p-4 bg-orange-50 border-l-4 border-orange-400"):
                ui.label("Dockerfile Database").classes("text-lg font-semibold mb-2")
                ui.label("The Dockerfile does not install the database, so usage will be slower especially after a few days of data due to much slower CSV-based data storage.").classes("text-sm")
            
            with ui.card().classes("p-4 bg-orange-50 border-l-4 border-orange-400"):
                ui.label("Analytics Page").classes("text-lg font-semibold mb-2")
                ui.label("The analytics page is currently 'more the merrier' - many features are included but not all are equally useful. Any advice for what's most useful or most useless would be appreciated.").classes("text-sm")
            
            with ui.card().classes("p-4 bg-orange-50 border-l-4 border-orange-400"):
                ui.label("Incomplete Features").classes("text-lg font-semibold mb-2")
                ui.label("Not every feature is fully implemented. Some sections are more placeholders or scaffolding than refined features.").classes("text-sm")
    
    # Bugs Section
    with ui.card().classes("w-full max-w-4xl mb-4"):
        ui.label("Bugs").classes("text-2xl font-bold mb-3 text-red-600")
        
        with ui.column().classes("gap-3"):
            with ui.card().classes("p-4 bg-red-50 border-l-4 border-red-400"):
                ui.label("Pause/Resume Time Tracking").classes("text-lg font-semibold mb-2")
                ui.label("There is a known bug where time spent on task may not always save correctly between pause and resume. Please verify your time is tracked correctly after resuming.").classes("text-sm")
            
            with ui.card().classes("p-4 bg-red-50 border-l-4 border-red-400"):
                ui.label("Search Bars on Initial Load").classes("text-lg font-semibold mb-2")
                ui.label("Sometimes search bars don't work on initial page load. A page refresh will fix it.").classes("text-sm")
            
            with ui.card().classes("p-4 bg-red-50 border-l-4 border-red-400"):
                ui.label("Monitored Metrics Display").classes("text-lg font-semibold mb-2")
                ui.label("Many monitored metrics do not display correct values. Graphs do not display for monitored metrics yet.").classes("text-sm")
    
    # Minor/QOL Issues Section
    with ui.card().classes("w-full max-w-4xl mb-4"):
        ui.label("Minor / Quality of Life Issues").classes("text-2xl font-bold mb-3 text-yellow-600")
        
        with ui.column().classes("gap-3"):
            with ui.card().classes("p-4 bg-yellow-50 border-l-4 border-yellow-400"):
                ui.label("Current Emotions Display").classes("text-lg font-semibold mb-2")
                ui.label("'Current emotions' from a task initialized but having a delay to activation will actually display the initialization emotions instead of the most recently completed task emotions.").classes("text-sm")
    
    # Back to Dashboard button
    with ui.row().classes("mt-6"):
        ui.button("← Back to Dashboard", 
                 on_click=lambda: ui.navigate.to('/'),
                 icon="home").classes("bg-blue-500 text-white")
