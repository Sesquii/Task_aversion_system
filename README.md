# Task Aversion System

A productivity application designed to help overcome task aversion and increase daily functioning through comprehensive tracking of emotions, cognitive load, motivation, and task performance metrics.

## Overview

This system goes beyond a simple to-do list by incorporating psychological and behavioral tracking to help you understand and overcome task avoidance patterns. It tracks how you feel about tasks before, during, and after completion, providing insights into what makes tasks easier or harder for you.

**Core Philosophy:** By tracking aversion, stress, relief, and other psychological factors alongside task completion, you can identify patterns and make data-driven decisions about which tasks to tackle and when.

---

## Current Features

### Task Management

- **Task Creation & Templates**: Create reusable task templates with default estimates, categories, and metadata
- **Task Lifecycle**: Full workflow from creation → initialization → completion/cancellation
- **Task Instances**: Track multiple attempts/completions of the same task over time
- **Task Versioning**: Track changes to task definitions while preserving historical data

### Psychological & Behavioral Tracking

- **Emotion Tracking**: Record emotional states before, during, and after tasks
- **Stress Level Measurement**: Multi-dimensional stress tracking combining:
  - Cognitive load
  - Emotional load
  - Physical load
- **Aversion Tracking**: Measure task avoidance levels (0-100 scale) to identify patterns
- **Relief Score**: Quantify the sense of relief after completing tasks
- **Motivation Metrics**: Track motivation levels and their relationship to task completion

### Analytics & Insights

- **Analytics Dashboard**: Basic interactive charts and visualizations including:
  - Relief score trends over time
  - Stress level distributions
  - Attribute correlations and scatter plots
  - Multi-attribute trend analysis
- **Composite Score System**: Customizable weighted score combining:
  - Completion percentage
  - Persistence multiplier (rewards repeated completions)
  - Time tracking consistency
  - Overall improvement ratio
  - Difficulty bonuses
  - Improvement multipliers
- **Performance Metrics**:
  - Productivity score
  - Grit score (persistence measurement)
  - Stress efficiency
  - Net wellbeing
  - Behavioral score
  - Historical efficiency

### Task Recommendations

- **Basic Recommendations**: Rule-based task suggestions using multiple metrics (relief score, difficulty, efficiency, etc.)
- **Category-Based Filtering**: Get recommendations filtered by task category
- **Customizable Metric Selection**: Choose which factors to prioritize in recommendations

### Dashboard Features

- **Three-Column Layout**: Organized view of:
  - Task templates and quick actions
  - Active task instances and current task
  - Recommendations and metrics
- **Real-Time Metrics**: Live tracking of key performance indicators
- **Interactive Tooltips**: Detailed information on hover for tasks and metrics
- **Gap Detection**: Automatic detection and handling of data gaps in your tracking

### Additional Tools

- **Mental Health Survey**: Integrated survey system for tracking overall wellbeing
- **Settings Management**: Centralized configuration and preferences
- **Tutorial System**: Guided walkthrough for new users
- **Data Archival**: Automatic archiving of historical data with metadata

### Data Management

- **CSV-Based Storage**: Simple, portable data format (currently)
- **Data Validation**: Automatic validation and error handling
- **Backup & Recovery**: Tools for data backup and restoration
- **Audit System**: Data integrity checking and reporting

---

## Planned Features

### Recommendation Engine Enhancement

- **Machine Learning Integration**: 
  - ML-based task suggestions (currently using rule-based algorithms)
  - Personalized recommendations based on historical patterns
  - Dynamic adjustment based on time of day, energy levels, and context

### Database Migration

- **PostgreSQL Integration**: Migrate from CSV to database for better scalability
- **Dual Backend Support**: Seamless transition with CSV fallback
- **Connection Pooling**: Efficient database connection management
- **Migration Tools**: Safe data migration scripts with rollback capability

### Online Deployment

- **VPS Deployment**: Deploy to production server for online access
- **Multi-User Support**: User accounts and data isolation
- **Cloud Sync**: Synchronize data across devices
- **API Development**: RESTful API for external integrations

### Mobile Support

- **Responsive Design**: Mobile-optimized interface
- **Mobile App**: Native mobile application (future consideration)
- **Quick Actions**: Mobile-friendly task completion workflows

### AI & Automation

- **Chatbot Integration**: AI assistant for task guidance and support
- **Automated Insights**: AI-generated insights from your data
- **Smart Scheduling**: AI-powered task scheduling recommendations

### Additional Planned Features

- **Data Guide**: Comprehensive documentation for local setup, data backup, and troubleshooting
- **Habit Tracking**: Long-term habit formation tracking
- **Goal Setting**: Set and track long-term goals
- **Export/Import**: Enhanced data portability
- **Integration APIs**: Connect with other productivity tools

---

## Installation

**👋 New to this? Start here:** [Install_instructions.txt](Install_instructions.txt) - Simple step-by-step guide for non-technical users

---

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Task_aversion_system
   ```

2. **Install dependencies:**
   ```bash
   cd task_aversion_app
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Access the application:**
   - Open your browser and navigate to `http://localhost:8080`
   - The dashboard will be your home page

### Windows-Specific Notes

- The application is tested and works on Windows
- Ensure Python is added to your system PATH
- If using OneDrive for file storage, be aware that file locking may occur during sync

---

## Docker Installation (Recommended for Non-Technical Users)

> **📖 For detailed step-by-step instructions, see [Install_instructions.txt](Install_instructions.txt)**

If you're not comfortable with Python setup, you can use Docker instead. Docker packages everything needed to run the app.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux)

### Quick Start with Docker

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Task_aversion_system
   ```

2. **Start the application:**
   ```bash
   docker-compose up
   ```
   
   The first time you run this, the app will automatically create empty data files. Each user gets their own fresh data directory.

3. **Access the application:**
   - Open your browser to `http://localhost:8080`
   - Your data is stored in a Docker volume (persists between restarts but separate from the repository)

### Alternative: Use Your Own Data Folder

If you prefer to store data in a specific folder on your computer, edit `docker-compose.yml` and change:
```yaml
volumes:
  - task-aversion-data:/app/data
```
to:
```yaml
volumes:
  - ./my-task-data:/app/data  # or any path you want
```

### Using a Release Tag

If you want to use a specific release version:

```bash
git clone <repository-url>
cd Task_aversion_system
git checkout v0.1.0  # Replace with actual tag
docker-compose up
```

### Docker Notes

- **Fresh data for each user**: The default setup uses a Docker named volume, so each user starts with empty data files (the app creates them automatically)
- **Data persistence**: Your data persists between container restarts
- **Stopping the app**: Press `Ctrl+C` in the terminal, or run `docker-compose down`
- **Viewing logs**: Run `docker-compose logs -f` to see application output
- **Port conflicts**: If port 8080 is in use, edit `docker-compose.yml` and change `"8080:8080"` to `"8081:8080"` (then access at `http://localhost:8081`)
- **Finding your data**: If using the default named volume, your data is stored in Docker's volume system. To access it directly, you can change the volume mount in `docker-compose.yml` to a folder path (see "Alternative: Use Your Own Data Folder" above)

---

## Usage

### Getting Started

1. **Create Your First Task:**
   - Click "Create Task" from the dashboard
   - Fill in task details (name, description, estimated time, etc.)
   - Save the task template

2. **Initialize a Task Instance:**
   - Select a task template from the dashboard
   - Click "Initialize" to start working on it
   - Record your initial emotions, stress levels, and aversion

3. **Complete a Task:**
   - When finished, click "Complete Task"
   - Record actual time taken, relief felt, and final emotions
   - The system will calculate performance metrics automatically

4. **View Analytics:**
   - Navigate to the Analytics page to see trends and insights
   - Explore correlations between different metrics
   - Use recommendations to choose your next task

### Key Concepts

- **Task Templates**: Reusable task definitions that can be instantiated multiple times
- **Task Instances**: Individual attempts or completions of a task template
- **Aversion**: Your level of avoidance or resistance to a task (0-100)
- **Relief Score**: How much relief you feel after completing a task
- **Stress Level**: Combined measure of cognitive, emotional, and physical stress

---

## Technical Details

### Architecture

- **Frontend**: NiceGUI (Python-based web framework)
- **Backend**: Python with pandas for data manipulation
- **Visualization**: Plotly for interactive charts
- **Data Storage**: CSV files (migrating to PostgreSQL)

### Key Components

- `backend/task_manager.py`: Task CRUD operations
- `backend/instance_manager.py`: Task instance management
- `backend/emotion_manager.py`: Emotion tracking
- `backend/analytics.py`: Analytics and recommendation engine
- `backend/compute_priority.py`: Priority scoring algorithms
- `ui/dashboard.py`: Main dashboard interface
- `ui/analytics_page.py`: Analytics visualization

### Data Schema

Tasks and instances track:
- Basic info (name, description, categories)
- Time estimates and actuals
- Psychological metrics (aversion, stress, emotions, relief)
- Performance metrics (efficiency, productivity, grit)
- Behavioral data (skills improved, environmental effects)

---

## Contributing

This is currently a personal project, but contributions and suggestions are welcome! If you find bugs or have feature requests, please open an issue.

---

## License

See LICENSE file for details.

---

## Known Limitations & Shortcomings

### Current Limitations

- **CSV-Based Storage**: Data is stored in CSV files, which can have file locking issues (especially with OneDrive sync) and doesn't scale well for multiple users
- **Local-Only**: The app currently runs locally only - no online access or multi-device sync
- **No User Accounts**: Single-user system with no authentication or data isolation
- **Mobile Experience**: The interface is designed for desktop - mobile browser experience is not optimized
- **Data Guide**: Currently missing - documentation for local setup, data backup, and troubleshooting not implemented

### Technical Debt

- **Error Handling**: Some error messages could be more user-friendly
- **Data Validation**: Limited validation on data entry - invalid data can cause issues
- **Performance**: With large datasets (1000+ task instances), some operations may be slow
- **Testing**: Limited automated testing - mostly manual testing during development

---

## Status

**Current Status**: Work in progress - actively developed and used for personal productivity

The core workflow is functional and stable for daily use. The system works well for personal use but has limitations around scalability, multi-user support, and some advanced features. Development is ongoing with focus on database migration and addressing the limitations listed above.

---

## Notes

- The system is designed to be data-driven: the more you use it, the better the recommendations become
- All data is stored locally (CSV files) - you have full control over your data, but be aware of file locking issues with OneDrive
- The composite score system is highly customizable - adjust weights to match your priorities
- Regular use (daily task completion) provides the most valuable insights
- This is a personal project - some features may be rough around the edges

---

## Support

For issues, questions, or feature requests, please check the documentation in the `docs/` folder or open an issue in the repository.
