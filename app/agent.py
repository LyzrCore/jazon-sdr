from lyzr_automata.agents.agent_base import Agent
from lyzr_automata.ai_models.openai import OpenAIModel
from lyzr_automata.ai_models.perplexity import PerplexityModel
from lyzr_automata.memory.open_ai import OpenAIMemory
import email
import time

from lyzr_automata.tasks.task_base import Task
from lyzr_automata.tasks.task_literals import InputType, OutputType
from lyzr_automata.tools.prebuilt_tools import send_email_by_smtp_tool
from duckduckgo_search import AsyncDDGS

class JaWorker:
    def __init__(
        self,
        open_ai_key,
        perplexity_api_key,
        company_product_data_fp,
        previous_sales_data_fp,
        mailer,
    ):
        self.open_ai_key = open_ai_key
        self.perplexity_api_key = perplexity_api_key
        self.company_product_data_fp = company_product_data_fp
        self.previous_sales_data_fp = previous_sales_data_fp
        self.logs = []
        self.mailer = mailer

    def init(self):

        self.create_models(self.open_ai_key, self.perplexity_api_key)

        self.create_memories(self.company_product_data_fp, self.previous_sales_data_fp)

        self.create_agents()

        self.create_tools()

    def configure_mail_service(
        self,
        username,
        password,
        port,
        sender_email,
        imap_server,
        smtp_server,
    ):
        self.mail_sender_config = {
            "username": username,
            "password": password,
            "host": smtp_server,
            "port": port,
            "sender_email": sender_email,
        }
        self.mail_receiver_config = {
            "username": username,
            "password": password,
            "imap_server": imap_server,
            "smtp_server": smtp_server,
        }

    def create_tools(self):
        self.email_sender_tool = send_email_by_smtp_tool(**self.mail_sender_config)

    async def search_website(self, query):
        results = await AsyncDDGS().text(query, max_results=3)
        return results

    async def run_pipeline(self, prospect_email):
        self.prospect_email = prospect_email
        research = await self.research_task(email=prospect_email)
        self.first_email = self.email_composer(
            input=f" PROSPECT_INFO : {research}",
            instructions="create a email selling the product/service based on the pdf file provided during creation of assistant. Use the Client/ Prospect information provided (to whom you are selling) as PROSPECT_INFO:  to make the customized mail [IMPORTANT!] use html dont use css make it look fully human written. Send only EMAIL nothing extra",
        )
        first_email_rp = self.send_mail_task(input=self.first_email)
        self.subject = first_email_rp["subject"]
        self.auto_reply(subject=self.subject)

    def create_models(self, open_ai_key, perplexity_api_key):
        self.open_ai_model_text = OpenAIModel(
            api_key=open_ai_key,
            parameters={
                "model": "gpt-4-turbo-preview",
                "temperature": 1,
                "max_tokens": 1500,
            },
        )
        self.perplexity_model_text = PerplexityModel(
            api_key=perplexity_api_key,
            parameters={
                "model": "pplx-7b-online",
            },
        )
        print(self.open_ai_model_text)
        print(self.perplexity_model_text)

    def create_agents(self):
        self.email_composer_agent = Agent(
            prompt_persona="you are a expert research draft email creator who is pervasive and will do anything to sell",
            role="Draft Email Expert",
            memory=self.company_product_memory,
        )
        self.sales_expert_agent = Agent(
            prompt_persona="you are a sales head manager who is good at recreating emails according to company's sales email history provided in the file, and you only return directly sendable email",
            role="Sales Head Manager",
            memory=self.previous_sales_conversation_memory,
        )

    def create_memories(self, company_product_data_fp, previous_sales_data_fp):
        self.company_product_memory = OpenAIMemory(file_path=company_product_data_fp)
        self.previous_sales_conversation_memory = OpenAIMemory(
            file_path=previous_sales_data_fp
        )

    async def research_task(self, email):
        self.logs.append(f"Researching about our prospect {self.prospect_email}")
        info = email.split("@")
        name = info[0]
        domain = info[1]
        ddg_results = await self.search_website(domain)
        self.logs.append("I am searching about our prospect on internet")

        pp_search = Task(
            name="Research Task",
            output_type=OutputType.TEXT,
            input_type=InputType.TEXT,
            model=self.perplexity_model_text,
            instructions=f"search information online in points about {domain}   1. who is {name} with respect to {domain} website,  2. what does {domain} website do provide a big summary 3. {email}",
            log_output=True,
        ).execute()
        response = Task(
            name="task compiler",
            output_type=OutputType.TEXT,
            input_type=InputType.TEXT,
            model=self.open_ai_model_text,
            instructions=f" {pp_search} {ddg_results} - compile this information into a small paragraph",
            log_output=True,
        ).execute()
        self.logs.append("I have completed the research")
        return response

    def email_composer(self, input, instructions):
        self.logs.append("I am drafting an email based on our prospectus")
        email_draft_task = Task(
            name="email composer",
            output_type=OutputType.TEXT,
            input_type=InputType.TEXT,
            model=self.open_ai_model_text,
            agent=self.email_composer_agent,
            instructions=instructions,
            log_output=True,
            default_input=input,
        ).execute()
        self.logs.append("Refining email based on our previous sales calls")
        email_composer_task = Task(
            name="email composer",
            output_type=OutputType.TEXT,
            input_type=InputType.TEXT,
            model=self.open_ai_model_text,
            instructions="re write this MAIL according to pervious conversions given in the pdf file [IMPORTANT!] use html make it looks humanly written dont use css and make sure you send only the email no extra text as output",
            agent=self.sales_expert_agent,
            log_output=True,
            default_input=f"MAIL : ${email_draft_task}",
        ).execute()
        return email_composer_task

    def send_mail_task(self, input):
        self.logs.append("Sending first email to our prospect")
        response = Task(
            name="Send Email Task",
            tool=self.email_sender_tool,
            instructions="Send Email",
            model=self.open_ai_model_text,
            previous_output=input,
            default_input=f"email:{self.prospect_email}",
        ).execute()
        self.logs.append("First email sent")
        return response

    def auto_reply(self, subject):
        SUBJECT = subject
        CHECK_INTERVAL = 60
        mail = self.mailer

        self.previous_message = self.first_email

        def search_emails(subject):
            mail.select("inbox")
            result, data = mail.search(None, '(SUBJECT "{}")'.format(subject))
            if result == "OK":
                return data[0].split()
            return []

        def reply_email(to_addr, subject, message_id, current_message):
            self.logs.append("Received email from the prospect")
            self.logs.append("Crafting a email based on our sales call history")
            response_email = self.email_composer(
                input=f"previous_email:{self.previous_message} current_email:{current_message}",
                instructions="based on the email response by user and previous email sent. send a response email adapting to the email. Use HTML but make it look like human written email make sure its well formatted. Use the conversions text file to draft it accordingly. **IMPORTANT** Only send the email no additional text",
            )
            self.logs.append("Sending an reply to the prospect")
            Task(
                name="Send Email Task",
                tool=self.email_sender_tool,
                instructions="Send Email",
                model=self.open_ai_model_text,
                previous_output=response_email,
                default_input=f"$ email: {to_addr}, thread_id:${message_id} ,subject: {subject}",
            ).execute()
            self.logs.append("Reply sent")

        def get_email_details(email_id):
            _, data = mail.fetch(email_id, "(RFC822)")
            raw_email = data[0][1]
            email_message = email.message_from_bytes(raw_email)
            from_addr = email.utils.parseaddr(email_message["From"])[1]
            message_id = email_message["Message-ID"]
            return from_addr, message_id, email_message

        replied_ids = set()
        auto_log_sent = True
        i = 1
        while True:
            if auto_log_sent:
                self.logs.append(
                    f"I am listening to incoming mails from prospect (${i})"
                )
                auto_log_sent = False
            try:
                email_ids = search_emails(SUBJECT)
                for email_id in email_ids:
                    if email_id in replied_ids:
                        continue
                    from_addr, message_id, email_message = get_email_details(email_id)
                    reply_email(from_addr, SUBJECT, message_id, email_message)
                    self.previous_message = email_message
                    replied_ids.add(email_id)
                    auto_log_sent = True
                    i = i + 1
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)
