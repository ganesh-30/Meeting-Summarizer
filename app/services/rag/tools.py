from langchain_core.tools import tool
from app.services.rag.retriever import MeetingRetriever
from app.services.rag.store import MeetingVectorStore
from app.utils.logger import get_logger
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.core.config import settings
import json

logger = get_logger(__name__)

async def _get_mcp_tools() -> list:
    """Fetch MCP tools async. Returns empty list if MCP unavailable."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        import json
        with open(settings.MCP_CONFIG_FILE) as f:
            servers = json.load(f)
        client = MultiServerMCPClient(servers)
        tools = await client.get_tools()
        logger.info(f"MCP tools loaded: {[t.name for t in tools]}")
        return tools
    except Exception as e:
        logger.warning(f"MCP tools unavailable: {e}")
        return []

def create_tools(store: MeetingVectorStore , mcp_tools: list = None) -> list:
    retriever = MeetingRetriever(store, k=5)

    @tool
    def search_transcript(query: str) -> str:
        """
        Search the meeting transcript for relevant information.
        Use for ANY question about what was said, discussed,
        decided, assigned, or mentioned during the meeting.
        Always use this first for meeting-related questions.
        """
        result = retriever.retrieve(query)

        if not result.found:
            return (
                f"No relevant content found. "
                f"{store.count} sentences indexed so far."
            )

        logger.info(f"search_transcript: '{query[:40]}' - {result.count} results")
        return f"Relevant meeting content:\n{result.context}"

    @tool
    def web_search(query: str):
        """
        use this tool to search the web for information NOT in the meeting.
        also if any question explicitly asks for "web search" or "search the web" or "external information".
        """
        try:
            tavily = TavilySearchResults(max_results=3)
            results = tavily.invoke(query)
            
            
            formatted_results = []
            for r in results:
                formatted_results.append(
                    f"Source: {r.get('url')}\nContent: {r.get('content')}"
                )
            return "\n---\n".join(formatted_results)
        except Exception as e:
            return f"Error searching web: {e}"

    return [search_transcript, web_search]+(mcp_tools or [])