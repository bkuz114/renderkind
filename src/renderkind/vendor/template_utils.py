"""
template_utils.py - Template rendering utilities for build scripts.

This module provides pure functions for substituting placeholders in text
templates. Placeholders are denoted as {{name}} and are replaced with
provided content. No file I/O is performed—callers are responsible for
reading templates and writing results.

Example:
    >>> template = "<title>{{title}}</title><body>{{content}}</body>"
    >>> render_template(template, {"title": "My Page", "content": "<p>Hello</p>"})
    '<title>My Page</title><body><p>Hello</p></body>'
"""

import re
from typing import Optional


def find_placeholders(template: str) -> set[str]:
    """
    Extract all placeholder names from a template string.

    Placeholders are defined as {{name}} where "name" must contain at least one
    non-whitespace character except '}'. Whitespace (spaces and tabs only) are
    allowed around the name but are not part of the captured name.
    This function returns the set of all such names.

    Args:
        template: The template string to scan

    Returns:
        Set of placeholder names (the text between the double curly braces)
        with surrounding whitespace stripped.
        Returns an empty set if no valid placeholders are found.

    Example:
        >>> find_placeholders("Hello {{ name }}, welcome to {{site}}")
        {'name', 'site'}

        >>> find_placeholders("Invalid {{   }} should be ignored")
        set()

        >>> find_placeholders("{{first}} and {{  second  }} and {{ third }}")
        {'first', 'second', 'third'}
    """
    # Pattern explanation:
    # - {{   : literal opening double braces
    # - ([^}]+) : capture group: one or more characters that are not '}'
    #             This ensures we stop at the first closing brace
    # - }}   : literal closing double braces
    # Note: This pattern intentionally matches whitespace-only content like
    # "   " from {{   }}. Such matches are filtered out by the validation step below.
    pattern = re.compile(r"{{([^}]+)}}")
    matches = pattern.findall(template)

    # Validate and clean: require at least one non-whitespace character
    validated = set()
    for match in matches:
        stripped = match.strip()
        if stripped:  # non-empty after stripping whitespace
            validated.add(stripped)

    return validated


def _replace_placeholder(text: str, key: str, value: str) -> tuple[str, bool]:
    """
    Replace {{key}} (with optional whitespace padding) with value.

    Args:
        text: String to perform replacement on
        key: Placeholder name (without braces)
        value: Replacement string

    Returns:
        Tuple of (modified_text, replacement_occurred)

        modified_text:
          Text with all occurrences of {{key}} (allowing spaces/tabs around key)
          replaced by value.
        replacement_occurred:
          Boolean indicating whether any replacement was made.
          This enables the caller (render_template) to distinguish between:
          - A stable state (no replacements occurred → done)
          - A circular reference (replacements occurred but net change zero → error)

    Example:
        >>> _replace_placeholder("Hi {{ name }}!", "name", "Alice")
        ('Hi Alice!', True)
        >>> _replace_placeholder("{{a}} {{ a }} {{  a  }}", "a", "b")
        ('b b b', True)
        >>> _replace_placeholder("No match here", "name", "Alice")
        ('No match here', False)
    """
    # Pattern explanation:
    # {{        : literal opening double braces
    # \s*       : zero or more whitespace characters (space/tab)
    # {key}     : the placeholder name (escaped to handle regex special chars)
    # \s*       : zero or more whitespace characters
    # }}        : literal closing double braces
    #
    # Notes:
    # 1. re.escape(key) ensures that keys containing regex metacharacters
    #    (e.g., "a.b", "a+b", "a*b") are treated as literals, not patterns.
    # 2. r"\{\{" : \ escapes { chars; r allows \ chars to be interpreted as literal
    pattern = re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}")

    # subn returns a tuple: (new_string, number_of_replacements_made)
    # It replaces all non-overlapping occurrences of the pattern with the
    # replacement string, processing the input in a single pass.
    new_text, replacement_count = pattern.subn(value, text)

    # replacement_count > 0 indicates whether any placeholder was actually replaced.
    # This allows the caller (render_template) to detect cycles and stability.
    return new_text, replacement_count > 0


def render_template(
    template: str,
    substitutions: dict[str, str],
    recursive: bool = False,
    strict: bool = False,
    max_passes: int = 10,
    warning_comment: Optional[str] = None,
) -> str:
    """
    Replace {{placeholder}} occurrences with provided content.

    Each key in substitutions corresponds to a placeholder name. The value
    replaces every occurrence of {{key}} in the template. Whitespace around
    the placeholder name (spaces and tabs) is ignored, so {{key}}, {{ key }},
    and {{key  }} are all treated identically.

    Args:
        template: String containing {{placeholder}} markers
        substitutions: Mapping from placeholder name to replacement content
        recursive: If True, repeatedly substitute until no placeholders
                   remain or max_passes is reached. Use this when
                   substituted content may itself contain placeholders.
        strict: If True, raise KeyError when any placeholder in the
                original template lacks a substitution.
        max_passes: Maximum substitution passes when recursive=True.
                    Prevents infinite loops from circular references.
        warning_comment: If provided, prepends an HTML comment to the
                         result. Use "auto" for the default warning
                         ("THIS FILE IS GENERATED. DO NOT EDIT DIRECTLY."),
                         or provide a custom string.

    Returns:
        Rendered template with all substitutions applied, optionally
        prefixed with a warning comment.

    Raises:
        KeyError: If strict=True and a placeholder lacks a substitution
        ValueError: If recursive=True and the template still contains
                    placeholders after max_passes iterations (possible
                    circular reference or insufficient passes)

    Example:
        >>> render_template(
        ...     "{{greeting}}, {{ name }}!",
        ...     {"greeting": "Hello", "name": "Alice"}
        ... )
        'Hello, Alice!'

        >>> render_template(
        ...     "{{greeting}}, {{ name }}!",
        ...     {"greeting": "Hello"},
        ...     strict=True
        ... )
        Traceback (most recent call last):
        ...
        KeyError: "Missing substitutions for placeholders: {'name'}"
    """
    # Strict mode: verify all placeholders in original template have substitutions
    if strict:
        placeholders = find_placeholders(template)
        missing = placeholders - set(substitutions.keys())
        if missing:
            raise KeyError(f"Missing substitutions for placeholders: {missing}")

    # Apply substitutions
    result = template

    for pass_num in range(max_passes if recursive else 1):
        new_result = result

        # Replace each placeholder with its content using regex to allow
        # optional whitespace padding around the placeholder name.
        any_replacement_made = False
        for key, value in substitutions.items():
            new_result, replacement_made = _replace_placeholder(new_result, key, value)
            if replacement_made:
                any_replacement_made = True

        # If no replacements occurred in this pass, no further changes are possible.
        # This can happen either because:
        #   1. All placeholders have been resolved (template is fully rendered)
        #   2. Remaining placeholders have no matching keys in substitutions
        # In either case, recursive substitution is complete.
        # Note: This does not detect cycles (e.g., a→b→a) where replacements
        # occur but net change is zero. Cycle detection will be added in a
        # subsequent commit.
        if not any_replacement_made:
            # Add warning comment if requested, then return
            result = new_result
            return _add_warning_comment(result, warning_comment)

        # If replacements occurred but the string didn't change, we have a cycle.
        # Example: template "{{a}}" with substitutions {"a": "{{b}}", "b": "{{a}}"}
        #   Pass 1: "{{a}}" → "{{b}}" → "{{a}}" (net change zero)
        # Without detection, recursive mode would alternate forever.
        # Non-recursive mode is unaffected (only one pass).
        if recursive and new_result == result:
            raise ValueError(
                f"Circular reference detected after {pass_num + 1} passes. "
                f"Substitutions were applied but the result did not change."
            )

        result = new_result

        if not recursive:
            # Single pass mode: return after first iteration
            return _add_warning_comment(result, warning_comment)

    # If we exit the loop in recursive mode, we hit max_passes without stability
    # Check if any placeholders remain to help diagnose the issue
    remaining = find_placeholders(result)
    if remaining:
        raise ValueError(
            f"Recursive substitution did not converge after {max_passes} passes. "
            f"Remaining placeholders: {remaining}. "
            f"Possible circular reference? Try increasing max_passes."
        )

    # No placeholders remain but we hit max_passes (unlikely, but handle gracefully)
    return _add_warning_comment(result, warning_comment)


def _add_warning_comment(content: str, warning_comment: Optional[str]) -> str:
    """
    Internal helper to prepend a warning comment if requested.

    Args:
        content: The content to potentially prefix
        warning_comment: If None, returns content unchanged.
                         If "auto", uses default message.
                         Otherwise, uses the provided string.

    Returns:
        Content with optional comment prepended, followed by a blank line.
    """
    if warning_comment is None:
        return content

    if warning_comment == "auto":
        comment_text = "THIS FILE IS GENERATED. DO NOT EDIT DIRECTLY."
    else:
        comment_text = warning_comment

    return f"<!-- {comment_text} -->\n\n{content}"
