# cctns_copilot/agents/database_interaction_agent.py

import cx_Oracle
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime

# For PDF Generation - using reportlab as it's more comprehensive
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

# A simple in-memory store for datasets
# In a real app, this might be persisted or managed more robustly
SAVED_DATASETS = {}

class DatabaseInteractionAgent:
    def __init__(self, db_user, db_password, db_dsn):
        self.db_user = db_user
        self.db_password = db_password
        self.db_dsn = db_dsn
        self.connection = None
        self._connect_db()

    def _connect_db(self):
        try:
            # Ensure Oracle Client is correctly installed and configured.
            # For thin mode (no separate client needed for cx_Oracle >= 8.0):
            # cx_Oracle.init_oracle_client() # Call this once if using thin mode
            self.connection = cx_Oracle.connect(
                user=self.db_user,
                password=self.db_password,
                dsn=self.db_dsn
            )
            print("Successfully connected to Oracle database.")
        except cx_Oracle.Error as error:
            print(f"Error connecting to Oracle database: {error}")
            # Consider if thin mode can be enabled by default if client is an issue.
            # try:
            #     print("Attempting connection with Oracle Thin Mode...")
            #     cx_Oracle.init_oracle_client()
            #     self.connection = cx_Oracle.connect(user=self.db_user, password=self.db_password, dsn=self.db_dsn)
            #     print("Successfully connected using Oracle Thin Mode.")
            # except Exception as thin_error:
            #     print(f"Thin Mode connection also failed: {thin_error}")
            #     self.connection = None
            #     raise
            self.connection = None # Ensure connection is None if failed
            raise # Re-raise the exception to signal failure to the caller

    def execute_query(self, sql_query: str) -> pd.DataFrame | None:
        """
        Executes a SQL query and returns the results as a Pandas DataFrame.
        Only allows SELECT statements.
        """
        if not self.connection:
            print("Error: No database connection.")
            self._connect_db() # Attempt to reconnect
            if not self.connection:
                 print("Error: Reconnection failed. Cannot execute query.")
                 return None


        if not sql_query.strip().upper().startswith("SELECT"):
            print("Error: Only SELECT statements are allowed.")
            return None

        try:
            cursor = self.connection.cursor()
            cursor.execute(sql_query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            df = pd.DataFrame(rows, columns=columns)
            print(f"Query executed successfully. Fetched {len(df)} rows.")
            return df
        except cx_Oracle.Error as error:
            print(f"Error executing query: {error}")
            return None
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()

    def save_dataset(self, df: pd.DataFrame, name: str, tags: list[str] = None, sql_query: str = ""):
        """
        Saves a DataFrame as a named and tagged dataset in memory.
        """
        if df is None or name is None or not name.strip():
            print("Error: DataFrame and a valid name are required to save dataset.")
            return
        dataset_id = f"{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        SAVED_DATASETS[dataset_id] = {
            "name": name,
            "dataframe": df,
            "tags": tags if tags else [],
            "sql_query": sql_query,
            "created_at": datetime.now()
        }
        print(f"Dataset '{name}' (ID: {dataset_id}) saved with {len(df)} rows.")
        return dataset_id

    def get_dataset(self, dataset_id: str) -> dict | None:
        return SAVED_DATASETS.get(dataset_id)

    def list_datasets(self) -> dict:
        return {
            ds_id: {
                "name": data["name"],
                "tags": data["tags"],
                "rows": len(data["dataframe"]),
                "sql": data["sql_query"][:50] + "..." if data["sql_query"] else "N/A",
                "created_at": data["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            }
            for ds_id, data in SAVED_DATASETS.items()
        }

    def export_df_to_csv(self, df: pd.DataFrame, filename: str = "export.csv"):
        """Exports a DataFrame to a CSV file."""
        try:
            df.to_csv(filename, index=False)
            print(f"DataFrame successfully exported to {filename}")
            return filename
        except Exception as e:
            print(f"Error exporting DataFrame to CSV: {e}")
            return None

    def _generate_charts_for_pdf(self, df: pd.DataFrame, output_path: str = "temp_charts"):
        """
        Generates a few sample charts (bar, pie) from the DataFrame if applicable.
        Saves them as images and returns their paths.
        This is a heuristic function; specific charting logic would be needed based on data.
        """
        if df.empty:
            return []

        os.makedirs(output_path, exist_ok=True)
        chart_paths = []

        # Attempt a bar chart if there's a categorical column and a numerical column
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        numerical_cols = df.select_dtypes(include=['number']).columns

        if len(categorical_cols) > 0 and len(numerical_cols) > 0:
            cat_col = categorical_cols[0]
            num_col = numerical_cols[0]

            try:
                # Bar chart (top 10 categories)
                plt.figure(figsize=(10, 6))
                top_10 = df.groupby(cat_col)[num_col].sum().nlargest(10)
                top_10.plot(kind='bar')
                plt.title(f'Top 10 {cat_col} by Sum of {num_col}')
                plt.xlabel(cat_col)
                plt.ylabel(f'Sum of {num_col}')
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                bar_chart_path = os.path.join(output_path, "bar_chart.png")
                plt.savefig(bar_chart_path)
                plt.close()
                chart_paths.append(bar_chart_path)

                # Pie chart (top 5 categories for the first numerical column)
                if len(top_10) > 1: # Pie chart needs more than one slice
                    plt.figure(figsize=(8, 8))
                    # Use a different aggregation for pie if sum is not appropriate, e.g. count
                    pie_data = df[cat_col].value_counts().nlargest(5)
                    pie_data.plot(kind='pie', autopct='%1.1f%%', startangle=90)
                    plt.title(f'Distribution of Top 5 {cat_col}')
                    plt.ylabel('') # Hide y-label for pie charts
                    plt.tight_layout()
                    pie_chart_path = os.path.join(output_path, "pie_chart.png")
                    plt.savefig(pie_chart_path)
                    plt.close()
                    chart_paths.append(pie_chart_path)
            except Exception as e:
                print(f"Could not generate standard charts: {e}")


        # Attempt a line chart if there's a date/datetime column and a numerical column
        date_cols = df.select_dtypes(include=['datetime', 'datetimetz', 'datetime64[ns]']) # Added datetime64[ns]
        # Convert potential date columns to datetime if they are objects
        for col in df.select_dtypes(include=['object']).columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except Exception:
                pass # Ignore columns that can't be converted

        # Re-check date_cols after potential conversion
        date_cols = df.select_dtypes(include=['datetime', 'datetimetz', 'datetime64[ns]']).columns


        if len(date_cols) > 0 and len(numerical_cols) > 0:
            date_col = date_cols[0]
            num_col = numerical_cols[0] # Use the first numerical column
            try:
                plt.figure(figsize=(10, 6))
                # Ensure the date column is actually datetime
                if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

                # Drop rows where date conversion might have failed
                df_plot = df.dropna(subset=[date_col, num_col])
                if not df_plot.empty:
                    df_plot.set_index(date_col)[num_col].resample('M').sum().plot(kind='line', marker='o')
                    plt.title(f'{num_col} Trend Over Time (Monthly Sum)')
                    plt.xlabel('Time')
                    plt.ylabel(num_col)
                    plt.xticks(rotation=45, ha="right")
                    plt.tight_layout()
                    line_chart_path = os.path.join(output_path, "line_chart.png")
                    plt.savefig(line_chart_path)
                    plt.close()
                    chart_paths.append(line_chart_path)
            except Exception as e:
                print(f"Could not generate line chart: {e}")

        return chart_paths


    def export_to_pdf(self, df: pd.DataFrame, filename: str = "report.pdf", title: str = "Report", query_sql: str = None):
        """Exports a DataFrame and any generated charts to a PDF file."""
        if df is None: # Allow empty DataFrame for reports that might just have a message
            print("Warning: DataFrame is None for PDF export. Report might be empty or show an error.")
            # df = pd.DataFrame() # Create an empty df to avoid other errors, or handle specifically

        doc = SimpleDocTemplate(filename, pagesize=landscape(letter)) # Use landscape for wider tables
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(title, styles['h1']))
        story.append(Spacer(1, 0.2 * inch))

        # Query SQL if provided
        if query_sql:
            story.append(Paragraph("<b>Query SQL:</b>", styles['h3']))
            # Ensure query_sql is a string before replacing
            query_sql_display = str(query_sql) if query_sql is not None else "N/A"
            story.append(Paragraph(query_sql_display.replace('\n', '<br/>'), styles['Code']))
            story.append(Spacer(1, 0.2 * inch))

        # Data Table
        if df is not None and not df.empty:
            story.append(Paragraph("<b>Data Table:</b>", styles['h3']))
            data_for_table = [df.columns.tolist()] + df.values.tolist()

            # Convert all data to string for ReportLab Table
            data_for_table = [[str(cell) if cell is not None else "" for cell in row] for row in data_for_table]

            table = Table(data_for_table, repeatRows=1) # Repeat header row
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Added for better cell vertical alignment
                ('LEFTPADDING', (0,0), (-1,-1), 5), # Added padding
                ('RIGHTPADDING', (0,0), (-1,-1), 5) # Added padding
            ])
            table.setStyle(table_style)
            story.append(table)
            story.append(Spacer(1, 0.5 * inch))
        elif df is not None and df.empty:
            story.append(Paragraph("<b>Data Table:</b>", styles['h3']))
            story.append(Paragraph("The query returned no data.", styles['Normal']))
            story.append(Spacer(1, 0.5 * inch))
        else: # df is None
            story.append(Paragraph("<b>Data Table:</b>", styles['h3']))
            story.append(Paragraph("No data available for the table.", styles['Normal']))
            story.append(Spacer(1, 0.5 * inch))


        # Charts
        if df is not None and not df.empty:
            story.append(Paragraph("<b>Charts:</b>", styles['h3']))
            # Ensure temp directory for charts is cleaned or unique per call if concurrent access is a concern
            temp_chart_dir_pdf = f"temp_pdf_charts_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            chart_image_paths = self._generate_charts_for_pdf(df, output_path=temp_chart_dir_pdf)

            if not chart_image_paths:
                story.append(Paragraph("No charts could be automatically generated for this dataset.", styles['Normal']))

            for chart_path in chart_image_paths:
                try:
                    # Check image size before adding, ReportLab can be sensitive
                    img = Image(chart_path, width=6*inch, height=4*inch)
                    img.hAlign = 'CENTER'
                    story.append(img)
                    story.append(Spacer(1, 0.2 * inch))
                except Exception as e:
                    print(f"Could not embed chart {chart_path}: {e}")
                finally: # Attempt to clean up individual chart image
                    if os.path.exists(chart_path):
                        try: os.remove(chart_path)
                        except Exception as e_del: print(f"Error deleting temp chart {chart_path}: {e_del}")

            # Attempt to clean up the temporary directory for charts if it's empty
            if os.path.exists(temp_chart_dir_pdf):
                try:
                    if not os.listdir(temp_chart_dir_pdf): # Only remove if empty
                        os.rmdir(temp_chart_dir_pdf)
                except Exception as e_rmdir: print(f"Error deleting temp chart directory {temp_chart_dir_pdf}: {e_rmdir}")
        else:
            story.append(Paragraph("<b>Charts:</b>", styles['h3']))
            story.append(Paragraph("No data available to generate charts.", styles['Normal']))


        try:
            doc.build(story)
            print(f"Report successfully exported to {filename}")
            return filename
        except Exception as e:
            print(f"Error exporting report to PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def close_connection(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            print("Database connection closed.")

    # --- UI Related Methods (Placeholders - to be implemented with Flask/Streamlit or CLI) ---
    def display_table(self, df: pd.DataFrame, page_size=10, page_num=1):
        """
        Placeholder for displaying table with pagination and sorting (CLI or Web UI).
        For CLI, this would print a slice of the DataFrame.
        """
        if df is None or df.empty:
            print("No data to display.")
            return

        print(f"\n--- Displaying Table (Page {page_num}) ---")
        # Simple CLI pagination
        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size
        print(df.iloc[start_idx:end_idx].to_string()) # Using to_string for better CLI table format
        total_rows = len(df)
        total_pages = (total_rows - 1) // page_size + 1 if total_rows > 0 else 1
        print(f"Showing rows {start_idx+1}-{min(end_idx, total_rows)} of {total_rows}. Total pages: {total_pages}")


    def display_charts(self, df: pd.DataFrame):
        """
        Placeholder for rendering charts (e.g., using matplotlib.show() or embedding in web UI).
        For CLI, it might save files and print paths.
        """
        if df is None or df.empty:
            print("No data for charts.")
            return

        print("\n--- Generating and Saving Charts (matplotlib) ---")

        temp_chart_dir_display = f"temp_display_charts_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        chart_paths = self._generate_charts_for_pdf(df, output_path=temp_chart_dir_display)

        if chart_paths:
            print(f"Charts generated and saved in '{os.path.abspath(temp_chart_dir_display)}':")
            for path in chart_paths:
                print(f" - {os.path.basename(path)}")
            # In a true CLI app, you might just print paths. For interactive, plt.show() could be used
            # but it's blocking. For a server, you'd serve these images.
        else:
            print("Could not automatically generate charts for display.")

# Example Usage (Illustrative - requires running Oracle DB)
if __name__ == '__main__':
    print("Starting DatabaseInteractionAgent example...")
    DB_USER = os.getenv("CCTNS_DB_USER", "system")
    DB_PASSWORD = os.getenv("CCTNS_DB_PASSWORD", "oracle") # Use your actual password
    DB_DSN = os.getenv("CCTNS_DB_DSN", "localhost:1521/orclpdb1") # Use your actual DSN for Oracle PDB

    agent = None

    try:
        # Attempt to initialize cx_Oracle in thin mode (no separate client needed)
        # This should be called once per process, before the first connect.
        try:
            if os.name != 'nt': # cx_Oracle.init_oracle_client() is not needed on windows with python 3.10+
                 cx_Oracle.init_oracle_client()
                 print("Oracle Thin Mode initialized (if applicable for your cx_Oracle version).")
        except Exception as init_e:
            print(f"Could not initialize Oracle client (this might be okay if using thick mode or client is already set up): {init_e}")

        agent = DatabaseInteractionAgent(db_user=DB_USER, db_password=DB_PASSWORD, db_dsn=DB_DSN)

        if agent.connection:
            print("\n--- Setting up dummy data for testing ---")
            cursor = agent.connection.cursor()
            try:
                cursor.execute("DROP TABLE TEST_CRIMES_DATA_AGENT") # Using a different name
            except cx_Oracle.DatabaseError as e:
                if "ORA-00942" in str(e): pass
                else: raise

            cursor.execute("""
                CREATE TABLE TEST_CRIMES_DATA_AGENT (
                    id NUMBER PRIMARY KEY,
                    crime_type VARCHAR2(100),
                    location VARCHAR2(100),
                    event_date DATE,
                    severity NUMBER
                )
            """)
            sample_data = [
                (1, 'Theft', 'Market Street', datetime(2023, 1, 15), 3),
                (2, 'Robbery', 'Downtown', datetime(2023, 1, 20), 7),
                (3, 'Assault', 'Park Avenue', datetime(2023, 2, 10), 5),
                (4, 'Theft', 'Mall Road', datetime(2023, 2, 12), 2),
                (5, 'Vandalism', 'Old Town', datetime(2023, 3, 5), 4),
                (6, 'Theft', 'Market Street', datetime(2023, 3, 7), 3),
                (7, 'Robbery', 'Downtown', datetime(2023, 4, 1), 8),
                (8, 'Burglary', 'Suburb', datetime(2023, 4, 5), 6),
                (9, 'Arson', 'Industrial Area', datetime(2023, 5, 10), 9),
                (10, 'Fraud', 'Financial District', datetime(2023, 5, 15), 7),
                (11, 'Theft', 'Market Street', datetime(2023, 6, 1), 3),
                (12, 'Assault', 'Park Avenue', datetime(2023, 6, 5), 5),
            ]
            cursor.executemany("""
                INSERT INTO TEST_CRIMES_DATA_AGENT (id, crime_type, location, event_date, severity)
                VALUES (:1, :2, :3, :4, :5)
            """, sample_data)
            agent.connection.commit()
            print("Dummy table TEST_CRIMES_DATA_AGENT created and populated.")


            print("\n--- Testing Query Execution ---")
            query = "SELECT id, crime_type, location, TO_CHAR(event_date, 'YYYY-MM-DD') AS event_date_str, severity FROM TEST_CRIMES_DATA_AGENT WHERE severity > 4 ORDER BY event_date DESC"
            df_results = agent.execute_query(query)

            if df_results is not None and not df_results.empty:
                # Convert event_date_str back to datetime for charting if needed, or ensure SQL provides it as date type for Pandas
                # For this example, _generate_charts_for_pdf will try to convert string columns that look like dates
                # df_results['EVENT_DATE_STR'] = pd.to_datetime(df_results['EVENT_DATE_STR'])


                agent.display_table(df_results, page_size=5, page_num=1)
                agent.display_table(df_results, page_size=5, page_num=2)

                print("\n--- Testing Save Dataset ---")
                dataset_id = agent.save_dataset(df_results, name="High Severity Crimes 2023", tags=["high_severity", "2023_test"], sql_query=query)

                print("\nAll saved datasets:", agent.list_datasets())

                print("\n--- Testing CSV Export ---")
                csv_file = agent.export_df_to_csv(df_results, "high_severity_crimes_agent.csv")
                if csv_file: print(f"CSV saved to: {os.path.abspath(csv_file)}")

                print("\n--- Testing Chart Display (saves to temp_display_charts_*) ---")
                agent.display_charts(df_results)

                print("\n--- Testing PDF Export ---")
                pdf_file = agent.export_to_pdf(df_results, "high_severity_crimes_report_agent.pdf", title="High Severity Crimes Report 2023 (Agent Test)", query_sql=query)
                if pdf_file: print(f"PDF report saved to: {os.path.abspath(pdf_file)}")

            else:
                print("Query returned no results or failed, skipping further tests.")

            print("\n--- Cleaning up dummy data ---")
            cursor.execute("DROP TABLE TEST_CRIMES_DATA_AGENT")
            agent.connection.commit()
            print("Dummy table TEST_CRIMES_DATA_AGENT dropped.")
            cursor.close()
        else:
            print("Could not connect to database. Skipping example execution.")

    except RuntimeError as e:
        print(f"RuntimeError during agent initialization: {e}")
    except cx_Oracle.Error as e:
        print(f"Database error during example: {e}")
        import traceback
        traceback.print_exc() # More detailed cx_Oracle error
    except Exception as e:
        print(f"An unexpected error occurred in the example: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if agent and agent.connection:
            agent.close_connection()

    print("\nDatabaseInteractionAgent example finished.")
