#!/usr/bin/env python3
"""Export database data to CSV files."""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set database URL if not already set
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

from backend.csv_export import export_all_data_to_csv, get_export_summary

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def export_to_csv():
    """Export all database tables and user preferences to CSV files."""
    try:
        print(f"[Export] Exporting database data to CSV files in {DATA_DIR}...\n")
        
        export_counts, exported_files = export_all_data_to_csv(
            data_dir=DATA_DIR,
            include_user_preferences=True
        )
        
        summary = get_export_summary(export_counts)
        print(summary)
        print(f"\n[Export] Export complete!")
        print(f"[Export] CSV files saved to: {DATA_DIR}")
        print("\nExported files:")
        for file_path in exported_files:
            print(f"  - {os.path.basename(file_path)}")
        
    except Exception as e:
        print(f"[Export] Error during export: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == '__main__':
    export_to_csv()
