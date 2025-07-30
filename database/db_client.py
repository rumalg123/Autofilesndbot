import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import info

# Use a single Mongo client with connection pooling
# maxPoolSize can be tuned based on expected concurrency
client = AsyncIOMotorClient(info.DATABASE_URI, maxPoolSize=100)

# Reference to the default database
db = client[info.DATABASE_NAME]

# Semaphore to limit concurrent DB operations
mongo_sem = asyncio.Semaphore(100)

async def close():
    client.close()
