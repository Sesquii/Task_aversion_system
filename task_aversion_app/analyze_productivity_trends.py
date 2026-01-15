"""
Comprehensive Productivity Trend Analysis

Analyzes commit messages, productivity hours, and burnout indicators to provide
goal recommendations for coding, productivity hours, music, and fitness.
"""
import os
import sys
import json
import subprocess
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.productivity_tracker import ProductivityTracker
from backend.analytics import Analytics


class ProductivityTrendAnalyzer:
    """Analyze productivity trends and provide goal recommendations."""
    
    def __init__(self, repo_path: Optional[str] = None):
        """Initialize analyzer.
        
        Args:
            repo_path: Path to git repository (default: parent directory)
        """
        self.productivity_tracker = ProductivityTracker()
        self.analytics = Analytics()
        self.default_user_id = "default_user"
        
        if repo_path is None:
            # Default to parent directory (where .git should be)
            repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.repo_path = repo_path
    
    def get_commit_data(self) -> Dict[str, Any]:
        """Get commit statistics from git repository."""
        try:
            cmd = ['git', 'log', '--format=%H|%ai|%s', '--all', '--reverse']
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = line.split('|', maxsplit=2)
                if len(parts) < 3:
                    continue
                
                commit_hash = parts[0].strip()
                date_str = parts[1].strip()
                subject = parts[2].strip()
                
                try:
                    dt = datetime.strptime(date_str.split()[0] + ' ' + date_str.split()[1], '%Y-%m-%d %H:%M:%S')
                    commits.append({
                        'hash': commit_hash,
                        'date': dt.date(),
                        'datetime': dt,
                        'subject': subject
                    })
                except (ValueError, IndexError):
                    continue
            
            if not commits:
                return {}
            
            # Calculate weekly commit patterns
            commits_by_week = defaultdict(int)
            commits_by_date = defaultdict(int)
            
            for commit in commits:
                week_start = commit['date'] - timedelta(days=commit['date'].weekday())
                week_key = week_start.isoformat()
                commits_by_week[week_key] += 1
                commits_by_date[commit['date']] += 1
            
            first_date = min(c['date'] for c in commits)
            last_date = max(c['date'] for c in commits)
            days_span = (last_date - first_date).days + 1
            
            # Recent weeks (last 4 weeks)
            recent_weeks = []
            today = date.today()
            for i in range(4):
                week_start = today - timedelta(days=today.weekday() + (i * 7))
                week_key = week_start.isoformat()
                recent_weeks.append({
                    'week_start': week_key,
                    'commits': commits_by_week.get(week_key, 0)
                })
            
            # This month's commits
            current_month_start = date(today.year, today.month, 1)
            this_month_commits = [c for c in commits if c['date'] >= current_month_start]
            
            return {
                'total_commits': len(commits),
                'first_commit_date': first_date.isoformat(),
                'last_commit_date': last_date.isoformat(),
                'days_span': days_span,
                'avg_commits_per_day': len(commits) / max(days_span, 1),
                'recent_weeks': recent_weeks,
                'this_month_commits': len(this_month_commits),
                'this_month_avg_per_day': len(this_month_commits) / max((today - current_month_start).days + 1, 1),
                'commits_by_date': dict(commits_by_date),
                'max_commits_per_day': max(commits_by_date.values()) if commits_by_date else 0
            }
        except Exception as e:
            print(f"[WARNING] Could not get commit data: {e}")
            return {}
    
    def analyze_productivity_score_per_hour(self, days: int = 90) -> Dict[str, Any]:
        """Analyze productivity score per hour to detect efficiency changes.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with score per hour analysis
        """
        # Load completed instances
        daily_data = self.productivity_tracker.get_daily_productivity_data(
            self.default_user_id,
            days=days
        )
        
        if not daily_data:
            return {}
        
        # Load instances to calculate productivity scores
        use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
        if not use_csv:
            if not os.getenv('DATABASE_URL'):
                os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
        
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
        
        if not use_csv:
            try:
                from backend.database import get_session, TaskInstance
                session = get_session()
                try:
                    instances = session.query(TaskInstance).filter(
                        TaskInstance.completed_at.isnot(None),
                        TaskInstance.completed_at != ''
                    ).all()
                    
                    if not instances:
                        return {}
                    
                    data = [inst.to_dict() for inst in instances]
                    df = pd.DataFrame(data).fillna('')
                    
                    if 'actual' in df.columns:
                        df['actual_dict'] = df['actual'].apply(_safe_json)
                    else:
                        df['actual_dict'] = pd.Series([{}] * len(df))
                    
                    df['completed_at_dt'] = pd.to_datetime(df['completed_at'], errors='coerce')
                    df = df[df['completed_at_dt'].notna()]
                    df['completed_date'] = df['completed_at_dt'].dt.date
                finally:
                    session.close()
            except Exception:
                return {}
        else:
            from backend.instance_manager import InstanceManager
            im = InstanceManager()
            im._reload()
            df = im.df[
                (im.df['status'] == 'completed') &
                (im.df['completed_at'].notna()) &
                (im.df['completed_at'] != '')
            ].copy()
            
            if 'actual' in df.columns:
                df['actual_dict'] = df['actual'].apply(_safe_json)
            else:
                df['actual_dict'] = pd.Series([{}] * len(df))
            
            df['completed_at_dt'] = pd.to_datetime(df['completed_at'], errors='coerce')
            df = df[df['completed_at_dt'].notna()]
            df['completed_date'] = df['completed_at_dt'].dt.date
        
        # Filter to date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        df = df[(df['completed_date'] >= start_date) & (df['completed_date'] <= end_date)]
        
        if df.empty:
            return {}
        
        # Get task types
        from backend.task_manager import TaskManager
        tm = TaskManager()
        # Note: Analysis script - using user_id=None for analysis across all data
        tasks_df = tm.get_all(user_id=None)
        task_type_map = {}
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            for _, row in tasks_df.iterrows():
                task_id = row.get('task_id', '')
                task_type = row.get('task_type', 'Work')
                task_type_map[task_id] = str(task_type).strip().lower()
        
        df['task_type'] = df['task_id'].map(task_type_map).fillna('work')
        productive_types = ['work', 'self care', 'selfcare', 'self-care']
        df = df[df['task_type'].isin(productive_types)]
        
        # Calculate hours and productivity scores
        def _get_time_minutes(row):
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('time_actual_minutes', 0) or 0)
            return 0.0
        
        df['time_minutes'] = df.apply(_get_time_minutes, axis=1)
        df = df[df['time_minutes'] > 0]
        df['time_hours'] = df['time_minutes'] / 60.0
        
        # Calculate productivity scores
        df['week_start'] = df['completed_date'].apply(
            lambda d: (d - timedelta(days=d.weekday())).isoformat()
        )
        
        # Calculate scores (simplified - without all parameters)
        df['productivity_score'] = df.apply(
            lambda row: self.analytics.calculate_productivity_score(
                row,
                self_care_tasks_per_day={},
                weekly_avg_time=0.0,
                work_play_time_per_day=None,
                play_penalty_threshold=2.0,
                productivity_settings=None,
                weekly_work_summary=None,
                goal_hours_per_week=None,
                weekly_productive_hours=None
            ),
            axis=1
        )
        
        # Calculate weekly score per hour
        weekly_stats = df.groupby('week_start').agg({
            'productivity_score': 'sum',
            'time_hours': 'sum'
        }).reset_index()
        
        weekly_stats['score_per_hour'] = weekly_stats['productivity_score'] / weekly_stats['time_hours']
        weekly_stats = weekly_stats.sort_values('week_start')
        
        # Compare baseline vs recent
        if len(weekly_stats) >= 4:
            baseline = weekly_stats.head(4)
            recent = weekly_stats.tail(4)
            
            baseline_score_per_hour = baseline['score_per_hour'].mean()
            recent_score_per_hour = recent['score_per_hour'].mean()
            change_pct = ((recent_score_per_hour - baseline_score_per_hour) / max(baseline_score_per_hour, 1)) * 100
        else:
            baseline_score_per_hour = weekly_stats['score_per_hour'].mean() if len(weekly_stats) > 0 else 0
            recent_score_per_hour = baseline_score_per_hour
            change_pct = 0
        
        # Trend analysis
        score_per_hour_list = weekly_stats['score_per_hour'].tolist()
        if len(score_per_hour_list) >= 3:
            trend = 'decreasing' if score_per_hour_list[-1] < score_per_hour_list[-2] < score_per_hour_list[-3] else \
                   'increasing' if score_per_hour_list[-1] > score_per_hour_list[-2] > score_per_hour_list[-3] else 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'baseline_score_per_hour': round(baseline_score_per_hour, 2),
            'recent_score_per_hour': round(recent_score_per_hour, 2),
            'change_pct': round(change_pct, 1),
            'trend': trend,
            'weekly_data': weekly_stats.to_dict('records'),
            'indicates_burnout': change_pct < -15 and trend == 'decreasing'  # Significant decrease
        }
    
    def analyze_productivity_trends(self, days: int = 90) -> Dict[str, Any]:
        """Analyze productivity trends over time.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        daily_data = self.productivity_tracker.get_daily_productivity_data(
            self.default_user_id,
            days=days
        )
        
        if not daily_data:
            return {}
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(daily_data)
        df['date'] = pd.to_datetime(df['date'])
        df['week_start'] = df['date'].apply(lambda d: (d.date() - timedelta(days=d.weekday())).isoformat())
        
        # Calculate weekly totals
        weekly_totals = df.groupby('week_start').agg({
            'hours': 'sum',
            'work_hours': 'sum',
            'self_care_hours': 'sum',
            'task_count': 'sum'
        }).reset_index()
        
        weekly_totals = weekly_totals.sort_values('week_start')
        
        # Identify baseline period (first few weeks) vs recent period
        if len(weekly_totals) >= 4:
            baseline_weeks = weekly_totals.head(4)
            recent_weeks = weekly_totals.tail(4)
            
            baseline_avg = baseline_weeks['hours'].mean()
            recent_avg = recent_weeks['hours'].mean()
            current_week = weekly_totals.iloc[-1]['hours'] if len(weekly_totals) > 0 else 0
        else:
            baseline_avg = weekly_totals['hours'].mean() if len(weekly_totals) > 0 else 0
            recent_avg = baseline_avg
            current_week = weekly_totals.iloc[-1]['hours'] if len(weekly_totals) > 0 else 0
        
        # Detect burnout indicators
        # 1. Sudden spike in hours
        hours_list = weekly_totals['hours'].tolist()
        if len(hours_list) >= 3:
            recent_avg_hours = sum(hours_list[-3:]) / 3
            earlier_avg_hours = sum(hours_list[:-3]) / max(len(hours_list) - 3, 1) if len(hours_list) > 3 else recent_avg_hours
            spike_ratio = recent_avg_hours / max(earlier_avg_hours, 1)
        else:
            spike_ratio = 1.0
        
        # 2. Consistency (days with activity)
        days_with_activity = len(df[df['hours'] > 0])
        total_days = len(df)
        consistency = (days_with_activity / total_days) * 100 if total_days > 0 else 0
        
        # 3. Recent trend (increasing/decreasing)
        if len(hours_list) >= 3:
            recent_trend = 'increasing' if hours_list[-1] > hours_list[-2] > hours_list[-3] else \
                          'decreasing' if hours_list[-1] < hours_list[-2] < hours_list[-3] else 'stable'
        else:
            recent_trend = 'insufficient_data'
        
        return {
            'daily_data': daily_data,
            'weekly_totals': weekly_totals.to_dict('records'),
            'baseline_avg_hours_per_week': round(baseline_avg, 2),
            'recent_avg_hours_per_week': round(recent_avg, 2),
            'current_week_hours': round(current_week, 2),
            'spike_ratio': round(spike_ratio, 2),
            'consistency_pct': round(consistency, 1),
            'recent_trend': recent_trend,
            'total_weeks': len(weekly_totals),
            'avg_hours_per_week': round(weekly_totals['hours'].mean(), 2),
            'max_weekly_hours': round(weekly_totals['hours'].max(), 2),
            'min_weekly_hours': round(weekly_totals['hours'].min(), 2),
            'std_weekly_hours': round(weekly_totals['hours'].std(), 2)
        }
    
    def detect_burnout_indicators(self, productivity_trends: Dict[str, Any],
                                  commit_data: Dict[str, Any],
                                  score_per_hour: Dict[str, Any] = None) -> Dict[str, Any]:
        """Detect potential burnout indicators.
        
        Args:
            productivity_trends: Results from analyze_productivity_trends
            commit_data: Results from get_commit_data
            
        Returns:
            Dictionary with burnout analysis
        """
        indicators = {
            'warnings': [],
            'concerns': [],
            'positive_signs': [],
            'overall_assessment': 'unknown'
        }
        
        # Check 1: Sudden spike in hours
        spike_ratio = productivity_trends.get('spike_ratio', 1.0)
        if spike_ratio > 3.0:
            indicators['warnings'].append(
                f"Productivity spike detected: {spike_ratio:.1f}x increase from baseline. "
                "This level of increase may be unsustainable."
            )
        elif spike_ratio > 2.0:
            indicators['concerns'].append(
                f"Significant productivity increase: {spike_ratio:.1f}x from baseline. "
                "Monitor for sustainability."
            )
        else:
            indicators['positive_signs'].append(
                f"Productivity increase is moderate: {spike_ratio:.1f}x from baseline."
            )
        
        # Check 2: Current hours vs sustainable levels
        current_week = productivity_trends.get('current_week_hours', 0)
        recent_avg = productivity_trends.get('recent_avg_hours_per_week', 0)
        
        if current_week >= 49 or recent_avg >= 45:
            indicators['warnings'].append(
                f"Very high hours: {current_week:.1f} hrs/week. "
                "49+ hours/week (7+ hrs/day) is typically unsustainable long-term."
            )
        elif current_week >= 40 or recent_avg >= 40:
            indicators['concerns'].append(
                f"High hours: {current_week:.1f} hrs/week. "
                "40+ hours/week is high but may be sustainable if well-managed."
            )
        else:
            indicators['positive_signs'].append(
                f"Hours are in reasonable range: {current_week:.1f} hrs/week."
            )
        
        # Check 3: Consistency
        consistency = productivity_trends.get('consistency_pct', 0)
        if consistency < 50:
            indicators['concerns'].append(
                f"Low consistency: {consistency:.1f}% of days have activity. "
                "This may indicate burnout or motivation issues."
            )
        elif consistency >= 80:
            indicators['positive_signs'].append(
                f"High consistency: {consistency:.1f}% of days have activity."
            )
        
        # Check 4: Commit patterns (coding intensity)
        if commit_data:
            this_month_commits = commit_data.get('this_month_commits', 0)
            days_in_month = (date.today() - date(date.today().year, date.today().month, 1)).days + 1
            commits_per_day = this_month_commits / max(days_in_month, 1)
            
            if commits_per_day > 5:
                indicators['concerns'].append(
                    f"High coding intensity: {commits_per_day:.1f} commits/day this month. "
                    "Very rapid iteration may indicate unsustainable pace."
                )
            elif commits_per_day > 3:
                indicators['positive_signs'].append(
                    f"Active coding: {commits_per_day:.1f} commits/day this month."
                )
        
        # Check 5: Productivity score per hour (efficiency)
        if score_per_hour:
            change_pct = score_per_hour.get('change_pct', 0)
            trend = score_per_hour.get('trend', 'unknown')
            indicates_burnout = score_per_hour.get('indicates_burnout', False)
            
            if indicates_burnout:
                indicators['warnings'].append(
                    f"Productivity score per hour decreasing: {change_pct:.1f}% decrease from baseline. "
                    f"Trend: {trend}. This suggests efficiency is declining as hours increase - potential burnout indicator."
                )
            elif change_pct < -10:
                indicators['concerns'].append(
                    f"Productivity score per hour decreased: {change_pct:.1f}% from baseline. "
                    "Monitor efficiency trends."
                )
            elif change_pct > 10:
                indicators['positive_signs'].append(
                    f"Productivity score per hour increased: {change_pct:.1f}% from baseline. "
                    "Efficiency is improving!"
                )
            else:
                indicators['positive_signs'].append(
                    f"Productivity score per hour stable: {change_pct:.1f}% change. "
                    "Efficiency maintained despite increased hours."
                )
        
        # Overall assessment
        if len(indicators['warnings']) >= 2:
            indicators['overall_assessment'] = 'high_risk'
        elif len(indicators['warnings']) >= 1 or len(indicators['concerns']) >= 2:
            indicators['overall_assessment'] = 'moderate_risk'
        elif len(indicators['positive_signs']) >= 2 and len(indicators['concerns']) == 0:
            indicators['overall_assessment'] = 'low_risk'
        else:
            indicators['overall_assessment'] = 'moderate_risk'
        
        return indicators
    
    def recommend_productivity_goals(self, productivity_trends: Dict[str, Any],
                                     burnout_indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend productivity hour goals.
        
        Args:
            productivity_trends: Results from analyze_productivity_trends
            burnout_indicators: Results from detect_burnout_indicators
            
        Returns:
            Dictionary with goal recommendations
        """
        baseline = productivity_trends.get('baseline_avg_hours_per_week', 10)
        recent_avg = productivity_trends.get('recent_avg_hours_per_week', 35)
        current_week = productivity_trends.get('current_week_hours', 35)
        assessment = burnout_indicators.get('overall_assessment', 'moderate_risk')
        
        recommendations = {
            'conservative_goal': None,
            'moderate_goal': None,
            'ambitious_goal': None,
            'recommended_goal': None,
            'rationale': []
        }
        
        # Conservative: Average of baseline and recent, or 30 hrs/week
        conservative = min(30, (baseline + recent_avg) / 2)
        recommendations['conservative_goal'] = round(conservative, 1)
        
        # Moderate: Recent average with slight reduction for sustainability
        moderate = recent_avg * 0.9  # 10% reduction from recent peak
        recommendations['moderate_goal'] = round(moderate, 1)
        
        # Ambitious: 49 hrs/week (7 hrs/day) - user's suggestion
        recommendations['ambitious_goal'] = 49.0
        
        # Recommended based on assessment
        if assessment == 'high_risk':
            recommendations['recommended_goal'] = recommendations['conservative_goal']
            recommendations['rationale'].append(
                "High burnout risk detected. Recommend conservative goal to prevent burnout."
            )
        elif assessment == 'moderate_risk':
            recommendations['recommended_goal'] = recommendations['moderate_goal']
            recommendations['rationale'].append(
                "Some concerns detected. Recommend moderate goal that's sustainable."
            )
        else:
            # Low risk - can be more ambitious but still sustainable
            recommended = min(40, recent_avg * 0.95)
            recommendations['recommended_goal'] = round(recommended, 1)
            recommendations['rationale'].append(
                "Low burnout risk. Can sustain higher hours but recommend gradual increase."
            )
        
        # Additional rationale
        recommendations['rationale'].append(
            f"Baseline was {baseline:.1f} hrs/week, recent average is {recent_avg:.1f} hrs/week."
        )
        recommendations['rationale'].append(
            f"49 hrs/week (7 hrs/day) is very ambitious - consider this a stretch goal, not a target."
        )
        recommendations['rationale'].append(
            "30 hrs/week average over the year balances ambition with sustainability."
        )
        recommendations['rationale'].append(
            "Since you're iterating rapidly, you may be able to maintain higher hours short-term, "
            "but long-term sustainability should be the priority."
        )
        
        return recommendations
    
    def recommend_coding_goals(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend coding goals for this month based on commit patterns.
        
        Args:
            commit_data: Results from get_commit_data
            
        Returns:
            Dictionary with coding goal recommendations
        """
        if not commit_data:
            return {
                'this_month_commits': 0,
                'recommended_commits': 0,
                'recommended_hours': 0,
                'rationale': ['No commit data available']
            }
        
        this_month_commits = commit_data.get('this_month_commits', 0)
        today = date.today()
        month_start = date(today.year, today.month, 1)
        # Calculate next month start
        if today.month == 12:
            next_month_start = date(today.year + 1, 1, 1)
        else:
            next_month_start = date(today.year, today.month + 1, 1)
        days_elapsed = (today - month_start).days + 1
        days_remaining = (next_month_start - today).days
        total_days_in_month = (next_month_start - month_start).days
        
        # User's target: 150-200 commits/month
        target_min = 150
        target_max = 200
        
        # Calculate what's needed
        commits_needed_min = max(0, target_min - this_month_commits)
        commits_needed_max = max(0, target_max - this_month_commits)
        
        # Estimate hours (rough: 1.5 hrs per commit average)
        hours_needed_min = commits_needed_min * 1.5
        hours_needed_max = commits_needed_max * 1.5
        
        # Daily pace needed
        commits_per_day_needed_min = commits_needed_min / max(days_remaining, 1)
        commits_per_day_needed_max = commits_needed_max / max(days_remaining, 1)
        
        # Historical average for context
        historical_avg = commit_data.get('avg_commits_per_day', 3.5)
        historical_weekly = commit_data.get('avg_commits_per_day', 3.5) * 7
        
        # Conservative: Lower end of range
        conservative_commits = target_min
        conservative_hours = conservative_commits * 1.5
        
        # Moderate: Middle of range
        moderate_commits = int((target_min + target_max) / 2)
        moderate_hours = moderate_commits * 1.5
        
        # Ambitious: Upper end of range
        ambitious_commits = target_max
        ambitious_hours = ambitious_commits * 1.5
        
        return {
            'this_month_commits': this_month_commits,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'total_days_in_month': total_days_in_month,
            'target_range': {'min': target_min, 'max': target_max},
            'commits_needed': {'min': commits_needed_min, 'max': commits_needed_max},
            'commits_per_day_needed': {
                'min': round(commits_per_day_needed_min, 1),
                'max': round(commits_per_day_needed_max, 1)
            },
            'conservative_target': {
                'commits': conservative_commits,
                'hours': round(conservative_hours, 1)
            },
            'moderate_target': {
                'commits': moderate_commits,
                'hours': round(moderate_hours, 1)
            },
            'ambitious_target': {
                'commits': ambitious_commits,
                'hours': round(ambitious_hours, 1)
            },
            'recommended_target': 'moderate',
            'rationale': [
                f"Target range: {target_min}-{target_max} commits/month",
                f"Need {commits_needed_min}-{commits_needed_max} more commits ({round(hours_needed_min, 1)}-{round(hours_needed_max, 1)} hrs)",
                f"Daily pace needed: {round(commits_per_day_needed_min, 1)}-{round(commits_per_day_needed_max, 1)} commits/day",
                f"Historical average: {historical_avg:.1f} commits/day ({historical_weekly:.0f}/week)"
            ]
        }
    
    def recommend_music_goals(self) -> Dict[str, Any]:
        """Recommend music goals based on user's time estimates and preferences.
        
        Returns:
            Dictionary with music goal recommendations
        """
        # User's time estimates:
        # - 30 min for Suno song
        # - 3-4 hours for own version
        # - 2-3 hours for backtrack
        # - Top 5% for Spotify release
        
        suno_time = 0.5  # hours
        own_version_time = 3.5  # hours (average of 3-4)
        backtrack_time = 2.5  # hours (average of 2-3)
        
        # User's preferences:
        # - 80% Suno, 10% self-recorded, 10% backtracks
        # - 10-15 hours/month instead of 7
        
        monthly_hours = 12.5  # Middle of 10-15 range
        weekly_hours = monthly_hours / 4.33
        
        # Calculate based on 80/10/10 ratio
        # Total time = (0.8 * suno_count * 0.5) + (0.1 * own_count * 3.5) + (0.1 * backtrack_count * 2.5)
        # For simplicity, let's work backwards from hours
        
        # If 80% Suno, 10% own, 10% backtrack:
        # Let x = number of own versions
        # Then: 8x Suno songs, x own versions, x backtracks
        # Time = (8x * 0.5) + (x * 3.5) + (x * 2.5) = 4x + 3.5x + 2.5x = 10x
        # So x = monthly_hours / 10
        
        own_versions_per_month = monthly_hours / 10.0
        suno_per_month = own_versions_per_month * 8
        backtracks_per_month = own_versions_per_month
        
        # Round to reasonable numbers
        own_versions_per_month = round(own_versions_per_month)
        suno_per_month = round(suno_per_month)
        backtracks_per_month = round(backtracks_per_month)
        
        # Recalculate actual hours
        actual_hours = (suno_per_month * suno_time) + (own_versions_per_month * own_version_time) + (backtracks_per_month * backtrack_time)
        
        # Spotify releases (top 5% of own versions)
        own_versions_per_year = own_versions_per_month * 12
        spotify_releases = max(1, int(own_versions_per_year * 0.05))
        
        return {
            'monthly_hours': round(monthly_hours, 1),
            'weekly_hours': round(weekly_hours, 1),
            'monthly': {
                'suno_songs': suno_per_month,
                'own_versions': own_versions_per_month,
                'backtracks': backtracks_per_month,
                'total_hours': round(actual_hours, 1)
            },
            'yearly': {
                'suno_songs': suno_per_month * 12,
                'own_versions': own_versions_per_month * 12,
                'backtracks': backtracks_per_month * 12,
                'spotify_releases': spotify_releases
            },
            'ratio': '80% Suno, 10% own versions, 10% backtracks',
            'rationale': [
                f"Monthly target: {round(monthly_hours, 1)} hrs/month ({round(weekly_hours, 1)} hrs/week)",
                f"Breakdown: {suno_per_month} Suno ({suno_per_month * suno_time:.1f} hrs), "
                f"{own_versions_per_month} own version ({own_versions_per_month * own_version_time:.1f} hrs), "
                f"{backtracks_per_month} backtrack ({backtracks_per_month * backtrack_time:.1f} hrs)",
                f"Yearly: {suno_per_month * 12} Suno, {own_versions_per_month * 12} own versions, "
                f"{backtracks_per_month * 12} backtracks, {spotify_releases} Spotify releases (top 5%)"
            ]
        }
    
    def analyze_category_productivity(self, days: int = 90) -> Dict[str, Any]:
        """Analyze productivity by category (coding, music, coursera, self-care).
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with category analysis
        """
        # Load completed instances
        use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
        if not use_csv:
            if not os.getenv('DATABASE_URL'):
                os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
        
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
        
        if not use_csv:
            try:
                from backend.database import get_session, TaskInstance
                session = get_session()
                try:
                    instances = session.query(TaskInstance).filter(
                        TaskInstance.completed_at.isnot(None),
                        TaskInstance.completed_at != ''
                    ).all()
                    
                    if not instances:
                        return {}
                    
                    data = [inst.to_dict() for inst in instances]
                    df = pd.DataFrame(data).fillna('')
                    
                    if 'actual' in df.columns:
                        df['actual_dict'] = df['actual'].apply(_safe_json)
                    else:
                        df['actual_dict'] = pd.Series([{}] * len(df))
                    
                    df['completed_at_dt'] = pd.to_datetime(df['completed_at'], errors='coerce')
                    df = df[df['completed_at_dt'].notna()]
                    df['completed_date'] = df['completed_at_dt'].dt.date
                finally:
                    session.close()
            except Exception as e:
                print(f"[WARNING] Could not load instances: {e}")
                return {}
        else:
            from backend.instance_manager import InstanceManager
            im = InstanceManager()
            im._reload()
            df = im.df[
                (im.df['status'] == 'completed') &
                (im.df['completed_at'].notna()) &
                (im.df['completed_at'] != '')
            ].copy()
            
            if 'actual' in df.columns:
                df['actual_dict'] = df['actual'].apply(_safe_json)
            else:
                df['actual_dict'] = pd.Series([{}] * len(df))
            
            df['completed_at_dt'] = pd.to_datetime(df['completed_at'], errors='coerce')
            df = df[df['completed_at_dt'].notna()]
            df['completed_date'] = df['completed_at_dt'].dt.date
        
        # Filter to date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        df = df[(df['completed_date'] >= start_date) & (df['completed_date'] <= end_date)]
        
        if df.empty:
            return {}
        
        # Get task information for categorization
        from backend.task_manager import TaskManager
        tm = TaskManager()
        # Note: Analysis script - using user_id=None for analysis across all data
        tasks_df = tm.get_all(user_id=None)
        task_info = {}
        if not tasks_df.empty:
            for _, task_row in tasks_df.iterrows():
                task_id = task_row.get('task_id', '')
                task_name = task_row.get('name', '')
                categories_str = task_row.get('categories', '[]')
                task_type = str(task_row.get('task_type', 'Work')).strip().lower()
                try:
                    categories = json.loads(categories_str) if isinstance(categories_str, str) else categories_str
                except (json.JSONDecodeError, TypeError):
                    categories = []
                task_info[task_id] = {
                    'name': task_name,
                    'categories': categories,
                    'task_type': task_type
                }
        
        # Category keywords
        category_keywords = {
            'coding': ['code', 'program', 'develop', 'script', 'app', 'software', 'git', 'github', 'commit', 'debug', 'refactor', 'api', 'database', 'backend', 'frontend', 'task aversion', 'aversion system', 'feature', 'fix', 'bug', 'ui', 'analytics', 'migration', 'schema', 'sql'],
            'coursera': ['coursera', 'course', 'learn', 'study', 'lecture', 'assignment', 'quiz', 'module', 'certificate'],
            'music': ['music', 'song', 'suno', 'record', 'track', 'audio', 'produce', 'production', 'spotify', 'release', 'backtrack', 'compose', 'mix', 'master'],
            'self_care': ['self care', 'selfcare', 'self-care']  # Will also check task_type
        }
        
        def identify_category(task_id: str, task_name: str) -> str:
            """Identify category for a task."""
            info = task_info.get(task_id, {'name': task_name, 'categories': [], 'task_type': 'work'})
            name_lower = str(info['name']).lower()
            categories_str = ' '.join([str(c).lower() for c in info.get('categories', [])])
            combined = f"{name_lower} {categories_str}"
            
            # Check self-care first (by task_type)
            if info.get('task_type') in ['self care', 'selfcare', 'self-care']:
                return 'self_care'
            
            # Check other categories
            for category, keywords in category_keywords.items():
                if category == 'self_care':
                    continue  # Already checked
                if any(keyword in combined for keyword in keywords):
                    return category
            
            return 'other'
        
        # Categorize tasks
        df['category'] = df.apply(lambda row: identify_category(row.get('task_id', ''), row.get('task_name', '')), axis=1)
        
        # Calculate time and scores
        def _get_time_minutes(row):
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('time_actual_minutes', 0) or 0)
            return 0.0
        
        df['time_minutes'] = df.apply(_get_time_minutes, axis=1)
        df = df[df['time_minutes'] > 0]
        df['time_hours'] = df['time_minutes'] / 60.0
        
        # Calculate productivity scores
        df['productivity_score'] = df.apply(
            lambda row: self.analytics.calculate_productivity_score(
                row,
                self_care_tasks_per_day={},
                weekly_avg_time=0.0,
                work_play_time_per_day=None,
                play_penalty_threshold=2.0,
                productivity_settings=None,
                weekly_work_summary=None,
                goal_hours_per_week=None,
                weekly_productive_hours=None
            ),
            axis=1
        )
        
        # Analyze by category
        category_stats = {}
        for category in ['coding', 'music', 'coursera', 'self_care', 'other']:
            cat_df = df[df['category'] == category]
            
            if len(cat_df) == 0:
                continue
            
            total_hours = cat_df['time_hours'].sum()
            total_score = cat_df['productivity_score'].sum()
            task_count = len(cat_df)
            
            score_per_hour = total_score / total_hours if total_hours > 0 else 0
            tasks_per_hour = task_count / total_hours if total_hours > 0 else 0
            hours_per_task = total_hours / task_count if task_count > 0 else 0
            
            category_stats[category] = {
                'total_hours': round(total_hours, 2),
                'total_score': round(total_score, 2),
                'task_count': task_count,
                'score_per_hour': round(score_per_hour, 2),
                'tasks_per_hour': round(tasks_per_hour, 2),
                'hours_per_task': round(hours_per_task, 2),
                'percentage_of_total_hours': 0,  # Will calculate after
                'percentage_of_total_tasks': 0   # Will calculate after
            }
        
        # Calculate percentages
        total_hours_all = sum(s['total_hours'] for s in category_stats.values())
        total_tasks_all = sum(s['task_count'] for s in category_stats.values())
        
        for category in category_stats:
            if total_hours_all > 0:
                category_stats[category]['percentage_of_total_hours'] = round(
                    (category_stats[category]['total_hours'] / total_hours_all) * 100, 1
                )
            if total_tasks_all > 0:
                category_stats[category]['percentage_of_total_tasks'] = round(
                    (category_stats[category]['task_count'] / total_tasks_all) * 100, 1
                )
        
        # Find best productivity per hour
        best_category = None
        best_score_per_hour = 0
        for category, stats in category_stats.items():
            if stats['score_per_hour'] > best_score_per_hour:
                best_score_per_hour = stats['score_per_hour']
                best_category = category
        
        return {
            'categories': category_stats,
            'best_productivity_per_hour': {
                'category': best_category,
                'score_per_hour': round(best_score_per_hour, 2)
            } if best_category else None,
            'total_hours': round(total_hours_all, 2),
            'total_tasks': total_tasks_all
        }
    
    def recommend_fitness_goals(self) -> Dict[str, Any]:
        """Recommend fitness goals based on user's description.
        
        Returns:
            Dictionary with fitness goal recommendations
        """
        return {
            'walking': {
                'goal': '3-5+ walks per week',
                'tracking': 'Track as self-care (not including social/play walks)',
                'rationale': 'Walking is low-barrier and helps maintain consistency',
                'target': '3-5 walks/week minimum'
            },
            'lifting': {
                'goal': '30-50 sets per week',
                'tracking': 'Track sets completed, not just workouts',
                'rationale': 'Volume-based tracking is more precise than workout count',
                'target': '30-50 sets/week',
                'milestones': [
                    'Month 1: Build to 30 sets/week consistently',
                    'Month 2-3: Maintain 30-40 sets/week',
                    'Month 4+: Reach 40-50 sets/week'
                ]
            },
            'running': {
                'goal': 'Track miles run per week',
                'tracking': 'Track total miles, not just runs',
                'rationale': 'Volume-based tracking allows flexibility in workout structure',
                'target': 'Set weekly mile target based on current fitness level'
            },
            'body_composition': {
                'goal': 'Get leaner',
                'tracking': 'Caliper skinfold and weight measurements regularly (weekly/monthly)',
                'rationale': 'Long-term goal, focus on process (sets, miles, nutrition)',
                'note': 'Best tracking available: caliper + weight, focus on trends not daily fluctuations'
            },
            'current_status': {
                'note': 'Was at 2-3x/week beginning of December, fell off around Christmas',
                'recommendation': 'Rebuild habit gradually, focus on sets/miles not workout frequency'
            },
            'recommended_structure': {
                'type': 'volume-based (sets, miles, walks)',
                'rationale': 'Volume-based goals are more flexible and measurable than workout frequency'
            }
        }
    
    def generate_comprehensive_report(self) -> str:
        """Generate comprehensive analysis report."""
        print("[INFO] Analyzing commit patterns...")
        commit_data = self.get_commit_data()
        
        print("[INFO] Analyzing productivity trends...")
        productivity_trends = self.analyze_productivity_trends(days=90)
        
        print("[INFO] Analyzing productivity score per hour...")
        score_per_hour = self.analyze_productivity_score_per_hour(days=90)
        
        print("[INFO] Detecting burnout indicators...")
        burnout_indicators = self.detect_burnout_indicators(productivity_trends, commit_data, score_per_hour)
        
        print("[INFO] Analyzing category productivity...")
        category_productivity = self.analyze_category_productivity(days=90)
        
        print("[INFO] Generating goal recommendations...")
        productivity_goals = self.recommend_productivity_goals(productivity_trends, burnout_indicators)
        coding_goals = self.recommend_coding_goals(commit_data)
        music_goals = self.recommend_music_goals()
        fitness_goals = self.recommend_fitness_goals()
        
        # Build report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("COMPREHENSIVE PRODUCTIVITY TREND ANALYSIS & GOAL RECOMMENDATIONS")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Productivity Trends
        report_lines.append("PRODUCTIVITY TRENDS")
        report_lines.append("-" * 80)
        if productivity_trends:
            report_lines.append(f"Baseline Average: {productivity_trends.get('baseline_avg_hours_per_week', 0):.1f} hrs/week")
            report_lines.append(f"Recent Average: {productivity_trends.get('recent_avg_hours_per_week', 0):.1f} hrs/week")
            report_lines.append(f"Current Week: {productivity_trends.get('current_week_hours', 0):.1f} hrs/week")
            report_lines.append(f"Spike Ratio: {productivity_trends.get('spike_ratio', 1.0):.2f}x")
            report_lines.append(f"Consistency: {productivity_trends.get('consistency_pct', 0):.1f}%")
            report_lines.append(f"Recent Trend: {productivity_trends.get('recent_trend', 'unknown')}")
        else:
            report_lines.append("[WARNING] No productivity data available")
        report_lines.append("")
        
        # Productivity Score Per Hour Analysis
        report_lines.append("PRODUCTIVITY SCORE PER HOUR (EFFICIENCY ANALYSIS)")
        report_lines.append("-" * 80)
        if score_per_hour:
            report_lines.append(f"Baseline Score/Hour: {score_per_hour.get('baseline_score_per_hour', 0):.2f}")
            report_lines.append(f"Recent Score/Hour: {score_per_hour.get('recent_score_per_hour', 0):.2f}")
            report_lines.append(f"Change: {score_per_hour.get('change_pct', 0):+.1f}%")
            report_lines.append(f"Trend: {score_per_hour.get('trend', 'unknown')}")
            if score_per_hour.get('indicates_burnout'):
                report_lines.append("")
                report_lines.append("[WARNING] Efficiency is decreasing significantly - potential burnout indicator!")
            elif score_per_hour.get('change_pct', 0) > 0:
                report_lines.append("")
                report_lines.append("[POSITIVE] Efficiency is improving or maintained!")
        else:
            report_lines.append("[WARNING] No productivity score data available")
        report_lines.append("")
        
        # Burnout Analysis
        report_lines.append("BURNOUT INDICATORS")
        report_lines.append("-" * 80)
        report_lines.append(f"Overall Assessment: {burnout_indicators.get('overall_assessment', 'unknown').upper().replace('_', ' ')}")
        report_lines.append("")
        report_lines.append("Note: Data gap in early December was due to gitignore issues (resolved), not burnout.")
        report_lines.append("")
        
        if burnout_indicators.get('warnings'):
            report_lines.append("WARNINGS:")
            for warning in burnout_indicators['warnings']:
                report_lines.append(f"  [WARNING] {warning}")
            report_lines.append("")
        
        if burnout_indicators.get('concerns'):
            report_lines.append("CONCERNS:")
            for concern in burnout_indicators['concerns']:
                report_lines.append(f"  [CONCERN] {concern}")
            report_lines.append("")
        
        if burnout_indicators.get('positive_signs'):
            report_lines.append("POSITIVE SIGNS:")
            for sign in burnout_indicators['positive_signs']:
                report_lines.append(f"  [POSITIVE] {sign}")
            report_lines.append("")
        
        # Productivity Goal Recommendations
        report_lines.append("PRODUCTIVITY HOUR GOALS (Work + Self Care)")
        report_lines.append("-" * 80)
        report_lines.append(f"Conservative Goal: {productivity_goals.get('conservative_goal', 0):.1f} hrs/week")
        report_lines.append(f"Moderate Goal: {productivity_goals.get('moderate_goal', 0):.1f} hrs/week")
        report_lines.append(f"Ambitious Goal: {productivity_goals.get('ambitious_goal', 0):.1f} hrs/week (7 hrs/day)")
        report_lines.append(f"RECOMMENDED: {productivity_goals.get('recommended_goal', 0):.1f} hrs/week")
        report_lines.append("")
        report_lines.append("Rationale:")
        for rationale in productivity_goals.get('rationale', []):
            report_lines.append(f"  - {rationale}")
        report_lines.append("")
        report_lines.append("RECOMMENDATION:")
        recommended = productivity_goals.get('recommended_goal', 30)
        if recommended <= 30:
            report_lines.append(f"  Set goal at {recommended:.1f} hrs/week average for the year.")
            report_lines.append("  This balances your recent increase with long-term sustainability.")
            report_lines.append("  You can have weeks above this (like your current 35 hrs), but average should be sustainable.")
        else:
            report_lines.append(f"  Set goal at {recommended:.1f} hrs/week average for the year.")
            report_lines.append("  Monitor closely and adjust if burnout indicators appear.")
        report_lines.append("")
        report_lines.append("  Regarding 49 hrs/week (7 hrs/day):")
        report_lines.append("  - This is a STRETCH GOAL, not a target")
        report_lines.append("  - Use for peak weeks when you're highly motivated")
        report_lines.append("  - Don't make this your average - it's unsustainable long-term")
        report_lines.append("  - If you can maintain 30-35 hrs/week average, that's excellent")
        report_lines.append("")
        
        # Coding Goals
        report_lines.append("CODING GOALS FOR THIS MONTH")
        report_lines.append("-" * 80)
        if coding_goals:
            target_range = coding_goals.get('target_range', {})
            commits_needed = coding_goals.get('commits_needed', {})
            pace_needed = coding_goals.get('commits_per_day_needed', {})
            report_lines.append(f"Commits So Far: {coding_goals.get('this_month_commits', 0)}")
            report_lines.append(f"Target Range: {target_range.get('min', 0)}-{target_range.get('max', 0)} commits/month")
            report_lines.append(f"Commits Needed: {commits_needed.get('min', 0)}-{commits_needed.get('max', 0)}")
            report_lines.append(f"Daily Pace Needed: {pace_needed.get('min', 0):.1f}-{pace_needed.get('max', 0):.1f} commits/day")
            report_lines.append("")
            report_lines.append("Target Options:")
            conservative = coding_goals.get('conservative_target', {})
            moderate = coding_goals.get('moderate_target', {})
            ambitious = coding_goals.get('ambitious_target', {})
            report_lines.append(f"  Conservative: {conservative.get('commits', 0)} commits ({conservative.get('hours', 0):.1f} hrs)")
            report_lines.append(f"  Moderate: {moderate.get('commits', 0)} commits ({moderate.get('hours', 0):.1f} hrs) [RECOMMENDED]")
            report_lines.append(f"  Ambitious: {ambitious.get('commits', 0)} commits ({ambitious.get('hours', 0):.1f} hrs)")
            report_lines.append("")
            report_lines.append("Note: You're planning a commit value analysis project to weight commits by significance.")
            report_lines.append("This will help distinguish between 4 tiny commits vs 1 substantial feature.")
            report_lines.append("")
            for rationale in coding_goals.get('rationale', []):
                report_lines.append(f"  - {rationale}")
        else:
            report_lines.append("[WARNING] No commit data available")
        report_lines.append("")
        
        # Music Goals
        report_lines.append("MUSIC GOALS")
        report_lines.append("-" * 80)
        monthly = music_goals.get('monthly', {})
        yearly = music_goals.get('yearly', {})
        report_lines.append(f"Monthly Hours: {music_goals.get('monthly_hours', 0):.1f} hrs ({music_goals.get('weekly_hours', 0):.1f} hrs/week)")
        report_lines.append(f"Ratio: {music_goals.get('ratio', '')}")
        report_lines.append("")
        report_lines.append("Monthly Targets:")
        report_lines.append(f"  - {monthly.get('suno_songs', 0)} Suno songs ({monthly.get('suno_songs', 0) * 0.5:.1f} hrs) - 80%")
        report_lines.append(f"  - {monthly.get('own_versions', 0)} own version ({monthly.get('own_versions', 0) * 3.5:.1f} hrs) - 10%")
        report_lines.append(f"  - {monthly.get('backtracks', 0)} backtrack ({monthly.get('backtracks', 0) * 2.5:.1f} hrs) - 10%")
        report_lines.append(f"  - Total: {monthly.get('total_hours', 0):.1f} hrs/month")
        report_lines.append("")
        report_lines.append("Yearly Targets:")
        report_lines.append(f"  - {yearly.get('suno_songs', 0)} Suno songs")
        report_lines.append(f"  - {yearly.get('own_versions', 0)} own versions")
        report_lines.append(f"  - {yearly.get('backtracks', 0)} backtracks")
        report_lines.append(f"  - {yearly.get('spotify_releases', 0)} Spotify releases (top 5% of own versions)")
        report_lines.append("")
        for rationale in music_goals.get('rationale', []):
            report_lines.append(f"  - {rationale}")
        report_lines.append("")
        
        # Category Productivity Analysis
        report_lines.append("CATEGORY PRODUCTIVITY ANALYSIS")
        report_lines.append("-" * 80)
        if category_productivity and category_productivity.get('categories'):
            categories = category_productivity['categories']
            best = category_productivity.get('best_productivity_per_hour')
            
            report_lines.append("Productivity Score Per Hour by Category:")
            report_lines.append("")
            
            # Sort by score per hour (highest first)
            sorted_categories = sorted(
                categories.items(),
                key=lambda x: x[1].get('score_per_hour', 0),
                reverse=True
            )
            
            for category, stats in sorted_categories:
                category_name = category.replace('_', ' ').title()
                report_lines.append(f"{category_name.upper()}:")
                report_lines.append(f"  Total Hours: {stats['total_hours']:.1f} hrs ({stats['percentage_of_total_hours']:.1f}% of total)")
                report_lines.append(f"  Total Tasks: {stats['task_count']} ({stats['percentage_of_total_tasks']:.1f}% of total)")
                report_lines.append(f"  Productivity Score/Hour: {stats['score_per_hour']:.2f}")
                report_lines.append(f"  Tasks/Hour: {stats['tasks_per_hour']:.2f}")
                report_lines.append(f"  Hours/Task: {stats['hours_per_task']:.2f}")
                report_lines.append(f"  Total Score: {stats['total_score']:.1f}")
                report_lines.append("")
            
            if best:
                report_lines.append(f"BEST PRODUCTIVITY PER HOUR: {best['category'].replace('_', ' ').title()}")
                report_lines.append(f"  Score/Hour: {best['score_per_hour']:.2f}")
                report_lines.append("")
            
            # Summary table
            report_lines.append("Summary Table:")
            report_lines.append(f"{'Category':<15} {'Hours':<10} {'Tasks':<10} {'Score/Hr':<12} {'Tasks/Hr':<12} {'Hrs/Task':<12}")
            report_lines.append("-" * 80)
            for category, stats in sorted_categories:
                category_name = category.replace('_', ' ').title()
                report_lines.append(
                    f"{category_name:<15} "
                    f"{stats['total_hours']:>8.1f}  "
                    f"{stats['task_count']:>8}  "
                    f"{stats['score_per_hour']:>10.2f}  "
                    f"{stats['tasks_per_hour']:>10.2f}  "
                    f"{stats['hours_per_task']:>10.2f}"
                )
            report_lines.append("")
            
            # Insights
            report_lines.append("Insights:")
            if len(sorted_categories) >= 2:
                best_cat = sorted_categories[0]
                second_cat = sorted_categories[1]
                ratio = best_cat[1]['score_per_hour'] / max(second_cat[1]['score_per_hour'], 1)
                report_lines.append(
                    f"  - {best_cat[0].replace('_', ' ').title()} is {ratio:.1f}x more productive per hour "
                    f"than {second_cat[0].replace('_', ' ').title()}"
                )
            
            # Time allocation recommendations
            report_lines.append("")
            report_lines.append("Time Allocation Recommendations:")
            total_hours = category_productivity.get('total_hours', 0)
            if total_hours > 0:
                for category, stats in sorted_categories:
                    category_name = category.replace('_', ' ').title()
                    current_pct = stats['percentage_of_total_hours']
                    score_per_hour = stats['score_per_hour']
                    
                    # Recommend based on productivity per hour
                    if score_per_hour > 50:  # High productivity
                        recommendation = "Consider allocating more time - high productivity per hour"
                    elif score_per_hour > 30:  # Medium productivity
                        recommendation = "Current allocation seems reasonable"
                    else:  # Lower productivity
                        recommendation = "Consider if time could be better allocated elsewhere"
                    
                    report_lines.append(
                        f"  {category_name}: {current_pct:.1f}% of time, "
                        f"{score_per_hour:.1f} score/hr - {recommendation}"
                    )
        else:
            report_lines.append("[WARNING] No category productivity data available")
        report_lines.append("")
        
        # Fitness Goals
        report_lines.append("FITNESS GOALS")
        report_lines.append("-" * 80)
        fitness = fitness_goals
        report_lines.append("Walking:")
        report_lines.append(f"  Goal: {fitness.get('walking', {}).get('goal', '')}")
        report_lines.append(f"  Target: {fitness.get('walking', {}).get('target', '')}")
        report_lines.append(f"  Note: {fitness.get('walking', {}).get('tracking', '')}")
        report_lines.append("")
        report_lines.append("Lifting:")
        report_lines.append(f"  Goal: {fitness.get('lifting', {}).get('goal', '')}")
        report_lines.append(f"  Target: {fitness.get('lifting', {}).get('target', '')}")
        report_lines.append(f"  Rationale: {fitness.get('lifting', {}).get('rationale', '')}")
        report_lines.append("  Milestones:")
        for milestone in fitness.get('lifting', {}).get('milestones', []):
            report_lines.append(f"    - {milestone}")
        report_lines.append("")
        report_lines.append("Running:")
        report_lines.append(f"  Goal: {fitness.get('running', {}).get('goal', '')}")
        report_lines.append(f"  Target: {fitness.get('running', {}).get('target', '')}")
        report_lines.append("")
        report_lines.append("Body Composition:")
        report_lines.append(f"  Goal: {fitness.get('body_composition', {}).get('goal', '')}")
        report_lines.append(f"  Tracking: {fitness.get('body_composition', {}).get('tracking', '')}")
        report_lines.append(f"  Note: {fitness.get('body_composition', {}).get('note', '')}")
        report_lines.append("")
        report_lines.append("Current Status:")
        report_lines.append(f"  {fitness.get('current_status', {}).get('note', '')}")
        report_lines.append(f"  Recommendation: {fitness.get('current_status', {}).get('recommendation', '')}")
        report_lines.append("")
        
        # Summary
        report_lines.append("=" * 80)
        report_lines.append("SUMMARY & FINAL RECOMMENDATIONS")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append("1. PRODUCTIVITY HOURS:")
        recommended_hours = productivity_goals.get('recommended_goal', 30)
        report_lines.append(f"   Set yearly average goal: {recommended_hours:.1f} hrs/week")
        report_lines.append(f"   - This allows for weeks at 35+ hrs when motivated")
        report_lines.append(f"   - But prevents burnout by not requiring 49 hrs/week consistently")
        report_lines.append(f"   - Your baseline was 10 hrs/week, recent is 35 hrs/week")
        report_lines.append(f"   - 30 hrs/week average is a 3x increase from baseline - very ambitious!")
        report_lines.append("")
        report_lines.append("2. CODING:")
        if coding_goals:
            moderate = coding_goals.get('moderate_target', {})
            this_month = coding_goals.get('this_month_commits', 0)
            total_commits = this_month + moderate.get('commits', 0)
            report_lines.append(f"   This month: Aim for {total_commits} total commits ({moderate.get('commits', 0)} more needed)")
            report_lines.append(f"   Estimated: ~{moderate.get('hours', 0):.1f} hours of coding")
        report_lines.append("")
        report_lines.append("3. MUSIC:")
        report_lines.append(f"   Monthly: {monthly.get('suno_songs', 0)} Suno + {monthly.get('own_versions', 0)} own + {monthly.get('backtracks', 0)} backtrack")
        report_lines.append(f"   Yearly: {yearly.get('spotify_releases', 0)} Spotify releases")
        report_lines.append("")
        report_lines.append("4. FITNESS:")
        report_lines.append("   Focus on consistency over intensity")
        report_lines.append("   Start with 2x/week workouts, build gradually")
        report_lines.append("")
        report_lines.append("5. RAPID ITERATION & GOAL-SETTING STRATEGY:")
        report_lines.append("   You asked about setting AGGRESSIVE long-term goals vs conservative ones.")
        report_lines.append("   ")
        report_lines.append("   TRADITIONAL APPROACH (Conservative long-term):")
        report_lines.append("   - Long-term goals are conservative to ensure achievability")
        report_lines.append("   - Short-term goals are aggressive to drive immediate progress")
        report_lines.append("   - Rationale: Prevents disappointment, builds confidence through wins")
        report_lines.append("   ")
        report_lines.append("   YOUR APPROACH (Aggressive long-term):")
        report_lines.append("   - Long-term goals are ambitious to drive growth")
        report_lines.append("   - Short-term goals incrementally build toward the long-term vision")
        report_lines.append("   - Rationale: Stretch goals push you further, rapid iteration allows course correction")
        report_lines.append("   ")
        report_lines.append("   RECOMMENDATION FOR YOU:")
        report_lines.append("   - Your rapid iteration ability makes aggressive long-term goals MORE viable")
        report_lines.append("   - You can adjust quickly if you're off track")
        report_lines.append("   - Set ambitious yearly goals (e.g., 30 hrs/week average, 200 commits/month)")
        report_lines.append("   - Break into aggressive quarterly milestones")
        report_lines.append("   - Use monthly/weekly goals to track progress and adjust")
        report_lines.append("   - Key: Review monthly and adjust if consistently missing by >20%")
        report_lines.append("   ")
        report_lines.append("   This approach works well for you because:")
        report_lines.append("   - You iterate quickly (can adjust goals based on reality)")
        report_lines.append("   - You're in a growth phase (3x increase from baseline)")
        report_lines.append("   - Ambitious goals can drive more achievement than conservative ones")
        report_lines.append("   - But still set a 'floor' (minimum acceptable) to prevent burnout")
        
        return "\n".join(report_lines)


def main():
    """Main execution function."""
    print("=" * 80)
    print("PRODUCTIVITY TREND ANALYSIS")
    print("=" * 80)
    print("")
    
    analyzer = ProductivityTrendAnalyzer()
    
    try:
        report = analyzer.generate_comprehensive_report()
        print(report)
        
        # Save to file
        output_file = os.path.join('data', 'productivity_trend_analysis.txt')
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

