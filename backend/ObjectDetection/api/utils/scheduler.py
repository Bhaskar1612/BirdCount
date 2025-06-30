import time
from apscheduler.schedulers.background import BackgroundScheduler
from .enms_divproto import update_active_learning_rankings
from Common.shared_utils import get_db_connection, MODEL_TYPE_OBJECT_DETECTION, logger

last_processed_count = 0
THRESHOLD = 50


def check_and_update_rankings():
    global last_processed_count
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM images WHERE consent = true AND model_type = %s",
                    (MODEL_TYPE_OBJECT_DETECTION,)
                )
                image_count = cur.fetchone()[0]

                if image_count - last_processed_count >= THRESHOLD:
                    logger.info(
                        f"New images count ({image_count - last_processed_count}) reached threshold. Updating active learning rankings."
                    )
                    update_active_learning_rankings()
                    last_processed_count = image_count

    except Exception as e:
        logger.error(f"Error checking/updating rankings: {e}")


if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(check_and_update_rankings, 'interval', minutes=1)
    scheduler.start()
    logger.info(
        "APScheduler started: checking for ranking updates every minute.")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("APScheduler shutdown.")
