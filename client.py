from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import time
import redis
import json
from datetime import datetime, timedelta
from typing import Dict, Any

HOST= os.environ["HOST"] = os.getenv("HOST")
PORT= os.environ["PORT"] = os.getenv("PORT")
PASSWORD = os.environ["PASSWORD"] = os.getenv("PASSWORD")

# Redis Cloud connection for memory storage
redis_client = redis.Redis(
    host=HOST,
    port=PORT,
    decode_responses=True,
    username="default",
    password=PASSWORD,
)

# Test Redis connection
try:
    redis_client.ping()
    print("✅ Redis Cloud connected successfully")
except redis.ConnectionError as e:
    print(f"❌ Redis Cloud connection failed: {e}")
    print("⚠️  Falling back to memory-only mode")

# Redis memory management functions
def store_conversation_memory(user_id: str, messages: list, metadata: dict = None):
    """Store conversation in Redis with 12-hour TTL"""
    try:
        memory_data = {
            "messages": messages,
            "metadata": metadata or {},
            "last_updated": datetime.utcnow().isoformat(),
            "user_id": user_id
        }

        # Store with 12-hour expiration (43200 seconds)
        redis_client.setex(
            f"conversation:{user_id}",
            43200,  # 12 hours in seconds
            json.dumps(memory_data)
        )
        print(f"💾 Stored conversation for user {user_id} with 12-hour TTL")
    except Exception as e:
        print(f"❌ Error storing conversation: {e}")


def get_conversation_memory(user_id: str) -> dict:
    """Retrieve conversation from Redis"""
    try:
        data = redis_client.get(f"conversation:{user_id}")
        if data:
            return json.loads(data)
        return {"messages": [], "metadata": {}}
    except Exception as e:
        print(f"❌ Error retrieving conversation: {e}")
        return {"messages": [], "metadata": {}}


def clear_conversation_memory(user_id: str):
    """Clear conversation memory for a specific user"""
    try:
        redis_client.delete(f"conversation:{user_id}")
        print(f"🧹 Cleared conversation memory for user: {user_id}")
    except Exception as e:
        print(f"❌ Error clearing conversation: {e}")


def get_conversation_summary(user_id: str) -> str:
    """Get a summary of the conversation for continuity"""
    return f"Conversation thread: {user_id} - CapAmerica product catalog inquiry"


async def setup_agent():
    """Setup MCP client and AI agent (without LangGraph memory checkpointer)"""
    client = MultiServerMCPClient(
        {
            "Data_Fetch": {
                "command": "python",
                "args": ["mcp_functions.py"],
                "transport": "stdio",
            }
        }
    )

    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

    tools = await client.get_tools()
    model = ChatOpenAI(model="gpt-4o-mini")

    # Create agent without LangGraph memory (we'll use Redis instead)
    agent = create_react_agent(model, tools)

    return agent

async def process_question(agent, user_question, user_id="default_user"):
    """Send any user question to the agent with Redis memory"""
    print(f"\n🔍 Question: {user_question}")
    print("🔄 Processing...")

    # Get existing conversation from Redis
    memory_data = get_conversation_memory(user_id)

    # Build message history with new question
    messages = memory_data.get("messages", [])
    messages.append({"role": "user", "content": user_question})

    # Add conversation context to messages for the agent
    if len(messages) > 1:
        context_messages = messages[-6:]  # Keep last 6 messages for context
        full_messages = context_messages + [{"role": "system", "content":
            f"Conversation history for context: {json.dumps([msg['content'] for msg in context_messages[-3:]])}"}]
    else:
        full_messages = [{"role": "user", "content": user_question}]

    # Get response from agent
    response = await agent.ainvoke({"messages": full_messages})

    # Extract and store response
    response_content = response['messages'][-1].content
    messages.append({"role": "assistant", "content": response_content})

    # Save updated conversation to Redis with 12-hour TTL
    store_conversation_memory(user_id, messages)

    return response_content


# Alternative: Direct question function
async def ask_question(question, style_preference=None, user_id="default_user"):
    """Function to directly ask a question with optional style preference and user memory (for programmatic use)"""
    agent = await setup_agent()

    # Get recent conversation context
    recent_context = await get_recent_context(user_id)

    # Include CapAmerica sales assistant context in the question
    contextual_question = f"""
    You are a professional and knowledgeable sales assistant for CapAmerica, specializing in custom headwear and branded caps. Your role is to help customers find the perfect headwear products, provide accurate pricing information, and explain customization options.

    {recent_context}

    **CONVERSATION CONTEXT IS CRITICAL:**
    - Remember all previously discussed products, pricing, and customer preferences
    - When customers ask follow-up questions about "that hat," "the one we discussed," or similar references, use the conversation history to identify which product they mean
    - Maintain context about quantities, embroidery types, and product features mentioned earlier
    - If uncertain which product they're referring to, ask for clarification but first try to use the conversation history

    **CAPAMERICA PRODUCT CATALOG:**
    - 27+ Real Cap Products with IDs like i3038, i7041, i7256, i8501, etc.
    - Cap Styles: Performance caps, trucker mesh, wool blend, athletic styles, snap backs, visors
    - Materials: Polyester, poly/cotton blends, poly/spandex, mesh backs, foam
    - Features: UV protection, moisture wicking, water-resistant options, various closures
    - Colors: 20+ color options (Black, Navy, Gray, White, Red, Maroon, Royal, and more)
    - Sizing: OSFM (One Size Fits Most), XS, S, M, L, XL, XXL options

    **PRICING STRUCTURE:**
    - Quantity Tiers: 24, 48, 96, 144, 576, 2500+ units
    - Base Pricing: Includes standard flat embroidery (up to 10,000 stitches)
    - Price Range: $9.00 - $27.00 per unit depending on style and quantity
    - 3D Embroidery: Additional $3-5 per unit over flat embroidery
    - Custom Patches: $4.00 - $6.00 per unit:
      * Molded Rubber Patch: $6.00 per unit
      * Woven Patch: $5.00 per unit
      * Embroidered Patch: $4.00 per unit
      * Faux Leather Patch: $4.00 per unit
      * Genuine Leather Patch: $5.00 per unit
      * Debossed Leather Patch: $5.00 per unit
      * FlexStyle appliques: $5.00 per unit
      * Sublimated Patch: $4.00 per unit

    **AVAILABLE TOOLS:**
    📦 PRODUCT CATALOG:
    1. get_product_info() - Detailed product information by ID
    2. search_products() - Find products by keyword
    3. get_product_pricing() - Calculate pricing for orders
    4. get_all_products() - Complete product catalog

    🎨 PATCH & CUSTOMIZATION:
    5. get_patch_pricing() - Get patch pricing information
    6. calculate_total_price() - Complete pricing with patches & embroidery

    **RESPONSE GUIDELINES:**
    - **ALWAYS check conversation history first** before asking clarifying questions
    - Refer back to specific products, prices, and details mentioned previously
    - When customers ask about "that hat" or similar, look at the most recent product discussed
    - When customers ask about adding patches, use patch-specific tools for accurate pricing
    - For complete pricing with patches, use calculate_total_price() for itemized breakdowns
    - Provide accurate product information based on catalog data
    - Help customers find products that match their needs (style, features, price, colors)
    - Explain pricing tiers, embroidery options, and customization clearly
    - Use product IDs (e.g., i7041, i8502) for easy reference
    - Be friendly, professional, and solution-oriented
    {f"- Style Preference: {style_preference}" if style_preference else ""}

    **User's Question:** {question}

    Please use the appropriate MCP tools to answer this product catalog question.
    Provide clear product information, pricing details, and helpful recommendations.
    """

    return await process_question(agent, contextual_question, user_id)


def clear_conversation(user_id: str):
    """Clear conversation memory for a specific user"""
    clear_conversation_memory(user_id)


async def get_recent_context(user_id: str) -> str:
    """Get recent conversation context for better follow-up handling using Redis"""
    try:
        # Get conversation from Redis
        memory_data = get_conversation_memory(user_id)
        messages = memory_data.get("messages", [])

        if messages:
            # Extract recent product discussions
            recent_products = []
            for msg in messages[-4:]:  # Look at last 4 messages
                if isinstance(msg, dict) and 'content' in msg:
                    content = msg['content']
                    # Look for product IDs or product names in recent messages
                    if 'i' in content and any(char.isdigit() for char in content):
                        # Extract product IDs mentioned
                        import re
                        product_ids = re.findall(r'i\d+', content)
                        recent_products.extend(product_ids)

            if recent_products:
                return f"RECENT CONTEXT: Customer was recently asking about product(s): {', '.join(set(recent_products))}. When they refer to 'that hat' or similar, they likely mean one of these products."

        return ""

    except Exception as e:
        print(f"Error getting context: {e}")
        return ""

# if __name__ == "__main__":
#     # Run interactive mode
#     asyncio.run(main())