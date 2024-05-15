from lyzr_automata.agents.agent_base import Agent
from lyzr_automata.ai_models.openai import OpenAIModel
from lyzr_automata.ai_models.perplexity import PerplexityModel
from lyzr_automata.memory.open_ai import OpenAIMemory

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
        draft_mail_agent_prompt,
        sales_agent_prompt,
        first_email_task_prompt,
        reply_email_task_prompt,
    ):
        self.open_ai_key = open_ai_key
        self.perplexity_api_key = perplexity_api_key
        self.company_product_data_fp = company_product_data_fp
        self.previous_sales_data_fp = previous_sales_data_fp
        self.logs = []
        self.draft_mail_agent_prompt = draft_mail_agent_prompt
        self.sales_expert_agent_prompt = sales_agent_prompt
        self.first_email_task_prompt = first_email_task_prompt
        self.reply_email_task_prompt = reply_email_task_prompt

    def init(self):

        self.create_models(self.open_ai_key, self.perplexity_api_key)

        self.create_memories(self.company_product_data_fp, self.previous_sales_data_fp)

        self.create_agents()

        self.create_tools()

    def create_tools(self):
        pass

    async def search_website(self, query):
        results = await AsyncDDGS().text(query, max_results=3)
        return results

    async def run_pipeline(self, prospect_email):
        self.prospect_email = prospect_email
        research = await self.research_task(email=prospect_email)
        self.first_email = self.email_composer(
            input=f" PROSPECT_INFO : {research}",
            instructions=self.first_email_task_prompt,
        )
        first_email_rp = self.send_mail_task(input=self.first_email)
        self.subject = first_email_rp["subject"]
        # self.auto_reply(subject=self.subject)

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
            prompt_persona=self.draft_mail_agent_prompt,
            role="Draft Email Expert",
            memory=self.company_product_memory,
        )
        self.sales_expert_agent = Agent(
            prompt_persona=self.sales_expert_agent_prompt,
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
        try:
            ddg_results = await self.search_website(domain)
        except:
            ddg_results = ""
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

    def reply_email(self, history_email_body: str, current_email_body: str):
        return self.email_composer(
            input=f"previous_email:{history_email_body} current_email:{current_email_body}",
            instructions=self.reply_email_task_prompt,
        )