import logging
from database import SessionLocal
from models import Log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def db_log(message: str, level: str = "info"):
    # Log vers la console
    getattr(logger, level, logger.info)(message)
    # Persistance en BDD
    db = SessionLocal()
    try:
        db.add(Log(message=message, level=level))
        db.commit()
    except Exception as e:
        logger.error(f"Erreur log BDD: {e}")
    finally:
        db.close()
