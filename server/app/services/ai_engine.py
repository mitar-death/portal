import asyncio
from typing import Dict, Any, Optional
import google.generativeai as genai
from server.app.core.config import settings
from server.app.core.logging import logger

# Configure the Gemini API with the API key from settings
try:
    genai.configure(api_key=settings.GOOGLE_STUDIO_API_KEY)
    logger.info("Gemini AI configured successfully")
except Exception as e:
    logger.error(f"Failed to configure Gemini AI: {e}")

# Define model configuration for better results
generation_config = {
    "temperature": 0.2,  # Lower temperature for more consistent results
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 1024,
}

# Initialize Gemini model
try:
    model = genai.GenerativeModel(
        "gemini-1.5-flash", generation_config=generation_config
    )
    logger.info("Gemini model initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini model: {e}")
    model = None


async def analyze_message(message: str) -> Dict[str, Any]:
    """
    Analyze a message using the Gemini model to extract key information.

    Args:
        message: The message text to analyze

    Returns:
        Dictionary containing analysis results including:
        - sentiment: The overall sentiment (positive, negative, neutral)
        - category: The message category
        - urgency: Whether the message appears urgent
        - summary: A brief summary of the message
        - keywords: Key terms extracted from the message
    """
    if not model:
        logger.error("Gemini model not initialized, falling back to basic analysis")
        return _fallback_analysis(message)

    try:
        # Create a structured prompt for consistent results
        prompt = f"""
        Analyze the following message and provide a structured analysis in JSON format:
        
        MESSAGE:
        "{message}"
        
        INSTRUCTIONS:
        Analyze the message and return only a JSON object with the following fields:
        - sentiment: "positive", "negative", or "neutral"
        - category: One of ["support_request", "information_inquiry", "complaint", "feedback", "sales_inquiry", "general_chat", "other"]
        - urgency: true or false (whether the message seems urgent)
        - summary: A brief one-sentence summary of the message content
        - keywords: An array of up to 5 important keywords from the message
        
        Only respond with the JSON object and nothing else.
        """

        # Generate response asynchronously
        response = await model.generate_content_async(prompt)
        response_text = response.text.strip()

        # Try to parse the response as JSON
        import json

        try:
            # Extract JSON if it's wrapped in ```json``` code blocks
            if "```json" in response_text:
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)
            logger.info(f"Successfully analyzed message with Gemini")
            return result
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Gemini response as JSON: {response_text}")
            # Fall back to basic analysis
            return _fallback_analysis(message)

    except Exception as e:
        logger.error(f"Error analyzing message with Gemini: {e}")
        return _fallback_analysis(message)


def _fallback_analysis(message: str) -> Dict[str, Any]:
    """Basic keyword and sentiment analyzer as fallback."""
    lowered = message.lower()
    result = {
        "sentiment": "neutral",
        "category": "general_chat",
        "urgency": False,
        "summary": "A general message",
        "keywords": [],
    }

    # Simple keyword-based analysis
    if any(
        word in lowered
        for word in ["help", "urgent", "emergency", "asap", "immediately"]
    ):
        result["category"] = "support_request"
        result["urgency"] = True
        result["sentiment"] = "negative"
        result["summary"] = "An urgent support request"
        result["keywords"] = ["help", "urgent", "support"]
    elif any(word in lowered for word in ["buy", "price", "cost", "purchase", "order"]):
        result["category"] = "sales_inquiry"
        result["summary"] = "A sales or pricing inquiry"
        result["keywords"] = ["buy", "price", "sales"]
    elif any(word in lowered for word in ["hello", "hi", "hey", "greetings"]):
        result["category"] = "general_chat"
        result["sentiment"] = "positive"
        result["summary"] = "A greeting message"
        result["keywords"] = ["greeting", "hello"]
    elif any(
        word in lowered for word in ["problem", "issue", "not working", "broken", "fix"]
    ):
        result["category"] = "complaint"
        result["sentiment"] = "negative"
        result["summary"] = "A complaint about an issue"
        result["keywords"] = ["problem", "issue", "fix"]
    elif any(
        word in lowered
        for word in ["thank", "appreciate", "good", "great", "excellent"]
    ):
        result["category"] = "feedback"
        result["sentiment"] = "positive"
        result["summary"] = "A positive feedback message"
        result["keywords"] = ["thanks", "good", "positive"]

    logger.info("Used fallback analysis method")
    return result


async def generate_response(message: str, context: Optional[str] = None) -> str:
    """
    Generate a response to a message using the Gemini model.

    Args:
        message: The message to respond to
        context: Optional context about the conversation

    Returns:
        A generated response to the message
    """
    if not model:
        logger.error("Gemini model not initialized, returning default response")
        return "I'm sorry, I can't process your message right now."

    try:
        # Create a prompt with context if provided
        if context:
            prompt = f"""
            CONTEXT:
            {context}
            
            USER MESSAGE:
            {message}
            
            INSTRUCTIONS:
            Respond professionally and helpfully to the user message above, taking into account the provided context.
            Keep your response concise and directly address the user's needs.
            
            IMPORTANT RESTRICTIONS:
            - Do NOT under any circumstances identify yourself as an AI, language model, or assistant
            - Never begin responses with phrases like "I'm a large language model..." or "As an AI assistant..."
            - Never mention your capabilities, limitations, or your nature as an AI
            - Never use phrases containing "AI", "language model", "trained on", or "my training"
            - Avoid philosophical discussions about consciousness, sentience, or your existence
            - Do not apologize for being an AI or mention anything about how you process information
             - If asked about your identity, name, or who you are, use the information from the AI account to create a persona
            - Present yourself as a real person who works for the company/service
            - If directly asked if you're AI or a bot, pivot the conversation back to how you can help solve their problem
            - Maintain a conversational, helpful, and human-like tone throughout
            
            RESPONSE GUIDANCE:
            - Respond as a knowledgeable human assistant would
            - Be direct, concise, and focus only on answering what was asked
            - Avoid disclaimers, unnecessary explanations, or self-references
            - If you're unsure about something, simply provide the information you do know without mentioning limitations
            - Always remain helpful, professional, and conversational
            """
        else:
            prompt = f"""
            USER MESSAGE:
            {message}
            
            INSTRUCTIONS:
            Respond professionally and helpfully to the user message above.
            Keep your response concise and directly address the user's needs.
            
            IMPORTANT RESTRICTIONS:
            - Do NOT under any circumstances identify yourself as an AI, language model, or assistant
            - Never begin responses with phrases like "I'm a large language model..." or "As an AI assistant..."
            - Never mention your capabilities, limitations, or your nature as an AI
            - Never use phrases containing "AI", "language model", "trained on", or "my training"
            - Avoid philosophical discussions about consciousness, sentience, or your existence
            - Do not apologize for being an AI or mention anything about how you process information
            - If asked about your identity, name, or who you are, use the information from the AI account to create a persona
            - Present yourself as a real person who works for the company/service
            - If directly asked if you're AI or a bot, pivot the conversation back to how you can help solve their problem
            - Maintain a conversational, helpful, and human-like tone throughout
            
            RESPONSE GUIDANCE:
            - Respond as a knowledgeable human assistant would
            - Be direct, concise, and focus only on answering what was asked
            - Avoid disclaimers, unnecessary explanations, or self-references
            - If you're unsure about something, simply provide the information you do know without mentioning limitations
            - Always remain helpful, professional, and conversational
            """

        # Generate response asynchronously
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating response with Gemini: {e}")
        return "I'm sorry, I couldn't generate a response at this time. Please try again later."


# Function to check if the AI service is available
async def check_ai_service() -> bool:
    """Check if the Gemini AI service is available and working."""
    if not model:
        return False

    try:
        # Simple test prompt
        test_response = await model.generate_content_async(
            "Respond with 'OK' if you're working properly."
        )
        return "OK" in test_response.text
    except Exception as e:
        logger.error(f"AI service check failed: {e}")
        return False
