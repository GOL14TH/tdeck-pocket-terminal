"""Local-only browser simulator; never connects to the Pi."""

from pathlib import Path
import uvicorn
from fastapi.responses import HTMLResponse
from tdeck_companion.app import create_app
from tdeck_companion.config import Settings, HostProfile

def main():
    app = create_app(
        Settings(
            token="tdeck-simulation-only-do-not-use-on-pi",
            simulation=True,
            hosts=[HostProfile(id="pi", name="Simulated Pi")],
        )
    )

    @app.get("/", response_class=HTMLResponse)
    def index():
        return Path(__file__).with_name("simulator.html").read_text(encoding="utf-8")

    uvicorn.run(app, host="127.0.0.1", port=8788)

if __name__ == "__main__":
    main()
