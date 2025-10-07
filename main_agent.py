import logging
import json
from dotenv import load_dotenv
from typing import TypedDict
import pandas as pd

# LangGraph libraries for building the agent workflow
from langgraph.graph import StateGraph, END

# Import your specialist functions and classes
from tools import generate_sql_query, validate_and_correct_sql, execute_sql_query, recommend_visualization, generate_insight_from_data
from formatter import DataFormatter
from llm_config import get_llm
from langchain_community.utilities import SQLDatabase

# Load environment variables from .env file
load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- 1. Define the State for our Graph ---
# This is the "memory" that is passed between each step of the agent.
class AgentState(TypedDict):
    question: str
    db_schema: str
    generated_sql: str
    validated_sql: str
    sql_dataframe: pd.DataFrame
    visualization: str
    formatted_data_for_visualization: dict
    insight: str
    error: str

# --- 2. Create Instances of Our Tools ---
helper_llm = get_llm(model_name="gemini-1.5-flash", temperature=0)
formatter = DataFormatter(llm=helper_llm)
db = SQLDatabase.from_uri("sqlite:///db/analytics.db")

# --- 3. Define the Nodes for our Graph ---
# Each node is a function that performs a specific action.

def insight_node(state: AgentState):
    """Generates an insight from the data."""
    logging.info("---NODE: GENERATING INSIGHT---")
    if state.get("error") or state.get("sql_dataframe") is None or state.get("sql_dataframe").empty:
        logging.warning("Skipping insight generation due to error or no data.")
        return {"insight": "No insight available."}
    
    insight = generate_insight_from_data(state['question'], state['sql_dataframe'])
    return {"insight": insight}

def sql_generation_node(state: AgentState):
    """Generates the initial SQL query from the user's question."""
    logging.info("---NODE: GENERATING SQL---")
    db_schema = db.get_table_info()
    query = generate_sql_query(state['question'], db_schema)
    return {"generated_sql": query, "db_schema": db_schema}

def sql_validation_node(state: AgentState):
    """Validates and corrects the generated SQL query."""
    logging.info("---NODE: VALIDATING SQL---")
    validation_result = validate_and_correct_sql(state['generated_sql'], state['db_schema'])
    if validation_result.get("valid"):
        return {"validated_sql": state['generated_sql']}
    else:
        logging.warning(f"SQL was invalid. Issues: {validation_result.get('issues')}. Using corrected query.")
        return {"validated_sql": validation_result.get("corrected_query")}

def sql_execution_node(state: AgentState):
    """Executes the validated SQL query against the database."""
    logging.info("---NODE: EXECUTING SQL---")
    execution_result = execute_sql_query(state['validated_sql'])
    if "error" in execution_result:
        return {"error": execution_result["error"], "sql_dataframe": pd.DataFrame()}
    return {"sql_dataframe": execution_result["sql_dataframe"]}

def visualizer_node(state: AgentState):
    """Recommends a visualization type based on the query result."""
    logging.info("---NODE: RECOMMENDING VISUALIZATION---")
    df = state.get('sql_dataframe')
    if state.get("error") or df is None or df.empty:
        logging.warning("Skipping visualization due to error or no data.")
        return {"visualization": "none"}
    
    recommendation = recommend_visualization(state['question'], df)
    
    try:
        chart_type = recommendation.split('\n')[0].split(':')[1].strip()
    except (IndexError, AttributeError):
        chart_type = "none"
    return {"visualization": chart_type}

def formatter_node(state: AgentState):
    """Formats the data into a chart-ready JSON object."""
    logging.info("---NODE: FORMATTING DATA---")
    formatted_data_dict = formatter.format_data_for_visualization(state)
    return {"formatted_data_for_visualization": formatted_data_dict}

# --- 4. Build the Graph ---
workflow = StateGraph(AgentState)

# Add the nodes
workflow.add_node("generate_sql", sql_generation_node)
workflow.add_node("validate_sql", sql_validation_node)
workflow.add_node("execute_sql", sql_execution_node)
workflow.add_node("visualizer", visualizer_node)
workflow.add_node("formatter", formatter_node)
workflow.add_node("insight", insight_node)

# Define the workflow sequence
workflow.set_entry_point("generate_sql")
workflow.add_edge("generate_sql", "validate_sql")
workflow.add_edge("validate_sql", "execute_sql")
workflow.add_edge("execute_sql", "visualizer")
workflow.add_edge("visualizer", "formatter")
workflow.add_edge("formatter", "insight")
workflow.add_edge("insight", END)

# Compile the graph into a runnable application
app = workflow.compile()
logging.info("LangGraph app with SQL validation compiled.")

# --- 5. Main Execution Block (for command-line testing) ---
def main():
    test_query = "What are the top 5 regions by total contract cost?"
    logging.info(f"Running test query: {test_query}")

    inputs = {"question": test_query}
    final_state = app.invoke(inputs)

    print("\n" + "="*50)
    print("--- AGENT EXECUTION COMPLETE ---")
    print("="*50 + "\n")
    
    if final_state.get("error"):
        print(f"An error occurred during execution: {final_state['error']}")

    print("## Data Result:\n")
    if final_state.get("sql_dataframe") is not None and not final_state["sql_dataframe"].empty:
        print(final_state["sql_dataframe"].to_string())
    else:
        print("No data was returned from the query.")
    print("\n" + "-"*50 + "\n")

    print("## Validated SQL Query:\n")
    print(final_state.get("validated_sql", "N/A"))
    print("\n" + "-"*50 + "\n")

    print("## Visualization Recommendation:\n")
    print(f"Recommended Chart Type: {final_state.get('visualization', 'N/A')}")
    print("\n" + "-"*50 + "\n")

    print("## Chart-Ready JSON Data:\n")
    print(json.dumps(final_state.get("formatted_data_for_visualization"), indent=2))
    print("\n" + "="*50 + "\n")

    print("## Insight:\n")
    print(final_state.get("insight", "N/A"))
    print("\n" + "="*50 + "\n")

    from IPython.display import Image

    # This will render the graph to a .png file
    workflow_image = app.get_graph().draw_mermaid_png()
    with open("workflow.png", "wb") as f:
        f.write(workflow_image)

    print("Graph saved as workflow.png")

if __name__ == "__main__":
    main()
