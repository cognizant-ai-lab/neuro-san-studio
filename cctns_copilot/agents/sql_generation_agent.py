import vanna
from vanna.ollama import Ollama
from vanna.chromadb import ChromaDBVectorStore
import os # For API keys or environment variables if needed

# Placeholder for database connection details - these should be securely managed
# In a real application, use environment variables or a config file
# For the hackathon, VPN details and DB access will be provided.
# ORACLE_USER = os.getenv("ORACLE_USER", "your_user")
# ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "your_password")
# ORACLE_DSN = os.getenv("ORACLE_DSN", "your_host:your_port/your_service_name") # e.g., localhost:1521/XEPDB1

class SqlGenerationAgent:
    def __init__(self, db_user, db_password, db_dsn, ollama_model="codellama:latest", vanna_model_name="cctns_copilot_vanna"):
        """
        Initializes the SQL Generation Agent using Vanna AI.

        Args:
            db_user (str): Oracle database username.
            db_password (str): Oracle database password.
            db_dsn (str): Oracle database DSN (e.g., 'host:port/service_name').
            ollama_model (str): The Ollama model to use (e.g., 'llama2', 'codellama:latest').
                               Ensure this model is pulled and available in Ollama.
            vanna_model_name (str): A name for the Vanna model collection in ChromaDB.
        """
        self.db_user = db_user
        self.db_password = db_password
        self.db_dsn = db_dsn
        self.ollama_model_name = ollama_model
        self.vanna_model_name = vanna_model_name # This is used as the collection name in ChromaDB

        # Initialize Vanna with Ollama and ChromaDB
        # Vanna arugments: model (for LLM), database (for RAG), vector_store (for storing training data)
        # The 'model' here is a Vanna concept, often a descriptive name for your trained setup.
        # ChromaDB will store its data in a directory named 'chroma_db' by default.

        # Setup Vanna RAG backend with Ollama
        self.vn = Ollama(config={'model': self.ollama_model_name})

        # Setup Vanna to use ChromaDB for storing training data (DDL, Documentation, SQL)
        # This will create a collection in ChromaDB named self.vanna_model_name
        self.vn.set_vector_store(ChromaDBVectorStore(collection_name=self.vanna_model_name))

        # Connect Vanna to the Oracle database
        # This allows Vanna to understand the schema and also to potentially run queries
        # (though we might run queries separately after generation for more control).
        try:
            # dsn can be in format: host:port/service_name or a full cx_Oracle DSN string
            # cx_Oracle.makedsn(host, port, service_name=service_name)
            # For simplicity, assuming dsn is directly usable or pre-formatted.
            conn_info = {
                'user': self.db_user,
                'password': self.db_password,
                'dsn': self.db_dsn,
                'db_type': 'oracle' # Vanna needs to know the DB type
            }
            self.vn.connect_to_db(**conn_info)
            print(f"Successfully connected Vanna to Oracle DB: {self.db_dsn}")
        except Exception as e:
            print(f"Error connecting Vanna to Oracle DB: {e}")
            print("Please ensure Oracle client is installed and DSN is correct.")
            print("Example DSN: 'localhost:1521/XEPDB1' or full TNS entry name.")
            raise RuntimeError(f"Vanna DB connection failed: {e}")

        print(f"SqlGenerationAgent initialized with Ollama model '{self.ollama_model_name}' and Vanna collection '{self.vanna_model_name}'.")

    def train_with_schema(self, include_information_schema=False):
        """
        Trains Vanna with the database schema.
        Vanna can introspect the schema from the connected database.

        Args:
            include_information_schema (bool): Whether to include system/information schema tables.
                                               Usually False for application-specific queries.
        """
        print("Training Vanna with database schema...")
        try:
            # This method in Vanna typically extracts DDLs and stores them.
            # The exact method might vary based on Vanna version or specific database connector.
            # df_ddl = self.vn.run_sql("SELECT table_name, ddl FROM vanna_ddl_table") # This is a Vanna concept
            # For many DBs, Vanna can pull this automatically or via helper functions.
            # Let's rely on Vanna's built-in mechanism to get DDL.
            # With a live connection, Vanna can often infer schema for training.
            # The vn.train() method is flexible. We can add DDLs directly.
            # For now, assuming Vanna's connector will handle schema introspection as part of training
            # when DDLs are not explicitly added via vn.train(ddl="...").
            # We can also explicitly add DDLs if we fetch them.

            # The `vn.train` method is used for various types of training data.
            # To train on schema, you typically add DDL statements.
            # Vanna's database connector might have utilities to extract these,
            # or you might need to provide them if auto-extraction is limited.
            # For Oracle, getting all DDLs might require querying system tables like ALL_TABLES, ALL_TAB_COLUMNS
            # and then constructing CREATE TABLE statements or using dbms_metadata.get_ddl.

            # Let's assume we have a way to get DDLs (perhaps a helper function not shown here)
            # For now, we'll just inform that Vanna *can* be trained on DDL.
            # The user should provide DDLs using vn.train(ddl="CREATE TABLE ...")
            print("Schema training with Vanna relies on DDL statements.")
            print("You should add DDLs using vn.train(ddl='CREATE TABLE your_table (...)', ...)")
            print("And also table and column documentation for better accuracy:")
            print("vn.train(documentation='Table your_table stores X information')")
            print("vn.train(documentation='Column Y in your_table means Z')")
            # Example:
            # self.vn.train(ddl="CREATE TABLE MY_TABLE (id INT PRIMARY KEY, name VARCHAR(20))")

            # Vanna will automatically use the connected database's schema information for RAG.
            # Explicitly "training" on DDLs helps store them in the vector DB for faster/better retrieval.
            # If the schema is very large, one might selectively train on relevant tables' DDLs.

            # TODO: Implement actual DDL extraction and training if needed beyond Vanna's auto-RAG.
            print("Vanna is connected to the DB and can use its schema for RAG.")
            print("For fine-tuning like results, provide DDL, docs, and SQL examples via vn.train().")

        except Exception as e:
            print(f"Error during schema training: {e}")

    def train_with_sample_queries(self, sample_queries: list[dict]):
        """
        Trains Vanna with sample natural language questions and their corresponding SQL queries.
        Args:
            sample_queries (list[dict]): A list of dictionaries, each with 'text' (natural language)
                                         and 'sql' (corresponding SQL query).
                                         e.g., [{'text': 'Show me all users', 'sql': 'SELECT * FROM users'}]
        """
        print(f"Training Vanna with {len(sample_queries)} sample queries...")
        for i, sample in enumerate(sample_queries):
            try:
                self.vn.train(question=sample['text'], sql=sample['sql'])
                print(f"  Trained sample {i+1}/{len(sample_queries)}: {sample['text']}")
            except Exception as e:
                print(f"  Error training sample '{sample['text']}': {e}")
        print("Sample query training complete.")

    def train_with_documentation(self, documentation_data: list[str]):
        """
        Trains Vanna with textual documentation about tables, columns, or general business logic.
        Args:
            documentation_data (list[str]): A list of documentation strings.
                                           e.g., ["Table 'FIR' stores First Information Reports.",
                                                  "Column 'incident_date' is the date of the crime."]
        """
        print(f"Training Vanna with {len(documentation_data)} documentation entries...")
        for i, doc_entry in enumerate(documentation_data):
            try:
                self.vn.train(documentation=doc_entry)
                print(f"  Trained documentation {i+1}/{len(documentation_data)}: {doc_entry[:100]}...")
            except Exception as e:
                print(f"  Error training documentation: {e}")
        print("Documentation training complete.")


    def generate_sql(self, natural_language_query: str) -> str | None:
        """
        Generates SQL query from a natural language question.
        Args:
            natural_language_query (str): The user's question in natural language.
        Returns:
            str | None: The generated SQL query, or None if generation failed.
        """
        print(f"Generating SQL for: '{natural_language_query}'")
        try:
            # Vanna's ask method uses the LLM (Ollama) and RAG (ChromaDB + DB schema)
            sql_query = self.vn.ask(natural_language_query)

            if sql_query:
                # Basic validation: Ensure it's a SELECT query
                if not sql_query.strip().upper().startswith("SELECT"):
                    print(f"Warning: Generated query is not a SELECT statement: {sql_query}")
                    # Depending on policy, either return None, error, or attempt to fix/re-prompt.
                    # For now, returning None for non-SELECT.
                    return None
                print(f"Generated SQL: {sql_query}")
                return sql_query
            else:
                print("Vanna did not return an SQL query.")
                return None
        except Exception as e:
            print(f"Error generating SQL: {e}")
            return None

# Example Usage (Illustrative - requires running Ollama and Oracle DB)
if __name__ == '__main__':
    print("Starting SQLGenerationAgent example...")
    print("Ensure Ollama is running with a model like 'codellama:latest' (`ollama pull codellama`)")
    print("Ensure Oracle DB is accessible and client libraries are configured.")

    # --- CONFIGURATION ---
    # These should be obtained from environment variables or a secure config in a real app
    # For the hackathon, these will be provided.
    # IMPORTANT: Replace with your actual DB credentials and DSN
    DB_USER = os.getenv("CCTNS_DB_USER", "system") # Replace "system" with actual user if different
    DB_PASSWORD = os.getenv("CCTNS_DB_PASSWORD", "oracle")  # Replace "oracle" with actual password
    # DSN might be like: "localhost:1521/XEPDB1" for Oracle XE
    # Or a TNS name if tnsnames.ora is configured
    DB_DSN = os.getenv("CCTNS_DB_DSN", "localhost:1521/orclpdb1") # Replace with your actual DSN

    OLLAMA_SQL_MODEL = "codellama:13b" # Using a specific variant, ensure it's pulled

    print(f"Attempting to connect to Oracle with User: {DB_USER}, DSN: {DB_DSN}")

    # Example Schema (DDLs - these should match your CCTNS database)
    # In a real scenario, you'd fetch these from the DB or have them in files.
    example_ddls = [
        """CREATE TABLE DISTRICT_MASTER (
            district_id NUMBER PRIMARY KEY,
            district_code VARCHAR2(10) UNIQUE,
            district_name VARCHAR2(100) NOT NULL
        )""",
        """CREATE TABLE STATION_MASTER (
            station_id NUMBER PRIMARY KEY,
            station_name VARCHAR2(100) NOT NULL,
            district_id NUMBER,
            CONSTRAINT fk_district FOREIGN KEY (district_id) REFERENCES DISTRICT_MASTER(district_id)
        )""",
        """CREATE TABLE FIR (
            fir_id NUMBER PRIMARY KEY,
            district_id NUMBER,
            station_id NUMBER,
            crime_type_id NUMBER,
            incident_date DATE,
            description VARCHAR2(4000),
            CONSTRAINT fk_fir_district FOREIGN KEY (district_id) REFERENCES DISTRICT_MASTER(district_id),
            CONSTRAINT fk_fir_station FOREIGN KEY (station_id) REFERENCES STATION_MASTER(station_id)
        )"""
        # Add more DDLs for CRIME_TYPE_MASTER, OFFICER_MASTER, ARREST etc.
    ]

    # Example Documentation
    example_docs = [
        "DISTRICT_MASTER table contains the list of all police districts.",
        "STATION_MASTER table stores information about police stations and links to their district.",
        "FIR table contains records of First Information Reports filed.",
        "incident_date in the FIR table is the date when the crime occurred.",
        "To get Guntur's district_id, look for 'Guntur' in district_name in DISTRICT_MASTER."
    ]

    # Example Question-SQL Pairs for Training
    example_qa_pairs = [
        {
            "text": "How many FIRs were filed in Guntur district?",
            "sql": "SELECT COUNT(f.fir_id) FROM FIR f JOIN DISTRICT_MASTER dm ON f.district_id = dm.district_id WHERE dm.district_name = 'Guntur'"
        },
        {
            "text": "List all police stations in Guntur.",
            "sql": "SELECT s.station_name FROM STATION_MASTER s JOIN DISTRICT_MASTER dm ON s.district_id = dm.district_id WHERE dm.district_name = 'Guntur'"
        },
        {
            "text": "Show total crimes and breakdown by type for District Guntur.",
            # This is more complex, might need CRIME_TYPE_MASTER and joins
            # Simplified for now, or would require the CRIME_TYPE_MASTER DDL and training
            "sql": "SELECT ct.description, COUNT(f.fir_id) AS total_crimes FROM FIR f JOIN DISTRICT_MASTER dm ON f.district_id = dm.district_id JOIN CRIME_TYPE_MASTER ct ON f.crime_type_id = ct.crime_type_id WHERE dm.district_name = 'Guntur' GROUP BY ct.description"
        }
    ]

    # Create a dummy CRIME_TYPE_MASTER DDL for the third query to be more plausible
    example_ddls.append(
        """CREATE TABLE CRIME_TYPE_MASTER (
            crime_type_id NUMBER PRIMARY KEY,
            crime_code VARCHAR2(10) UNIQUE,
            description VARCHAR2(255) NOT NULL
        )"""
    )


    try:
        agent = SqlGenerationAgent(db_user=DB_USER, db_password=DB_PASSWORD, db_dsn=DB_DSN, ollama_model=OLLAMA_SQL_MODEL)

        # --- Training Phase ---
        # 1. Train with DDL (Schema)
        print("\n--- Training with DDLs ---")
        for ddl_query in example_ddls:
            agent.vn.train(ddl=ddl_query)
            print(f"Trained DDL: {ddl_query.splitlines()[0]}...") # Print first line of DDL

        # 2. Train with Documentation
        print("\n--- Training with Documentation ---")
        agent.train_with_documentation(example_docs)

        # 3. Train with Question-SQL Pairs
        print("\n--- Training with Q&A Pairs ---")
        agent.train_with_sample_queries(example_qa_pairs)

        print("\n--- Vanna Training Complete ---")
        # You can see the training data using:
        # training_data = agent.vn.get_training_data()
        # print("\nRetrieved Training Data sample:", training_data.head())


        # --- Query Phase ---
        print("\n--- Generating SQL from Natural Language ---")

        test_queries = [
            "How many FIRs are there in Guntur?",
            "What are the police stations in Guntur district?",
            "Show me crime types and their counts in Guntur district"
        ]

        for nL_query in test_queries:
            generated_sql = agent.generate_sql(nL_query)
            if generated_sql:
                print(f"  NL: '{nL_query}'\n  SQL: '{generated_sql}'")
            else:
                print(f"  NL: '{nL_query}'\n  SQL: Could not generate SQL.")
            print("-" * 20)

    except RuntimeError as e:
        print(f"RuntimeError during agent initialization or use: {e}")
        print("Please check Ollama server status, model availability, and DB connection details/client setup.")
    except Exception as e:
        print(f"An unexpected error occurred in the example: {e}")
        import traceback
        traceback.print_exc()

    print("\nSQLGenerationAgent example finished.")
