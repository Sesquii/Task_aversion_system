import os

PROJECT_NAME = "TASK_AVERSION_SYSTEM"

# Folder structure
folders = [
    f"{PROJECT_NAME}",
    f"{PROJECT_NAME}/ui",
    f"{PROJECT_NAME}/backend",
    f"{PROJECT_NAME}/assets",
    f"{PROJECT_NAME}/data",
]

# Files with initial content
files = {
    f"{PROJECT_NAME}/app.py": """# Entry point for the NiceGUI app
from nicegui import ui

# Temporary placeholder UI
ui.label('Task Aversion App Initialized')

ui.run(title='Task Aversion Logger', port=8080)
""",

    f"{PROJECT_NAME}/requirements.txt": """nicegui
pandas
matplotlib
""",

    f"{PROJECT_NAME}/ui/__init__.py": "",
    f"{PROJECT_NAME}/ui/main_menu.py": "# Main menu UI will go here\n",
    f"{PROJECT_NAME}/ui/add_log.py": "# Add log entry UI will go here\n",
    f"{PROJECT_NAME}/ui/view_tasks.py": "# View tasks UI will go here\n",
    f"{PROJECT_NAME}/ui/stats_dashboard.py": "# Statistics dashboard UI will go here\n",
    f"{PROJECT_NAME}/ui/settings_page.py": "# Settings page UI will go here\n",

    f"{PROJECT_NAME}/backend/__init__.py": "",
    f"{PROJECT_NAME}/backend/csv_manager.py": "# CSV read/write helper functions\n",
    f"{PROJECT_NAME}/backend/task_manager.py": "# Task metadata handler\n",
    f"{PROJECT_NAME}/backend/stats_engine.py": "# Data analysis and graph functions\n",
    f"{PROJECT_NAME}/backend/compute_priority.py": "# Ranking algorithm for task suggestions\n",

    f"{PROJECT_NAME}/assets/styles.css": "/* custom styles go here */\n",

    f"{PROJECT_NAME}/data/logs.csv": "timestamp,task,aversion_level,relief_prediction,relief_actual,completion_percent,perceived_overextension,time_estimate_minutes,time_actual_minutes,comment,blocker_type\n",
    f"{PROJECT_NAME}/data/tasks.csv": "task,category,times_logged,avg_aversion,avg_relief,last_logged\n",
}


def main():
    # Create folders
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"Created folder: {folder}")

    # Create files with content
    for filepath, content in files.items():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created file: {filepath}")

    print("\nProject structure initialized successfully!")
    print(f"You can now open {PROJECT_NAME}/app.py and begin building the UI.")


if __name__ == "__main__":
    main()
