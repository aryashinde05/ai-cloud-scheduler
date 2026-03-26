#!/usr/bin/env python3
"""
Task Monitoring Script
Simple CLI tool to monitor Celery tasks
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.tasks import TaskMonitor

def print_task_status(task_id: str):
    """Print status of a specific task"""
    status = TaskMonitor.get_task_status(task_id)
    print(f"\nTask ID: {task_id}")
    print(f"Status: {status['status']}")
    print(f"Result: {status['result']}")
    if status['traceback']:
        print(f"Error: {status['traceback']}")
    if status['date_done']:
        print(f"Completed: {status['date_done']}")

def print_active_tasks():
    """Print all active tasks"""
    tasks = TaskMonitor.get_active_tasks()
    
    if not tasks:
        print("No active tasks")
        return
    
    print(f"\nActive Tasks ({len(tasks)}):")
    print("-" * 80)
    
    for task in tasks:
        print(f"Task ID: {task['task_id']}")
        print(f"Name: {task['name']}")
        print(f"Worker: {task['worker']}")
        print(f"Args: {task['args']}")
        print(f"Started: {datetime.fromtimestamp(task['time_start']) if task['time_start'] else 'Unknown'}")
        print("-" * 40)

def print_worker_stats():
    """Print worker statistics"""
    stats = TaskMonitor.get_worker_stats()
    
    if not stats:
        print("No workers found")
        return
    
    print(f"\nWorker Statistics ({len(stats)} workers):")
    print("-" * 80)
    
    for worker_name, worker_stats in stats.items():
        print(f"Worker: {worker_name}")
        print(f"Status: {worker_stats.get('status', 'unknown')}")
        
        if 'pool' in worker_stats:
            pool = worker_stats['pool']
            print(f"Pool: {pool.get('max-concurrency', 'unknown')} max, {pool.get('processes', 'unknown')} processes")
        
        if 'rusage' in worker_stats:
            rusage = worker_stats['rusage']
            print(f"Memory: {rusage.get('maxrss', 0) / 1024:.1f} MB")
        
        print("-" * 40)

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python monitor_tasks.py status <task_id>  - Check specific task status")
        print("  python monitor_tasks.py active            - Show active tasks")
        print("  python monitor_tasks.py workers           - Show worker statistics")
        print("  python monitor_tasks.py watch             - Watch active tasks (refresh every 5s)")
        print("  python monitor_tasks.py cancel <task_id>  - Cancel a task")
        return
    
    command = sys.argv[1]
    
    try:
        if command == "status" and len(sys.argv) > 2:
            task_id = sys.argv[2]
            print_task_status(task_id)
        
        elif command == "active":
            print_active_tasks()
        
        elif command == "workers":
            print_worker_stats()
        
        elif command == "watch":
            print("Watching active tasks (Ctrl+C to stop)...")
            try:
                while True:
                    print("\033[2J\033[H")  # Clear screen
                    print(f"Task Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print_active_tasks()
                    print_worker_stats()
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\nStopped watching")
        
        elif command == "cancel" and len(sys.argv) > 2:
            task_id = sys.argv[2]
            success = TaskMonitor.cancel_task(task_id)
            if success:
                print(f"Task {task_id} cancelled successfully")
            else:
                print(f"Failed to cancel task {task_id}")
        
        else:
            print(f"Unknown command: {command}")
            return
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
