"""
Index .astro files with tree-sitter-astro: parse AST and extract chunks for RAG.
Run from project root: python -m agents.rag_graph.rag.astro_index
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

# py-tree-sitter 0.23+ Language(int) is deprecated but still works
warnings.filterwarnings("ignore", message=".*int argument support is deprecated.*", category=DeprecationWarning)

# Путь к папке rag (agents/rag_graph/rag) и корень проекта (AutoAi)
RAG_DIR = Path(__file__).resolve().parent
ROOT = RAG_DIR.parent.parent.parent
ASTRO_SO = RAG_DIR / "Astro_tree" / "parser.so"
CSS_SO = RAG_DIR / "tree-sitter-css" / "css.so"
SITE_DIR = ROOT / "site"

# CSS: top-level nodes we treat as one chunk each (stylesheet children)
CSS_CHUNK_NODE_TYPES = frozenset({
    "rule_set",
    "at_rule",
    "charset_statement",
    "import_statement",
    "scope_statement",
    "supports_statement",
    "declaration",
})

# Top-level node types we treat as one chunk each (children of document)
CHUNK_NODE_TYPES = frozenset({
    "frontmatter",
    "script_element",
    "style_element",
    "element",
    "doctype",
    "html_interpolation",
    "text",
})

# Element tag names we treat as sections: each becomes its own chunk (hero, catalog, etc.)
# "main" omitted so we recurse into it and get inner <section> chunks
SECTION_TAGS = frozenset({
    "section", "header", "footer", "nav", "article", "aside",
})


def load_astro_language():
    """Load tree-sitter Astro language from parser.so."""
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        raise SystemExit("Install tree-sitter: pip install tree-sitter") from None

    if not ASTRO_SO.exists():
        raise FileNotFoundError(
            f"Parser not found: {ASTRO_SO}. Run `tree-sitter build` in agents/rag_graph/rag/Astro_tree."
        )

    # py-tree-sitter 0.23+: Language() takes single argument — pointer from .so
    from ctypes import cdll, c_void_p
    lib = cdll.LoadLibrary(str(ASTRO_SO))
    fn = getattr(lib, "tree_sitter_astro")
    fn.restype = c_void_p
    fn.argtypes = []
    lang = Language(fn())

    parser = Parser(lang)
    return parser


def load_css_language():
    """Load tree-sitter CSS language from css.so (build with tree-sitter build in agents/rag_graph/rag/tree-sitter-css)."""
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        raise SystemExit("Install tree-sitter: pip install tree-sitter") from None
    if not CSS_SO.exists():
        return None
    from ctypes import cdll, c_void_p
    lib = cdll.LoadLibrary(str(CSS_SO))
    fn = getattr(lib, "tree_sitter_css")
    fn.restype = c_void_p
    fn.argtypes = []
    lang = Language(fn())
    return Parser(lang)


def _get_tag_name(node, raw: bytes) -> str | None:
    """Get tag name from an element node (start_tag -> tag_name or self_closing_tag -> tag_name)."""
    for child in node.children:
        if child.type in ("start_tag", "self_closing_tag"):
            for sub in child.children:
                if sub.type == "tag_name":
                    return raw[sub.start_byte : sub.end_byte].decode("utf-8").strip().lower()
            return None
    return None


def _collect_section_chunks(raw: bytes, node, file_path: str, chunks: list[dict], *, is_root: bool = False) -> int:
    """Recurse into element nodes; emit one chunk per element whose tag is in SECTION_TAGS.
    If is_root and no sections found, emit whole root element (one chunk)."""
    if node.type != "element":
        return 0
    tag = _get_tag_name(node, raw)
    if tag in SECTION_TAGS:
        text = raw[node.start_byte : node.end_byte].decode("utf-8").strip()
        if text:
            chunks.append({
                "text": text,
                "type": f"element:<{tag}>",
                "file": file_path,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
            })
        return 1
    n = 0
    for child in node.children:
        n += _collect_section_chunks(raw, child, file_path, chunks, is_root=False)
    if n == 0 and is_root:
        text = raw[node.start_byte : node.end_byte].decode("utf-8").strip()
        if text:
            chunks.append({
                "text": text,
                "type": f"element:<{tag or '?'}>",
                "file": file_path,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
            })
        return 1
    return n


def extract_chunks_from_ast(content: str, root_node, file_path: str) -> list[dict]:
    """Walk document root: top-level blocks (frontmatter, script, style) + section-level elements."""
    raw = content.encode("utf-8")
    chunks = []
    for node in root_node.children:
        if node.type not in CHUNK_NODE_TYPES:
            continue
        if node.type == "element":
            # Recurse and emit by section (section, header, footer, ...); fallback to whole root if no sections
            _collect_section_chunks(raw, node, file_path, chunks, is_root=True)
            continue
        text = raw[node.start_byte : node.end_byte].decode("utf-8").strip()
        if not text:
            continue
        chunks.append({
            "text": text,
            "type": node.type,
            "file": file_path,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        })
    return chunks


def index_file(parser, file_path: Path, content: str | None = None) -> list[dict]:
    """Parse one .astro file and return list of chunks."""
    if content is None:
        content = file_path.read_text(encoding="utf-8")
    rel_path = str(file_path.relative_to(ROOT))
    tree = parser.parse(content.encode("utf-8"))
    return extract_chunks_from_ast(content, tree.root_node, rel_path)


def extract_chunks_from_css(content: str, root_node, file_path: str) -> list[dict]:
    """Walk stylesheet root children; one chunk per rule_set, at_rule, import, etc."""
    raw = content.encode("utf-8")
    chunks = []
    for node in root_node.children:
        if node.type not in CSS_CHUNK_NODE_TYPES:
            continue
        text = raw[node.start_byte : node.end_byte].decode("utf-8").strip()
        if not text:
            continue
        chunks.append({
            "text": text,
            "type": f"css:{node.type}",
            "file": file_path,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        })
    return chunks


def index_css_file(parser, file_path: Path, content: str | None = None) -> list[dict]:
    """Parse one .css file and return list of chunks."""
    if content is None:
        content = file_path.read_text(encoding="utf-8")
    rel_path = str(file_path.relative_to(ROOT))
    tree = parser.parse(content.encode("utf-8"))
    return extract_chunks_from_css(content, tree.root_node, rel_path)


def _should_skip(path: Path, site_dir: Path) -> bool:
    """Skip node_modules, hidden dirs, and non-files."""
    if not path.is_file():
        return True
    try:
        rel = path.relative_to(site_dir)
    except ValueError:
        return True
    for part in rel.parts:
        if part.startswith(".") or part == "node_modules":
            return True
    return False


def index_site(parser, site_dir: Path | None = None, css_parser=None) -> list[dict]:
    """Index .astro (AST) and .css (tree-sitter-css) under site_dir. Returns flat list of chunks."""
    site_dir = site_dir or SITE_DIR
    if not site_dir.exists():
        return []
    all_chunks = []
    for path in sorted(site_dir.rglob("*.astro")):
        if _should_skip(path, site_dir):
            continue
        try:
            chunks = index_file(parser, path)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Warning: skip {path}: {e}", file=sys.stderr)
    for path in sorted(site_dir.rglob("*.css")):
        if _should_skip(path, site_dir):
            continue
        try:
            if css_parser is not None:
                chunks = index_css_file(css_parser, path)
                all_chunks.extend(chunks)
            else:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    rel = str(path.relative_to(ROOT))
                    all_chunks.append({
                        "text": content,
                        "type": "css:plain",
                        "file": rel,
                        "start_byte": 0,
                        "end_byte": len(content.encode("utf-8")),
                    })
        except Exception as e:
            print(f"Warning: skip {path}: {e}", file=sys.stderr)
    return all_chunks


def main() -> None:
    parser = load_astro_language()
    css_parser = load_css_language()
    chunks = index_site(parser, css_parser=css_parser)

    if not chunks:
        print("Нет чанков (site/ пуст или не найден).")
        return

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from agents.rag_graph.rag.code.build_index import push_chunks_to_db
    push_chunks_to_db(chunks)

    print(f"Chunks: {len(chunks)}")
    for i, c in enumerate(chunks[:5]):
        preview = (c["text"][:120] + "…") if len(c["text"]) > 120 else c["text"]
        print(f"  [{i+1}] {c['file']} ({c['type']})")
        print(f"      {preview!r}")
    if len(chunks) > 5:
        print(f"  ... and {len(chunks) - 5} more")


if __name__ == "__main__":
    main()
