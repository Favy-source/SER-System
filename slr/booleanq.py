"""
Boolean query parsing and local evaluation.

WHY THIS EXISTS
    The protocol's nine search strings are written in the Boolean syntax that
    Scopus and Web of Science accept. The free APIs available to this review
    (OpenAlex, Crossref, PubMed, arXiv) do NOT all support that syntax, and none
    support it identically.

    So the strategy is: retrieve BROADLY from each API using whatever query form
    it accepts, then apply the exact Boolean predicate LOCALLY to each record's
    title + abstract. The protocol string becomes executable code.

    That is more reproducible than a subscription index, not less. With Scopus
    you get a number and must trust the black box; here the filter is a function
    anyone can read, test, and re-run.

SYNTAX SUPPORTED
    "quoted phrase"     matched with word boundaries
    bare_term           matched with word boundaries
    prefix*             wildcard — prosod* matches prosody, prosodic
    AND / OR / NOT      case-sensitive operators
    ( ... )             grouping
    implicit AND        two adjacent terms with no operator

PRECEDENCE
    NOT  >  AND  >  OR      (standard, and what Scopus/WoS use)
"""
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Union


# ── AST ────────────────────────────────────────────────────

@dataclass
class Term:
    """A single searchable token: word, phrase, or wildcard prefix."""
    text: str
    wildcard: bool = False

    def matches(self, haystack: str) -> bool:
        return bool(self._regex().search(haystack))

    def _regex(self):
        if not hasattr(self, "_compiled"):
            body = re.escape(self.text.lower())
            # Phrases may contain hyphens/spaces; allow either as a separator so
            # "audio-visual" and "audio visual" both match "audio-visual".
            body = body.replace(r"\-", r"[\s\-]").replace(r"\ ", r"[\s\-]+")
            pattern = rf"\b{body}\w*" if self.wildcard else rf"\b{body}\b"
            object.__setattr__(self, "_compiled", re.compile(pattern, re.I))
        return self._compiled

    def __repr__(self):
        return f"{self.text}{'*' if self.wildcard else ''}"


@dataclass
class Not:
    child: "Node"
    def matches(self, h): return not self.child.matches(h)
    def __repr__(self): return f"NOT {self.child!r}"


@dataclass
class And:
    children: List["Node"]
    def matches(self, h): return all(c.matches(h) for c in self.children)
    def __repr__(self): return "(" + " AND ".join(repr(c) for c in self.children) + ")"


@dataclass
class Or:
    children: List["Node"]
    def matches(self, h): return any(c.matches(h) for c in self.children)
    def __repr__(self): return "(" + " OR ".join(repr(c) for c in self.children) + ")"


Node = Union[Term, Not, And, Or]


# ── tokeniser ──────────────────────────────────────────────

_TOKEN = re.compile(r'''
      \s*(?:
        (?P<lparen>\()
      | (?P<rparen>\))
      | "(?P<phrase>[^"]+)"
      | (?P<word>[^\s()"]+)
      )
''', re.X)


def tokenise(q: str):
    pos, out = 0, []
    while pos < len(q):
        m = _TOKEN.match(q, pos)
        if not m:
            break
        pos = m.end()
        if m.group("lparen"):
            out.append(("(", None))
        elif m.group("rparen"):
            out.append((")", None))
        elif m.group("phrase") is not None:
            out.append(("term", m.group("phrase").strip()))
        else:
            w = m.group("word")
            if w in ("AND", "OR", "NOT"):
                out.append((w, None))
            else:
                out.append(("term", w))
    return out


# ── recursive-descent parser ───────────────────────────────

class _Parser:
    def __init__(self, tokens):
        self.t, self.i = tokens, 0

    def peek(self):
        return self.t[self.i][0] if self.i < len(self.t) else None

    def take(self):
        tok = self.t[self.i]; self.i += 1; return tok

    def parse(self):
        node = self.parse_or()
        if self.i < len(self.t):
            raise ValueError(f"unparsed input at token {self.i}: {self.t[self.i:]}")
        return node

    def parse_or(self):
        nodes = [self.parse_and()]
        while self.peek() == "OR":
            self.take()
            nodes.append(self.parse_and())
        return nodes[0] if len(nodes) == 1 else Or(nodes)

    def parse_and(self):
        nodes = [self.parse_unary()]
        while True:
            p = self.peek()
            if p == "AND":
                self.take()
                nodes.append(self.parse_unary())
            # Implicit AND: a term or '(' directly following another operand.
            elif p in ("term", "("):
                nodes.append(self.parse_unary())
            else:
                break
        return nodes[0] if len(nodes) == 1 else And(nodes)

    def parse_unary(self):
        if self.peek() == "NOT":
            self.take()
            return Not(self.parse_unary())
        if self.peek() == "(":
            self.take()
            node = self.parse_or()
            if self.peek() != ")":
                raise ValueError("unbalanced parenthesis")
            self.take()
            return node
        kind, val = self.take()
        if kind != "term":
            raise ValueError(f"expected a term, got {kind}")
        if val.endswith("*"):
            return Term(val[:-1], wildcard=True)
        return Term(val)


@lru_cache(maxsize=256)
def _parse_cached(query: str) -> Node:
    return _Parser(tokenise(query)).parse()


def parse(query: str) -> Node:
    """Parse a protocol search string into an evaluable AST.

    Memoised, and deliberately so. Screening evaluates every record against
    every search string, so an un-cached parse meant re-tokenising and
    re-compiling ~20 regexes per record per string — roughly 316,000 regex
    compilations for a 1,757-record corpus, which turned a seconds-long
    screening pass into a run that outlived a 15-minute timeout.

    Sharing AST nodes between calls is safe: evaluation never mutates them, and
    the compiled-regex cache on Term is exactly what we want to reuse.
    """
    return _parse_cached(query)


def matches(query_or_ast, title: str, abstract: str = "") -> bool:
    """Does this record satisfy the Boolean predicate?

    Evaluated against title + abstract, which is what TITLE-ABS-KEY means in
    Scopus and TS= means in Web of Science. Keywords are not consistently
    available across the free APIs, so they are deliberately excluded rather
    than silently included for some sources and not others.
    """
    ast = parse(query_or_ast) if isinstance(query_or_ast, str) else query_or_ast
    return ast.matches(f"{title or ''}\n{abstract or ''}")


def terms(node: Node) -> List[Term]:
    """Every Term in the tree — used to build API-side queries."""
    if isinstance(node, Term):
        return [node]
    if isinstance(node, Not):
        return terms(node.child)
    return [t for c in node.children for t in terms(c)]


def api_query(node_or_str, max_terms: int = 8) -> str:
    """A bag-of-words relevance query for engines with NO Boolean support.

    Used for Crossref only. `query.bibliographic` is OR-with-ranking, not AND —
    verified empirically: adding terms INCREASES the result count (411k for
    "emotion recognition", 1.02M once two more phrases are appended). So a longer
    term list widens recall and improves ranking rather than over-constraining,
    which is the opposite of how it would behave on a Boolean engine.

    Precision therefore comes entirely from relevance ordering plus the local
    matches() predicate. That is acceptable because over-fetching is recoverable
    and under-fetching is not.
    """
    node = parse(node_or_str) if isinstance(node_or_str, str) else node_or_str
    phrases = sorted({t.text for t in terms(node) if " " in t.text},
                     key=len, reverse=True)
    if not phrases:
        phrases = sorted({t.text for t in terms(node)}, key=len, reverse=True)
    return " ".join(phrases[:max_terms])


# ── wildcard expansion ─────────────────────────────────────
#
# OpenAlex and arXiv have no truncation operator. Emitting the bare stem would
# match nothing ("quantiz" is not a word), silently zeroing out that alternative
# and quietly narrowing the protocol. Every stem the protocol actually uses is
# therefore expanded EXPLICITLY into its real word forms. Listing them by hand
# rather than guessing keeps the translation auditable — a reviewer can check
# this table against the protocol strings.

WILDCARD_EXPANSIONS = {
    "compress":   ["compression", "compressed", "compressing", "compressive"],
    "distill":    ["distillation", "distilled", "distilling"],
    "generalis":  ["generalisation", "generalise", "generalised", "generalisability"],
    "generaliz":  ["generalization", "generalize", "generalized", "generalizability"],
    "modalit":    ["modality", "modalities"],
    "prosod":     ["prosody", "prosodic"],
    "prun":       ["pruning", "pruned", "prune"],
    "quantis":    ["quantisation", "quantised", "quantise"],
    "quantiz":    ["quantization", "quantized", "quantize"],
    "reproducib": ["reproducibility", "reproducible"],
    "robust":     ["robust", "robustness"],
}


def expand_wildcard(stem: str) -> List[str]:
    """Word forms for a truncated stem. Unknown stems fall back to the stem
    itself so a protocol edit degrades rather than crashes — but the unit tests
    assert every stem in the protocol is covered here."""
    return WILDCARD_EXPANSIONS.get(stem.lower(), [stem])


def to_openalex(node_or_str) -> str:
    """Translate to OpenAlex `search` syntax.

    OpenAlex DOES support Boolean, verified empirically against the live API:
    a quoted phrase narrows (582k -> 108k), OR widens (108k -> 115k), AND
    narrows (108k -> 12k), and nested AND-of-ORs works. So the protocol string
    is translated faithfully rather than flattened.

    Wildcards are expanded to explicit OR groups; NOT becomes OpenAlex's NOT.
    """
    node = parse(node_or_str) if isinstance(node_or_str, str) else node_or_str

    def quote(text: str) -> str:
        return f'"{text}"' if " " in text else text

    def walk(n):
        if isinstance(n, Term):
            if n.wildcard:
                forms = expand_wildcard(n.text)
                if len(forms) == 1:
                    return quote(forms[0])
                return "(" + " OR ".join(quote(f) for f in forms) + ")"
            return quote(n.text)
        if isinstance(n, Not):
            return f"NOT ({walk(n.child)})"
        joiner = " AND " if isinstance(n, And) else " OR "
        return "(" + joiner.join(walk(c) for c in n.children) + ")"

    return walk(node)


# ── native translations ────────────────────────────────────
#
# PubMed and arXiv both accept real Boolean queries, so for those two the
# protocol string is translated faithfully instead of being flattened by
# api_query(). matches() still runs afterwards — belt and braces, and it keeps
# every source subject to the identical final predicate.

def to_pubmed(node_or_str) -> str:
    """Translate to PubMed syntax with [tiab] field tags.

    [tiab] = title/abstract, the closest PubMed equivalent of Scopus
    TITLE-ABS-KEY. PubMed truncation is a trailing `*`, same as the protocol.
    """
    node = parse(node_or_str) if isinstance(node_or_str, str) else node_or_str

    def walk(n):
        if isinstance(n, Term):
            body = f"{n.text}*" if n.wildcard else n.text
            # PubMed treats a quoted multi-word string as a phrase; unquoted
            # multi-word input gets silently ANDed, which would change meaning.
            return f'"{body}"[tiab]' if " " in body else f"{body}[tiab]"
        if isinstance(n, Not):
            return f"NOT ({walk(n.child)})"
        joiner = " AND " if isinstance(n, And) else " OR "
        return "(" + joiner.join(walk(c) for c in n.children) + ")"

    return walk(node)


def to_arxiv(node_or_str) -> str:
    """Translate to the arXiv API's search_query grammar.

    Three arXiv-specific quirks are handled here:

    1. ANDNOT instead of NOT.
    2. No wildcards — expanded via WILDCARD_EXPANSIONS, as for OpenAlex.
    3. UNRELIABLE PHRASE MATCHING. This one matters. Measured against the live
       API, `all:"speech emotion recognition" AND all:"facial expression
       recognition"` returns **1** record, while the same query with each phrase
       decomposed into word-level ANDs returns **153**. arXiv's tokenizer does
       not honour multi-word quoted phrases the way its documentation implies,
       and a phrase query silently loses ~99% of the true hits.

       So phrases are decomposed into ANDed words. That is strictly broader than
       the protocol (word adjacency is lost, so "recognition of facial
       expression" now matches too), which is the safe direction: matches()
       re-applies the exact phrase predicate locally and discards the extras.
    """
    node = parse(node_or_str) if isinstance(node_or_str, str) else node_or_str

    # Dropped from decomposed phrases: arXiv's index ignores them and including
    # them can zero out an otherwise good query.
    STOP = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
            "is", "of", "on", "or", "the", "to", "with"}

    def field(text: str) -> str:
        words = [w for w in re.split(r"[\s\-]+", text.lower())
                 if w and w not in STOP]
        if len(words) <= 1:
            return f"all:{words[0]}" if words else f"all:{text}"
        return "(" + " AND ".join(f"all:{w}" for w in words) + ")"

    def walk(n, negated=False):
        if isinstance(n, Term):
            if n.wildcard:
                forms = expand_wildcard(n.text)
                if len(forms) > 1:
                    return "(" + " OR ".join(field(f) for f in forms) + ")"
                return field(forms[0])
            return field(n.text)
        if isinstance(n, Not):
            return f"ANDNOT ({walk(n.child)})"
        joiner = " AND " if isinstance(n, And) else " OR "
        parts = []
        for c in n.children:
            s = walk(c)
            if s.startswith("ANDNOT "):
                parts.append(s)          # already carries its own operator
            else:
                parts.append(s)
        out = parts[0]
        for p in parts[1:]:
            out += (" " + p) if p.startswith("ANDNOT ") else (joiner + p)
        return f"({out})"

    return walk(node)
