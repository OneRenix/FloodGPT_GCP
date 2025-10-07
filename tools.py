import logging
import pandas as pd
import json
from google.cloud import firestore

# LangChain and Google AI libraries
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# The safe LLM factory function
from llm_config import get_llm

# --- 1. FIRESTORE QUERY PLAN GENERATION ---
def generate_firestore_query_plan(question: str, schema: dict) -> dict:
    """
    Takes a user question and a schema of the Firestore collections
    and generates a structured query plan in JSON format.
    """
    logging.info("Generating Firestore query plan...")

    prompt = ChatPromptTemplate.from_template(
        """
        You are an expert Firestore database engineer. Your task is to convert a user's question into a structured query plan for Firestore.

        Given the following Firestore schema:
        ---
        {schema}
        ---

        Generate a JSON object that represents the query plan to answer the user's question: "{question}"

        The JSON object should have the following structure:
        {{
            "collection": "collection_name",
            "select": ["field1", "field2"],
            "where": [
                {{
                    "field": "field_name",
                    "operator": "==",
                    "value": "some_value"
                }}
            ],
            "order_by": [
                {{
                    "field": "field_name",
                    "direction": "DESCENDING"
                }}
            ],
            "limit": 10
        }}

        - "collection" is the name of the collection to query.
        - "select" is a list of fields to include in the result. If empty, all fields are returned.
        - "where" is a list of conditions to filter the documents.
        - "order_by" is a list of fields to sort the results by.
        - "limit" is the maximum number of documents to return.

        Only respond with the JSON object.
        """
    )

    llm = get_llm(model_name="gemini-1.5-flash", temperature=0)
    chain = prompt | llm | StrOutputParser()

    response_str = chain.invoke({"schema": json.dumps(schema, indent=2), "question": question})
    clean_response_str = response_str.strip().replace('`json', '').replace('`', '')
    
    try:
        query_plan = json.loads(clean_response_str)
        return query_plan
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from query plan response: {clean_response_str}")
        return {{}}

# --- 2. FIRESTORE QUERY EXECUTION ---
def execute_firestore_query(query_plan: dict) -> dict:
    """
    Executes a Firestore query based on the provided query plan
    and returns the results as a Pandas DataFrame.
    """
    logging.info(f"Executing Firestore query plan: {query_plan}")

    try:
        db = firestore.Client()
        collection_name = query_plan.get("collection")
        if not collection_name:
            raise ValueError("The 'collection' field is missing from the query plan.")

        query = db.collection(collection_name)

        # Apply where clauses
        if "where" in query_plan and query_plan["where"]:
            for condition in query_plan["where"]:
                query = query.where(condition["field"], condition["operator"], condition["value"])

        # Apply order_by clauses
        if "order_by" in query_plan and query_plan["order_by"]:
            for order in query_plan["order_by"]:
                direction = firestore.Query.DESCENDING if order.get("direction") == "DESCENDING" else firestore.Query.ASCENDING
                query = query.order_by(order["field"], direction=direction)

        # Apply limit
        if "limit" in query_plan:
            query = query.limit(query_plan["limit"])

        # Execute the query
        docs = query.stream()
        data = [doc.to_dict() for doc in docs]

        if not data:
            return {"sql_dataframe": pd.DataFrame()}

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Apply select fields
        if "select" in query_plan and query_plan["select"]:
            df = df[query_plan["select"]]

        return {"sql_dataframe": df}

    except Exception as e:
        logging.error(f"Firestore query execution failed: {e}")
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
        viz_llm = get_llm(model_name="gemini-1.5-flash", temperature=0)
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

    llm = get_llm(model_name="gemini-1.5-flash", temperature=0.7)
    chain = prompt | llm | StrOutputParser()

    data_summary = f"Columns: {', '.join(df.columns)}\n\n{df.head().to_string()}"
    
    insight = chain.invoke({"question": question, "data_summary": data_summary})
    return insight