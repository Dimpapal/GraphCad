"""Primary entry point for GraphCad; legacy run_graphite.py remains compatible."""
from graphite.app import main

if __name__ == "__main__":
    raise SystemExit(main())
