import os
import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    port = int(os.environ.get("PORT", settings.PORT))
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=port,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )

