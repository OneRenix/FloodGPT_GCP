import pandas as pd
import numpy as np
import json
import logging
import asyncio
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

# Import the compiled LangGraph app from your main agent script
from main_agent import app

# --- 1. Custom JSON Encoder ---
# This class teaches Python's JSON library how to handle special types
# that it doesn't know about, like NumPy numbers and Pandas DataFrames.
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, pd.DataFrame):
            # Convert DataFrame to a JSON-friendly dict with 'split' orientation
            return obj.to_dict(orient='split')
        # Let the base class default method raise the TypeError
        return super(CustomJSONEncoder, self).default(obj)

# --- API Setup ---
api = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# --- API Endpoints ---

@api.get("/stream-agent")
async def stream_agent_endpoint(question: str):
    """
    Receives a question via a query parameter and streams the agent's progress.
    """
    inputs = {"question": question}

    async def event_stream():
        """The generator function that yields events as the agent runs."""
        try:
            # Use 'astream' to get real-time updates from the LangGraph
            async for chunk in app.astream(inputs):
                # Each chunk is a dictionary where the key is the node that just ran
                for node_name, node_output in chunk.items():
                    event_data = {"event": node_name, "data": node_output}
                    # Yield the event in Server-Sent Event format, using our custom encoder
                    yield f"data: {json.dumps(event_data, cls=CustomJSONEncoder)}\n\n"
                    await asyncio.sleep(0.1)
            
            # Send a final 'end' event
            yield f"data: {json.dumps({'event': 'end'})}\n\n"

        except Exception as e:
            logging.error(f"Error during stream: {e}")
            yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@api.get("/")
async def read_index():
    """Serves the main index.html file at the root URL."""
    return FileResponse('index.html')