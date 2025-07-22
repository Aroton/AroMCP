"""Expression evaluation engine for MCP Workflow System.

Provides JavaScript-like expression evaluation for workflow conditions and transformations.
Supports boolean expressions, property access, comparisons, and basic operations.
"""

from enum import Enum
from typing import Any


class ExpressionError(Exception):
    """Raised when expression evaluation fails."""

    pass


class TokenType(Enum):
    """Token types for expression parsing."""

    NUMBER = "NUMBER"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    NULL = "NULL"
    IDENTIFIER = "IDENTIFIER"
    DOT = "DOT"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    OPERATOR = "OPERATOR"
    LOGICAL = "LOGICAL"
    COMPARISON = "COMPARISON"
    TERNARY = "TERNARY"
    EOF = "EOF"


class Token:
    """A token in an expression."""

    def __init__(self, type_: TokenType, value: str, position: int = 0):
        self.type = type_
        self.value = value
        self.position = position

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


class ExpressionLexer:
    """Tokenizes JavaScript-like expressions."""

    def __init__(self, text: str):
        self.text = text
        self.position = 0
        self.current_char = self.text[0] if text else None

    def advance(self):
        """Move to next character."""
        self.position += 1
        if self.position >= len(self.text):
            self.current_char = None
        else:
            self.current_char = self.text[self.position]

    def skip_whitespace(self):
        """Skip whitespace characters."""
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def read_number(self) -> str:
        """Read a number token."""
        result = ""
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == "."):
            result += self.current_char
            self.advance()
        return result

    def read_string(self, quote_char: str) -> str:
        """Read a string token."""
        result = ""
        self.advance()  # Skip opening quote

        while self.current_char is not None and self.current_char != quote_char:
            if self.current_char == "\\":
                self.advance()
                if self.current_char is not None:
                    # Basic escape sequences
                    if self.current_char == "n":
                        result += "\n"
                    elif self.current_char == "t":
                        result += "\t"
                    elif self.current_char == "r":
                        result += "\r"
                    elif self.current_char == "\\":
                        result += "\\"
                    elif self.current_char == quote_char:
                        result += quote_char
                    else:
                        result += self.current_char
                    self.advance()
            else:
                result += self.current_char
                self.advance()

        if self.current_char == quote_char:
            self.advance()  # Skip closing quote

        return result

    def read_identifier(self) -> str:
        """Read an identifier or keyword."""
        result = ""
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char in "_$"):
            result += self.current_char
            self.advance()
        return result

    def peek_next(self, offset: int = 1) -> str | None:
        """Peek at next character(s)."""
        peek_pos = self.position + offset
        if peek_pos < len(self.text):
            return self.text[peek_pos]
        return None

    def tokenize(self) -> list[Token]:
        """Tokenize the entire expression."""
        tokens = []

        while self.current_char is not None:
            self.skip_whitespace()

            if self.current_char is None:
                break

            start_pos = self.position

            # Numbers
            if self.current_char.isdigit():
                value = self.read_number()
                tokens.append(Token(TokenType.NUMBER, value, start_pos))

            # Strings
            elif self.current_char in "\"'":
                quote_char = self.current_char
                value = self.read_string(quote_char)
                tokens.append(Token(TokenType.STRING, value, start_pos))

            # Identifiers and keywords
            elif self.current_char.isalpha() or self.current_char in "_$":
                value = self.read_identifier()
                if value in ("true", "false"):
                    tokens.append(Token(TokenType.BOOLEAN, value, start_pos))
                elif value == "null":
                    tokens.append(Token(TokenType.NULL, value, start_pos))
                else:
                    tokens.append(Token(TokenType.IDENTIFIER, value, start_pos))

            # Operators and symbols
            elif self.current_char == ".":
                tokens.append(Token(TokenType.DOT, ".", start_pos))
                self.advance()

            elif self.current_char == "[":
                tokens.append(Token(TokenType.LBRACKET, "[", start_pos))
                self.advance()

            elif self.current_char == "]":
                tokens.append(Token(TokenType.RBRACKET, "]", start_pos))
                self.advance()

            elif self.current_char == "(":
                tokens.append(Token(TokenType.LPAREN, "(", start_pos))
                self.advance()

            elif self.current_char == ")":
                tokens.append(Token(TokenType.RPAREN, ")", start_pos))
                self.advance()

            elif self.current_char == ",":
                tokens.append(Token(TokenType.COMMA, ",", start_pos))
                self.advance()

            elif self.current_char == "?":
                tokens.append(Token(TokenType.TERNARY, "?", start_pos))
                self.advance()

            elif self.current_char == ":":
                tokens.append(Token(TokenType.TERNARY, ":", start_pos))
                self.advance()

            # Two-character operators
            elif self.current_char == "&" and self.peek_next() == "&":
                tokens.append(Token(TokenType.LOGICAL, "&&", start_pos))
                self.advance()
                self.advance()

            elif self.current_char == "|" and self.peek_next() == "|":
                tokens.append(Token(TokenType.LOGICAL, "||", start_pos))
                self.advance()
                self.advance()

            elif self.current_char == "=" and self.peek_next() == "=" and self.peek_next(2) == "=":
                tokens.append(Token(TokenType.COMPARISON, "===", start_pos))
                self.advance()
                self.advance()
                self.advance()
                
            elif self.current_char == "=" and self.peek_next() == "=":
                tokens.append(Token(TokenType.COMPARISON, "==", start_pos))
                self.advance()
                self.advance()

            elif self.current_char == "!" and self.peek_next() == "=" and self.peek_next(2) == "=":
                tokens.append(Token(TokenType.COMPARISON, "!==", start_pos))
                self.advance()
                self.advance()
                self.advance()
                
            elif self.current_char == "!" and self.peek_next() == "=":
                tokens.append(Token(TokenType.COMPARISON, "!=", start_pos))
                self.advance()
                self.advance()

            elif self.current_char == "<" and self.peek_next() == "=":
                tokens.append(Token(TokenType.COMPARISON, "<=", start_pos))
                self.advance()
                self.advance()

            elif self.current_char == ">" and self.peek_next() == "=":
                tokens.append(Token(TokenType.COMPARISON, ">=", start_pos))
                self.advance()
                self.advance()

            # Single-character operators
            elif self.current_char in "+-*/%":
                tokens.append(Token(TokenType.OPERATOR, self.current_char, start_pos))
                self.advance()

            elif self.current_char in "<>":
                tokens.append(Token(TokenType.COMPARISON, self.current_char, start_pos))
                self.advance()

            elif self.current_char == "!":
                tokens.append(Token(TokenType.LOGICAL, "!", start_pos))
                self.advance()

            else:
                raise ExpressionError(f"Unexpected character '{self.current_char}' at position {self.position}")

        tokens.append(Token(TokenType.EOF, "", len(self.text)))
        return tokens


class ExpressionParser:
    """Parses tokenized expressions into an AST."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0
        self.current_token = tokens[0] if tokens else Token(TokenType.EOF, "")

    def advance(self):
        """Move to next token."""
        self.position += 1
        if self.position < len(self.tokens):
            self.current_token = self.tokens[self.position]
        else:
            self.current_token = Token(TokenType.EOF, "")

    def parse(self) -> dict[str, Any]:
        """Parse the expression into an AST."""
        return self.ternary()

    def ternary(self) -> dict[str, Any]:
        """Parse ternary conditional (condition ? true_val : false_val)."""
        expr = self.logical_or()

        if self.current_token.type == TokenType.TERNARY and self.current_token.value == "?":
            self.advance()
            true_val = self.ternary()

            if self.current_token.type != TokenType.TERNARY or self.current_token.value != ":":
                raise ExpressionError("Expected ':' in ternary expression")
            self.advance()

            false_val = self.ternary()

            return {"type": "ternary", "condition": expr, "true_value": true_val, "false_value": false_val}

        return expr

    def logical_or(self) -> dict[str, Any]:
        """Parse logical OR (||)."""
        left = self.logical_and()

        while self.current_token.type == TokenType.LOGICAL and self.current_token.value == "||":
            op = self.current_token.value
            self.advance()
            right = self.logical_and()
            left = {"type": "binary", "operator": op, "left": left, "right": right}

        return left

    def logical_and(self) -> dict[str, Any]:
        """Parse logical AND (&&)."""
        left = self.equality()

        while self.current_token.type == TokenType.LOGICAL and self.current_token.value == "&&":
            op = self.current_token.value
            self.advance()
            right = self.equality()
            left = {"type": "binary", "operator": op, "left": left, "right": right}

        return left

    def equality(self) -> dict[str, Any]:
        """Parse equality operators (==, !=)."""
        left = self.comparison()

        while self.current_token.type == TokenType.COMPARISON and self.current_token.value in ("==", "!=", "===", "!=="):
            op = self.current_token.value
            self.advance()
            right = self.comparison()
            left = {"type": "binary", "operator": op, "left": left, "right": right}

        return left

    def comparison(self) -> dict[str, Any]:
        """Parse comparison operators (<, >, <=, >=)."""
        left = self.addition()

        while self.current_token.type == TokenType.COMPARISON and self.current_token.value in ("<", ">", "<=", ">="):
            op = self.current_token.value
            self.advance()
            right = self.addition()
            left = {"type": "binary", "operator": op, "left": left, "right": right}

        return left

    def addition(self) -> dict[str, Any]:
        """Parse addition and subtraction."""
        left = self.multiplication()

        while self.current_token.type == TokenType.OPERATOR and self.current_token.value in ("+", "-"):
            op = self.current_token.value
            self.advance()
            right = self.multiplication()
            left = {"type": "binary", "operator": op, "left": left, "right": right}

        return left

    def multiplication(self) -> dict[str, Any]:
        """Parse multiplication, division, and modulo."""
        left = self.unary()

        while self.current_token.type == TokenType.OPERATOR and self.current_token.value in ("*", "/", "%"):
            op = self.current_token.value
            self.advance()
            right = self.unary()
            left = {"type": "binary", "operator": op, "left": left, "right": right}

        return left

    def unary(self) -> dict[str, Any]:
        """Parse unary operators (!, -, +)."""
        if (self.current_token.type == TokenType.LOGICAL and self.current_token.value == "!") or (
            self.current_token.type == TokenType.OPERATOR and self.current_token.value in ("+", "-")
        ):
            op = self.current_token.value
            self.advance()
            expr = self.unary()
            return {"type": "unary", "operator": op, "operand": expr}

        return self.postfix()

    def postfix(self) -> dict[str, Any]:
        """Parse postfix operations (property access, array access, method calls)."""
        left = self.primary()

        while True:
            if self.current_token.type == TokenType.DOT:
                self.advance()
                if self.current_token.type != TokenType.IDENTIFIER:
                    raise ExpressionError("Expected property name after '.'")

                property_name = self.current_token.value
                self.advance()

                # Check for method call
                if self.current_token.type == TokenType.LPAREN:
                    self.advance()
                    args = []

                    if self.current_token.type != TokenType.RPAREN:
                        args.append(self.ternary())

                        while (
                            self.current_token.type == TokenType.OPERATOR
                            and self.current_token.value == ","
                            and len(args) < 10
                        ):  # Prevent infinite loops
                            self.advance()
                            args.append(self.ternary())

                    if self.current_token.type != TokenType.RPAREN:
                        raise ExpressionError("Expected ')' after method arguments")
                    self.advance()

                    left = {"type": "method_call", "object": left, "method": property_name, "arguments": args}
                else:
                    left = {"type": "property_access", "object": left, "property": property_name}

            elif self.current_token.type == TokenType.LBRACKET:
                self.advance()
                index = self.ternary()

                if self.current_token.type != TokenType.RBRACKET:
                    raise ExpressionError("Expected ']' after array index")
                self.advance()

                left = {"type": "array_access", "object": left, "index": index}

            else:
                break

        return left

    def primary(self) -> dict[str, Any]:
        """Parse primary expressions (literals, identifiers, parentheses)."""
        if self.current_token.type == TokenType.NUMBER:
            value = (
                float(self.current_token.value) if "." in self.current_token.value else int(self.current_token.value)
            )
            self.advance()
            return {"type": "literal", "value": value}

        elif self.current_token.type == TokenType.STRING:
            value = self.current_token.value
            self.advance()
            return {"type": "literal", "value": value}

        elif self.current_token.type == TokenType.BOOLEAN:
            value = self.current_token.value == "true"
            self.advance()
            return {"type": "literal", "value": value}

        elif self.current_token.type == TokenType.NULL:
            self.advance()
            return {"type": "literal", "value": None}

        elif self.current_token.type == TokenType.IDENTIFIER:
            name = self.current_token.value
            self.advance()
            return {"type": "identifier", "name": name}

        elif self.current_token.type == TokenType.LPAREN:
            self.advance()
            expr = self.ternary()

            if self.current_token.type != TokenType.RPAREN:
                raise ExpressionError("Expected ')' after expression")
            self.advance()

            return expr

        elif self.current_token.type == TokenType.LBRACKET:
            # Array literal [item1, item2, ...]
            self.advance()
            elements = []
            
            # Handle empty array []
            if self.current_token.type == TokenType.RBRACKET:
                self.advance()
                return {"type": "array_literal", "elements": elements}
            
            # Parse array elements
            while True:
                elements.append(self.ternary())
                
                if self.current_token.type == TokenType.RBRACKET:
                    self.advance()
                    break
                elif self.current_token.type == TokenType.COMMA:
                    self.advance()
                    # Handle trailing comma
                    if self.current_token.type == TokenType.RBRACKET:
                        self.advance()
                        break
                else:
                    raise ExpressionError("Expected ',' or ']' in array literal")
            
            return {"type": "array_literal", "elements": elements}

        else:
            raise ExpressionError(f"Unexpected token: {self.current_token}")


class ExpressionEvaluator:
    """Evaluates parsed expression ASTs against a context."""

    def __init__(self):
        self.context = {}
        self.scoped_context = {}

    def evaluate(self, expression: str, context: dict[str, Any], scoped_context: dict[str, dict[str, Any]] | None = None) -> Any:
        """Evaluate an expression string against a context.
        
        Args:
            expression: The expression string to evaluate
            context: Legacy context for backward compatibility
            scoped_context: Optional scoped context with keys like 'this', 'global', 'loop', 'inputs'
        """
        self.context = context
        self.scoped_context = scoped_context or {}

        if not expression.strip():
            return None

        try:
            lexer = ExpressionLexer(expression)
            tokens = lexer.tokenize()
            parser = ExpressionParser(tokens)
            ast = parser.parse()
            return self._evaluate_node(ast)
        except Exception as e:
            raise ExpressionError(f"Failed to evaluate expression '{expression}': {str(e)}") from e

    def _evaluate_node(self, node: dict[str, Any]) -> Any:
        """Evaluate a single AST node."""
        node_type = node["type"]

        if node_type == "literal":
            return node["value"]

        elif node_type == "identifier":
            name = node["name"]
            
            # For simple identifiers, use legacy context resolution
            if name in self.context:
                return self.context[name]
            else:
                # JavaScript-like behavior: undefined variables return undefined
                return None

        elif node_type == "array_literal":
            # Evaluate each element in the array
            return [self._evaluate_node(element) for element in node["elements"]]

        elif node_type == "binary":
            left = self._evaluate_node(node["left"])
            right = self._evaluate_node(node["right"])
            op = node["operator"]

            return self._evaluate_binary_op(op, left, right)

        elif node_type == "unary":
            operand = self._evaluate_node(node["operand"])
            op = node["operator"]

            return self._evaluate_unary_op(op, operand)

        elif node_type == "property_access":
            # Check if this is a scoped variable access (e.g., this.variable)
            obj_node = node["object"]
            prop = node["property"]
            
            if (obj_node["type"] == "identifier" and 
                obj_node["name"] in ["this", "global", "loop", "inputs"] and
                self.scoped_context):
                # This is a scoped variable access
                scope_name = obj_node["name"]
                return self._get_scoped_variable(scope_name, prop)
            
            # Regular property access - evaluate the object first
            obj = self._evaluate_node(obj_node)
            return self._get_property(obj, prop)

        elif node_type == "array_access":
            # Check if the object is a scoped variable
            obj_node = node["object"]
            
            # Handle nested scoped access (e.g., this.items[0])
            if (obj_node["type"] == "property_access" and
                obj_node["object"]["type"] == "identifier" and
                obj_node["object"]["name"] in ["this", "global", "loop", "inputs"] and
                self.scoped_context):
                # Get the scoped object first
                scope_name = obj_node["object"]["name"]
                prop = obj_node["property"]
                obj = self._get_scoped_variable(scope_name, prop)
            else:
                # Regular object evaluation
                obj = self._evaluate_node(obj_node)
            
            index = self._evaluate_node(node["index"])
            return self._get_array_element(obj, index)

        elif node_type == "method_call":
            obj = self._evaluate_node(node["object"])
            method = node["method"]
            args = [self._evaluate_node(arg) for arg in node["arguments"]]

            return self._call_method(obj, method, args)

        elif node_type == "ternary":
            condition = self._evaluate_node(node["condition"])
            if self._to_boolean(condition):
                return self._evaluate_node(node["true_value"])
            else:
                return self._evaluate_node(node["false_value"])

        else:
            raise ExpressionError(f"Unknown node type: {node_type}")

    def _get_scoped_variable(self, scope_name: str, variable_path: str) -> Any:
        """Get a variable from a scoped context.
        
        Args:
            scope_name: The scope name ('this', 'global', 'loop', 'inputs')
            variable_path: The path within that scope (e.g., 'config.settings.value')
            
        Returns:
            The value at the specified path, or None if not found
        """
        if scope_name not in self.scoped_context:
            return None
            
        scope_data = self.scoped_context[scope_name]
        if scope_data is None:
            return None
            
        return self._navigate_path(scope_data, variable_path)
    
    def _navigate_path(self, obj: Any, path: str) -> Any:
        """Navigate a nested object path like 'config.settings.value'.
        
        Args:
            obj: The object to navigate
            path: Dot-separated path string
            
        Returns:
            The value at the path, or None if not found
        """
        if obj is None:
            return None
            
        current = obj
        path_parts = path.split(".")
        
        for part in path_parts:
            if current is None:
                return None
                
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                # Handle array properties like 'length'
                if part == "length":
                    current = len(current)
                else:
                    # Try to convert to int for array index
                    try:
                        index = int(part)
                        current = current[index] if 0 <= index < len(current) else None
                    except (ValueError, IndexError):
                        current = None
            else:
                # Try to get attribute for other objects
                current = getattr(current, part, None)
                
        return current

    def _evaluate_binary_op(self, op: str, left: Any, right: Any) -> Any:
        """Evaluate a binary operation."""
        # Logical operators
        if op == "&&":
            return right if self._to_boolean(left) else left
        elif op == "||":
            return left if self._to_boolean(left) else right

        # Equality operators
        elif op == "==":
            return self._loose_equals(left, right)
        elif op == "!=":
            return not self._loose_equals(left, right)
        elif op == "===":
            return self._strict_equals(left, right)
        elif op == "!==":
            return not self._strict_equals(left, right)

        # Comparison operators
        elif op == "<":
            return self._to_number(left) < self._to_number(right)
        elif op == ">":
            return self._to_number(left) > self._to_number(right)
        elif op == "<=":
            return self._to_number(left) <= self._to_number(right)
        elif op == ">=":
            return self._to_number(left) >= self._to_number(right)

        # Arithmetic operators
        elif op == "+":
            # String concatenation vs addition
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return self._to_number(left) + self._to_number(right)
        elif op == "-":
            return self._to_number(left) - self._to_number(right)
        elif op == "*":
            return self._to_number(left) * self._to_number(right)
        elif op == "/":
            right_num = self._to_number(right)
            if right_num == 0:
                return float("inf") if self._to_number(left) > 0 else float("-inf")
            return self._to_number(left) / right_num
        elif op == "%":
            return self._to_number(left) % self._to_number(right)

        else:
            raise ExpressionError(f"Unknown binary operator: {op}")

    def _evaluate_unary_op(self, op: str, operand: Any) -> Any:
        """Evaluate a unary operation."""
        if op == "!":
            return not self._to_boolean(operand)
        elif op == "-":
            return -self._to_number(operand)
        elif op == "+":
            return self._to_number(operand)
        else:
            raise ExpressionError(f"Unknown unary operator: {op}")

    def _get_property(self, obj: Any, prop: str) -> Any:
        """Get a property from an object."""
        if obj is None:
            return None

        if isinstance(obj, dict):
            return obj.get(prop)
        elif isinstance(obj, list):
            # Array properties
            if prop == "length":
                return len(obj)
            # Convert to int for array indices
            try:
                index = int(prop)
                return obj[index] if 0 <= index < len(obj) else None
            except (ValueError, IndexError):
                return None
        elif isinstance(obj, str):
            if prop == "length":
                return len(obj)

        # Try to get attribute for other objects
        return getattr(obj, prop, None)

    def _get_array_element(self, obj: Any, index: Any) -> Any:
        """Get an element from an array-like object."""
        if obj is None:
            return None

        try:
            if isinstance(obj, list | str):
                idx = int(self._to_number(index))
                return obj[idx] if 0 <= idx < len(obj) else None
            elif isinstance(obj, dict):
                # Dictionaries can be accessed with string keys
                key = str(index)
                return obj.get(key)
        except (ValueError, IndexError, TypeError):
            return None

        return None

    def _call_method(self, obj: Any, method: str, args: list[Any]) -> Any:
        """Call a method on an object."""
        if obj is None:
            return None

        # String methods
        if isinstance(obj, str):
            if method == "includes":
                search = str(args[0]) if args else ""
                return search in obj
            elif method == "startsWith":
                prefix = str(args[0]) if args else ""
                return obj.startswith(prefix)
            elif method == "endsWith":
                suffix = str(args[0]) if args else ""
                return obj.endswith(suffix)
            elif method == "split":
                delimiter = str(args[0]) if args else ""
                return obj.split(delimiter)
            elif method == "trim":
                return obj.strip()
            elif method == "toLowerCase":
                return obj.lower()
            elif method == "toUpperCase":
                return obj.upper()

        # Array methods
        elif isinstance(obj, list):
            if method == "includes":
                return args[0] in obj if args else False
            elif method == "concat":
                # Concatenate arrays or values to create a new array
                result = obj.copy()
                for arg in args:
                    if isinstance(arg, list):
                        result.extend(arg)
                    else:
                        result.append(arg)
                return result
            elif method == "filter":
                # Filter array based on a boolean function or property
                if not args:
                    return obj
                # For now, support simple property-based filtering
                filter_value = args[0]
                if isinstance(filter_value, str):
                    # Filter by property existence or truthiness
                    return [item for item in obj if isinstance(item, dict) and item.get(filter_value)]
                else:
                    # Filter by equality
                    return [item for item in obj if item == filter_value]
            elif method == "map":
                # Map array elements (basic implementation for common use cases)
                if not args:
                    return obj
                map_value = args[0]
                if isinstance(map_value, str):
                    # Map by property extraction
                    return [item.get(map_value) if isinstance(item, dict) else str(item) for item in obj]
                else:
                    # Simple transformation (convert to string, etc.)
                    return [str(item) for item in obj]
            elif method == "slice":
                # Slice array like JavaScript Array.slice(start, end)
                start = int(args[0]) if args and args[0] is not None else 0
                end = int(args[1]) if len(args) > 1 and args[1] is not None else len(obj)
                return obj[start:end]
            elif method == "join":
                delimiter = str(args[0]) if args else ","
                return delimiter.join(str(item) for item in obj)
            elif method == "push":
                # Add elements to end of array (mutates original)
                for arg in args:
                    obj.append(arg)
                return len(obj)  # Return new length like JavaScript
            elif method == "pop":
                # Remove and return last element
                return obj.pop() if obj else None

        return None

    def _to_boolean(self, value: Any) -> bool:
        """Convert a value to boolean using JavaScript rules."""
        if value is None:
            return False
        elif isinstance(value, bool):
            return value
        elif isinstance(value, int | float):
            return value != 0 and not (isinstance(value, float) and value != value)  # NaN check
        elif isinstance(value, str):
            return len(value) > 0
        elif isinstance(value, list | dict):
            return True  # Objects and arrays are always truthy
        else:
            return bool(value)

    def _to_number(self, value: Any) -> int | float:
        """Convert a value to number using JavaScript rules."""
        if value is None:
            return 0
        elif isinstance(value, bool):
            return 1 if value else 0
        elif isinstance(value, int):
            return value  # Preserve integers
        elif isinstance(value, float):
            return value
        elif isinstance(value, str):
            if value.strip() == "":
                return 0
            try:
                # Try to parse as int first, then float
                if "." not in value:
                    return int(value)
                else:
                    return float(value)
            except ValueError:
                return float("nan")
        else:
            return float("nan")

    def _loose_equals(self, left: Any, right: Any) -> bool:
        """Implement JavaScript == comparison."""
        # Same type comparison
        if type(left) is type(right):
            return left == right

        # null/undefined equivalence
        if left is None and right is None:
            return True

        # Number conversion comparisons
        if isinstance(left, int | float) and isinstance(right, str):
            try:
                return left == float(right)
            except ValueError:
                return False
        elif isinstance(left, str) and isinstance(right, int | float):
            try:
                return float(left) == right
            except ValueError:
                return False

        # Boolean conversion
        if isinstance(left, bool):
            return self._loose_equals(1 if left else 0, right)
        elif isinstance(right, bool):
            return self._loose_equals(left, 1 if right else 0)

        return False
    
    def _strict_equals(self, left: Any, right: Any) -> bool:
        """Implement JavaScript === comparison (strict equality)."""
        # Same type and value
        if type(left) is type(right):
            return left == right
        
        # No type coercion in strict equality
        return False
