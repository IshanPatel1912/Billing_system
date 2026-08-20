import logging
import logging.handlers
import os
import sys

if os.name == 'nt':  # Windows
    base_dir = os.getenv('LOCALAPPDATA')
    # Falls back to User Profile if AppData is missing
    if not base_dir:
        base_dir = os.path.expanduser('~')
    LOG_DIR = os.path.join(base_dir, 'BillingSystem', 'logs')
else:  # Linux/Mac
    LOG_DIR = os.path.join(os.path.expanduser('~'), '.BillingSystem', 'logs')

os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'app.log') 


def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)

    fmt = logging.Formatter('%(asctime)s %(levelname)-8s [%(name)s] %(message)s')

    fh = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=5_000_000, backupCount=5, encoding='utf-8')
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    logging.getLogger('pyinstaller').setLevel(logging.INFO)

    root.info('Logging initialized. Log file: %s', LOG_PATH)
