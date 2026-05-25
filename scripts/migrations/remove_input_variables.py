"""Migration: remove deprecated input_variables field from workflows collection."""
from pymongo import MongoClient
import sys

MONGO_URI = "mongodb://admin:tradingagents123@mongodb:27017/tradingagentscn?authSource=admin"


def up():
    client = MongoClient(MONGO_URI)
    db = client["tradingagentscn"]
    result = db.workflows.update_many(
        {"input_variables": {"$exists": True}},
        {"$unset": {"input_variables": ""}},
    )
    print(f"Removed input_variables from {result.modified_count} workflow docs")
    client.close()


if __name__ == "__main__":
    up()
