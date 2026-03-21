# llm/tools/tools_init.py
"""
Split tools into two camps:
- design: skills + MCP (context, guidelines, read-only).
- development: writing code (write_file, shell_execute, read_file for reference).
"""
from langchain_core.tools import BaseTool

from .act_tools import (
    load_skill,
    list_skills,
    read_file,
    list_directory,
    read_file_in_site,
    list_directory_in_site,
    write_file,
    write_file_in_site,
    shell_execute,
    move_on,
    ready_to_execute,
)
from .mcp_tools import get_mcp_tools, get_sequential_thinking_tools


def get_load_skills_tools() -> list[BaseTool]:
    """Tools for load_skills node only: load context, then ready_to_execute. No MCP, no sequential thinking."""
    return [
        load_skill,
        list_skills,
        read_file_in_site,
        list_directory_in_site,
        ready_to_execute,
    ]


def get_gather_context_tools() -> list[BaseTool]:
    """Tools for gather_context node: load_skill + list_skills + ready_to_execute only (no read_file_in_site — context size)."""
    return [
        load_skill,
        list_skills,
        ready_to_execute,
    ]


def get_design_tools() -> list[BaseTool]:
    """Tools for design phase: skills, MCP, read files/dirs under site/ only, ready_to_execute."""
    mcp = get_mcp_tools()
    return get_load_skills_tools() + mcp + get_sequential_thinking_tools()


def get_development_tools() -> list[BaseTool]:
    """Tools for development phase: write files, run shell, move_on, sequential thinking."""
    return [
        read_file,
        write_file,
        shell_execute,
        move_on,
    ] + get_sequential_thinking_tools()


def get_execute_tools() -> list[BaseTool]:
    """Tools for execute node: read-only (read in site + MCP) + development (write_file_in_site, move_on). Skills are pre-loaded in state by gather_context; no load_skill/list_skills here."""
    mcp = get_mcp_tools()
    sequential = get_sequential_thinking_tools()
    read_part = [
        read_file_in_site,
        list_directory_in_site,
    ] + mcp + sequential
    dev_part = [write_file_in_site, move_on]
    return read_part + dev_part


def get_execute_tools_write_only() -> list[BaseTool]:
    """Tools for execute node: only write_file_in_site. One file per step; after write, graph goes to analyze (no move_on tool)."""
    return [write_file_in_site]


def get_shell_tools() -> list[BaseTool]:
    """Tools for init phase: shell commands + create file (reasoning → tools_init → analyze)."""
    return [read_file, shell_execute, write_file]


def get_init_tools() -> list[BaseTool]:
    """Init-only tools for reasoning: read + shell. No write_file — reasoning must not write code."""
    return [read_file, shell_execute]


def get_reasoning_tools() -> list[BaseTool]:
    """Tools for reasoning node: sequential thinking + init (read, shell only). No write_file."""
    return get_sequential_thinking_tools() + get_init_tools()


def get_base_tools() -> list[BaseTool]:
    """All tools (design + development). Backward compatibility."""
    return get_design_tools() + [write_file, shell_execute]
