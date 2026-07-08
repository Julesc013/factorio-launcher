from __future__ import annotations


def render_args(template_args: list[str], values: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for arg in template_args:
        current = arg
        for key, value in values.items():
            current = current.replace("{" + key + "}", value)
        rendered.append(current)
    return rendered

