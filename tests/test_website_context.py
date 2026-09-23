import tempfile
import unittest
from pathlib import Path

from website import create_app
from website.utils.dashboard_context import build_dashboard_context, get_storage_overview


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

    def test_dashboard_context_exposes_outline(self):
        context = build_dashboard_context(
            website_port=9090,
            discord_oauth_ready=True,
            server_data_loader=lambda: {},
        )

        self.assertEqual(context["outline"]["port"], 9090)
        self.assertEqual(context["outline"]["auth"], "Discord OAuth2 login flow")
        self.assertIn("React mount point", context["outline"]["frontend"])

    def test_dashboard_route_renders_outline(self):
        app = create_app()
        client = app.test_client()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Team Organizer Website Foundation", response.data)
        self.assertIn(b"React mount point", response.data)


if __name__ == "__main__":
    unittest.main()
