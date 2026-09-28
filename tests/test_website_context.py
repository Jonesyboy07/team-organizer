import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from website import create_app
from website.utils.auth_store import create_session, get_session
from website.utils.dashboard_context import get_storage_overview


class WebsiteContextTests(unittest.TestCase):
    def test_storage_overview_summarizes_repo_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            data_dir = repo_root / "data"
            events_dir = data_dir / "events"
            data_dir.mkdir()
            events_dir.mkdir()
            (data_dir / "storage.db").write_text("", encoding="utf-8")
            (data_dir / "servers.json").write_text("{}", encoding="utf-8")
            (data_dir / "commands.json").write_text("{}", encoding="utf-8")

            overview = get_storage_overview(
                repo_root=repo_root,
                server_data_loader=lambda: {
                    "1": {"teams": [{"name": "Alpha"}, {"name": "Bravo"}]},
                    "2": {"teams": [{"name": "Charlie"}]},
                },
            )

        self.assertEqual(overview["summary"]["server_count"], 2)
        self.assertEqual(overview["summary"]["team_count"], 3)
        self.assertTrue(overview["sources"][0]["exists"])
        self.assertTrue(any(source["path"] == "data/events" and source["exists"] for source in overview["sources"]))

    def test_storage_overview_handles_uninitialized_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            data_dir = repo_root / "data"
            data_dir.mkdir()
            (data_dir / "storage.db").write_text("", encoding="utf-8")

            overview = get_storage_overview(repo_root=repo_root)

        self.assertEqual(overview["summary"]["server_count"], 0)
        self.assertEqual(overview["summary"]["team_count"], 0)

    def test_dashboard_route_renders_outline(self):
        app = create_app()
        client = app.test_client()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"react-root", response.data)
        self.assertIn(b"dist/assets/dashboard.js", response.data)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        script = client.get("/static/dist/assets/dashboard.js")
        self.assertEqual(script.mimetype, "application/javascript")
        private_response = client.get("/api/dashboard")
        self.assertEqual(private_response.status_code, 401)
        self.assertNotIn(b"tracked_users", private_response.data)

    def test_private_api_and_legal_pages(self):
        app = create_app()
        client = app.test_client()

        status = client.get("/api/session")
        self.assertFalse(status.json["authenticated"])
        self.assertEqual(client.get("/api/dashboard").status_code, 401)
        self.assertIn(b"not published for public browsing", client.get("/privacy").data)
        self.assertIn(b"j0nesy_", client.get("/terms").data)

    def test_oauth_login_requires_configuration(self):
        with patch.dict(os.environ, {"DISCORD_OAUTH_CLIENT_SECRET": ""}, clear=False):
            client = create_app().test_client()
            response = client.get("/auth/discord/login")

        self.assertEqual(response.status_code, 503)

    def test_oauth_credentials_are_encrypted_in_persistent_session_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = str(Path(tmpdir) / "storage.db")
            with patch.dict(os.environ, {"WEBSITE_SECRET_KEY": "test-stable-key"}, clear=False), patch(
                "utils.server_store.DB_FILE", database
            ), patch("utils.website_queue.DB_FILE", database), patch("website.utils.auth_store.DB_FILE", database):
                app = create_app()
                with app.app_context():
                    session_id, _ = create_session(
                        {"id": "42", "username": "tester"},
                        {"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 3600},
                        [{"id": "99", "name": "Test server"}],
                    )
                    restored = get_session(session_id)
                connection = sqlite3.connect(database)
                try:
                    raw_session = connection.execute("SELECT data FROM website_sessions").fetchone()[0]
                finally:
                    connection.close()

        self.assertEqual(restored["refresh_token"], "refresh-secret")
        self.assertEqual(restored["guilds"][0]["id"], "99")
        self.assertNotIn("refresh-secret", raw_session)

    def test_dashboard_route_uses_configured_env_values(self):
        with patch.dict(
            os.environ,
            {
                "WEBSITE_HOST": "localhost",
                "WEBSITE_PORT": "9091",
                "WEBSITE_BASE_URL": "https://dashboard.example.com/",
                "WEBSITE_SECRET_KEY": "test-secret",
                "DISCORD_OAUTH_CLIENT_ID": "client-id",
                "DISCORD_OAUTH_CLIENT_SECRET": "client-secret",
            },
            clear=False,
        ):
            app = create_app()

        client = app.test_client()
        response = client.get("/")

        self.assertEqual(app.config["WEBSITE_PORT"], 9091)
        self.assertEqual(
            app.config["DISCORD_OAUTH_REDIRECT_URI"],
            "https://dashboard.example.com/auth/discord/callback",
        )
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"dist/assets/dashboard.js", response.data)
        self.assertIn("max-age=31536000", response.headers["Strict-Transport-Security"])
        login = client.get("/auth/discord/login")
        self.assertEqual(
            parse_qs(urlsplit(login.location).query)["redirect_uri"],
            ["https://dashboard.example.com/auth/discord/callback"],
        )

    def test_invalid_port_raises_clear_error(self):
        with patch.dict(os.environ, {"WEBSITE_PORT": "not-a-number"}, clear=False):
            with self.assertRaisesRegex(ValueError, "WEBSITE_PORT must be set to a numeric port value."):
                create_app()

    def test_out_of_range_port_raises_clear_error(self):
        for port in ("0", "70000"):
            with self.subTest(port=port):
                with patch.dict(os.environ, {"WEBSITE_PORT": port}, clear=False):
                    with self.assertRaisesRegex(ValueError, "WEBSITE_PORT must be between 1 and 65535."):
                        create_app()

    def test_blank_redirect_override_uses_derived_callback(self):
        with patch.dict(
            os.environ,
            {
                "WEBSITE_HOST": "localhost",
                "WEBSITE_PORT": "9092",
                "WEBSITE_BASE_URL": "",
            },
            clear=False,
        ):
            app = create_app()

        self.assertEqual(
            app.config["DISCORD_OAUTH_REDIRECT_URI"],
            "http://localhost:9092/auth/discord/callback",
        )

    def test_bind_all_host_uses_loopback_callback(self):
        with patch.dict(
            os.environ,
            {
                "WEBSITE_HOST": "0.0.0.0",
                "WEBSITE_PORT": "9093",
                "WEBSITE_BASE_URL": "",
            },
            clear=False,
        ):
            app = create_app()

        self.assertEqual(
            app.config["DISCORD_OAUTH_REDIRECT_URI"],
            "http://127.0.0.1:9093/auth/discord/callback",
        )

    def test_invalid_website_base_url_raises_clear_error(self):
        for base_url in (
            "ftp://dashboard.example.com",
            "https://dashboard.example.com/path",
            "https://dashboard.example.com?query=1",
        ):
            with self.subTest(base_url=base_url), patch.dict(
                os.environ, {"WEBSITE_BASE_URL": base_url}, clear=False
            ):
                with self.assertRaisesRegex(ValueError, r"WEBSITE_BASE_URL must be an http\(s\) origin"):
                    create_app()


if __name__ == "__main__":
    unittest.main()
