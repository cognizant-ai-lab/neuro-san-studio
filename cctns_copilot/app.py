import os
from dotenv import load_dotenv

from agents.voice_input_agent import VoiceInputAgent
from agents.text_processing_agent import TextProcessingAgent
from agents.sql_generation_agent import SqlGenerationAgent
from agents.database_interaction_agent import DatabaseInteractionAgent, SAVED_DATASETS

# Load environment variables from .env file if it exists
load_dotenv()

# --- Configuration ---
# Database Credentials (ensure these are set in your .env file or environment)
DB_USER = os.getenv("CCTNS_DB_USER")
DB_PASSWORD = os.getenv("CCTNS_DB_PASSWORD")
DB_DSN = os.getenv("CCTNS_DB_DSN") # e.g., "localhost:1521/orclpdb1"

# Ollama model for SQL generation (ensure this model is pulled in Ollama)
OLLAMA_SQL_MODEL = os.getenv("OLLAMA_SQL_MODEL", "codellama:13b") # Default if not set

# Vanna model name (collection name in ChromaDB)
VANNA_MODEL_NAME = os.getenv("VANNA_MODEL_NAME", "cctns_copilot_vanna_main")

# Voice input language ('en-IN' for English, 'te-IN' for Telugu)
VOICE_LANGUAGE = os.getenv("VOICE_LANGUAGE", "en-IN")


def setup_and_train_sql_agent(sql_agent: SqlGenerationAgent, example_ddls_func, example_docs_func, example_qa_pairs_func):
    """
    Trains Vanna with provided DDLs, documentation, and Q&A pairs.
    """
    print("\n--- Setting up and Training SQL Generation Agent (Vanna) ---")

    example_ddls = example_ddls_func()
    example_docs = example_docs_func()
    example_qa_pairs = example_qa_pairs_func()

    # 1. Train with DDL (Schema)
    print("\nTraining with DDLs...")
    if example_ddls:
        for ddl_query in example_ddls:
            sql_agent.vn.train(ddl=ddl_query)
            print(f"  Trained DDL: {ddl_query.splitlines()[0]}...")
    else:
        print("  No DDLs provided for training.")

    # 2. Train with Documentation
    print("\nTraining with Documentation...")
    if example_docs:
        for doc_entry in example_docs:
            sql_agent.vn.train(documentation=doc_entry)
            print(f"  Trained Doc: {doc_entry[:60]}...")
    else:
        print("  No documentation provided for training.")

    # 3. Train with Question-SQL Pairs
    print("\nTraining with Q&A Pairs...")
    if example_qa_pairs:
        sql_agent.train_with_sample_queries(example_qa_pairs) # This method already prints details
    else:
        print("  No Q&A pairs provided for training.")

    print("\n--- Vanna Training Phase Complete for this session ---")


# Functions to provide training data (to keep main CLI cleaner)
def get_example_ddls():
    return [
        """CREATE TABLE DISTRICT_MASTER (
            district_id NUMBER PRIMARY KEY,
            district_code VARCHAR2(10) UNIQUE,
            district_name VARCHAR2(100) NOT NULL
        )""",
        """CREATE TABLE STATION_MASTER (
            station_id NUMBER PRIMARY KEY,
            station_name VARCHAR2(100) NOT NULL,
            district_id NUMBER,
            CONSTRAINT fk_sm_district FOREIGN KEY (district_id) REFERENCES DISTRICT_MASTER(district_id)
        )""",
         """CREATE TABLE CRIME_TYPE_MASTER (
            crime_type_id NUMBER PRIMARY KEY,
            crime_code VARCHAR2(10) UNIQUE,
            description VARCHAR2(255) NOT NULL
        )""",
        """CREATE TABLE FIR (
            fir_id NUMBER PRIMARY KEY,
            district_id NUMBER,
            station_id NUMBER,
            crime_type_id NUMBER,
            incident_date DATE,
            description_text VARCHAR2(4000),
            CONSTRAINT fk_fir_district FOREIGN KEY (district_id) REFERENCES DISTRICT_MASTER(district_id),
            CONSTRAINT fk_fir_station FOREIGN KEY (station_id) REFERENCES STATION_MASTER(station_id),
            CONSTRAINT fk_fir_crime_type FOREIGN KEY (crime_type_id) REFERENCES CRIME_TYPE_MASTER(crime_type_id)
        )"""
        # User should expand this with their full CCTNS schema or relevant parts
    ]

def get_example_docs():
    return [
        "DISTRICT_MASTER table contains the list of all police districts.",
        "STATION_MASTER table stores information about police stations and links to their district using district_id.",
        "CRIME_TYPE_MASTER defines different types of crimes with a description.",
        "FIR table contains records of First Information Reports filed. It links to districts, stations, and crime types.",
        "incident_date in the FIR table is the date when the crime occurred.",
        "description_text in FIR table is the narrative of the incident.",
        "To get Guntur's district_id, look for 'Guntur' in district_name in DISTRICT_MASTER.",
        "When asked for crime breakdown by type, you should join FIR with CRIME_TYPE_MASTER and group by crime type description."
        # User should add more domain-specific documentation.
    ]

def get_example_qa_pairs():
    # These should be the 8 texts and SQL queries provided by the user/problem statement.
    return [
        {
            "text": "Show total crimes and breakdown by type for District Guntur.",
            "sql": "SELECT ct.description, COUNT(f.fir_id) AS total_crimes FROM FIR f JOIN DISTRICT_MASTER dm ON f.district_id = dm.district_id JOIN CRIME_TYPE_MASTER ct ON f.crime_type_id = ct.crime_type_id WHERE dm.district_name = 'Guntur' GROUP BY ct.description"
        },
        {
            "text": "How many FIRs were filed in Guntur district?",
            "sql": "SELECT COUNT(f.fir_id) AS total_firs FROM FIR f JOIN DISTRICT_MASTER dm ON f.district_id = dm.district_id WHERE dm.district_name = 'Guntur'"
        },
        {
            "text": "List all police stations in Guntur.",
            "sql": "SELECT s.station_name FROM STATION_MASTER s JOIN DISTRICT_MASTER dm ON s.district_id = dm.district_id WHERE dm.district_name = 'Guntur'"
        }
        # User must add their 8 specific text-SQL pairs here for proper fine-tuning.
        # Example for Officer Performance (requires ARREST and OFFICER_MASTER DDLs from user):
        # {
        # "text": "List arrests made by Officer XYZ between 2025-01-01 and 2025-06-01.",
        #  "sql": "SELECT AR.arrest_id, AR.arrest_date, OM.officer_name, F.fir_id FROM ARREST AR JOIN OFFICER_MASTER OM ON AR.officer_id = OM.officer_id JOIN FIR F ON AR.fir_id = F.fir_id WHERE OM.officer_name = 'XYZ' AND AR.arrest_date BETWEEN TO_DATE('2025-01-01', 'YYYY-MM-DD') AND TO_DATE('2025-06-01', 'YYYY-MM-DD')"
        # },
        # Example for Station Activity Trend (requires FIR and STATION_MASTER DDLs):
        # {
        #  "text": "Plot monthly FIR counts for Police Station ABC over the last year.",
        #  "sql": "SELECT TO_CHAR(F.incident_date, 'YYYY-MM') AS fir_month, COUNT(F.fir_id) AS monthly_fir_count FROM FIR F JOIN STATION_MASTER SM ON F.station_id = SM.station_id WHERE SM.station_name = 'Police Station ABC' AND F.incident_date >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -12) GROUP BY TO_CHAR(F.incident_date, 'YYYY-MM') ORDER BY fir_month"
        # }
    ]


def main_cli():
    print("--- CCTNS Copilot Voice Query System ---")

    if not all([DB_USER, DB_PASSWORD, DB_DSN]):
        print("Critical Error: Database credentials (CCTNS_DB_USER, CCTNS_DB_PASSWORD, CCTNS_DB_DSN) not found.")
        print("Please set them in your environment or a .env file. Exiting.")
        return

    # Initialize Agents
    try:
        print(f"\nInitializing Voice Input Agent for language: {VOICE_LANGUAGE}...")
        voice_agent = VoiceInputAgent(language=VOICE_LANGUAGE)

        print("\nInitializing Text Processing Agent...")
        text_agent = TextProcessingAgent()

        print("\nInitializing SQL Generation Agent...")
        sql_agent = SqlGenerationAgent(
            db_user=DB_USER,
            db_password=DB_PASSWORD,
            db_dsn=DB_DSN,
            ollama_model=OLLAMA_SQL_MODEL,
            vanna_model_name=VANNA_MODEL_NAME
        )

        print("\nInitializing Database Interaction Agent...")
        db_interaction_agent = DatabaseInteractionAgent(
            db_user=DB_USER,
            db_password=DB_PASSWORD,
            db_dsn=DB_DSN
        )
    except RuntimeError as e:
        print(f"Error during agent initialization: {e}")
        print("Please check model availability (STT, T5, Ollama), Ollama server status, and Oracle DB connectivity/client setup.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during agent initialization: {e}")
        import traceback
        traceback.print_exc()
        return

    # Vanna Training (conditionally)
    training_data_count = 0
    try:
        current_training_df = sql_agent.vn.get_training_data() # Vanna method to see stored training data
        if current_training_df is not None:
            training_data_count = len(current_training_df)
        print(f"Found {training_data_count} items in Vanna's existing training data for model '{VANNA_MODEL_NAME}'.")
    except Exception as e:
        print(f"Could not check existing Vanna training data: {e}. Assuming fresh training might be needed.")

    # Heuristic: If very few items, or user explicitly wants to train.
    # Sum of items we'd add in one training session:
    expected_training_items = len(get_example_ddls()) + len(get_example_docs()) + len(get_example_qa_pairs())

    if training_data_count < expected_training_items :
        print(f"Vanna training data ({training_data_count}) seems less than example data items ({expected_training_items}).")
        train_choice = input("Do you want to run/refresh the Vanna training process with sample data? (yes/no): ").strip().lower()
        if train_choice == 'yes':
            setup_and_train_sql_agent(sql_agent, get_example_ddls, get_example_docs, get_example_qa_pairs)
        else:
            print("Skipping Vanna training. Using existing knowledge if any.")
    else:
        print("Sufficient training data items found in Vanna. To retrain or add more, modify checks or run training manually.")


    # Main interaction loop
    natural_language_query = None
    while True:
        print("\n-----------------------------------------")
        action = input("Choose action: [L]isten, [T]ext query, [S]aved datasets, [Q]uit: ").strip().lower()
        natural_language_query = None # Reset query for each loop iteration unless chaining.

        if action == 'l':
            print("\n--- Voice Query ---")
            raw_text = voice_agent.listen_and_transcribe(duration=8) # Listen for 8 seconds
            if not raw_text:
                print("No transcription received.")
                continue

            print(f"Raw transcription ({voice_agent.language}): {raw_text}")
            original_lang_code = voice_agent.language.split('-')[0]
            processed_text = text_agent.process_text(raw_text, original_language=original_lang_code)
            print(f"Processed text (English, grammar-corrected): {processed_text}")
            natural_language_query = processed_text

        elif action == 't':
            print("\n--- Text Query ---")
            user_text_query = input("Enter your query in English: ").strip()
            if not user_text_query:
                continue
            natural_language_query = text_agent.correct_grammar(user_text_query, language='en')
            print(f"Using query: {natural_language_query}")

        elif action == 's':
            print("\n--- Saved Datasets ---")
            datasets = db_interaction_agent.list_datasets()
            if not datasets:
                print("No datasets saved yet.")
                continue
            print("Available datasets:")
            for ds_id, info in datasets.items():
                print(f"  ID: {ds_id} | Name: {info['name']} | Rows: {info['rows']} | SQL: {info['sql']} | Created: {info['created_at']}")

            ds_choice = input("Enter Dataset ID to manage, or [B]ack: ").strip()
            if ds_choice.lower() == 'b':
                continue

            selected_dataset_info = db_interaction_agent.get_dataset(ds_choice)
            if not selected_dataset_info:
                print("Invalid Dataset ID.")
                continue

            df_to_process = selected_dataset_info["dataframe"]
            ds_name_sanitized = selected_dataset_info["name"].replace(" ", "_").lower()
            print(f"\nManaging dataset: '{selected_dataset_info['name']}'")
            ds_action = input("Action for this dataset: [V]iew table, [C]SV export, [P]DF report, [G]raphs, [B]ack to menu: ").strip().lower()

            if ds_action == 'v':
                db_interaction_agent.display_table(df_to_process)
            elif ds_action == 'c':
                db_interaction_agent.export_df_to_csv(df_to_process, filename=f"{ds_name_sanitized}_export.csv")
            elif ds_action == 'p':
                db_interaction_agent.export_to_pdf(df_to_process, filename=f"{ds_name_sanitized}_report.pdf", title=selected_dataset_info["name"], query_sql=selected_dataset_info["sql_query"])
            elif ds_action == 'g':
                db_interaction_agent.display_charts(df_to_process)
            continue

        elif action == 'q':
            print("Exiting CCTNS Copilot.")
            break
        else:
            print("Invalid action. Please choose L, T, S, or Q.")
            continue

        # Common path for new voice or text queries:
        if natural_language_query:
            print("\n--- Generating SQL ---")
            sql_query = sql_agent.generate_sql(natural_language_query)

            if sql_query:
                print(f"Generated SQL: {sql_query}")

                execute_confirm = input("Execute this SQL? (yes/no/edit): ").strip().lower()
                if execute_confirm == 'edit':
                    edited_sql = input(f"Edit SQL [{sql_query}]: ").strip()
                    if edited_sql: sql_query = edited_sql
                elif execute_confirm != 'yes':
                    print("SQL execution cancelled.")
                    continue

                print("\n--- Executing SQL & Fetching Results ---")
                results_df = db_interaction_agent.execute_query(sql_query)

                if results_df is not None:
                    if results_df.empty:
                        print("Query executed successfully but returned no data.")
                    else:
                        print(f"Fetched {len(results_df)} rows.")
                        db_interaction_agent.display_table(results_df, page_size=10) # Display first page

                        df_name_default = natural_language_query[:40].replace(" ", "_").replace("'", "").replace("?","")
                        post_query_action = input("Result actions: [S]ave, [C]SV, [P]DF, [G]raphs, [N]ew query: ").strip().lower()

                        if post_query_action == 's':
                            ds_name = input(f"Enter name for this dataset (default: {df_name_default}): ").strip() or df_name_default
                            ds_tags_str = input("Enter tags (comma-separated): ").strip()
                            ds_tags = [tag.strip() for tag in ds_tags_str.split(',') if tag.strip()]
                            db_interaction_agent.save_dataset(results_df, name=ds_name, tags=ds_tags, sql_query=sql_query)
                        elif post_query_action == 'c':
                            db_interaction_agent.export_df_to_csv(results_df, filename=f"{df_name_default}.csv")
                        elif post_query_action == 'p':
                            db_interaction_agent.export_to_pdf(results_df, filename=f"{df_name_default}_report.pdf", title=natural_language_query, query_sql=sql_query)
                        elif post_query_action == 'g':
                             db_interaction_agent.display_charts(results_df)
                else: # results_df is None (meaning an error during execution)
                    print("Failed to execute SQL query.") # db_interaction_agent already printed error details
            else:
                print("Could not generate SQL for the query.")

    # Cleanup
    if 'db_interaction_agent' in locals() and db_interaction_agent and db_interaction_agent.connection:
        db_interaction_agent.close_connection()
    # sql_agent also holds a DB connection via Vanna. Vanna's Ollama class's underlying cx_Oracle connection
    # should ideally be closed. If Vanna doesn't expose a `disconnect_db()` or similar,
    # the connection might close when sql_agent object is garbage collected.
    # For robustness, one might need to access sql_agent.vn._db._conn and close it if it's a cx_Oracle connection.
    print("Application finished.")


if __name__ == '__main__':
    # Note on cx_Oracle.init_oracle_client():
    # For cx_Oracle 8+, Thin Mode (no Oracle Client s/w needed) can be used.
    # init_oracle_client() might be needed to specify lib_dir if client is not in PATH/LD_LIBRARY_PATH for thick mode
    # or for some older versions. For modern cx_Oracle and Python, often not required if DSN is well-formed
    # (like EZCONNECT string) or if Oracle Client is properly installed and configured for thick mode.
    # If issues arise, uncommenting and potentially configuring init_oracle_client() might be necessary.
    # Example: cx_Oracle.init_oracle_client(lib_dir="/opt/oracle/instantclient_21_12")
    # However, for a hackathon, relying on a correctly set up environment (PATH/DSN) is common.
    main_cli()
