import sys
from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.utils.logger import get_logger
from app.core.exceptions import SummaryGenerationException
from app.core.config import settings
from dotenv import load_dotenv

logger = get_logger(__name__)

load_dotenv()

# initialize clients once at module level
try:
    groq_client = Groq(api_key=settings.GROQ_API_KEY)

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0.3,
        api_key=settings.GROQ_API_KEY
    )
    logger.info("Groq client initialized successfully")

except Exception as e:
    raise SummaryGenerationException(
        f"Failed to initialize Groq client: {str(e)}", sys
    )

# text splitter for long transcripts
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=4000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ".", " "]
)

# output parser — strips metadata, returns clean string
output_parser = StrOutputParser()

# MAP prompt — runs on each chunk individually
MAP_PROMPT = PromptTemplate(
    template="""
You are analyzing a portion of a meeting transcript.
Extract key points, decisions, and action items from this section only.
Be concise and factual.

TRANSCRIPT SECTION:
{text}

KEY POINTS FROM THIS SECTION:
""",
    input_variables=["text"]
)

# REDUCE prompt — runs on combined chunk summaries
REDUCE_PROMPT = PromptTemplate(
    template="""
You are an expert meeting assistant.
Below are summaries of different sections of a meeting.
Combine them into one comprehensive structured final summary.

SECTION SUMMARIES:
{text}

Provide the final summary in this exact format:

## Meeting Summary

### Key Topics Discussed
-

### Decisions Made
-

### Action Items
- (format: Task — Owner if mentioned)

### Key Points
-

### Open Questions
-
""",
    input_variables=["text"]
)

# DIRECT prompt — single call for short transcripts
DIRECT_PROMPT = PromptTemplate(
    template="""
You are an expert meeting assistant.
Analyze this meeting transcript and provide a structured summary.

TRANSCRIPT:
{text}

Provide the summary in this exact format:

## Meeting Summary

### Key Topics Discussed
-

### Decisions Made
-

### Action Items
- (format: Task — Owner if mentioned)

### Key Points
-

### Open Questions
-
""",
    input_variables=["text"]
)

# LCEL chains — built once, reused for every request
map_chain = MAP_PROMPT | llm | output_parser
reduce_chain = REDUCE_PROMPT | llm | output_parser
direct_chain = DIRECT_PROMPT | llm | output_parser


def generate_summary(transcript: str) -> dict:
    """
    Generates structured meeting summary.
    Automatically picks direct or MapReduce strategy
    based on transcript length.

    Args:
        transcript: Full meeting transcript text

    Returns:
        dict with keys:
            - summary: formatted summary string
            - model: model used
            - tokens_used: approximate tokens consumed
            - strategy: "direct" or "mapreduce"

    Raises:
        SummaryGenerationException: if generation fails
    """
    logger.info(
        f"Generating summary — "
        f"length: {len(transcript)} chars, "
        f"words: {len(transcript.split())}"
    )

    if not transcript or len(transcript.strip()) < 50:
        raise SummaryGenerationException(
            "Transcript too short — minimum 50 characters required",
            sys
        )

    try:
        # rough token estimate: 1 token ≈ 0.75 words
        estimated_tokens = len(transcript.split()) / 0.75
        logger.info(f"Estimated tokens: {estimated_tokens:.0f}")

        if estimated_tokens < 100000:
            logger.info("Strategy: direct")
            return _direct_summary(transcript)
        else:
            logger.info("Strategy: mapreduce")
            return _mapreduce_summary(transcript)

    except SummaryGenerationException:
        raise
    except Exception as e:
        raise SummaryGenerationException(
            f"Summary generation failed: {str(e)}", sys
        )


def _direct_summary(transcript: str) -> dict:
    """
    Single LCEL chain call for shorter transcripts.
    """
    try:
        summary = direct_chain.invoke({"text": transcript})

        logger.info("Direct summary generated successfully")

        return {
            "summary": summary,
            "model": settings.GROQ_MODEL,
            "tokens_used": len(transcript.split()) // 1,  # approximate
            "strategy": "direct"
        }

    except Exception as e:
        raise SummaryGenerationException(
            f"Direct summary failed: {str(e)}", sys
        )


def _mapreduce_summary(transcript: str) -> dict:
    """
    MapReduce via LCEL batch for long transcripts.
    Batch runs map phase in parallel automatically.
    """
    try:
        chunks = text_splitter.split_text(transcript)
        logger.info(f"Split into {len(chunks)} chunks")

        # MAP phase — batch runs all chunks in parallel
        # max_concurrency=5 keeps us within Groq free tier limits
        logger.info("Starting parallel map phase via LCEL batch")
        chunk_summaries = map_chain.batch(
            [{"text": chunk} for chunk in chunks],
            config={"max_concurrency": 5}    #5 - to reduce rate limit for free use
        )
        logger.info(f"Map phase complete — {len(chunk_summaries)} summaries generated")

        # REDUCE phase — single call combining all summaries
        combined = "\n\n---\n\n".join(chunk_summaries)
        logger.info("Starting reduce phase")
        final_summary = reduce_chain.invoke({"text": combined})

        logger.info("MapReduce complete")

        return {
            "summary": final_summary,
            "model": settings.GROQ_MODEL,
            "tokens_used": len(chunks) * 600,
            "strategy": "mapreduce_parallel",
            "chunks_processed": len(chunks)
        }

    except Exception as e:
        raise SummaryGenerationException(
            f"MapReduce summary failed: {str(e)}", sys
        )


def generate_progressive_summary(transcript: str) -> dict:
    """
    Lightweight summary for mid-meeting updates.
    Called every 10 minutes during live meeting.
    Uses direct Groq call for speed — no chain overhead.
    """
    logger.info("Generating progressive summary")

    if not transcript or len(transcript.strip()) < 50:
        return {
            "summary": "Not enough transcript yet.",
            "tokens_used": 0
        }

    try:
        response = groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Briefly summarize what has been discussed so far.
3-5 bullet points maximum. Be concise.

TRANSCRIPT SO FAR:
{transcript}
"""
                }
            ],
            temperature=0.3,
            max_tokens=500
        )

        return {
            "summary": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens
        }

    except Exception as e:
        raise SummaryGenerationException(
            f"Progressive summary failed: {str(e)}", sys
        )