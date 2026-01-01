"""Check for running Python processes and system resource usage."""
import psutil
import os
import sys

def check_python_processes():
    """Check all running Python processes and their resource usage."""
    print("=" * 80)
    print("PYTHON PROCESS CHECK")
    print("=" * 80)
    
    python_processes = []
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'cpu_percent']):
        try:
            proc_info = proc.info
            name = proc_info.get('name', '').lower()
            cmdline = proc_info.get('cmdline') or []
            
            # Check if it's a Python process
            if 'python' in name or (cmdline and any('python' in str(arg).lower() for arg in cmdline)):
                # Get full command line
                cmdline_str = ' '.join(str(arg) for arg in cmdline) if cmdline else 'N/A'
                
                # Get memory usage
                memory = proc_info.get('memory_info')
                memory_mb = memory.rss / (1024 * 1024) if memory else 0
                
                # Get CPU usage (non-blocking)
                try:
                    cpu = proc.cpu_percent(interval=0.1)
                except:
                    cpu = 0.0
                
                is_current = proc_info['pid'] == current_pid
                
                python_processes.append({
                    'pid': proc_info['pid'],
                    'name': name,
                    'cmdline': cmdline_str,
                    'memory_mb': memory_mb,
                    'cpu_percent': cpu,
                    'is_current': is_current
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    # Sort by memory usage (descending)
    python_processes.sort(key=lambda x: x['memory_mb'], reverse=True)
    
    print(f"\nFound {len(python_processes)} Python process(es):\n")
    
    total_memory = 0
    for proc in python_processes:
        marker = " <-- CURRENT PROCESS" if proc['is_current'] else ""
        print(f"PID: {proc['pid']}{marker}")
        print(f"  Name: {proc['name']}")
        print(f"  Memory: {proc['memory_mb']:.1f} MB")
        print(f"  CPU: {proc['cpu_percent']:.1f}%")
        print(f"  Command: {proc['cmdline'][:200]}..." if len(proc['cmdline']) > 200 else f"  Command: {proc['cmdline']}")
        print()
        total_memory += proc['memory_mb']
    
    print(f"Total Python processes memory: {total_memory:.1f} MB")
    
    # Check for app.py processes specifically
    app_processes = [p for p in python_processes if 'app.py' in p['cmdline'].lower()]
    if len(app_processes) > 1:
        print(f"\n[WARNING] Found {len(app_processes)} instances of app.py running!")
        print("This could cause performance issues. Consider stopping duplicate instances.")
        for proc in app_processes:
            if not proc['is_current']:
                print(f"  - PID {proc['pid']}: {proc['memory_mb']:.1f} MB")
    elif len(app_processes) == 1:
        print(f"\n[OK] Found 1 instance of app.py (current process)")
    
    return python_processes

def check_system_resources():
    """Check overall system resource usage."""
    print("\n" + "=" * 80)
    print("SYSTEM RESOURCE USAGE")
    print("=" * 80)
    
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    print(f"\nCPU: {cpu_percent:.1f}% used ({cpu_count} cores)")
    
    # Memory usage
    memory = psutil.virtual_memory()
    print(f"Memory: {memory.percent:.1f}% used ({memory.used / (1024**3):.1f} GB / {memory.total / (1024**3):.1f} GB)")
    if memory.percent > 80:
        print("  [WARNING] Memory usage is high!")
    
    # Disk usage
    disk = psutil.disk_usage('/')
    print(f"Disk: {disk.percent:.1f}% used ({disk.used / (1024**3):.1f} GB / {disk.total / (1024**3):.1f} GB)")
    
    # Network connections (Python processes)
    print(f"\nNetwork connections from Python processes:")
    python_pids = [p['pid'] for p in check_python_processes() if 'app.py' in p['cmdline'].lower()]
    for pid in python_pids:
        try:
            proc = psutil.Process(pid)
            connections = proc.connections()
            if connections:
                print(f"  PID {pid}: {len(connections)} connection(s)")
                for conn in connections[:5]:  # Show first 5
                    print(f"    - {conn.status}: {conn.laddr} -> {conn.raddr if conn.raddr else 'N/A'}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

if __name__ == '__main__':
    try:
        processes = check_python_processes()
        check_system_resources()
        
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print("If you see multiple app.py processes:")
        print("  1. Close all browser tabs with the app")
        print("  2. Stop the current Python process (Ctrl+C)")
        print("  3. Check Task Manager for any remaining Python processes")
        print("  4. Restart the app")
        print("\nTo kill a specific process (Windows PowerShell):")
        print("  Stop-Process -Id <PID> -Force")
        
    except ImportError:
        print("ERROR: psutil is not installed.")
        print("Install it with: python -m pip install psutil")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
