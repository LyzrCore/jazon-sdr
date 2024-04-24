import imaplib
from uuid import uuid4
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import Dict, Optional

from app.agent import JaWorker
from app import settings,imap_service

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

ja_workers: Dict[str, JaWorker] = {}


@app.post("/add-prospect/")
async def run_sales_pipeline(email: str, background_tasks: BackgroundTasks):
    """
    Starts a sales pipeline for the given email. If the email already has an associated pipeline, returns an error.
    """
    if email in ja_workers:
        raise HTTPException(status_code=400, detail="Email already taken")

    sales_agent = JaWorker(
        open_ai_key=settings.open_ai_key,
        perplexity_api_key=settings.perplexity_key,
        company_product_data_fp=settings.company_product_data_fp,
        previous_sales_data_fp=settings.previous_sales_data_fp,
        mailer=imap_service,
    )
    sales_agent.configure_mail_service(
        username=settings.email,
        password=settings.password,
        port=settings.port,
        sender_email=settings.email,
        imap_server=settings.imap_server,
        smtp_server=settings.smtp_server,
    )
    sales_agent.init()
    ja_workers[email] = sales_agent
    background_tasks.add_task(start_async_task, email, sales_agent)
    return {"message": "Sales pipeline initiated", "email": email}


def start_async_task(email: str, sales_agent: JaWorker):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(sales_agent.run_pipeline(prospect_email=email))
    loop.close()


@app.get("/logs/")
async def get_logs(email: Optional[str] = Query(None)):
    """
    Returns the logs for the specified email. If the email does not have an associated sales pipeline, returns an error.
    """
    if email is None or email not in ja_workers:
        raise HTTPException(status_code=404, detail="No logs found for the given email")

    sales_agent = ja_workers[email]
    return {"logs": sales_agent.logs}
