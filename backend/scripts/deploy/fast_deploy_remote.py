import subprocess
import tarfile
import os
import tempfile
from pathlib import Path

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"
LOCAL_BACKEND = Path(__file__).resolve().parent.parent.parent

FILES_TO_DEPLOY = [
    "app/core/id_generator.py",
    "app/core/redis.py",
    "app/celery_app.py",
    "app/models/community.py",
    "app/services/trending_service.py",
    "app/services/community_service.py",
    "app/services/community_cache_service.py",
    "app/services/portfolio_service.py",
    "app/api/v1/community/posts.py",
    "app/api/v1/community/comments.py",
    "app/api/v1/community/follows.py",
    "app/api/v1/community/profile.py",
    "app/api/v1/community/notifications.py",
    "app/services/stock_service.py",
    "app/tasks/refresh_fundamentals.py",
    "app/tasks/scrape_news.py",
    "app/data/scraper/run_after_close.py",
    "app/schemas/stock.py",
]

def main():
    tar_path = LOCAL_BACKEND / "deploy_update.tar.gz"
    print("1. Creating tar archive of updated files...")
    with tarfile.open(tar_path, "w:gz") as tar:
        for rel in FILES_TO_DEPLOY:
            local_path = LOCAL_BACKEND / rel
            if local_path.exists():
                tar.add(local_path, arcname=rel)
                print(f"   + {rel}")
            else:
                print(f"   ! Missing: {local_path}")

    print("\n2. Uploading archive to remote /tmp...")
    scp_cmd = [
        "scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
        str(tar_path), f"{REMOTE_USER}@{REMOTE_HOST}:/tmp/deploy_update.tar.gz"
    ]
    res = subprocess.run(scp_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("SCP failed:", res.stderr)
        return
    print("   Archive uploaded successfully.")

    print("\n3. Extracting files into Docker containers and restarting...")
    remote_script = """
    set -e
    for container in basarat-app-1 basarat-celery-worker-1 basarat-celery-beat-1; do
        echo "Extracting into $container..."
        sudo docker cp /tmp/deploy_update.tar.gz $container:/tmp/deploy_update.tar.gz
        sudo docker exec $container tar -xzvf /tmp/deploy_update.tar.gz -C /app
    done
    echo "Restarting containers..."
    sudo docker restart basarat-app-1 basarat-celery-worker-1 basarat-celery-beat-1
    echo "Checking container status..."
    sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
    """
    
    ssh_cmd = [
        "ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
        f"{REMOTE_USER}@{REMOTE_HOST}", remote_script
    ]
    res = subprocess.run(ssh_cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)

    if tar_path.exists():
        tar_path.unlink()
    print("\nDeployment complete!")

if __name__ == "__main__":
    main()
