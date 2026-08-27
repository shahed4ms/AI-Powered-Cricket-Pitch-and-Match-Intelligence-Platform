import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "::"),
        port=int(os.getenv("PORT", "5001")),
        debug=True,
        use_reloader=False,
    )
