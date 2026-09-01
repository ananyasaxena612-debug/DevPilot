import logging

logging.basicConfig(
    filename="../logs/app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.info("DevPilot application started")
logging.info("Application is running")
logging.error("Database connection failed")
