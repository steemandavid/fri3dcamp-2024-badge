# Fri3d Badge boot entry — runs the neon launcher menu as the default program.
# Delete this file (and reset) to restore the original REPL-only main.py (self-healing).
import logging
from fri3d.application import Application

logging.basicConfig(level=logging.WARNING, force=True)
Application(default_app='user.neon_launcher').run()
