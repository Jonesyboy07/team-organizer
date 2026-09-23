import os
import secrets

from flask import Flask, render_template

from .utils.dashboard_context import build_dashboard_context


def _get_website_port() -> int:
    raw_port = os.getenv("WEBSITE_PORT", "9090")
    try:
        return int(raw_port)
    except ValueError as exc:
        raise ValueError("WEBSITE_PORT must be set to a numeric port value.") from exc


def _get_redirect_uri(host: str, port: int) -> str:
    callback_host = "127.0.0.1" if host in {"", "0.0.0.0"} else host
    redirect_uri = os.getenv("DISCORD_OAUTH_REDIRECT_URI")
    return redirect_uri or f"http://{callback_host}:{port}/auth/discord/callback"


def create_app() -> Flask:
    website_host = os.getenv("WEBSITE_HOST", "127.0.0.1")
    website_port = _get_website_port()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=os.getenv("WEBSITE_SECRET_KEY") or secrets.token_hex(32),
        WEBSITE_HOST=website_host,
        WEBSITE_PORT=website_port,
        DISCORD_OAUTH_CLIENT_ID=os.getenv("DISCORD_OAUTH_CLIENT_ID", os.getenv("DISCORD_CLIENT_ID", "")),
        DISCORD_OAUTH_CLIENT_SECRET=os.getenv("DISCORD_OAUTH_CLIENT_SECRET", ""),
        DISCORD_OAUTH_REDIRECT_URI=_get_redirect_uri(website_host, website_port),
    )

    @app.get("/")
    def dashboard():
        context = build_dashboard_context(
            website_port=app.config["WEBSITE_PORT"],
            discord_oauth_ready=bool(
                app.config["DISCORD_OAUTH_CLIENT_ID"]
                and app.config["DISCORD_OAUTH_CLIENT_SECRET"]
            ),
        )
        return render_template("dashboard.html", **context)

    return app


app = create_app()


def main() -> None:
    app.run(
        host=app.config["WEBSITE_HOST"],
        port=app.config["WEBSITE_PORT"],
        debug=False,
    )


if __name__ == "__main__":
    main()
