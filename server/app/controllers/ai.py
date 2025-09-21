from fastapi import Request, HTTPException
from server.app.core.logging import logger
from server.app.services.ai_engine import generate_response


async def test_ai_controller(request: Request):
    """
    Test AI controller endpoint.
    This is a placeholder for the actual AI functionality.
    """
    try:
        # Try to parse JSON body
        try:
            body = await request.json()
            message = body.get("message", "")
        except ValueError as json_error:
            # Handle case where request body is not valid JSON
            logger.error(f"Invalid JSON in request body: {json_error}")
            # Try to get the raw body content instead
            body_bytes = await request.body()
            body_text = body_bytes.decode("utf-8", errors="replace")
            logger.info(f"Raw request body: {body_text}")

            message = body_text

        logger.info(f"Processing AI request with message: {message}")

        if not message:
            return {
                "error": "No message provided",
                "details": "Please provide a 'message' field in your request body.",
            }

        # Generate response using the AI engine
        response = await generate_response(message)
        return {"response": response}
    except Exception as e:
        logger.error(f"Error in AI test controller: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        ) from e
