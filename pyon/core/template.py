import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .vnode import VNode, h


class Node:
    pass

@dataclass
class TextNode(Node):
    text: str

@dataclass
class InterpolationNode(Node):
    expr: str

@dataclass
class ElementNode(Node):
    tag: str
    props: dict
    children: list

@dataclass
class ForNode(Node):
    var_name: str
    iterable_expr: str
    body: list[Node]

@dataclass
class IfNode(Node):
    branches: list[tuple[str | None, list[Node] | None]]

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img",
             "input", "link", "meta", "param", "source", "track", "wbr"}

TOKEN_RE = re.compile(
    r"(?P<INTERPOLATION>\{\{.*?\}\})"
    r"|(?P<STATEMENT>\{%.*?%\})"
    r"|(?P<ENDTAG></\s*(?P<endname>[a-zA-Z][\w:-]*)\s*>)"
    r"|(?P<STARTTAG><\s*(?P<startname>[a-zA-Z][\w:-]*)(?P<attrs>(?:\s+[^<>]*?)?)\s*(?P<selfclose>/)?>)",
    re.DOTALL,
)
ATTR_RE = re.compile(r'([a-zA-Z_:][\w:-]*)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'))?')
STMT_KEYWORDS = re.compile(r"^(for|endfor|if|elif|else|endif)\b")

@dataclass
class Token:
    type: str
    value: str
    extra: dict = field(default_factory=dict)

def parse_attrs(raw: str) -> dict:
    props = {}
    for m in ATTR_RE.finditer(raw):
        name = m.group(1)
        value = m.group(2) if m.group(2) is not None else m.group(3)
        props[name] = value if value is not None else True
    return props

def tokenize(template: str) -> list[Token]:
    tokens, pos = [], 0
    for m in TOKEN_RE.finditer(template):
        if m.start() > pos:
            tokens.append(Token("TEXT", template[pos:m.start()]))
        if m.lastgroup == "INTERPOLATION":
            tokens.append(Token("INTERPOLATION", m.group()[2:-2].strip()))
        elif m.lastgroup == "STATEMENT":
            value = m.group()[2:-2].strip()
            kw = STMT_KEYWORDS.match(value)
            tokens.append(Token(kw.group(1).upper() if kw else "STATEMENT", value))
        elif m.group("STARTTAG"):
            name = m.group("startname")
            selfclose = bool(m.group("selfclose")) or name.lower() in VOID_TAGS
            tokens.append(Token("STARTTAG", name, {
                "props": parse_attrs(m.group("attrs") or ""),
                "selfclose": selfclose,
            }))
        elif m.group("ENDTAG"):
            tokens.append(Token("ENDTAG", m.group("endname")))
        pos = m.end()
    if pos < len(template):
        tokens.append(Token("TEXT", template[pos:]))
    return tokens

FOR_RE = re.compile(r"^for\s+(\w+)\s+in\s+(.+)$")
IF_RE = re.compile(r"^if\s+(.+)$")
ELIF_RE = re.compile(r"^elif\s+(.+)$")

def parse(tokens: list[Token]) -> ElementNode:
    pos = 0

    def parse_nodes(stop_types: set[str]) -> list[Node]:
        nonlocal pos
        nodes = []
        while pos < len(tokens) and tokens[pos].type not in stop_types:
            tok = tokens[pos]
            if tok.type == "TEXT":
                # Preserve inline spaces, but drop formatting whitespace (newlines + spaces)
                if tok.value.isspace() and '\n' in tok.value:
                    pos += 1
                    continue
                if tok.value:
                    nodes.append(TextNode(tok.value))
                pos += 1
            elif tok.type == "INTERPOLATION":
                nodes.append(InterpolationNode(tok.value))
                pos += 1
            elif tok.type == "STARTTAG":
                props, selfclose = tok.extra["props"], tok.extra["selfclose"]
                pos += 1
                children = [] if selfclose else parse_nodes({"ENDTAG"})
                if not selfclose:
                    pos += 1  # skip ENDTAG
                nodes.append(ElementNode(tok.value, props, children))
            elif tok.type == "FOR":
                m = FOR_RE.match(tok.value)
                if not m:
                    raise SyntaxError(f"Invalid for loop syntax: {tok.value}")
                pos += 1
                body = parse_nodes({"ENDFOR"})
                pos += 1
                nodes.append(ForNode(m.group(1), m.group(2), body))
            elif tok.type == "IF":
                m = IF_RE.match(tok.value)
                if not m:
                    raise SyntaxError(f"Invalid if statement syntax: {tok.value}")
                branches: list[tuple[str | None, list[Node] | None]] = [(m.group(1), None)]
                pos += 1
                branches[0] = (branches[0][0], parse_nodes({"ELIF", "ELSE", "ENDIF"}))
                while pos < len(tokens) and tokens[pos].type == "ELIF":
                    m = ELIF_RE.match(tokens[pos].value)
                    if not m:
                        raise SyntaxError(f"Invalid elif statement syntax: {tokens[pos].value}")
                    cond = m.group(1)
                    pos += 1
                    branches.append((cond, parse_nodes({"ELIF", "ELSE", "ENDIF"})))
                if pos < len(tokens) and tokens[pos].type == "ELSE":
                    pos += 1
                    branches.append((None, parse_nodes({"ENDIF"})))
                pos += 1  # skip ENDIF
                nodes.append(IfNode(branches))
            else:
                raise SyntaxError(f"Unexpected token: {tok}")
        return nodes

    top = parse_nodes(set())
    real_nodes = [n for n in top if not (isinstance(n, TextNode) and n.text.isspace())]
    if len(real_nodes) == 1 and isinstance(real_nodes[0], ElementNode):
        return real_nodes[0]
    return ElementNode("#fragment", {}, top)

def eval_expr(expr: str, instance: Any, local_scope: dict) -> Any:
    """Evaluates an expression using the component's module globals and self."""
    # Combine component globals with explicit self
    import sys
    globals_dict = sys.modules[instance.__class__.__module__].__dict__.copy()
    globals_dict["self"] = instance
    return eval(expr, globals_dict, local_scope)

INTERP_IN_ATTR_RE = re.compile(r"\{\{(.*?)\}\}")

def render_props(props: dict, instance: Any, local_scope: dict) -> dict:
    resolved = {}
    for k, v in props.items():
        if k.startswith("on_") and isinstance(v, str):
            # Parse event handler reference (strip braces if present)
            if v.startswith("{{") and v.endswith("}}"):
                v = v[2:-2].strip()
            resolved[k] = eval_expr(v, instance, local_scope)
        else:
            if isinstance(v, str) and "{{" in v:
                v = v.strip()
                if v.startswith("{{") and v.endswith("}}") and v.count("{{") == 1:
                    resolved[k] = eval_expr(v[2:-2].strip(), instance, local_scope)
                    continue
                v = INTERP_IN_ATTR_RE.sub(
                    lambda m: str(eval_expr(m.group(1).strip(), instance, local_scope)), 
                    v
                )
            resolved[k] = v
    return resolved

def render_children(nodes: list[Node], instance: Any, local_scope: dict) -> Iterator:
    for node in nodes:
        if isinstance(node, TextNode):
            yield node.text
        elif isinstance(node, InterpolationNode):
            val = eval_expr(node.expr, instance, local_scope)
            if isinstance(val, list):
                yield from val
            elif isinstance(val, VNode):
                yield val
            else:
                yield str(val)
        elif isinstance(node, ElementNode):
            res = render_element(node, instance, local_scope)
            if isinstance(res, list):
                yield from res
            else:
                yield res
        elif isinstance(node, ForNode):
            for item in eval_expr(node.iterable_expr, instance, local_scope):
                yield from render_children(node.body, instance, {**local_scope, node.var_name: item})
        elif isinstance(node, IfNode):
            for cond, body in node.branches:
                if not body:
                    continue
                if cond is None or eval_expr(cond, instance, local_scope):
                    yield from render_children(body, instance, local_scope)
                    break

def render_element(node: ElementNode, instance: Any, local_scope: dict) -> VNode | list[VNode]:
    props = render_props(node.props, instance, local_scope)
    children = list(render_children(node.children, instance, local_scope))
    
    tag = node.tag
    if tag == "#fragment":
        return children
    
    # If tag is capitalized, it might be a component class. Resolve it via eval
    if tag[0].isupper():
        tag = eval_expr(tag, instance, local_scope)
        
    return h(tag, props, children)
