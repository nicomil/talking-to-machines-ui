#!/usr/bin/env python3
"""
Python app to run experiments with the talkingtomachines framework.
Usage: python run_experiment.py <excel_template_file>
"""

import sys
import os
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    print(f"Loading environment variables from {env_path}")
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Also try current directory
        load_dotenv()
except ImportError:
    # python-dotenv not installed, use only environment variables
    pass

# Try to import the Python package directly
try:
    import talkingtomachines  # noqa: F401
    HAS_PACKAGE = True
except ImportError:
    HAS_PACKAGE = False


def check_api_keys():
    """Check that API keys are configured."""
    required_keys = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'HF_API_KEY': os.getenv('HF_API_KEY'),
        'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY')
    }
    print(required_keys)
    
    missing_keys = [key for key, value in required_keys.items() if not value]
    
    if missing_keys:
        print("Warning: The following API keys are not configured in the .env file:")
        for key in missing_keys:
            print(f"   - {key}")
        print("\nConfigure API keys using one of the following methods:")
        print("\n1. Create a .env file in the project directory:")
        print("   OPENAI_API_KEY=sk-...")
        print("   HF_API_KEY=hf_...")
        print("   OPENROUTER_API_KEY=sk-...")
        print("\n2. Or as environment variables:")
        print("   export OPENAI_API_KEY=sk-...")
        print("   export HF_API_KEY=hf_...")
        print("   export OPENROUTER_API_KEY=sk-...")
        return False
    
    return True


def get_process_info(pid):
    """Get detailed process information."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return {
            'cpu_percent': proc.cpu_percent(interval=0.1),
            'memory_mb': proc.memory_info().rss / 1024 / 1024,
            'num_threads': proc.num_threads(),
            'num_connections': len(proc.connections()),
            'status': proc.status()
        }
    except ImportError:
        return None
    except Exception:
        # psutil.NoSuchProcess, psutil.AccessDenied, etc.
        return None


def monitor_process(process, start_time, verbose=False):
    """Monitor process status and show periodic updates with detailed info."""
    last_update = time.time()
    update_interval = 3 if verbose else 5
    
    while process.poll() is None:
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        
        # Get process details if available
        proc_info = None
        if hasattr(process, 'pid') and process.pid:
            proc_info = get_process_info(process.pid)
        
        # Check for results folder
        results_dir = Path('experiment_results')
        result_files = []
        if results_dir.exists():
            result_files = list(results_dir.glob('*.json')) + list(results_dir.glob('*.csv'))
        
        # Build status message
        status_parts = [f"⏱️  [Elapsed: {minutes}m {seconds}s]"]
        
        if proc_info:
            status_parts.append(f"CPU: {proc_info['cpu_percent']:.1f}%")
            status_parts.append(f"Mem: {proc_info['memory_mb']:.1f}MB")
            status_parts.append(f"Conn: {proc_info['num_connections']}")
        
        if result_files:
            total_size = sum(f.stat().st_size for f in result_files)
            status_parts.append(f"📁 {len(result_files)} file(s) ({total_size/1024:.1f}KB)")
        else:
            status_parts.append("⏳ Waiting for results...")
        
        status_msg = " | ".join(status_parts)
        print(f"\r{status_msg}", end='', flush=True)
        
        time.sleep(update_interval)
    
    print()  # New line after monitoring stops


def read_output_stream(stream, label, output_list):
    """Read from a stream and store output."""
    try:
        for line in iter(stream.readline, ''):
            if line:
                output_list.append(line)
                # Show important lines immediately
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in ['error', 'warning', 'completed', 'started', 'progress', '%']):
                    print(f"[{label}] {line.rstrip()}")
    except Exception as e:
        output_list.append(f"Error reading {label}: {str(e)}")
    finally:
        stream.close()


def run_experiment_via_cli(excel_file_path, mode='test', verbose=False):
    """
    Run an experiment using the talkingtomachines CLI tool.
    
    Args:
        excel_file_path: Path to the Excel template file
        mode: Execution mode ('test' or 'full')
        verbose: If True, show detailed error output
    
    Returns:
        True if the experiment completed successfully, False otherwise
    """
    try:
        print(f"\n🚀 Starting experiment execution...")
        print(f"📋 Mode: {mode.upper()}")
        print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        # Use the talkingtomachines CLI tool
        # The command accepts the Excel file and then asks for the mode
        process = subprocess.Popen(
            ['talkingtomachines', excel_file_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        # Send the selected mode
        process.stdin.write(f"{mode}\n")
        process.stdin.flush()
        process.stdin.close()
        
        # Start monitoring thread
        start_time = time.time()
        monitor_thread = threading.Thread(
            target=monitor_process,
            args=(process, start_time, verbose),
            daemon=True
        )
        monitor_thread.start()
        
        # Read output streams in real-time
        stdout_lines = []
        stderr_lines = []
        
        stdout_thread = threading.Thread(
            target=read_output_stream,
            args=(process.stdout, "STDOUT", stdout_lines),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=read_output_stream,
            args=(process.stderr, "STDERR", stderr_lines),
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for process to complete
        return_code = process.wait(timeout=3600)
        
        # Wait for threads to finish reading
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        
        # Combine output
        stdout = ''.join(stdout_lines)
        stderr = ''.join(stderr_lines)
        
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print(f"\n⏰ Total execution time: {minutes}m {seconds}s")
        
        # Show any warnings or errors from stderr
        if stderr and stderr.strip():
            print("\n" + "="*60)
            print("SYSTEM OUTPUT / ERRORS / WARNINGS:")
            print("="*60)
            print(stderr)
            print("="*60 + "\n")
        
        # Show full stdout if verbose or if there were errors
        if verbose and stdout:
            print("\n" + "="*60)
            print("FULL STDOUT:")
            print("="*60)
            print(stdout)
            print("="*60)
        
        if return_code == 0:
            print("\n" + "="*60)
            print("EXPERIMENT OUTPUT:")
            print("="*60)
            print(stdout)
            print("="*60)
            
            # Check if the experiment_results folder was created
            results_dir = Path('experiment_results')
            if results_dir.exists() and results_dir.is_dir():
                # Count files in the folder
                result_files = list(results_dir.glob('*.json')) + list(results_dir.glob('*.csv'))
                if result_files:
                    print(f"\nExperiment completed successfully!")
                    print(f"📁 Results saved in 'experiment_results' folder:")
                    for file in sorted(result_files):
                        file_size = file.stat().st_size
                        print(f"   - {file.name} ({file_size:,} bytes)")
                else:
                    print(f"\nExperiment completed, but no results were generated.")
                    print(f"The 'experiment_results' folder exists but is empty.")
                    print(f"\nDEBUG INFO:")
                    print(f"   - Return code: {return_code}")
                    print(f"   - Mode: {mode}")
                    print(f"   - Execution time: {minutes}m {seconds}s")
                    print(f"   - Check API keys in .env file")
                    if verbose:
                        print(f"\n Full stdout:\n{stdout}")
            else:
                print(f"\nExperiment completed, but the 'experiment_results' folder was not created.")
                print(f"\nDEBUG INFO:")
                print(f"   - Return code: {return_code}")
                print(f"   - Mode: {mode}")
                print(f"   - stdout length: {len(stdout)} characters")
                print(f"   - stderr length: {len(stderr)} characters")
                print(f"\n This can happen if:")
                print(f"   - API keys are not configured correctly in the .env file")
                print(f"   - The experiment did not generate results to save")
                print(f"   - The experiment was run in test mode without actual API calls")
                print(f"\n To generate real results:")
                print(f"   1. Make sure the .env file contains valid API keys")
                print(f"   2. Run the experiment in 'full' mode for complete results")
                if verbose:
                    print(f"\n Full stdout:\n{stdout}")
                    print(f"\n Full stderr:\n{stderr}")
            
            return True
        else:
            print("\n" + "="*60)
            print(" ERROR DURING EXPERIMENT EXECUTION:")
            print("="*60)
            print(f"Return code: {return_code}")
            print(f"Execution time: {minutes}m {seconds}s")
            print(f"\n STDOUT:")
            print(stdout)
            print(f"\n STDERR:")
            print(stderr)
            print("="*60)
            return False
            
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print(f"\n⏱️  Timeout: The experiment took too long ({minutes}m {seconds}s).")
        print("   Killing process...")
        process.kill()
        process.wait(timeout=5)
        return False
    except FileNotFoundError:
        print("Error: The 'talkingtomachines' command was not found.")
        print("   Make sure you have installed the package:")
        print("   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple talkingtomachines")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False


def run_experiment(excel_file_path, mode='test', verbose=False):
    """
    Run an experiment using the talkingtomachines framework.
    Tries to use the Python package first, then falls back to CLI.
    
    Args:
        excel_file_path: Path to the Excel template file
        mode: Execution mode ('test' or 'full')
        verbose: If True, show detailed debug output
    
    Returns:
        True if the experiment completed successfully, False otherwise
    """
    # Check that the file exists
    if not os.path.exists(excel_file_path):
        print(f" Error: The file '{excel_file_path}' does not exist.")
        return False
    
    # Check that it's an Excel file
    if not excel_file_path.lower().endswith(('.xlsx', '.xls')):
        print(f" Warning: The file '{excel_file_path}' might not be a valid Excel file.")
    
    print(f"Starting experiment with template: {excel_file_path}")
    print(f" Mode: {mode.upper()}")
    print("-" * 60)
    
    # Try to use the Python package if available
    if HAS_PACKAGE:
        try:
            print(" Using Python package talkingtomachines...")
            # Note: The exact API depends on the package implementation
            # For now we use CLI as the main method
            # If the package exposes a direct API, it can be integrated here
            return run_experiment_via_cli(excel_file_path, mode, verbose)
        except Exception as e:
            print(f"  Error with Python package: {str(e)}")
            print("Falling back to CLI tool...")
            return run_experiment_via_cli(excel_file_path, mode, verbose)
    else:
        # Use CLI directly
        return run_experiment_via_cli(excel_file_path, mode, verbose)


def main():
    """Main function."""
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    if verbose:
        sys.argv.remove('--verbose')
        if '-v' in sys.argv:
            sys.argv.remove('-v')
    
    if len(sys.argv) < 2:
        print(" Usage:")
        print(f"   python {sys.argv[0]} <excel_template_file> [mode] [--verbose|-v]")
        print("\nParameters:")
        print("   excel_template_file: Path to the Excel template file")
        print("   mode: (optional) Execution mode: 'test' or 'full' (default: 'test')")
        print("   --verbose, -v: (optional) Show detailed debug output")
        print("\n Examples:")
        print(f"   python {sys.argv[0]} template.xlsx")
        print(f"   python {sys.argv[0]} template.xlsx test")
        print(f"   python {sys.argv[0]} template.xlsx full --verbose")
        sys.exit(1)
    
    excel_file = sys.argv[1]
    mode = sys.argv[2].lower() if len(sys.argv) > 2 and sys.argv[2] not in ['--verbose', '-v'] else 'test'
    
    if mode not in ['test', 'full']:
        print(f"  Invalid mode '{mode}'. Using 'test' as default.")
        mode = 'test'
    
    # Check API keys
    api_keys_ok = check_api_keys()
    if not api_keys_ok:
        print("\n Continuing anyway... (some providers might not be required)")
    
    if verbose:
        print("\n" + "="*60)
        print("DEBUG MODE ENABLED")
        print("="*60)
        print(f"Excel file: {excel_file}")
        print(f"Mode: {mode}")
        print(f"API keys configured: {api_keys_ok}")
        print(f"Verbose: {verbose}")
        print("="*60 + "\n")
    
    # Run the experiment
    success = run_experiment(excel_file, mode, verbose)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

