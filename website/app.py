import os

from flask import Flask, render_template

from .utils.dashboard_context import build_dashboard_context


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=os.getenv("WEBSITE_SECRET_KEY") or "dev-website-secret-key",
        WEBSITE_HOST=os.getenv("WEBSITE_HOST", "127.0.0.1"),
        WEBSITE_PORT=int(os.getenv("WEBSITE_PORT", "9090")),
        DISCORD_OAUTH_CLIENT_ID=os.getenv("DISCORD_OAUTH_CLIENT_ID", os.getenv("DISCORD_CLIENT_ID", "")),
        DISCORD_OAUTH_CLIENT_SECRET=os.getenv("DISCORD_OAUTH_CLIENT_SECRET", ""),
        DISCORD_OAUTH_REDIRECT_URI=os.getenv(
            "DISCORD_OAUTH_REDIRECT_URI",
            "http://127.0.0.1:9090/auth/discord/callback",
        ),
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
