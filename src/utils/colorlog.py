import logging

class ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[41m', # Red background
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        msg = super().format(record)
        return f"{color}{msg}{self.RESET}"

handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter('[%(levelname)s] %(message)s'))
logger = logging.getLogger(__name__)
logger.handlers.clear()
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logging.getLogger().setLevel(logging.INFO)