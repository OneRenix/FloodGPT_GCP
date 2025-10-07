import logging
import pandas as pd
import json
import re
from sqlalchemy import create_engine

# LangChain and Google AI libraries
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# The safe LLM factory function
from llm_config import get_llm

# --- 1. SQL GENERATION FUNCTION ---
def generate_sql_query(question: str, db_schema: str) -> str:
    """Takes a user question and schema, and generates a SQL query."""
    logging.info("Generating SQL query...")
    
    prompt = ChatPromptTemplate.from_template(
        """You are an expert SQL analyst. Your task is to convert a user's question into a syntactically correct SQLite query.
        
        Given the following database schema:
        ---
        {schema}
        ---
        
        And the following critical rule for joining tables:
        - When a query requires joining `flood_control_projects` and `cpes_projects`, you MUST use the `contractor_name_mapping` table.
        
        Based on the schema and rules, generate a SQL query to answer the user's question: "{question}"
        """
    )
    
    llm = get_llm(model_name="h-110", temperature=0)
    chain = prompt | llm | StrOutputParser()
    
    sql_query = chain.invoke({"schema": db_schema, "question": question})
    # The LLM sometimes wraps the query in markdown, so we clean it.
    return sql_query.strip().replace("```sql", "").replace("```", "")

# --- 2. SQL VALIDATION & CORRECTION FUNCTION ---
def validate_and_correct_sql(sql_query: str, db_schema: str) -> dict:
    """Validates a SQL query against the schema and corrects it if needed."""
    logging.info("Validating and correcting SQL query...")

    prompt = ChatPromptTemplate.from_template(
        """You are an AI assistant that validates and fixes SQL queries. Your task is to:
        1. Check if the SQL query is valid for SQLite.
        2. Ensure all table and column names are correctly spelled and exist in the schema.
        3. If there are any issues, fix them. If you make a correction, set "valid" to false.
        4. If no issues are found, return the original query and set "valid" to true.

        Respond in a valid JSON format with the following structure. Only respond with the JSON:
        {{
            "valid": boolean,
            "issues": string or null,
            "corrected_query": string
        }}
        
        ===Database schema:
        {schema}
        ===Generated SQL query:
        {sql_query}
        """
    )
    
    llm = get_llm(model_name="h-110", temperature=0)
    chain = prompt | llm | StrOutputParser()

    response_str = chain.invoke({"schema": db_schema, "sql_query": sql_query})
    clean_response_str = response_str.strip().replace('`json', '').replace('`', '')
    
    try:
        validation_json = json.loads(clean_response_str)
        
        # Add a final, robust cleanup step to remove any junk text before the SELECT statement.
        original_corrected_query = validation_json.get("corrected_query", "")
        
        # Find the position of the first 'SELECT' (case-insensitive)
        select_pos = original_corrected_query.upper().find("SELECT")
        
        if select_pos != -1:
            # If 'SELECT' is found, slice the string from that point
            cleaned_query = original_corrected_query[select_pos:]
            validation_json["corrected_query"] = cleaned_query
        else:
            # If no 'SELECT' is found, the query is likely invalid
            validation_json["valid"] = False
            validation_json["issues"] = "Query does not contain a SELECT statement."
            
        return validation_json
        
    except json.JSONDecodeError:
        return {"valid": False, "issues": "Failed to get a valid JSON response from the validation LLM.", "corrected_query": sql_query}

# --- 3. SQL EXECUTION FUNCTION ---
def execute_sql_query(sql_query: str) -> dict:
    """Executes a validated SQL query and returns the results as a Pandas DataFrame."""
    logging.info(f"Executing validated SQL query:\n{sql_query}")
    db_uri = "sqlite:///db/analytics.db"
    
    try:
        engine = create_engine(db_uri)
        df = pd.read_sql(sql_query, engine)
        return {"sql_dataframe": df}
    except Exception as e:
        logging.error(f"SQL execution failed: {e}")
        return {"sql_dataframe": pd.DataFrame(), "error": str(e)}

# --- 4. VISUALIZATION RECOMMENDATION FUNCTION ---

VISUALIZATION_PROMPT = """
You are an AI assistant that recommends appropriate data visualizations. Based on the user's question and the query results, suggest the most suitable type of graph or chart.

**Available chart types:** bar, horizontal_bar, line, pie, scatter, none

**Analyze the following information:**

1.  **User's Question:** "{question}"
2.  **Query Result Summary (Column Names and First 3 Rows):**
    ---
    {data_summary}
    ---

**Your Task:**
Provide your response in the following format ONLY:

Recommended Visualization: [Chart type or "None"]
Reason: [Brief explanation for your recommendation]
"""

def recommend_visualization(user_question: str, sql_result_df: pd.DataFrame) -> str:
    """Recommends a data visualization based on the user's question and a DataFrame."""
    logging.info("Generating visualization recommendation...")
    try:
        if sql_result_df.empty:
            return "Recommended Visualization: none\nReason: The query returned no data to visualize."
            
        data_summary = f"Columns: {', '.join(sql_result_df.columns)}\n\n{sql_result_df.head(3).to_string()}"

        prompt = ChatPromptTemplate.from_template(VISUALIZATION_PROMPT)
        viz_llm = get_llm(model_name="gemini-2.5-flash", temperature=0)
        chain = prompt | viz_llm | StrOutputParser()
        
        response = chain.invoke({"question": user_question, "data_summary": data_summary})
        return response

    except Exception as e:
        logging.error(f"Error in recommend_visualization: {e}")
        return "Recommended Visualization: none\nReason: An error occurred while processing the data for visualization."

# --- 5. INSIGHT GENERATION FUNCTION ---
def generate_insight_from_data(question: str, df: pd.DataFrame) -> str:
    """Generates a human-friendly insight from the data."""
    logging.info("Generating insight from data...")

    if df.empty:
        return "The query returned no data, so there is nothing to explain."

    prompt = ChatPromptTemplate.from_template(
        """You are an expert data analyst. Your task is to provide a clear, human-friendly explanation of the data returned from a user's query.
        
        The user asked the following question:
        "{question}"
        
        The query returned the following data:
        ---
        {data_summary}
        ---
        
        Based on the user's question and the data, please provide a concise explanation of what the data means.
        Focus on the key insights and patterns in the data.
        You can also include policy implications, anomalies, or recommendations if you see any.
        """
    )

    llm = get_llm(model_name="gemini-2.5-flash", temperature=0.7)
    chain = prompt | llm | StrOutputParser()

    data_summary = f"Columns: {', '.join(df.columns)}\n\n{df.head().to_string()}"
    
    insight = chain.invoke({"question": question, "data_summary": data_summary})
    return insight
