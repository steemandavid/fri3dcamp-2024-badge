# run_namebadge.py — test harness: run the NameBadge app under the real Application loop.
import logging
logging.basicConfig(level=logging.INFO, force=True)
from fri3d.application import Application
Application(default_app='user.name_badge').run()
print("APP_RUN_RETURNED")
