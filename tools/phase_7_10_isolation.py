"""Step 7 — Cross-user isolation end-to-end against the live backend."""
import json
import sys
import time

import requests

BASE = "http://127.0.0.1:8000"
tokens = json.load(open("tokens.json"))["tokens"]
TA = tokens["USER_A"]["id_token"]
TB = tokens["USER_B"]["id_token"]
UA = tokens["USER_A"]["local_id"]
UB = tokens["USER_B"]["local_id"]

H_A = {"Authorization": f"Bearer {TA}", "Content-Type": "application/json"}
H_B = {"Authorization": f"Bearer {TB}", "Content-Type": "application/json"}

failures = []


def expect(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    if not condition:
        failures.append(name)
    print(f"  [{status}] {name}{(' — ' + detail) if detail else ''}")


# 1. Create a draft for each user.
draft_a = requests.post(
    f"{BASE}/api/v1/drafts", headers=H_A, json={"topic": "iso A", "title": "iso-A", "content": "A"}
).json()
draft_b = requests.post(
    f"{BASE}/api/v1/drafts", headers=H_B, json={"topic": "iso B", "title": "iso-B", "content": "B"}
).json()
IDA, IDB = draft_a["draft_id"], draft_b["draft_id"]
print(f"created IDA={IDA} UB={UB}")
print(f"created IDB={IDB} UA={UA}")

# 2. Cross-user GET.
expect("USER_A GET USER_B draft -> 404",
       requests.get(f"{BASE}/api/v1/drafts/{IDB}", headers=H_A).status_code == 404)
expect("USER_B GET USER_A draft -> 404",
       requests.get(f"{BASE}/api/v1/drafts/{IDA}", headers=H_B).status_code == 404)
expect("USER_A GET own draft -> 200",
       requests.get(f"{BASE}/api/v1/drafts/{IDA}", headers=H_A).status_code == 200)

# 3. Cross-user PUT.
expect("USER_A PUT USER_B draft -> 404",
       requests.put(f"{BASE}/api/v1/drafts/{IDB}", headers=H_A,
                    json={"title": "hijack"}).status_code == 404)

# 4. Cross-user DELETE.
expect("USER_A DELETE USER_B draft -> 404",
       requests.delete(f"{BASE}/api/v1/drafts/{IDB}", headers=H_A).status_code == 404)
# Verify it still exists for USER_B.
expect("USER_B draft still exists after cross-user DELETE attempt",
       requests.get(f"{BASE}/api/v1/drafts/{IDB}", headers=H_B).status_code == 200)

# 5. List user-scoped.
list_a = requests.get(f"{BASE}/api/v1/drafts", headers=H_A).json()
list_b = requests.get(f"{BASE}/api/v1/drafts", headers=H_B).json()
ids_a = {x["draft_id"] for x in list_a["items"]}
ids_b = {x["draft_id"] for x in list_b["items"]}
expect("USER_A list does NOT include USER_B draft", IDB not in ids_a)
expect("USER_B list does NOT include USER_A draft", IDA not in ids_b)

# 6. Approval queue isolation.
queue_a = requests.get(f"{BASE}/api/v1/approval/queue", headers=H_A).json()
queue_b = requests.get(f"{BASE}/api/v1/approval/queue", headers=H_B).json()
tokens_a = {x["token"] for x in queue_a}
tokens_b = {x["token"] for x in queue_b}
expect("USER_A approval queue does NOT contain USER_B tokens",
       not tokens_a.intersection(tokens_b))

# 7. USER_A attempts to approve USER_B's token -> 404.
token_b = queue_b[0]["token"]
expect("USER_A approve USER_B token -> 404",
       requests.post(f"{BASE}/api/v1/approval/approve", headers=H_A,
                     json={"token": token_b}).status_code == 404)

# 8. USER_A attempts to edit USER_B draft -> 404.
expect("USER_A edit USER_B draft -> 404",
       requests.post(f"{BASE}/api/v1/approval/edit", headers=H_A,
                     json={"draft_id": IDB, "title": "hijack", "content": "x"}).status_code == 404)

# 9. Scheduler cancel isolation.
job_b = requests.post(
    f"{BASE}/api/v1/scheduler/schedule", headers=H_B,
    json={"title": "iso job B", "content": "B content", "hashtags": [],
          "scheduled_time": "2099-01-01T00:00:00Z"},
).json()
job_b_id = job_b["job_id"]
expect("USER_A cancel USER_B scheduled job -> 404",
       requests.delete(f"{BASE}/api/v1/scheduler/jobs/{job_b_id}", headers=H_A).status_code == 404)
# And USER_B can cancel their own job.
expect("USER_B cancel own scheduled job -> 204",
       requests.delete(f"{BASE}/api/v1/scheduler/jobs/{job_b_id}", headers=H_B).status_code == 204)

# 10. Dashboard / activity isolation.
summary_a = requests.get(f"{BASE}/api/v1/dashboard/summary", headers=H_A).json()
summary_b = requests.get(f"{BASE}/api/v1/dashboard/summary", headers=H_B).json()
expect("Dashboard counts differ per user (USER_A drafts >= 1)",
       summary_a["drafts_count"] >= 1)
# USER_B cancelled their own job; counts should match each user's own data
print(f"  USER_A dashboard: {summary_a}")
print(f"  USER_B dashboard: {summary_b}")

act_a = requests.get(f"{BASE}/api/v1/activity/recent", headers=H_A).json()
act_b = requests.get(f"{BASE}/api/v1/activity/recent", headers=H_B).json()
expect("Activity endpoints respond 200 for both users",
       isinstance(act_a.get("items"), list) and isinstance(act_b.get("items"), list))

# Cleanup test drafts.
requests.delete(f"{BASE}/api/v1/drafts/{IDA}", headers=H_A)
requests.delete(f"{BASE}/api/v1/drafts/{IDB}", headers=H_B)

if failures:
    print(f"\n{len(failures)} failures:", failures)
    sys.exit(1)
print("\nStep 7 — all cross-user isolation checks PASS.")