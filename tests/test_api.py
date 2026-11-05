import asyncio
import os
import sys

# Ensure backend root is on Python module path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import AsyncClient, ASGITransport
from app.main import app


async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "SSB Journey Voice API"
        assert "websocket_url" in data
        print("[PASS] Root endpoint passed:", data)


async def test_healthz():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/healthz")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "gemini-2.5-flash-native-audio-preview" in data["model"]
        print("[PASS] Healthz endpoint passed:", data)


async def test_readyz():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/readyz")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ready"
        print("[PASS] Readyz endpoint passed:", data)


async def main():
    print("Running FastAPI integration tests...")
    await test_root()
    await test_healthz()
    await test_readyz()
    print("All tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
