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
- **Task Pausing**: Pause and resume tasks with time tracking that persists across pauses
- **Completion Percentage Tracking**: Track partial completion of tasks (0-200%)

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

- **Analytics Dashboard**: Interactive charts and visualizations including:
  - Relief score trends over time
  - Stress level distributions
  - Attribute correlations and scatter plots
  - Multi-attribute trend analysis
- **Analytics Glossary**: Comprehensive glossary system with:
  - Versioned formula documentation (Execution Score v1.0, Productivity Score v1.1)
  - Graphic aids (theoretical and data-driven visualizations)
  - Module-based organization with expandable components
  - Interactive formula explanations and use cases
- **Composite Score System**: Customizable weighted score combining:
  - Time tracking consistency
  - Stress levels (inverted)
  - Net wellbeing
  - Stress efficiency
  - Relief scores
  - Work volume and consistency
  - Life balance
  - Completion rate
  - Self-care frequency
  - Execution score
- **Performance Metrics**:
  - **Productivity Score (v1.1)**: Measures productive output based on completion, task type, and efficiency
  - **Execution Score (v1.0)**: Rewards efficient execution of difficult tasks
  - **Grit Score**: Measures persistence and commitment (rewards repeated completions and taking longer)
  - **Stress Efficiency**: Relief per unit stress
  - **Net Wellbeing**: Relief minus stress (normalized)
  - **Behavioral Score**: Historical efficiency patterns

### Task Recommendations

- **Rule-Based Recommendations**: Task suggestions using multiple metrics (relief score, difficulty, efficiency, etc.)
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

### Experimental Features

Access via `/experimental` route:

- **Formula Control System**: Dynamic formula parameter adjustment system with:
  - Real-time Plotly visualizations
  - Parameter comparison charts
  - CSV persistence for formula settings
  - Support for productivity score formula tuning
- **Productivity Hours Goal Tracking**: Goal-based productivity tracking with:
  - Weekly productivity hour goals
  - Goal achievement tracking
  - Hybrid initialization (auto-estimate with manual adjustment)
  - Configurable productivity metrics charts
  - Goal-based score adjustments
- **Formula Baseline Charts**: Theoretical charts for formula analysis and refinement

### Data Management

- **Database Storage (Primary)**: SQLite database (default) with PostgreSQL support
- **CSV Fallback**: Automatic fallback to CSV when database is unavailable
- **Data Validation**: Automatic validation and error handling
- **Backup & Recovery**: Tools for data backup and restoration
- **Audit System**: Data integrity checking and reporting
- **Migration Tools**: Safe migration scripts with rollback capability

### Additional Tools

- **Mental Health Survey**: Integrated survey system for tracking overall wellbeing
- **Settings Management**: Centralized configuration including:
  - Composite score weight configuration
  - Cancellation penalty settings
  - Cancellation category management
- **Tutorial System**: Guided walkthrough for new users
- **Data Archival**: Automatic archiving of historical data with metadata
- **Cancelled Tasks Analytics**: Track and analyze cancelled tasks with category grouping

---

## Recent Updates

### Database Migration (Completed)

- **Database as Primary Backend**: SQLite is now the default storage method with CSV as fallback
- **Dual Backend Support**: All manager classes support both database and CSV backends
- **Migration Phases Completed**: Task creation, instance management, and emotion tracking fully migrated
- **Error Handling**: Enhanced error handling with strict mode support for database operations
- **Tables Migrated**: `tasks`, `task_instances`, and `emotions` tables fully operational

### Analytics & Scoring Enhancements

- **Execution Score v1.0**: New metric rewarding efficient execution of difficult tasks
  - Combines difficulty, speed, start speed, and completion factors
  - Fully documented with graphic aids and glossary entry
  - Integrated into composite score system
- **Productivity Score v1.1**: Major improvements to efficiency calculation
  - Fixed comparison to use task's own estimate (not weekly average)
  - Accounts for completion percentage in efficiency calculation
  - Capped efficiency multiplier (0.5x-1.5x) to prevent extreme scores
  - Fixed flattened_square curve calculation
  - Prevents negative scores from very fast completions
- **Analytics Glossary System**: Comprehensive glossary with versioned formulas
  - Module-based organization
  - Version badges (v1.0, v1.1)
  - Graphic aids (theoretical and data-driven)
  - Expandable component details
- **Grit Score Updates**: Refined grit score formula for persistence measurement

### Formula Control & Experimental Features

- **Formula Control System**: Universal formula parameter adjustment system
  - Dynamic parameter adjustment with real-time visualizations
  - CSV persistence for formula settings
  - Parameter comparison charts
  - Currently supports productivity score formula
- **Productivity Hours Goal Tracking**: Goal-based productivity system
  - Weekly goal setting with auto-estimation
  - Goal achievement tracking
  - Configurable chart views (points, score, hours, normalized)
  - Goal-based score adjustments integrated into analytics
- **Formula Baseline Charts**: Experimental analysis tools for formula refinement

### Task Management Improvements

- **Task Pausing**: Enhanced pause functionality with:
  - Time tracking that persists across pauses
  - Completion percentage tracking and display
  - Notes field for pause reasons
- **Cancellation System**: Enhanced cancellation tracking with:
  - Default and custom cancellation categories
  - Configurable productivity penalties per category
  - Cancelled tasks analytics page
  - Category-based grouping and analysis

### Documentation & Development

- **Formula Versioning Framework**: Established versioning system for all analytics formulas
- **Migration Rules**: Comprehensive cursor rules for analytics module development
- **Graphic Aid Generation Guidelines**: Standardized patterns for theoretical and data-driven visualizations
- **Development Plans**: Comprehensive plans for performance optimization, analytics modularization, and deployment

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
   git clone https://github.com/Sesquii/Task_aversion_system.git
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
   
   The application will automatically:
   - Create a SQLite database at `data/task_aversion.db` (if it doesn't exist)
   - Initialize all database tables
   - Fall back to CSV if database is unavailable

4. **Access the application:**
   - Open your browser and navigate to `http://localhost:8080`
   - The dashboard will be your home page

### Environment Variables

- **`DATABASE_URL`** (optional): Database connection string
  - Default: `sqlite:///data/task_aversion.db` (SQLite)
  - PostgreSQL: `postgresql://user:password@host:port/dbname`
- **`USE_CSV`** (optional): Set to `1`, `true`, or `yes` to use CSV backend instead of database
- **`DISABLE_CSV_FALLBACK`** (optional): Set to `1`, `true`, or `yes` to disable automatic CSV fallback on database errors

### Windows-Specific Notes

- The application is tested and works on Windows
- Ensure Python is added to your system PATH
- If using OneDrive for file storage, be aware that file locking may occur during sync (database storage mitigates this)

---

## Docker Installation (Recommended for Non-Technical Users)

> **📖 For detailed step-by-step instructions, see [Install_instructions.txt](Install_instructions.txt)**

If you're not comfortable with Python setup, you can use Docker instead. Docker packages everything needed to run the app.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux)

### Quick Start with Docker

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sesquii/Task_aversion_system.git
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
git clone https://github.com/Sesquii/Task_aversion_system.git
cd Task_aversion_system
git checkout release/docker-v0.1.0  # Use the docker release branch
docker-compose up
```

Alternatively, you can directly clone the release branch:
```bash
git clone -b release/docker-v0.1.0 https://github.com/Sesquii/Task_aversion_system.git
cd Task_aversion_system
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
   - Check the Analytics Glossary for detailed formula explanations
   - Use recommendations to choose your next task

5. **Explore Experimental Features:**
   - Visit `/experimental` to access experimental features
   - Try the Formula Control System to adjust formula parameters
   - Set productivity goals with the Goal Tracking System

### Key Concepts

- **Task Templates**: Reusable task definitions that can be instantiated multiple times
- **Task Instances**: Individual attempts or completions of a task template
- **Aversion**: Your level of avoidance or resistance to a task (0-100)
- **Relief Score**: How much relief you feel after completing a task
- **Stress Level**: Combined measure of cognitive, emotional, and physical stress
- **Execution Score**: Rewards efficient execution of difficult tasks
- **Productivity Score**: Measures productive output (completion, type, efficiency)
- **Grit Score**: Measures persistence and commitment (separate from productivity)

---

## Technical Details

### Architecture

- **Frontend**: NiceGUI (Python-based web framework)
- **Backend**: Python with pandas for data manipulation
- **Database**: SQLite (default) with PostgreSQL support via SQLAlchemy
- **Visualization**: Plotly for interactive charts
- **Data Storage**: Database (primary) with CSV fallback

### Key Components

- `backend/database.py`: Database models and connection management (Task, TaskInstance, Emotion)
- `backend/task_manager.py`: Task CRUD operations (dual backend: database/CSV)
- `backend/instance_manager.py`: Task instance management (dual backend: database/CSV)
- `backend/emotion_manager.py`: Emotion tracking
- `backend/analytics.py`: Analytics engine with versioned formulas (Execution Score v1.0, Productivity Score v1.1)
- `backend/compute_priority.py`: Priority scoring algorithms
- `backend/productivity_tracker.py`: Productivity goal tracking service
- `backend/user_state.py`: User preferences and state management
- `ui/dashboard.py`: Main dashboard interface
- `ui/analytics_page.py`: Analytics visualization
- `ui/analytics_glossary.py`: Analytics glossary with versioned formulas
- `ui/formula_control_system.py`: Experimental formula parameter adjustment
- `ui/productivity_goals_experimental.py`: Goal-based productivity tracking

### Database Schema

**Tasks Table:**
- Basic info (task_id, name, description, categories)
- Task properties (type, default_estimate_minutes, task_type)
- Routine scheduling fields
- Timestamps (created_at, updated_at)

**Task Instances Table:**
- Instance info (instance_id, task_id, status)
- Time tracking (estimated_minutes, actual_minutes, completion_percentage)
- Psychological metrics (aversion, stress_level, relief_score)
- Performance metrics (productivity_score, execution_score, grit_score)
- Behavioral data (skills_improved, environmental_effects)
- Timestamps (initialized_at, completed_at, cancelled_at)

**Emotions Table:**
- Emotion tracking (instance_id, phase: before/during/after)
- Emotional states and intensities
- Timestamps

### Formula Versioning

All analytics formulas are versioned with complete documentation:

- **Execution Score v1.0**: Documented in `docs/execution_module_v1.0.md`
- **Productivity Score v1.1**: Documented in `docs/productivity_score_v1.1.md`

Version information is displayed in the Analytics Glossary UI with version badges.

---

## Planned Features

### Recommendation Engine Enhancement

- **Machine Learning Integration**: 
  - ML-based task suggestions (currently using rule-based algorithms)
  - Personalized recommendations based on historical patterns
  - Dynamic adjustment based on time of day, energy levels, and context

### Performance Optimization

- **Caching Layer**: Implement caching for analytics calculations to reduce load times
- **Connection Pooling**: Enhanced database connection management
- **Loading Screens**: Improved UX for long-running operations

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

- **Analytics Modularization**: Refactor analytics page with module-based organization
- **Score Calibration**: Further refinement of scoring formulas based on user feedback
- **Spike Processing Enhancement**: Enhanced spike detection with batch processing and pattern analysis
- **Data Guide**: Comprehensive documentation for local setup, data backup, and troubleshooting
- **Habit Tracking**: Long-term habit formation tracking
- **Export/Import**: Enhanced data portability

---

## Contributing

This is currently a personal project, but contributions and suggestions are welcome! If you find bugs or have feature requests, please open an issue.

---

## License

See LICENSE file for details.

---

## Known Limitations & Shortcomings

### Current Limitations

- **Local-Only**: The app currently runs locally only - no online access or multi-device sync
- **No User Accounts**: Single-user system with no authentication or data isolation
- **Mobile Experience**: The interface is designed for desktop - mobile browser experience is not optimized
- **Performance**: With very large datasets (1000+ task instances), some analytics operations may be slow (optimization planned)
- **Experimental Features**: Some features are marked experimental and may change or be removed

### Technical Debt

- **Error Handling**: Some error messages could be more user-friendly
- **Data Validation**: Limited validation on data entry - invalid data can cause issues
- **Testing**: Limited automated testing - mostly manual testing during development
- **Documentation**: Some features need more comprehensive documentation

---

## Status

**Current Status**: Actively developed and used for personal productivity

The core workflow is functional and stable for daily use. Database migration is complete with SQLite as the default backend. The system includes versioned analytics formulas, comprehensive glossary system, and experimental features for formula tuning and goal tracking. Development is ongoing with focus on performance optimization, analytics modularization, and deployment preparation.

**Database Migration**: ✅ **Complete** - SQLite is now the primary backend with CSV fallback
**Analytics Formulas**: ✅ **Versioned** - Execution Score v1.0, Productivity Score v1.1
**Experimental Features**: 🔬 **Active Development** - Formula Control System, Goal Tracking

---

## Notes

- The system is designed to be data-driven: the more you use it, the better the recommendations become
- Database storage (SQLite/PostgreSQL) is now the default - this resolves file locking issues with CSV
- The composite score system is highly customizable - adjust weights to match your priorities
- All analytics formulas are versioned and documented in the Analytics Glossary
- Regular use (daily task completion) provides the most valuable insights
- Experimental features are available but may change - use with awareness that they're under active development
- This is a personal project - some features may be rough around the edges

---

## Support

For issues, questions, or feature requests, please check the documentation in the `docs/` folder or open an issue in the repository.

### Documentation Resources

- **Analytics Formulas**: See `docs/execution_module_v1.0.md` and `docs/productivity_score_v1.1.md`
- **Database Setup**: See `task_aversion_app/DATABASE_SETUP.md`
- **Installation Guide**: See `Install_instructions.txt`
- **Git Workflow**: See `docs/git_branch_strategy_guide.md` and `docs/merge_strategy_low_stress.md`
