#!/usr/bin/env python3

import sys
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

sys.path.insert(
    0,
    str(PROJECT_ROOT)
)


# ============================================================
# APPLICATION
# ============================================================

from app import create_app

from app.services.cricsheet_importer import (
    import_cricsheet_json
)


def main():

    print()
    print(
        "############################################"
    )

    print(
        "#        PITCHVISION AI DATA BUILDER       #"
    )

    print(
        "############################################"
    )

    json_directory = (
        PROJECT_ROOT
        / "all_json"
    )

    if not json_directory.exists():

        print(
            f"\nERROR: Directory does not exist:"
        )

        print(
            json_directory
        )

        sys.exit(1)

    json_files = list(
        json_directory.glob("*.json")
    )

    print()
    print(
        f"Project root : {PROJECT_ROOT}"
    )

    print(
        f"JSON folder  : {json_directory}"
    )

    print(
        f"JSON files   : {len(json_files)}"
    )

    print()

    if not json_files:

        print(
            "ERROR: No JSON files found."
        )

        sys.exit(1)

    # ================================================
    # CREATE APPLICATION
    # ================================================

    app = create_app()

    # ================================================
    # PROCESS DATA
    # ================================================

    with app.app_context():

        try:

            result = import_cricsheet_json(
                json_directory
            )

        except Exception as error:

            print()
            print(
                "ERROR DURING IMPORT:"
            )

            print(error)

            raise

    print()
    print(
        "############################################"
    )

    print(
        "#             IMPORT FINISHED              #"
    )

    print(
        "############################################"
    )

    print(
        f"Venue-format records created/updated: "
        f"{result}"
    )

    print()


if __name__ == "__main__":
    main()