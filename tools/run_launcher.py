import logging
logging.basicConfig(level=logging.INFO, force=True)
from fri3d.application import Application
Application(default_app='user.neon_launcher').run()
print("LAUNCHER_RETURNED")
