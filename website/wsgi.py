from dotenv import load_dotenv

from website.app import ROOT_DIR, create_app

load_dotenv(ROOT_DIR / ".env")

app = create_app()


def main():
    from waitress import serve

    serve(app, host=app.config["WEBSITE_HOST"], port=app.config["WEBSITE_PORT"])


if __name__ == "__main__":
    main()