"""Step 10 — Simulate USER_A having a LinkedIn account by inserting
encrypted tokens directly via the backend repository. Then verify USER_B
cannot see USER_A's connection status.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local", override=True)

MONGO_URI = os.environ["MONGODB_URI"]
DB_NAME = os.environ.get("MONGODB_DB_NAME", "linkedin_agent")
FERNET_KEY = os.environ["LINKEDIN_TOKEN_ENCRYPTION_KEY"].encode()
fernet = Fernet(FERNET_KEY)

tokens = json.load(open(ROOT / "tokens.json"))["tokens"]
UA = tokens["USER_A"]["local_id"]
UB = tokens["USER_B"]["local_id"]


async def main():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    # Plant USER_A's tokens (encrypted) directly into linkedin_accounts.
    expires_at = datetime.now(timezone.utc) + timedelta(days=60)
    await db["linkedin_accounts"].update_one(
        {"_id": UA},
        {
            "$set": {
                "access_token_enc": fernet.encrypt(b"FAKE_ACCESS_TOKEN_FOR_USER_A"),
                "refresh_token_enc": fernet.encrypt(b"FAKE_REFRESH_TOKEN_FOR_USER_A"),
                "expires_at": expires_at,
                "scope": "openid profile email w_member_social",
                "person_urn": "urn:li:person:FAKE_URN_FOR_USER_A",
                "connected_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    # Ensure USER_B has no record.
    await db["linkedin_accounts"].delete_one({"_id": UB})
    client.close()


asyncio.run(main())
print(f"planted USER_A ({UA}) linkedin_accounts record")
print(f"USER_B ({UB}) has no linkedin_accounts record")