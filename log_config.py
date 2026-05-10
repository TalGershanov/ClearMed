import logging
import logging.config
import os

# make log file
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,

    # format
    'formatters': {
        'detailed': {
            # time | level | module name | msg
            'format': '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(levelname)-8s | %(name)-15s | %(message)s'
        }
    },

    # where to (consule vs file)
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # up to 5mb
        'file_handler': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'clearmed.log'),
            'maxBytes': 5 * 1024 * 1024,  # 5 MB
            'backupCount': 3,
            'formatter': 'detailed',
            'encoding': 'utf-8'
        }
    },

    # logger hierarchy
    'loggers': {
        # parent logger
        'clearmed': {
            'handlers': ['console', 'file_handler'],
            'level': 'DEBUG',
            'propagate': False  # no double printing
        }
    }
}


def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)