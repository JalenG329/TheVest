import time
import subprocess
import os
import argparse

def tail_log(log_file, lines=10):
    """Display the last few lines of the log file."""
    if not os.path.exists(log_file):
        return "Log file not found"
    
    result = subprocess.run(['tail', '-n', str(lines), log_file], 
                           capture_output=True, text=True)
    return result.stdout

def monitor_system():
    """Monitor system resources."""
    result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
    return result.stdout

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Monitor haptic vest performance')
    parser.add_argument('--log', default='haptic_vest_performance.log', 
                       help='Path to performance log file')
    parser.add_argument('--interval', type=int, default=5,
                       help='Monitoring interval in seconds')
    args = parser.parse_args()
    
    try:
        while True:
            # Clear screen
            os.system('clear')
            
            # Print log tail
            print("=== PERFORMANCE LOG ===")
            print(tail_log(args.log))
            
            # Print system resources
            print("\n=== SYSTEM RESOURCES ===")
            print(monitor_system())
            
            # Wait for next update
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Monitoring stopped")