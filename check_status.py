#!/usr/bin/env python3
"""Quick script to check the status of running experiments."""

import subprocess
from pathlib import Path

def check_processes():
    """Check for running talkingtomachines processes."""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        
        lines = result.stdout.split('\n')
        talkingtomachines_procs = [l for l in lines if 'talkingtomachines' in l and 'grep' not in l]
        run_experiment_procs = [l for l in lines if 'run_experiment.py' in l and 'grep' not in l]
        
        print("="*60)
        print("RUNNING PROCESSES:")
        print("="*60)
        
        if talkingtomachines_procs:
            print("\n📊 talkingtomachines processes:")
            for proc in talkingtomachines_procs:
                print(f"   {proc}")
        else:
            print("\n✅ No talkingtomachines processes running")
        
        if run_experiment_procs:
            print("\n📊 run_experiment.py processes:")
            for proc in run_experiment_procs:
                print(f"   {proc}")
        else:
            print("\n✅ No run_experiment.py processes running")
        
        print("\n" + "="*60)
        print("EXPERIMENT RESULTS:")
        print("="*60)
        
        results_dir = Path('experiment_results')
        if results_dir.exists():
            files = list(results_dir.glob('*'))
            if files:
                print(f"\n📁 Found {len(files)} files in experiment_results/:")
                for f in sorted(files):
                    size = f.stat().st_size
                    mtime = f.stat().st_mtime
                    from datetime import datetime
                    mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"   - {f.name} ({size:,} bytes, modified: {mtime_str})")
            else:
                print("\n⚠️  experiment_results/ folder exists but is empty")
        else:
            print("\n⚠️  experiment_results/ folder does not exist")
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"Error checking processes: {e}")

if __name__ == "__main__":
    check_processes()

