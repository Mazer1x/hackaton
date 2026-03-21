"""
RAG search graph: поиск по векторному индексу через RAG HTTP-сервис (RAG_SERVICE_URL).
Input: query, top_k (optional).
Output: chunks, best_chunk (один чанк, выбранный LLM), error (если есть).
"""
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.rag_graph.state import RAGGraphState
from agents.rag_graph.nodes.search_node import search_node
from agents.rag_graph.nodes.select_best_node import select_best_node

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

print("Building rag_graph...")

builder = StateGraph(RAGGraphState)
builder.add_node("search", search_node)
builder.add_node("select_best", select_best_node)
builder.set_entry_point("search")
builder.add_edge("search", "select_best")
builder.add_edge("select_best", END)

graph = builder.compile()

print("rag_graph compiled successfully!")
print("   Flow: search → select_best → END")
