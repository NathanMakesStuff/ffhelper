"""PyInstaller entry point; the package's own __main__.py uses a relative import that can't be frozen."""

from ffhelper.cli import main

raise SystemExit(main())
