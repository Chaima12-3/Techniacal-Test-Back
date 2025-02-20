## RUN THE PROJECT
1/ setx GROQ_API_KEY "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" : To run GROQ 2/ uvicorn main:app --reload : To run python code

This code defines a FastAPI application for managing chat sessions, using SQLite as the database to store messages. The application provides several endpoints:

WebSocket /ws/{session_id}: This allows real-time chat between a user and an AI assistant. It handles both sending and receiving messages, saving them to the database, and streaming AI-generated responses.

GET /sessions: Returns a list of all unique session IDs from the database.

GET /chat/{session_id}: Retrieves the chat history for a specific session.

POST /sessions: Creates a new chat session and generates a unique session ID.

DELETE /sessions: Deletes all messages from the database, effectively removing all sessions.

PUT /update_messages: Updates messages in the database by extracting content from JSON formatted messages (though the actual JSON format seems to need clarification).
