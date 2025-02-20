from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
import sqlite3
from groq import Groq
from pydantic import BaseModel
from typing import List, Optional
import uuid
from fastapi.responses import JSONResponse
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)


groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_db_connection():
    conn = sqlite3.connect("chat.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


initialize_db()

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    conn = get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        history = cursor.fetchall()

        for message in history:
            await websocket.send_json({"role": message["role"], "content": message["content"]})

        while True:
            user_message = await websocket.receive_text()

            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, "user", user_message),
            )
            conn.commit()

            try:
                response = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": user_message}],
                    model="mixtral-8x7b-32768", 
                    stream=True
                )

                ai_response = ""
                for chunk in response:
                    token = chunk.choices[0].delta.content  
                    if token:
                        ai_response += token
                        await websocket.send_text(token)
                        await asyncio.sleep(0.02) 

                conn.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "assistant", ai_response),
                )
                conn.commit()

            except Exception as e:
                await websocket.send_text(f"Error: {str(e)}")
                break

    except WebSocketDisconnect:
        print(f"Session {session_id} disconnected")
    finally:
        conn.close()


@app.get("/sessions")
async def get_sessions():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT session_id FROM messages")
        sessions = [row["session_id"] for row in cursor.fetchall()]
        return {"sessions": sessions}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()
@app.get("/chat/{session_id}")
async def get_chat_history(session_id: str):
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        rows = cursor.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No messages found for this session")

        chat_history = [{"role": row["role"], "content": row["content"]} for row in rows]
        return JSONResponse(content=chat_history)

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()


@app.post("/sessions")
async def create_session():
    session_id = str(uuid.uuid4())  # Generate a unique session ID
    return {"session_id": session_id}
@app.delete("/sessions")
async def delete_all_sessions():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages")
        conn.commit()
        return {"status": "All sessions deleted successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()
@app.put("/update_messages")
async def update_messages():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE messages
            SET content = JSON_EXTRACT(content, '$.content')
            WHERE content LIKE '{%}';
        """)
        conn.commit()
        return {"status": "Messages updated successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()