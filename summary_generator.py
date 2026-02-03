import os
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

llm = None
llm2 = None
model1 = None
model2 = None

def initialize_models():
    """Initialize LLM models (lazy loading)"""
    global llm, llm2, model1, model2
    if llm is None:
        llm = HuggingFaceEndpoint(
            repo_id="Qwen/Qwen3-Next-80B-A3B-Instruct", 
            task="text-generation"
        )
        llm2 = HuggingFaceEndpoint(
            repo_id="meta-llama/Meta-Llama-3-8B-Instruct", 
            task="text-generation"
        )
        model1 = ChatHuggingFace(llm=llm)
        model2 = ChatHuggingFace(llm=llm2)
    return model1, model2

def generate_summary(transcript_file_path):
    """
    Generate a summary from a transcript file.
    
    Args:
        transcript_file_path (str): Path to the transcript text file
        
    Returns:
        str: Generated summary text, or None if error
    """
    try:
        model1, model2 = initialize_models()

        parser = StrOutputParser()
        
        loader = TextLoader(transcript_file_path, encoding='utf-8')
        docs = loader.load()
        
        splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=100)
        chunks = splitter.split_documents(docs)
        
        prompt1 = PromptTemplate(
            template="""You are assigned to do the task of generating the meeting summary \n \n so generate the summary based on this text  : \n {text}""",
            input_variables=['text']
        )
        
        chain1 = prompt1 | model2 | parser
        summaries = []
        
        print(f"Processing {len(chunks)} chunks...")
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")
            result = chain1.invoke({'text': chunk.page_content})
            summaries.append(result)
        
        entire_summary = " ".join(summary for summary in summaries)
        
        prompt2 = PromptTemplate(
            template="""your only work is to generate the summary of the meeting and now i will provide you with the different summaries of the single meeting but i did devide it into multiple chucks and generated multiple summaries
    now give me the one summary of all the summeries combined \n\n All summaries combined : \n {text}""",
            input_variables=['text']
        )
        
        chain2 = prompt2 | model1 | parser
        
        print("Generating final summary...")
        final_summary = chain2.invoke({'text': entire_summary})
        
        return final_summary
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return None

