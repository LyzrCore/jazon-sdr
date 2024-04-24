import os
from dotenv import load_dotenv

from app.settings import Settings
from app.utils import create_imap_service

load_dotenv()

settings_config = {
    "open_ai_key": os.getenv("OPEN_AI_KEY"),
    "perplexity_key": os.getenv("PERPLEXITY_KEY"),
    "email": os.getenv("EMAIL"),
    "password": os.getenv("PASSWORD"),
    "port": int(os.getenv("PORT")),
    "imap_server": os.getenv("IMAP_SERVER"),
    "smtp_server": os.getenv("SMTP_SERVER"),
    "company_product_data_fp": os.getenv("COMPANY_PRODUCT_DATA_FP"),
    "previous_sales_data_fp": os.getenv("PREVIOUS_SALES_DATA_FP"),
}
settings = Settings(**settings_config)

imap_service = create_imap_service(
    settings.imap_server, settings.email, settings.password
)
