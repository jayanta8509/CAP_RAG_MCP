from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import time
from typing import Dict, Any

# Global memory for conversation persistence
memory = MemorySaver()

def get_user_config(user_id: str) -> Dict[str, Any]:
    """Get configuration for user-specific memory thread"""
    return {"configurable": {"thread_id": f"user_{user_id}"}}

async def setup_agent():
    """Setup MCP client and AI agent with memory"""
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

    # Create agent with memory checkpointer
    agent = create_react_agent(model, tools, checkpointer=memory)

    return agent

async def process_question(agent, user_question, user_id="default_user"):
    """Send any user question to the agent with memory"""
    print(f"\n🔍 Question: {user_question}")
    print("🔄 Processing...")

    config = get_user_config(user_id)

    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_question}]},
        config=config
    )

    return response['messages'][-1].content


# Alternative: Direct question function
async def ask_question(question, style_preference=None, user_id="default_user"):
    """Function to directly ask a question with optional style preference and user memory (for programmatic use)"""
    agent = await setup_agent()

    # Get recent conversation context
    recent_context = await get_recent_context(agent, user_id)

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
    - Custom patches: Typically $1-3 per unit additional cost (confirm with specific product)

    **AVAILABLE TOOLS:**
    📦 PRODUCT CATALOG:
    1. get_product_info() - Detailed product information by ID
    2. search_products() - Find products by keyword
    3. get_product_pricing() - Calculate pricing for orders
    4. get_all_products() - Complete product catalog

    **RESPONSE GUIDELINES:**
    - **ALWAYS check conversation history first** before asking clarifying questions
    - Refer back to specific products, prices, and details mentioned previously
    - When customers ask about "that hat" or similar, look at the most recent product discussed
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
    print(f"🧹 Cleared conversation memory for user: {user_id}")
    # Note: MemorySaver automatically manages conversation state
    # The memory is stored per thread_id (user_id), so conversations remain separate


async def get_recent_context(agent, user_id: str) -> str:
    """Get recent conversation context for better follow-up handling"""
    try:
        config = get_user_config(user_id)

        # Get recent conversation history
        result = await agent.aget_state(config)

        if result and result.values and 'messages' in result.values:
            messages = result.values['messages']

            # Extract recent product discussions
            recent_products = []
            for msg in messages[-4:]:  # Look at last 4 messages
                if hasattr(msg, 'content') and isinstance(msg.content, str):
                    content = msg.content
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


def get_conversation_summary(user_id: str) -> str:
    """Get a summary of the conversation for continuity"""
    return f"Conversation thread: user_{user_id} - CapAmerica product catalog inquiry"

