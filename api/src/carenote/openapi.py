"""Print the OpenAPI schema as JSON. Used to generate TypeScript types for the web app."""

import json
import sys

from carenote.main import create_app


def main() -> None:
    json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
