# CapAmerica RAG MCP Server

An intelligent product catalog API for CapAmerica headwear, combining Retrieval-Augmented Generation (RAG) with Model Context Protocol (MCP) and FastAPI for seamless conversational AI-powered product search and pricing.

## 🧢 Overview

The CapAmerica RAG MCP Server provides a sophisticated AI-powered product catalog system that:
- **Maintains conversation memory** per user session
- **Leverages real-time MCP tools** for product data access
- **Supports natural language queries** for product discovery
- **Provides accurate pricing** calculations for bulk orders
- **Manages 27+ real cap products** with detailed specifications

## 📁 Project Structure

```
CAP_RAG_MCP/
├── app.py                 # FastAPI web server with memory support
├── client.py              # LangChain MCP client with conversation memory
├── rag.py                 # Gradio interface for interactive testing
├── mcp_functions.py       # MCP server with product catalog tools
├── products.csv           # Real CapAmerica product database
├── .env                   # Environment variables (OPENAI_API_KEY)
├── requirements.txt       # Python dependencies
└── README.md             # This documentation
```

## 🚀 Features

### 💬 Conversation Memory
- **User-specific threading**: Each `user_id` gets their own conversation thread
- **Context persistence**: Follow-up questions remember previous context
- **Memory management**: Clear conversations per user
- **LangGraph MemorySaver**: Robust memory backend

### 🛍️ Product Catalog Tools
1. **`get_product_info(product_id)`** - Detailed product specifications
2. **`search_products(keyword)`** - Find products by style/features
3. **`get_product_pricing(product_id, embroidery_type, quantity)`** - Exact pricing calculations
4. **`get_all_products()`** - Complete catalog access

### 📊 Real Product Data
- **27+ Cap Products**: Performance caps, trucker mesh, wool blend, athletic styles
- **Real Pricing**: $9.00 - $27.00 per unit (24 to 2500+ quantities)
- **Color Options**: 20+ color variations per product
- **Embroidery Options**: Flat and 3D embroidery pricing
- **Size Range**: XS to XXL, OSFM options

## 🔧 API Endpoints

### POST `/chat/agent`
Ask questions with conversation memory support.

**Request Format:**
```json
{
    "user_id": "xyz",
    "query": "What's the price for 48 units of i7041?",
    "use_agent": true
}
```

**Response Format:**
```json
{
    "response": "The price for 48 units of i7041 with flat embroidery is $15.75 per unit...",
    "status_code": 200,
    "query": "What's the price for 48 units of i7041?",
    "user_id": "xyz",
    "timestamp": 1699123456.789
}
```

### GET `/health`
Health check endpoint showing service status and available features.

### DELETE `/chat/{user_id}`
Clear conversation memory for a specific user.

## 📦 Installation & Setup

### 1. Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
Create `.env` file:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Start the Services

#### Start MCP Server (Background)
```bash
python mcp_functions.py
```

#### Start FastAPI Server
```bash
python app.py
```
The API will be available at: `http://localhost:8021`

#### Start Gradio Interface (Optional)
```bash
python rag.py
```
Access interactive web interface at: `http://localhost:7860`

## 🧠 Usage Examples

### Basic Product Queries
```bash
# Find specific product
curl -X POST "http://localhost:8021/chat/agent" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "customer_123",
       "query": "Show me details for product i7041"
     }'
```

### Search and Discovery
```bash
# Find products by style
curl -X POST "http://localhost:8021/chat/agent" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "customer_123",
       "query": "What trucker style caps do you have?"
     }'
```

### Pricing Calculations
```bash
# Get specific pricing
curl -X POST "http://localhost:8021/chat/agent" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "customer_123",
       "query": "What'\''s the price for 144 units of i8501 with 3D embroidery?"
     }'
```

### Memory-Powered Conversations
```bash
# First question
curl -X POST "http://localhost:8021/chat/agent" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "customer_456",
       "query": "Show me caps with UV protection"
     }'

# Follow-up question (remembers context)
curl -X POST "http://localhost:8021/chat/agent" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "customer_456",
       "query": "What about the moisture wicking ones you mentioned?"
     }'
```

## 🔧 MCP Tools Reference

### get_product_info(product_id)
```python
# Returns detailed product information
{
    "product_id": "i7041",
    "title": "Lightweight Aerated Performance Cap",
    "features": "Medium profile six panel structured cap...",
    "sizing": "XS / OSFM",
    "pricing": {
        "flat_embroidery": {"24": 17.5, "48": 15.75, ...},
        "3d_embroidery": {"24": 22.25, "48": 20.75, ...}
    },
    "available_colors": ["Black", "Gray", "Maroon", "Navy", ...]
}
```

### search_products(keyword)
```python
# Returns matching products
{
    "keyword": "trucker",
    "matches": 8,
    "products": [
        {
            "product_id": "i8501",
            "title": "Performance Trucker Mesh Back Cap",
            "features": "Mid profile six panel structured..."
        }
    ]
}
```

### get_product_pricing(product_id, embroidery_type, quantity)
```python
# Returns calculated pricing
{
    "product_id": "i7041",
    "product_title": "Lightweight Aerated Performance Cap",
    "embroidery_type": "flat",
    "quantity": 48,
    "unit_price": 15.75,
    "total_cost": 756.0,
    "currency": "USD"
}
```

## 🏗️ Architecture

### Memory Layer
- **LangGraph MemorySaver**: Persistent conversation storage
- **Thread-based isolation**: Each user gets isolated conversation thread
- **Configurable retention**: Easy memory management per user

### MCP Integration
- **MultiServerMCPClient**: Connects to product catalog MCP server
- **Dynamic tool loading**: Automatically loads available MCP tools
- **Error handling**: Robust error recovery and user feedback

### AI Layer
- **LangChain**: AI framework integration
- **OpenAI GPT-4o-mini**: Advanced language model
- **ReAct Agent**: Tool-using agent with reasoning capabilities

### API Layer
- **FastAPI**: High-performance async web framework
- **CORS support**: Cross-origin request handling
- **Automatic documentation**: OpenAPI/Swagger at `/docs`

## 📊 Product Catalog Statistics

- **Total Products**: 27+ real CapAmerica cap models
- **Price Range**: $9.00 - $27.00 per unit
- **Quantity Tiers**: 24, 48, 96, 144, 576, 2500+ units
- **Color Options**: 20+ variations per product
- **Embroidery Types**: Flat and 3D embroidery
- **Size Range**: XS, S, M, L, XL, XXL, OSFM
- **Cap Styles**: Performance, trucker, athletic, wool blend, snapback, visor

## 🔍 Example Conversation Flow

```json
[
    {
        "user_id": "outdoor_event_co",
        "query": "What caps do you recommend for outdoor sports events?",
        "response": "For outdoor sports events, I recommend performance caps with UV protection and moisture wicking features. Let me show you some options..."
    },
    {
        "user_id": "outdoor_event_co",
        "query": "What about the trucker style ones?",
        "response": "Great choice! The trucker mesh caps are perfect for outdoor events. We have the Performance Trucker (i8501) and Premium Trucker (i8502) with excellent ventilation..."
    },
    {
        "user_id": "outdoor_event_co",
        "query": "What's the pricing for 96 units of the i8501?",
        "response": "For 96 units of the Performance Trucker Mesh Back Cap (i8501), the pricing is $18.75 per unit with flat embroidery, or $21.75 per unit with 3D embroidery..."
    }
]
```

## 🛠️ Development

### Adding New MCP Tools
1. Define tool function in `mcp_functions.py` with `@mcp.tool()` decorator
2. Update tool documentation and examples
3. Tools are automatically available to the AI agent

### Extending Memory Features
- Memory configuration in `client.py`: `get_user_config(user_id)`
- Conversation management: `clear_conversation(user_id)`
- Thread isolation via `thread_id` parameter

### API Enhancements
- Add new endpoints in `app.py`
- Extend request/response models
- Update OpenAPI documentation automatically generated

## 🐛 Troubleshooting

### Common Issues

1. **MCP Server Connection**
   - Ensure `mcp_functions.py` is running in background
   - Check stdio transport connection

2. **Memory Not Working**
   - Verify user_id is consistent across requests
   - Check MemorySaver configuration

3. **Missing Environment Variables**
   - Set `OPENAI_API_KEY` in `.env` file
   - Verify API key validity

4. **Product Data Issues**
   - Ensure `products.csv` exists and is accessible
   - Check CSV format and required columns

### Debug Mode
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📄 License

This project is part of the CapAmerica headwear catalog system and contains proprietary product data and pricing information.

## 🤝 Support

For technical support or questions about the product catalog, please refer to the CapAmerica product documentation or contact the development team.

---

**Built with ❤️ using LangChain, FastAPI, and Model Context Protocol**