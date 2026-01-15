"""
Goal Recommendation Analysis Script

Analyzes historical productivity data to provide recommendations for:
- Goal types (hours/scores vs milestones)
- Goal structure (yearly/quarterly/monthly/weekly/daily)
- Specific goal targets for coding, Coursera, fitness, and music
"""
import os
import sys
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.analytics import Analytics
from backend.productivity_tracker import ProductivityTracker
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager


class GoalRecommendationAnalyzer:
    """Analyze historical data and provide goal recommendations."""
    
    def __init__(self):
        self.analytics = Analytics()
        self.productivity_tracker = ProductivityTracker()
        self.task_manager = TaskManager()
        self.instance_manager = InstanceManager()
        self.default_user_id = "default_user"
        
        # Category keywords for identifying activities
        self.category_keywords = {
            'coding': ['code', 'program', 'develop', 'script', 'app', 'software', 'git', 'github', 'commit', 'debug', 'refactor', 'api', 'database', 'backend', 'frontend', 'task aversion system', 'task aversion', 'aversion system'],
            'coursera': ['coursera', 'course', 'learn', 'study', 'lecture', 'assignment', 'quiz', 'module', 'certificate'],
            'fitness': ['fitness', 'workout', 'exercise', 'gym', 'run', 'running', 'lift', 'lifting', 'cardio', 'strength', 'train', 'training', 'diet', 'nutrition', 'meal'],
            'music': ['music', 'song', 'suno', 'record', 'track', 'audio', 'produce', 'production', 'spotify', 'release', 'backtrack', 'compose', 'mix', 'master']
        }
    
    def identify_task_category(self, task_name: str, task_categories: List[str] = None) -> Optional[str]:
        """Identify which category a task belongs to based on name and categories."""
        name_lower = str(task_name).lower()
        categories_str = ' '.join([str(c).lower() for c in (task_categories or [])])
        combined = f"{name_lower} {categories_str}"
        
        # Check each category
        for category, keywords in self.category_keywords.items():
            if any(keyword in combined for keyword in keywords):
                return category
        
        return None
    
    def load_completed_instances(self) -> pd.DataFrame:
        """Load all completed task instances."""
        # Use the same pattern as analytics.py
        use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
        
        if use_csv:
            use_db = False
        else:
            if not os.getenv('DATABASE_URL'):
                os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
            use_db = True
        
        import json
        def _safe_json(cell):
            if isinstance(cell, dict):
                return cell
            if pd.isna(cell) or cell == '':
                return {}
            try:
                if isinstance(cell, str):
                    return json.loads(cell)
                return {}
            except (json.JSONDecodeError, TypeError):
                return {}
        
        if use_db:
            # Load from database
            try:
                from backend.database import get_session, TaskInstance
                session = get_session()
                try:
                    instances = session.query(TaskInstance).filter(
                        TaskInstance.completed_at.isnot(None),
                        TaskInstance.completed_at != ''
                    ).all()
                    
                    if not instances:
                        return pd.DataFrame()
                    
                    # Convert to list of dicts
                    data = [inst.to_dict() for inst in instances]
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(data).fillna('')
                    
                    # Parse JSON fields
                    if 'actual' in df.columns:
                        df['actual_dict'] = df['actual'].apply(_safe_json)
                    else:
                        df['actual_dict'] = pd.Series([{}] * len(df))
                    
                    # Parse dates
                    df['completed_at_dt'] = pd.to_datetime(df['completed_at'], errors='coerce')
                    df = df[df['completed_at_dt'].notna()]
                    df['completed_date'] = df['completed_at_dt'].dt.date
                    
                    return df
                finally:
                    session.close()
            except Exception as e:
                print(f"[WARNING] Database error loading instances: {e}")
                return pd.DataFrame()
        else:
            # Load from CSV
            self.instance_manager._reload()
            completed = self.instance_manager.df[
                (self.instance_manager.df['status'] == 'completed') &
                (self.instance_manager.df['completed_at'].notna()) &
                (self.instance_manager.df['completed_at'] != '')
            ].copy()
            
            if completed.empty:
                return pd.DataFrame()
            
            # Parse JSON fields
            if 'actual' in completed.columns:
                completed['actual_dict'] = completed['actual'].apply(_safe_json)
            else:
                completed['actual_dict'] = pd.Series([{}] * len(completed))
            
            # Parse dates
            completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
            completed = completed[completed['completed_at_dt'].notna()]
            completed['completed_date'] = completed['completed_at_dt'].dt.date
            
            return completed
    
    def analyze_category_performance(self) -> Dict[str, Any]:
        """Analyze performance by category (coding, coursera, fitness, music)."""
        completed = self.load_completed_instances()
        if completed.empty:
            return {}
        
        # Get task information
        # Note: Analysis script - using user_id=None for analysis across all data
        tasks_df = self.task_manager.get_all(user_id=None)
        task_info = {}
        if not tasks_df.empty:
            for _, task_row in tasks_df.iterrows():
                task_id = task_row.get('task_id', '')
                task_name = task_row.get('name', '')
                categories_str = task_row.get('categories', '[]')
                try:
                    categories = json.loads(categories_str) if isinstance(categories_str, str) else categories_str
                except (json.JSONDecodeError, TypeError):
                    categories = []
                task_info[task_id] = {
                    'name': task_name,
                    'categories': categories
                }
        
        # Categorize instances
        category_data = defaultdict(lambda: {
            'instances': [],
            'total_hours': 0.0,
            'total_minutes': 0.0,
            'task_count': 0,
            'unique_tasks': set(),
            'dates': []
        })
        
        for _, row in completed.iterrows():
            task_id = row.get('task_id', '')
            task_name = row.get('task_name', '')
            task_info_entry = task_info.get(task_id, {'name': task_name, 'categories': []})
            
            category = self.identify_task_category(
                task_info_entry['name'],
                task_info_entry['categories']
            )
            
            if category:
                actual_dict = row.get('actual_dict', {})
                time_minutes = float(actual_dict.get('time_actual_minutes', 0) or 0)
                
                category_data[category]['instances'].append(row)
                category_data[category]['total_minutes'] += time_minutes
                category_data[category]['total_hours'] += time_minutes / 60.0
                category_data[category]['task_count'] += 1
                category_data[category]['unique_tasks'].add(task_id)
                category_data[category]['dates'].append(row['completed_date'])
        
        # Calculate statistics
        results = {}
        for category, data in category_data.items():
            if data['task_count'] == 0:
                continue
            
            dates = sorted(data['dates'])
            if not dates:
                continue
            
            first_date = dates[0]
            last_date = dates[-1]
            days_span = (last_date - first_date).days + 1
            weeks_span = days_span / 7.0
            
            # Calculate averages
            avg_hours_per_week = data['total_hours'] / max(weeks_span, 1)
            avg_hours_per_day = data['total_hours'] / max(days_span, 1)
            avg_minutes_per_instance = data['total_minutes'] / max(data['task_count'], 1)
            
            # Calculate consistency (days with activity / total days)
            unique_days = len(set(dates))
            consistency = (unique_days / max(days_span, 1)) * 100.0
            
            results[category] = {
                'total_hours': round(data['total_hours'], 2),
                'total_minutes': round(data['total_minutes'], 1),
                'task_count': data['task_count'],
                'unique_tasks': len(data['unique_tasks']),
                'first_date': first_date.isoformat(),
                'last_date': last_date.isoformat(),
                'days_span': days_span,
                'weeks_span': round(weeks_span, 1),
                'avg_hours_per_week': round(avg_hours_per_week, 2),
                'avg_hours_per_day': round(avg_hours_per_day, 2),
                'avg_minutes_per_instance': round(avg_minutes_per_instance, 1),
                'consistency_pct': round(consistency, 1),
                'active_days': unique_days
            }
        
        return results
    
    def analyze_productivity_patterns(self) -> Dict[str, Any]:
        """Analyze overall productivity patterns."""
        # Get weekly productivity data
        weekly_data = self.productivity_tracker.calculate_rolling_7day_productivity_hours(
            self.default_user_id
        )
        
        # Get daily data for last 90 days
        daily_data = self.productivity_tracker.get_daily_productivity_data(
            self.default_user_id,
            days=90
        )
        
        if not daily_data:
            return {}
        
        # Calculate statistics
        hours_list = [d['hours'] for d in daily_data]
        work_hours_list = [d['work_hours'] for d in daily_data]
        
        # Weekly aggregation
        weekly_totals = defaultdict(float)
        for day_data in daily_data:
            day_date = datetime.strptime(day_data['date'], '%Y-%m-%d').date()
            week_start = day_date - timedelta(days=day_date.weekday())
            week_key = week_start.isoformat()
            weekly_totals[week_key] += day_data['hours']
        
        weekly_hours = list(weekly_totals.values())
        
        return {
            'current_weekly_hours': round(weekly_data.get('total_hours', 0), 2),
            'avg_daily_hours': round(sum(hours_list) / len(hours_list), 2) if hours_list else 0,
            'avg_weekly_hours': round(sum(weekly_hours) / len(weekly_hours), 2) if weekly_hours else 0,
            'max_weekly_hours': round(max(weekly_hours), 2) if weekly_hours else 0,
            'min_weekly_hours': round(min(weekly_hours), 2) if weekly_hours else 0,
            'std_weekly_hours': round(pd.Series(weekly_hours).std(), 2) if weekly_hours else 0,
            'days_with_data': len([h for h in hours_list if h > 0]),
            'total_days_analyzed': len(daily_data),
            'consistency_pct': round((len([h for h in hours_list if h > 0]) / len(daily_data)) * 100, 1) if daily_data else 0
        }
    
    def recommend_goal_structure(self, category_performance: Dict[str, Any], 
                                  productivity_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend goal structure based on data patterns."""
        recommendations = {
            'goal_type_recommendation': {},
            'time_horizon_recommendation': {},
            'rationale': []
        }
        
        # Analyze consistency
        consistency_scores = {}
        for category, data in category_performance.items():
            consistency_scores[category] = data.get('consistency_pct', 0)
        
        overall_consistency = productivity_patterns.get('consistency_pct', 0)
        
        # Recommendation 1: Hours vs Milestones
        # If consistency is high (>60%), hours work well. If low, milestones may be better.
        for category, consistency in consistency_scores.items():
            if consistency >= 60:
                recommendations['goal_type_recommendation'][category] = {
                    'primary': 'hours',
                    'secondary': 'milestones',
                    'reason': f'High consistency ({consistency:.1f}%) suggests hours-based goals work well'
                }
            elif consistency >= 30:
                recommendations['goal_type_recommendation'][category] = {
                    'primary': 'milestones',
                    'secondary': 'hours',
                    'reason': f'Moderate consistency ({consistency:.1f}%) - milestones provide clearer targets'
                }
            else:
                recommendations['goal_type_recommendation'][category] = {
                    'primary': 'milestones',
                    'secondary': None,
                    'reason': f'Low consistency ({consistency:.1f}%) - focus on specific achievements'
                }
        
        # Recommendation 2: Time Horizon Structure
        # High consistency -> can use weekly/daily goals
        # Low consistency -> focus on monthly/quarterly
        if overall_consistency >= 60:
            recommendations['time_horizon_recommendation'] = {
                'yearly': 'High-level vision and major milestones',
                'quarterly': 'Key achievements and progress checkpoints',
                'monthly': 'Specific targets and habit formation',
                'weekly': 'Actionable targets (primary focus)',
                'daily': 'Task-level execution (not goals, but tasks)',
                'rationale': 'High consistency allows for shorter-term goal cycles'
            }
        elif overall_consistency >= 30:
            recommendations['time_horizon_recommendation'] = {
                'yearly': 'High-level vision and major milestones',
                'quarterly': 'Key achievements and progress checkpoints (primary focus)',
                'monthly': 'Specific targets and habit formation (primary focus)',
                'weekly': 'Supporting targets (secondary)',
                'daily': 'Task-level execution (not goals, but tasks)',
                'rationale': 'Moderate consistency - focus on monthly/quarterly to build habits'
            }
        else:
            recommendations['time_horizon_recommendation'] = {
                'yearly': 'High-level vision and major milestones',
                'quarterly': 'Key achievements and progress checkpoints (primary focus)',
                'monthly': 'Specific targets and habit formation',
                'weekly': 'Supporting targets (use sparingly)',
                'daily': 'Task-level execution (not goals, but tasks)',
                'rationale': 'Low consistency - focus on longer horizons to avoid discouragement'
            }
        
        recommendations['rationale'].append(
            f"Overall consistency: {overall_consistency:.1f}% - "
            f"{'High' if overall_consistency >= 60 else 'Moderate' if overall_consistency >= 30 else 'Low'} consistency pattern"
        )
        
        return recommendations
    
    def generate_specific_goals(self, category_performance: Dict[str, Any],
                                productivity_patterns: Dict[str, Any],
                                goal_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Generate specific goal recommendations."""
        goals = {}
        
        # Calculate baseline multipliers for ambition
        # Use 1.2x for moderate growth, 1.5x for ambitious, 2.0x for very ambitious
        ambition_multipliers = {
            'coding': 1.5,  # Primary focus - be ambitious
            'coursera': 1.3,  # Secondary - moderate growth
            'fitness': 1.4,  # Secondary - good growth
            'music': 1.3  # Secondary - moderate growth
        }
        
        for category in ['coding', 'coursera', 'fitness', 'music']:
            if category not in category_performance:
                # No historical data - suggest starting goals
                goals[category] = {
                    'yearly': self._suggest_starting_yearly_goal(category),
                    'quarterly': self._suggest_starting_quarterly_goal(category),
                    'monthly': self._suggest_starting_monthly_goal(category),
                    'weekly': None,
                    'note': 'No historical data - these are starting suggestions'
                }
                continue
            
            data = category_performance[category]
            goal_type = goal_structure['goal_type_recommendation'].get(category, {}).get('primary', 'hours')
            multiplier = ambition_multipliers.get(category, 1.2)
            
            avg_weekly = data.get('avg_hours_per_week', 0)
            consistency = data.get('consistency_pct', 0)
            
            if goal_type == 'hours':
                # Hours-based goals
                target_weekly = avg_weekly * multiplier
                goals[category] = {
                    'yearly': {
                        'type': 'hours',
                        'target': round(target_weekly * 52, 1),
                        'unit': 'hours',
                        'description': f'{round(target_weekly * 52, 1)} hours total for the year'
                    },
                    'quarterly': {
                        'type': 'hours',
                        'target': round(target_weekly * 13, 1),
                        'unit': 'hours',
                        'description': f'{round(target_weekly * 13, 1)} hours per quarter (~{round(target_weekly, 1)} hrs/week)'
                    },
                    'monthly': {
                        'type': 'hours',
                        'target': round(target_weekly * 4.33, 1),
                        'unit': 'hours',
                        'description': f'{round(target_weekly * 4.33, 1)} hours per month (~{round(target_weekly, 1)} hrs/week)'
                    },
                    'weekly': {
                        'type': 'hours',
                        'target': round(target_weekly, 1),
                        'unit': 'hours',
                        'description': f'{round(target_weekly, 1)} hours per week'
                    } if consistency >= 60 else None,
                    'baseline_avg': round(avg_weekly, 2),
                    'growth_target': f'{multiplier:.1f}x baseline'
                }
            else:
                # Milestone-based goals
                goals[category] = self._generate_milestone_goals(category, data, multiplier)
        
        return goals
    
    def _suggest_starting_yearly_goal(self, category: str) -> Dict[str, Any]:
        """Suggest starting yearly goal when no data exists."""
        suggestions = {
            'coding': {
                'type': 'milestones',
                'targets': [
                    'Deploy app online (hosted, accessible)',
                    'Make first $100 from app',
                    'Complete 2 major feature releases',
                    'Reach 100 active users or 1000 total users'
                ]
            },
            'coursera': {
                'type': 'milestones',
                'targets': [
                    'Complete 2-3 specializations',
                    'Earn 2-3 certificates',
                    'Complete 12 courses'
                ]
            },
            'fitness': {
                'type': 'milestones',
                'targets': [
                    'Reach goal weight (specify target)',
                    'Achieve PR in main lifts (bench/squat/deadlift)',
                    'Run personal best time for 5K/10K',
                    'Maintain consistent workout schedule (3-4x/week)'
                ]
            },
            'music': {
                'type': 'milestones',
                'targets': [
                    'Produce 12 Suno songs',
                    'Record 6 personally recorded songs',
                    'Create 20 backtracks',
                    'Release 2-3 songs on Spotify'
                ]
            }
        }
        return suggestions.get(category, {'type': 'milestones', 'targets': []})
    
    def _suggest_starting_quarterly_goal(self, category: str) -> Dict[str, Any]:
        """Suggest starting quarterly goal when no data exists."""
        suggestions = {
            'coding': {
                'type': 'milestones',
                'targets': [
                    'Complete 1 major feature',
                    'Deploy to production',
                    'Reach milestone user count'
                ]
            },
            'coursera': {
                'type': 'milestones',
                'targets': [
                    'Complete 1 specialization or 3-4 courses'
                ]
            },
            'fitness': {
                'type': 'milestones',
                'targets': [
                    'Achieve 1 PR or reach intermediate weight milestone',
                    'Maintain 3-month consistent schedule'
                ]
            },
            'music': {
                'type': 'milestones',
                'targets': [
                    'Produce 3 Suno songs',
                    'Record 1-2 personally recorded songs',
                    'Create 5 backtracks'
                ]
            }
        }
        return suggestions.get(category, {'type': 'milestones', 'targets': []})
    
    def _suggest_starting_monthly_goal(self, category: str) -> Dict[str, Any]:
        """Suggest starting monthly goal when no data exists."""
        suggestions = {
            'coding': {
                'type': 'hours',
                'target': 40,
                'unit': 'hours',
                'description': '40 hours per month (~10 hrs/week)'
            },
            'coursera': {
                'type': 'hours',
                'target': 20,
                'unit': 'hours',
                'description': '20 hours per month (~5 hrs/week)'
            },
            'fitness': {
                'type': 'hours',
                'target': 16,
                'unit': 'hours',
                'description': '16 hours per month (~4 hrs/week)'
            },
            'music': {
                'type': 'hours',
                'target': 12,
                'unit': 'hours',
                'description': '12 hours per month (~3 hrs/week)'
            }
        }
        return suggestions.get(category, {'type': 'hours', 'target': 0})
    
    def _generate_milestone_goals(self, category: str, data: Dict[str, Any], 
                                   multiplier: float) -> Dict[str, Any]:
        """Generate milestone-based goals for a category."""
        task_count = data.get('task_count', 0)
        weeks_span = data.get('weeks_span', 1)
        avg_tasks_per_week = task_count / max(weeks_span, 1)
        
        milestone_suggestions = {
            'coding': {
                'yearly': [
                    f'Deploy app online and make it accessible',
                    f'Make first $100+ from app',
                    f'Complete {max(2, int(avg_tasks_per_week * 52 * 0.1))} major feature releases',
                    f'Reach milestone user count (100 active or 1000 total)'
                ],
                'quarterly': [
                    f'Complete 1 major feature or release',
                    f'Deploy significant update',
                    f'Reach quarterly user growth target'
                ],
                'monthly': [
                    f'Complete 1 significant feature or bug fix',
                    f'Deploy monthly update'
                ]
            },
            'coursera': {
                'yearly': [
                    f'Complete {max(2, int(avg_tasks_per_week * 52 * 0.2))} specializations',
                    f'Earn {max(2, int(avg_tasks_per_week * 52 * 0.3))} certificates',
                    f'Complete {max(12, int(avg_tasks_per_week * 52 * 0.5))} courses'
                ],
                'quarterly': [
                    f'Complete 1 specialization or 3-4 courses'
                ],
                'monthly': [
                    f'Complete 1 course or 3-4 modules'
                ]
            },
            'fitness': {
                'yearly': [
                    'Reach goal weight (specify target)',
                    'Achieve PR in main lifts (bench/squat/deadlift)',
                    'Run personal best time for 5K/10K',
                    'Maintain consistent schedule (3-4x/week for 6+ months)'
                ],
                'quarterly': [
                    'Achieve 1 PR or reach intermediate weight milestone',
                    'Maintain 3-month consistent schedule'
                ],
                'monthly': [
                    'Achieve monthly workout consistency (12+ sessions)',
                    'Reach monthly weight/strength milestone'
                ]
            },
            'music': {
                'yearly': [
                    f'Produce {max(12, int(avg_tasks_per_week * 52 * 0.2))} Suno songs',
                    f'Record {max(6, int(avg_tasks_per_week * 52 * 0.1))} personally recorded songs',
                    f'Create {max(20, int(avg_tasks_per_week * 52 * 0.3))} backtracks',
                    'Release 2-3 songs on Spotify'
                ],
                'quarterly': [
                    f'Produce {max(3, int(avg_tasks_per_week * 13 * 0.2))} Suno songs',
                    f'Record {max(1, int(avg_tasks_per_week * 13 * 0.1))} personally recorded song',
                    f'Create {max(5, int(avg_tasks_per_week * 13 * 0.3))} backtracks'
                ],
                'monthly': [
                    f'Produce {max(1, int(avg_tasks_per_week * 4.33 * 0.2))} Suno song',
                    f'Create {max(1, int(avg_tasks_per_week * 4.33 * 0.3))} backtrack'
                ]
            }
        }
        
        suggestions = milestone_suggestions.get(category, {})
        
        return {
            'yearly': {
                'type': 'milestones',
                'targets': suggestions.get('yearly', [])
            },
            'quarterly': {
                'type': 'milestones',
                'targets': suggestions.get('quarterly', [])
            },
            'monthly': {
                'type': 'milestones',
                'targets': suggestions.get('monthly', [])
            },
            'weekly': None,
            'baseline_avg_tasks_per_week': round(avg_tasks_per_week, 2),
            'growth_target': f'{multiplier:.1f}x baseline activity'
        }
    
    def generate_report(self) -> str:
        """Generate comprehensive goal recommendation report."""
        print("[INFO] Analyzing category performance...")
        category_performance = self.analyze_category_performance()
        
        print("[INFO] Analyzing productivity patterns...")
        productivity_patterns = self.analyze_productivity_patterns()
        
        print("[INFO] Generating goal structure recommendations...")
        goal_structure = self.recommend_goal_structure(category_performance, productivity_patterns)
        
        print("[INFO] Generating specific goal recommendations...")
        specific_goals = self.generate_specific_goals(category_performance, productivity_patterns, goal_structure)
        
        # Build report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("NEW YEAR'S RESOLUTION GOAL RECOMMENDATIONS")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Overall Productivity Summary
        report_lines.append("OVERALL PRODUCTIVITY SUMMARY")
        report_lines.append("-" * 80)
        if productivity_patterns:
            report_lines.append(f"Current Weekly Hours: {productivity_patterns.get('current_weekly_hours', 0):.1f}")
            report_lines.append(f"Average Weekly Hours: {productivity_patterns.get('avg_weekly_hours', 0):.1f}")
            report_lines.append(f"Consistency: {productivity_patterns.get('consistency_pct', 0):.1f}%")
            report_lines.append(f"Days with Activity: {productivity_patterns.get('days_with_data', 0)} / {productivity_patterns.get('total_days_analyzed', 0)}")
        else:
            report_lines.append("[WARNING] No productivity data available")
        report_lines.append("")
        
        # Category Performance
        report_lines.append("CATEGORY PERFORMANCE ANALYSIS")
        report_lines.append("-" * 80)
        for category in ['coding', 'coursera', 'fitness', 'music']:
            if category in category_performance:
                data = category_performance[category]
                report_lines.append(f"\n{category.upper()}:")
                report_lines.append(f"  Total Hours: {data['total_hours']:.1f}")
                report_lines.append(f"  Average Hours/Week: {data['avg_hours_per_week']:.2f}")
                report_lines.append(f"  Consistency: {data['consistency_pct']:.1f}%")
                report_lines.append(f"  Active Days: {data['active_days']} / {data['days_span']:.0f}")
                report_lines.append(f"  Unique Tasks: {data['unique_tasks']}")
                report_lines.append(f"  Time Span: {data['first_date']} to {data['last_date']}")
            else:
                report_lines.append(f"\n{category.upper()}:")
                report_lines.append(f"  [No historical data found]")
        report_lines.append("")
        
        # Goal Structure Recommendations
        report_lines.append("GOAL STRUCTURE RECOMMENDATIONS")
        report_lines.append("-" * 80)
        report_lines.append("\nGoal Type Recommendations:")
        for category, rec in goal_structure['goal_type_recommendation'].items():
            report_lines.append(f"  {category.upper()}:")
            report_lines.append(f"    Primary: {rec['primary']}")
            if rec.get('secondary'):
                report_lines.append(f"    Secondary: {rec['secondary']}")
            report_lines.append(f"    Reason: {rec['reason']}")
        
        report_lines.append("\nTime Horizon Recommendations:")
        time_rec = goal_structure['time_horizon_recommendation']
        for horizon in ['yearly', 'quarterly', 'monthly', 'weekly', 'daily']:
            if horizon in time_rec:
                report_lines.append(f"  {horizon.upper()}: {time_rec[horizon]}")
        if 'rationale' in time_rec:
            report_lines.append(f"\n  Rationale: {time_rec['rationale']}")
        report_lines.append("")
        
        # Specific Goal Recommendations
        report_lines.append("SPECIFIC GOAL RECOMMENDATIONS")
        report_lines.append("-" * 80)
        for category in ['coding', 'coursera', 'fitness', 'music']:
            report_lines.append(f"\n{category.upper()} GOALS:")
            if category in specific_goals:
                goals = specific_goals[category]
                
                # Yearly
                if 'yearly' in goals:
                    yearly = goals['yearly']
                    report_lines.append(f"\n  YEARLY:")
                    if yearly.get('type') == 'hours':
                        report_lines.append(f"    Target: {yearly['target']} {yearly['unit']}")
                        report_lines.append(f"    Description: {yearly['description']}")
                    else:
                        report_lines.append(f"    Type: Milestones")
                        for target in yearly.get('targets', []):
                            report_lines.append(f"    - {target}")
                
                # Quarterly
                if 'quarterly' in goals:
                    quarterly = goals['quarterly']
                    report_lines.append(f"\n  QUARTERLY:")
                    if quarterly.get('type') == 'hours':
                        report_lines.append(f"    Target: {quarterly['target']} {quarterly['unit']}")
                        report_lines.append(f"    Description: {quarterly['description']}")
                    else:
                        report_lines.append(f"    Type: Milestones")
                        for target in quarterly.get('targets', []):
                            report_lines.append(f"    - {target}")
                
                # Monthly
                if 'monthly' in goals:
                    monthly = goals['monthly']
                    report_lines.append(f"\n  MONTHLY:")
                    if monthly.get('type') == 'hours':
                        report_lines.append(f"    Target: {monthly['target']} {monthly['unit']}")
                        report_lines.append(f"    Description: {monthly['description']}")
                    else:
                        report_lines.append(f"    Type: Milestones")
                        for target in monthly.get('targets', []):
                            report_lines.append(f"    - {target}")
                
                # Weekly
                if 'weekly' in goals and goals['weekly']:
                    weekly = goals['weekly']
                    report_lines.append(f"\n  WEEKLY:")
                    if weekly.get('type') == 'hours':
                        report_lines.append(f"    Target: {weekly['target']} {weekly['unit']}")
                        report_lines.append(f"    Description: {weekly['description']}")
                
                # Baseline info
                if 'baseline_avg' in goals:
                    report_lines.append(f"\n  Baseline Average: {goals['baseline_avg']} hours/week")
                if 'baseline_avg_tasks_per_week' in goals:
                    report_lines.append(f"\n  Baseline Average: {goals['baseline_avg_tasks_per_week']} tasks/week")
                if 'growth_target' in goals:
                    report_lines.append(f"  Growth Target: {goals['growth_target']}")
                if 'note' in goals:
                    report_lines.append(f"\n  Note: {goals['note']}")
            else:
                report_lines.append("  [No recommendations available]")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("RECOMMENDATIONS SUMMARY")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append("KEY INSIGHTS:")
        report_lines.append("")
        report_lines.append("1. GOAL TYPE (Hours vs Milestones):")
        report_lines.append("   - Use HOURS when you have consistent activity patterns")
        report_lines.append("   - Use MILESTONES when consistency is lower or for specific achievements")
        report_lines.append("   - Consider hybrid: hours for maintenance, milestones for breakthroughs")
        report_lines.append("")
        report_lines.append("2. TIME HORIZON STRUCTURE:")
        report_lines.append("   - YEARLY: Vision and major achievements (e.g., 'Make first $1000 from app')")
        report_lines.append("   - QUARTERLY: Key checkpoints (e.g., 'Deploy app online')")
        report_lines.append("   - MONTHLY: Habit formation and specific targets")
        report_lines.append("   - WEEKLY: Actionable targets (only if consistency is high)")
        report_lines.append("   - DAILY: Tasks, not goals (execution level)")
        report_lines.append("")
        report_lines.append("3. CONTROLLABLE FACTORS:")
        report_lines.append("   - Focus on inputs (hours worked, tasks completed) not outputs (money, users)")
        report_lines.append("   - Set goals for what you can control: time invested, consistency, effort")
        report_lines.append("   - Use milestones as outcomes that validate your input-focused work")
        report_lines.append("")
        report_lines.append("4. AMBITION LEVEL:")
        report_lines.append("   - Coding: 1.5x baseline (primary focus - be ambitious)")
        report_lines.append("   - Coursera: 1.3x baseline (secondary - moderate growth)")
        report_lines.append("   - Fitness: 1.4x baseline (secondary - good growth)")
        report_lines.append("   - Music: 1.3x baseline (secondary - moderate growth)")
        report_lines.append("")
        report_lines.append("5. ADJUSTMENT STRATEGY:")
        report_lines.append("   - Review goals monthly and adjust based on actual performance")
        report_lines.append("   - If consistently exceeding goals by 20%+, increase ambition")
        report_lines.append("   - If consistently missing goals by 20%+, reduce or refocus")
        report_lines.append("   - Celebrate progress, not just completion")
        
        return "\n".join(report_lines)


def main():
    """Main execution function."""
    print("=" * 80)
    print("GOAL RECOMMENDATION ANALYSIS")
    print("=" * 80)
    print("")
    
    analyzer = GoalRecommendationAnalyzer()
    
    try:
        report = analyzer.generate_report()
        print(report)
        
        # Save to file
        output_file = os.path.join('data', 'goal_recommendations.txt')
        os.makedirs('data', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("")
        print(f"[SUCCESS] Report saved to: {output_file}")
        
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

