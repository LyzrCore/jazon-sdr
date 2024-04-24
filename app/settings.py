class Settings:
    def __init__(
        self,
        open_ai_key,
        perplexity_key,
        imap_server,
        smtp_server,
        port,
        email,
        password,
        company_product_data_fp,
        previous_sales_data_fp
    ):
        self.open_ai_key = open_ai_key
        self.perplexity_key = perplexity_key
        self.imap_server = imap_server
        self.smtp_server = smtp_server
        self.port = port
        self.email = email
        self.password = password
        self.company_product_data_fp = company_product_data_fp
        self.previous_sales_data_fp = previous_sales_data_fp