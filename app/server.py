import imaplib
from uuid import uuid4

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import Dict, Optional

from app.agent import JaWorker
from app import settings, imap_service
from app.utils import create_imap_service


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

ja_workers: Dict[str, JaWorker] = {}
tasks = {}

prompts = {
    "draft_email_agent_prompt": "you are a expert research draft email creator who is pervasive and will do anything to sell",
    "sales_agent_prompt": "you are a sales head manager who is good at recreating emails according to company's sales email history provided in the file, and you only return directly sendable email",
    "first_email_task_prompt": "create a email selling the product/service based on the pdf file provided during creation of assistant. Use the Client/ Prospect information provided (to whom you are selling) as PROSPECT_INFO:  to make the customized mail [IMPORTANT!] use html dont use css make it look fully human written. Send only EMAIL nothing extra",
    "reply_email_task_prompt": "based on the email response by user and previous email sent. send a response email adapting to the email. Use HTML but make it look like human written email make sure its well formatted. Use the conversions text file to draft it accordingly. **IMPORTANT** Only send the email no additional text",
}
class PromptUpdate(BaseModel):
    draft_email_agent_prompt: Optional[str] = None
    sales_agent_prompt: Optional[str] = None
    first_email_task_prompt: Optional[str] = None
    reply_email_task_prompt: Optional[str] = None


@app.put("/prompts/")
async def update_prompts(
    prompt_input:PromptUpdate
):
    try:
        print(prompts)
        if prompt_input.draft_email_agent_prompt is not None:
            prompts["draft_email_agent_prompt"] = prompt_input.draft_email_agent_prompt
        if prompt_input.sales_agent_prompt is not None:
            prompts["sales_agent_prompt"] = prompt_input.sales_agent_prompt
        if prompt_input.first_email_task_prompt is not None:
            prompts["first_email_task_prompt"] = prompt_input.first_email_task_prompt
        if prompt_input.reply_email_task_prompt is not None:
            prompts["reply_email_task_prompt"] = prompt_input.reply_email_task_prompt
        
        return {"updated": True}
    except Exception as e:
        print(e)
        return {"updated": False}


@app.get("/prompts/")
async def get_prompts(
):
    try:
        return {"prompts":prompts}
    except:
        return {"prompts":""}

@app.post("/add-prospect/")
async def run_sales_pipeline(email: str, background_tasks: BackgroundTasks):
    """
    Starts a sales pipeline for the given email. If the email already has an associated pipeline, returns an error.
    """
    if email in ja_workers:
        raise HTTPException(status_code=400, detail="Email already taken")

    imap_service = create_imap_service(
        settings.imap_server, settings.email, settings.password
    )
    
    sales_agent = JaWorker(
        open_ai_key=settings.open_ai_key,
        perplexity_api_key=settings.perplexity_key,
        company_product_data_fp=settings.company_product_data_fp,
        previous_sales_data_fp=settings.previous_sales_data_fp,
        mailer=imap_service,
        draft_mail_agent_prompt=prompts["draft_email_agent_prompt"],
        sales_agent_prompt=prompts["sales_agent_prompt"],
        first_email_task_prompt=prompts["first_email_task_prompt"],
        reply_email_task_prompt=prompts["reply_email_task_prompt"],
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


# def start_async_task(email: str, sales_agent: JaWorker):
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     loop.run_until_complete(sales_agent.run_pipeline(prospect_email=email))
#     loop.close()

def start_async_task(email: str, sales_agent: JaWorker):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(sales_agent.run_pipeline(prospect_email=email))
    tasks[email] = (task, loop)  # Store task and its event loop
    try:
        loop.run_until_complete(task)
    finally:
        loop.close()
        tasks.pop(email, None)  # Remove task from tracking once it's done

@app.get("/reset/")
async def reset_application():
    global ja_workers
    ja_workers = {}
    for email, (task, loop) in tasks.items():
        loop.call_soon_threadsafe(task.cancel)  # Cancel task
        loop.stop()  # Stop the loop if it's still running
        loop.close()  # Close the loop
    tasks.clear()  # Clear all tasks
    ja_workers.clear()  # Optionally reset ja_workers
    return {"message": "All tasks stopped and application reset"}

@app.get("/logs/")
async def get_logs(email: Optional[str] = Query(None)):
    """
    Returns the logs for the specified email. If the email does not have an associated sales pipeline, returns an error.
    """
    if email is None or email not in ja_workers:
        raise HTTPException(status_code=404, detail="No logs found for the given email")

    sales_agent = ja_workers[email]
    
    return {"logs": sales_agent.logs}
