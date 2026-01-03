"""
Compile Git Commit Messages for Analysis

Extracts all commit messages from the git repository and saves them to a file
for goal analysis and productivity tracking.
"""
import os
import sys
import subprocess
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class CommitMessageCompiler:
    """Compile and analyze git commit messages."""
    
    def __init__(self, repo_path: Optional[str] = None):
        """Initialize with repository path.
        
        Args:
            repo_path: Path to git repository (default: current directory)
        """
        if repo_path is None:
            repo_path = os.getcwd()
        self.repo_path = Path(repo_path).resolve()
        
        # Verify it's a git repository
        if not (self.repo_path / '.git').exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")
    
    def get_all_commits(self) -> List[Dict[str, str]]:
        """Get all commit messages from the repository.
        
        Returns:
            List of dicts with 'hash', 'date', 'author', 'message', 'message_body'
        """
        try:
            # Get all commits with full information
            # Format: hash|date|author|subject|body
            cmd = [
                'git', 'log',
                '--format=%H|%ai|%an|%s|%b',
                '--all',
                '--reverse'  # Oldest first
            ]
            
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
                
                # Split by | separator
                parts = line.split('|', maxsplit=4)
                if len(parts) < 4:
                    continue
                
                commit_hash = parts[0].strip()
                date_str = parts[1].strip()
                author = parts[2].strip()
                subject = parts[3].strip() if len(parts) > 3 else ''
                body = parts[4].strip() if len(parts) > 4 else ''
                
                commits.append({
                    'hash': commit_hash,
                    'date': date_str,
                    'author': author,
                    'subject': subject,
                    'message_body': body,
                    'full_message': f"{subject}\n{body}".strip()
                })
            
            return commits
            
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Git command failed: {e}")
            print(f"  Command: {' '.join(cmd)}")
            print(f"  Error: {e.stderr}")
            return []
        except Exception as e:
            print(f"[ERROR] Failed to get commits: {e}")
            return []
    
    def get_commit_stats(self, commits: List[Dict[str, str]]) -> Dict[str, any]:
        """Calculate statistics about commits.
        
        Args:
            commits: List of commit dictionaries
            
        Returns:
            Dictionary with statistics
        """
        if not commits:
            return {}
        
        # Parse dates and calculate time span
        from datetime import datetime
        dates = []
        for commit in commits:
            try:
                # Parse ISO format date: 2025-12-15 10:30:45 -0500
                date_str = commit['date'].split()[0] + ' ' + commit['date'].split()[1]
                dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                dates.append(dt.date())
            except (ValueError, IndexError, AttributeError):
                pass
        
        if not dates:
            return {'total_commits': len(commits)}
        
        first_date = min(dates)
        last_date = max(dates)
        days_span = (last_date - first_date).days + 1 if first_date != last_date else 1
        
        # Count commits by date
        commits_by_date = {}
        for date in dates:
            commits_by_date[date] = commits_by_date.get(date, 0) + 1
        
        # Calculate averages
        avg_commits_per_day = len(commits) / max(days_span, 1)
        avg_commits_per_week = avg_commits_per_day * 7
        
        # Find most active days
        sorted_dates = sorted(commits_by_date.items(), key=lambda x: x[1], reverse=True)
        top_days = sorted_dates[:10]
        
        # Analyze commit message lengths
        message_lengths = [len(c['full_message']) for c in commits]
        avg_message_length = sum(message_lengths) / len(message_lengths) if message_lengths else 0
        
        return {
            'total_commits': len(commits),
            'first_commit_date': first_date.isoformat(),
            'last_commit_date': last_date.isoformat(),
            'days_span': days_span,
            'weeks_span': round(days_span / 7.0, 1),
            'avg_commits_per_day': round(avg_commits_per_day, 2),
            'avg_commits_per_week': round(avg_commits_per_week, 2),
            'max_commits_per_day': max(commits_by_date.values()) if commits_by_date else 0,
            'unique_days_with_commits': len(commits_by_date),
            'consistency_pct': round((len(commits_by_date) / max(days_span, 1)) * 100, 1),
            'top_commit_days': [(str(date), count) for date, count in top_days],
            'avg_message_length': round(avg_message_length, 1),
            'total_message_chars': sum(message_lengths)
        }
    
    def categorize_commits(self, commits: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
        """Categorize commits by keywords in messages.
        
        Args:
            commits: List of commit dictionaries
            
        Returns:
            Dictionary mapping categories to lists of commits
        """
        categories = {
            'coding': [],
            'coursera': [],
            'fitness': [],
            'music': [],
            'other': []
        }
        
        category_keywords = {
            'coding': ['code', 'program', 'develop', 'script', 'app', 'software', 'git', 'github', 'commit', 'debug', 'refactor', 'api', 'database', 'backend', 'frontend', 'task aversion', 'aversion system', 'feature', 'fix', 'bug', 'ui', 'analytics', 'migration', 'schema', 'database', 'sql'],
            'coursera': ['coursera', 'course', 'learn', 'study', 'lecture', 'assignment', 'quiz', 'module', 'certificate'],
            'fitness': ['fitness', 'workout', 'exercise', 'gym', 'run', 'running', 'lift', 'lifting', 'cardio', 'strength', 'train', 'training', 'diet', 'nutrition', 'meal'],
            'music': ['music', 'song', 'suno', 'record', 'track', 'audio', 'produce', 'production', 'spotify', 'release', 'backtrack', 'compose', 'mix', 'master']
        }
        
        for commit in commits:
            message_lower = commit['full_message'].lower()
            categorized = False
            
            for category, keywords in category_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    categories[category].append(commit)
                    categorized = True
                    break
            
            if not categorized:
                categories['other'].append(commit)
        
        return categories
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive commit analysis report.
        
        Args:
            output_file: Optional path to save report (default: data/commit_analysis.txt)
            
        Returns:
            Report text
        """
        print("[INFO] Fetching all commits...")
        commits = self.get_all_commits()
        
        if not commits:
            return "[ERROR] No commits found or git command failed"
        
        print(f"[INFO] Found {len(commits)} commits")
        print("[INFO] Calculating statistics...")
        stats = self.get_commit_stats(commits)
        
        print("[INFO] Categorizing commits...")
        categorized = self.categorize_commits(commits)
        
        # Build report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("GIT COMMIT MESSAGE ANALYSIS")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Repository: {self.repo_path}")
        report_lines.append("")
        
        # Overall Statistics
        report_lines.append("OVERALL STATISTICS")
        report_lines.append("-" * 80)
        report_lines.append(f"Total Commits: {stats.get('total_commits', 0)}")
        if 'first_commit_date' in stats:
            report_lines.append(f"First Commit: {stats['first_commit_date']}")
            report_lines.append(f"Last Commit: {stats['last_commit_date']}")
            report_lines.append(f"Time Span: {stats['days_span']} days ({stats['weeks_span']} weeks)")
            report_lines.append(f"Average Commits/Day: {stats['avg_commits_per_day']:.2f}")
            report_lines.append(f"Average Commits/Week: {stats['avg_commits_per_week']:.2f}")
            report_lines.append(f"Max Commits/Day: {stats['max_commits_per_day']}")
            report_lines.append(f"Days with Commits: {stats['unique_days_with_commits']}")
            report_lines.append(f"Consistency: {stats['consistency_pct']:.1f}%")
            report_lines.append(f"Average Message Length: {stats['avg_message_length']:.1f} characters")
        report_lines.append("")
        
        # Category Breakdown
        report_lines.append("COMMIT CATEGORIZATION")
        report_lines.append("-" * 80)
        for category in ['coding', 'coursera', 'fitness', 'music', 'other']:
            category_commits = categorized.get(category, [])
            count = len(category_commits)
            percentage = (count / len(commits)) * 100 if commits else 0
            report_lines.append(f"{category.upper()}: {count} commits ({percentage:.1f}%)")
        report_lines.append("")
        
        # Category Statistics
        report_lines.append("CATEGORY DETAILS")
        report_lines.append("-" * 80)
        for category in ['coding', 'coursera', 'fitness', 'music']:
            category_commits = categorized.get(category, [])
            if not category_commits:
                continue
            
            category_stats = self.get_commit_stats(category_commits)
            report_lines.append(f"\n{category.upper()}:")
            report_lines.append(f"  Total Commits: {category_stats.get('total_commits', 0)}")
            if 'first_commit_date' in category_stats:
                report_lines.append(f"  Time Span: {category_stats['days_span']} days")
                report_lines.append(f"  Avg Commits/Week: {category_stats.get('avg_commits_per_week', 0):.2f}")
                report_lines.append(f"  Consistency: {category_stats.get('consistency_pct', 0):.1f}%")
        report_lines.append("")
        
        # Top Commit Days
        if 'top_commit_days' in stats and stats['top_commit_days']:
            report_lines.append("TOP COMMIT DAYS")
            report_lines.append("-" * 80)
            for date_str, count in stats['top_commit_days'][:10]:
                report_lines.append(f"  {date_str}: {count} commits")
            report_lines.append("")
        
        # All Commit Messages
        report_lines.append("=" * 80)
        report_lines.append("ALL COMMIT MESSAGES")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        for i, commit in enumerate(commits, 1):
            report_lines.append(f"Commit #{i}: {commit['hash'][:8]}")
            report_lines.append(f"Date: {commit['date']}")
            report_lines.append(f"Author: {commit['author']}")
            report_lines.append(f"Subject: {commit['subject']}")
            if commit['message_body']:
                report_lines.append(f"Body:")
                for line in commit['message_body'].split('\n'):
                    report_lines.append(f"  {line}")
            report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        # Save to file
        if output_file is None:
            output_file = os.path.join('data', 'commit_analysis.txt')
        
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"[SUCCESS] Report saved to: {output_file}")
        
        return report_text


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Compile and analyze git commit messages')
    parser.add_argument('--repo', type=str, help='Path to git repository (default: current directory)')
    parser.add_argument('--output', type=str, help='Output file path (default: data/commit_analysis.txt)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("GIT COMMIT MESSAGE COMPILER")
    print("=" * 80)
    print("")
    
    try:
        compiler = CommitMessageCompiler(repo_path=args.repo)
        report = compiler.generate_report(output_file=args.output)
        
        # Print summary
        lines = report.split('\n')
        for line in lines[:50]:  # Print first 50 lines
            print(line)
        
        if len(lines) > 50:
            print(f"\n... (report continues, see full output in file) ...")
        
    except Exception as e:
        print(f"[ERROR] Failed to compile commits: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

