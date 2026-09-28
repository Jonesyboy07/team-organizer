import ipaddress
import os
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, render_template, request

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

from .api import api


def _get_website_port() -> int:
    raw_port = os.getenv("WEBSITE_PORT", "9090")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("WEBSITE_PORT must be set to a numeric port value.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("WEBSITE_PORT must be between 1 and 65535.")
    return port


def _get_callback_host(host: str) -> str:
    if host in {"", "0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"

    normalized = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        parsed_host = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized

    if parsed_host.version == 6:
        return f"[{parsed_host.compressed}]"
    return parsed_host.compressed


def _get_website_base_url(host: str, port: int) -> str:
    configured_url = os.getenv("WEBSITE_BASE_URL", "").strip()
    if configured_url:
        parsed_url = urlsplit(configured_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.path not in {"", "/"}
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("WEBSITE_BASE_URL must be an http(s) origin without a path, query, or fragment.")
        return configured_url.rstrip("/")

    callback_host = _get_callback_host(host)
    return f"http://{callback_host}:{port}"


def create_app() -> Flask:
    website_host = os.getenv("WEBSITE_HOST", "127.0.0.1")
    website_port = _get_website_port()
    website_base_url = _get_website_base_url(website_host, website_port)
    website_scheme = urlsplit(website_base_url).scheme

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=os.getenv("WEBSITE_SECRET_KEY") or secrets.token_hex(32),
        WEBSITE_HOST=website_host,
        WEBSITE_PORT=website_port,
        WEBSITE_BASE_URL=website_base_url,
        DISCORD_OAUTH_CLIENT_ID=os.getenv("DISCORD_OAUTH_CLIENT_ID", os.getenv("DISCORD_CLIENT_ID", "")),
        DISCORD_OAUTH_CLIENT_SECRET=os.getenv("DISCORD_OAUTH_CLIENT_SECRET", ""),
        DISCORD_OAUTH_REDIRECT_URI=f"{website_base_url}/auth/discord/callback",
        PERMANENT_SESSION_LIFETIME=timedelta(days=90),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=website_scheme == "https",
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    app.register_blueprint(api)

    @app.after_request
    def security_headers(response):
        if request.path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript; charset=utf-8"
        elif request.path.endswith(".css"):
            response.headers["Content-Type"] = "text/css; charset=utf-8"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://discord.com"
        )
        if request.path.startswith(("/api/", "/auth/", "/static/")) or request.path in {"/", "/terms", "/privacy"}:
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers["Cache-Control"] = "public, max-age=300"
        if website_scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", title="Team Organizer")

    @app.get("/terms")
    def terms():
        return render_template("legal.html", document="terms")

    @app.get("/privacy")
    def privacy():
        return render_template("legal.html", document="privacy")

    return app


def main() -> None:
    app = create_app()
    app.run(
        host=app.config["WEBSITE_HOST"],
        port=app.config["WEBSITE_PORT"],
        debug=False,
    )


if __name__ == "__main__":
    main()
