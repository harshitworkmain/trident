import os
import json
import shutil
import time
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('kaggle_runner')

KAGGLE_USERNAME = "harshitsingh7883"
DATASET_SLUG = "harshitsingh7883/trident-wearable-telemetry"
KERNEL_SLUG = "harshitsingh7883/trident-ml-tournament"

def get_kaggle_cmd():
    """Returns the kaggle command list to use."""
    local_bin = os.path.expanduser('~/.local/bin/kaggle')
    if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
        return [local_bin]
    return ['kaggle']

def run_cmd(cmd, cwd=None, check=True):
    """Runs a subprocess command and handles errors."""
    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        if check:
            raise
        return e

def create_and_upload_dataset(parquet_dir, dataset_slug):
    logger.info(f"Preparing dataset at {parquet_dir} with slug {dataset_slug}")
    parquet_path = Path(parquet_dir)
    
    metadata = {
        "title": "TRIDENT Wearable Telemetry",
        "id": dataset_slug,
        "licenses": [{"name": "CC0-1.0"}]
    }
    
    metadata_path = parquet_path / "dataset-metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Try to update first, if it fails, create
    kaggle_cmd = get_kaggle_cmd()
    logger.info("Attempting to create/update dataset on Kaggle...")
    
    # Try create
    result = run_cmd(kaggle_cmd + ['datasets', 'create', '-p', str(parquet_path)], check=False)
    
    if result.returncode != 0:
        logger.info("Dataset create failed (might already exist), attempting version update...")
        update_result = run_cmd(kaggle_cmd + ['datasets', 'version', '-p', str(parquet_path), '-m', 'Update dataset'], check=False)
        if update_result.returncode != 0:
            logger.error("Failed to upload dataset via create or version update.")
            return False
            
    logger.info("Dataset uploaded successfully.")
    return True

def prepare_kernel(tournament_script_path, dataset_slug, kernel_slug, tmp_dir):
    logger.info(f"Preparing kernel in {tmp_dir}")
    tmp_path = Path(tmp_dir)
    tmp_path.mkdir(parents=True, exist_ok=True)
    
    metadata = {
        "id": kernel_slug,
        "title": "TRIDENT ML Tournament",
        "code_file": "script.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "dataset_sources": [dataset_slug],
        "competition_sources": [],
        "kernel_sources": []
    }
    
    with open(tmp_path / 'kernel-metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
        
    script_content = f"""
import os
import sys

# Configure Kaggle paths
DATA_PATH = '/kaggle/input/trident-wearable-telemetry/fused_training_matrix.parquet'
OUTPUT_DIR = '/kaggle/working/'
DOCS_DIR = '/kaggle/working/'

# Add current directory to path so imports work if needed
sys.path.append('.')

"""
    
    with open(tournament_script_path, 'r') as f:
        original_script = f.read()
        
    # We append the original script, then append the entrypoint call
    script_content += original_script
    
    script_content += f"""

if __name__ == '__main__':
    # Provided we have a run_tournament in the original script
    if 'run_tournament' in dir() or 'run_tournament' in globals():
        run_tournament(
            parquet_path=DATA_PATH,
            output_dir=OUTPUT_DIR,
            docs_dir=DOCS_DIR
        )
    else:
        print("Error: run_tournament function not found in script.")
"""

    with open(tmp_path / 'script.py', 'w') as f:
        f.write(script_content)
        
    logger.info("Kernel prepared successfully.")
    return True

def push_kernel(kernel_dir):
    logger.info(f"Pushing kernel from {kernel_dir}")
    kaggle_cmd = get_kaggle_cmd()
    result = run_cmd(kaggle_cmd + ['kernels', 'push', '-p', str(kernel_dir)], check=False)
    if result.returncode == 0:
        logger.info("Kernel pushed successfully.")
        return True
    else:
        logger.error("Failed to push kernel.")
        return False

def poll_kernel_status(kernel_slug, timeout_minutes=120, poll_interval=60):
    logger.info(f"Polling kernel status for {kernel_slug}...")
    kaggle_cmd = get_kaggle_cmd()
    start_time = time.time()
    
    while time.time() - start_time < timeout_minutes * 60:
        result = run_cmd(kaggle_cmd + ['kernels', 'status', kernel_slug], check=False)
        if result.returncode != 0:
            logger.warning(f"Failed to get kernel status: {result.stderr}")
        else:
            output = result.stdout.lower()
            if 'complete' in output:
                logger.info("Kernel execution complete.")
                return 'complete'
            elif 'error' in output:
                logger.error("Kernel execution finished with error.")
                return 'error'
            elif 'cancelled' in output:
                logger.warning("Kernel execution was cancelled.")
                return 'cancelled'
            elif 'running' in output or 'queued' in output:
                logger.info("Kernel is still running/queued...")
            else:
                logger.info(f"Unknown status from Kaggle: {result.stdout.strip()}")
                
        time.sleep(poll_interval)
        
    logger.error(f"Timeout reached ({timeout_minutes} minutes) while waiting for kernel.")
    return 'timeout'

def download_output(kernel_slug, local_output_dir, project_root):
    logger.info(f"Downloading output for {kernel_slug} to {local_output_dir}")
    kaggle_cmd = get_kaggle_cmd()
    
    out_path = Path(local_output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    result = run_cmd(kaggle_cmd + ['kernels', 'output', kernel_slug, '-p', str(out_path)], check=False)
    if result.returncode != 0:
        logger.error("Failed to download kernel output.")
        return []
        
    downloaded_files = list(out_path.glob('*'))
    logger.info(f"Downloaded files: {[f.name for f in downloaded_files]}")
    
    project_root_path = Path(project_root)
    model_dest = project_root_path / 'src' / 'ml' / 'wearable_health_model.pkl'
    results_dest = project_root_path / 'docs' / 'MODEL_TOURNAMENT_RESULTS.md'
    
    for f in downloaded_files:
        if f.name == 'wearable_health_model.pkl':
            model_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, model_dest)
            logger.info(f"Copied model to {model_dest}")
        elif f.name == 'MODEL_TOURNAMENT_RESULTS.md':
            results_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, results_dest)
            logger.info(f"Copied results to {results_dest}")
            
    return [str(f) for f in downloaded_files]

def run_full_pipeline(project_root):
    project_path = Path(project_root)
    parquet_dir = project_path / 'data' / 'processed'
    tournament_script = project_path / 'src' / 'ml' / 'multi_model_tournament.py'
    
    if not parquet_dir.exists():
        parquet_dir.mkdir(parents=True, exist_ok=True)
        logger.warning(f"{parquet_dir} did not exist, created it. Ensure it contains the parquet files.")
        
    if not tournament_script.exists():
        logger.error(f"Tournament script not found at {tournament_script}")
        return False
        
    logger.info("=== STEP 1: Uploading Dataset ===")
    if not create_and_upload_dataset(str(parquet_dir), DATASET_SLUG):
        return False
        
    logger.info("=== STEP 2: Preparing Kernel ===")
    tmp_kernel_dir = project_path / 'tmp' / 'kaggle_kernel'
    if not prepare_kernel(str(tournament_script), DATASET_SLUG, KERNEL_SLUG, str(tmp_kernel_dir)):
        return False
        
    logger.info("=== STEP 3: Pushing Kernel ===")
    if not push_kernel(str(tmp_kernel_dir)):
        return False
        
    logger.info("=== STEP 4: Polling Status ===")
    status = poll_kernel_status(KERNEL_SLUG)
    if status != 'complete':
        logger.error(f"Pipeline stopped because kernel status is {status}")
        return False
        
    logger.info("=== STEP 5: Downloading Output ===")
    tmp_output_dir = project_path / 'tmp' / 'kaggle_output'
    downloaded = download_output(KERNEL_SLUG, str(tmp_output_dir), str(project_path))
    
    logger.info(f"Pipeline finished successfully. Downloaded {len(downloaded)} files.")
    return True

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='TRIDENT Kaggle Training Orchestrator')
    parser.add_argument('--project-root', default='.', help='Project root directory')
    parser.add_argument('--action', choices=['upload', 'push', 'status', 'download', 'full'], default='full')
    parser.add_argument('--kernel-slug', default=KERNEL_SLUG)
    parser.add_argument('--dataset-slug', default=DATASET_SLUG)
    args = parser.parse_args()
    
    if args.action == 'upload':
        parquet_dir = Path(args.project_root) / 'data' / 'processed'
        create_and_upload_dataset(str(parquet_dir), args.dataset_slug)
    elif args.action == 'push':
        tmp_kernel_dir = Path(args.project_root) / 'tmp' / 'kaggle_kernel'
        tournament_script = Path(args.project_root) / 'src' / 'ml' / 'multi_model_tournament.py'
        prepare_kernel(str(tournament_script), args.dataset_slug, args.kernel_slug, str(tmp_kernel_dir))
        push_kernel(str(tmp_kernel_dir))
    elif args.action == 'status':
        poll_kernel_status(args.kernel_slug)
    elif args.action == 'download':
        tmp_output_dir = Path(args.project_root) / 'tmp' / 'kaggle_output'
        download_output(args.kernel_slug, str(tmp_output_dir), args.project_root)
    elif args.action == 'full':
        run_full_pipeline(args.project_root)
