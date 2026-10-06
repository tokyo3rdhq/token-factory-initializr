import os
import pytest
import requests
from dotenv import load_dotenv

# 加载环境
load_dotenv("data/.env") # 假设环境变量优先
# 注意：web/.env 里的 CLOUDFLARE_API_TOKEN 会覆盖 data/.env 里的，
# 为了测试准确，我们直接通过路径读取
def get_env_val(path, key):
    if not os.path.exists(path): return None
    with open(path) as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

ACCOUNT_ID = "79e02135eb865f42843c8dccc62feaa2"
NAMESPACE_ID = "0d4734eae9ce4b5d9ad4fa32e6ef462c"

def check_token(token, label):
    assert token, f"{label} token is empty"
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Verify
    resp = requests.get("https://api.cloudflare.com/client/v4/user/tokens/verify", headers=headers)
    assert resp.status_code == 200, f"{label} verify failed: {resp.text}"
    
    # 2. KV Access (Manifest)
    kv_url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/tfi:manifest:latest"
    resp = requests.get(kv_url, headers=headers)
    assert resp.status_code == 200, f"{label} KV read failed: {resp.text}"

@pytest.mark.integration
def test_data_token():
    token = get_env_val("data/.env", "CLOUDFLARE_API_TOKEN")
    check_token(token, "Data")

@pytest.mark.integration
def test_web_token_pages_edit():
    token = get_env_val("web/.env", "CLOUDFLARE_API_TOKEN")
    assert token, "Web token not found"
    
    headers = {"Authorization": f"Bearer {token}"}
    pages_url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/pages/projects"
    resp = requests.get(pages_url, headers=headers)
    assert resp.status_code == 200, f"Web token Pages edit permission missing: {resp.text}"
