import os
import time
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, CharacterTextSplitter
# from langchain.chains.summarize import load_summarize_chain

load_dotenv()

TRANSCRIPT_DIR = os.path.join("data","transcripts","osi.txt")

summeries = []
parser = StrOutputParser()

llm = HuggingFaceEndpoint(
    repo_id="Qwen/Qwen3-Next-80B-A3B-Instruct", 
    task = "text-generation"
)

llm2 = HuggingFaceEndpoint(
    repo_id="meta-llama/Meta-Llama-3-8B-Instruct", 
    task = "text-generation"
)

model1 = ChatHuggingFace(llm=llm)
model2 = ChatHuggingFace(llm=llm2)

prompt = PromptTemplate(
    template = """You are assigned to do the task of generating the meeting summary \n \n so generate the summary based on this text  : \n {text}""",
    input_variables = ['text']
)

loader = TextLoader( TRANSCRIPT_DIR , encoding='utf-8')

docs = loader.load()
print(len(docs[0].page_content))

splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=100)

chunks = splitter.split_documents(docs)
print(len(chunks))

chain = prompt | model2 | parser

for i,chunk in enumerate (chunks):
    result = chain.invoke({'text' : chunk.page_content})
    summeries.append(result)

entire_summary = " ".join(summary for summary in summeries)

prompt2 = PromptTemplate(
    template = """your only work is to generate the summary of the meeting and now i will provide you with the different summaries of the single meeting but i did devide it into multiple chucks and generated multiple summaries
    now give me the one summary of all the summeries combined \n\n All summaries combined : \n {text}""",
    input_variables= ['text']
)

chain2 = prompt2 | model1 | parser

# summary_chain = load_summarize_chain(
#     llm= model,
#     chain_type= 'map_reduce',
#     map_prompt = prompt,
#     combine_prompt = prompt2 
# )


result = chain2.invoke({'text' : entire_summary})

print(result)
