import urllib.request
import json
import sys

def check_actions():
    url = "https://api.github.com/repos/iahmedd-k/Basarat-fyp-official/actions/runs?per_page=6"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"})

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            runs = data.get("workflow_runs", [])
            print(f"Total Workflow Runs: {data.get('total_count', len(runs))}")
            print("="*80)
            for r in runs:
                run_id = r.get("id")
                name = r.get("name")
                status = r.get("status")
                conclusion = r.get("conclusion")
                html_url = r.get("html_url")
                head_commit = r.get("head_commit", {}) or {}
                commit_sha = head_commit.get("id", "")[:7]
                commit_msg = (head_commit.get("message", "") or "").splitlines()[0]
                created_at = r.get("created_at")
                updated_at = r.get("updated_at")
                
                print(f"Run ID: {run_id} | Status: {status} | Conclusion: {conclusion}")
                print(f"Workflow: {name} | Commit: [{commit_sha}] {commit_msg}")
                print(f"URL: {html_url}")
                
                # Fetch job steps for in-progress / queued runs
                if status in ("in_progress", "queued", "pending"):
                    jobs_url = f"https://api.github.com/repos/iahmedd-k/Basarat-fyp-official/actions/runs/{run_id}/jobs"
                    j_req = urllib.request.Request(jobs_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"})
                    try:
                        with urllib.request.urlopen(j_req) as j_resp:
                            j_data = json.loads(j_resp.read().decode("utf-8"))
                            for j in j_data.get("jobs", []):
                                print(f"  [Job: {j.get('name')}] Status: {j.get('status')} | Conclusion: {j.get('conclusion')}")
                                for s in j.get("steps", []):
                                    print(f"    - Step: {s.get('name')} [{s.get('status')}] (Result: {s.get('conclusion')})")
                    except Exception:
                        pass
                print("-" * 80)
    except Exception as e:
        print(f"Error fetching GitHub Actions: {e}")

if __name__ == "__main__":
    check_actions()
