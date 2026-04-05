#!/usr/bin/env python3

import fnmatch
import glob
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_FILES = "**/*cloud-init*.{yml,yaml}"


def split_input_patterns(value: str | None, default: str = "") -> list[str]:
    raw_value = value if value and value.strip() else default
    patterns = []
    for line in raw_value.splitlines():
        segment_start = 0
        depth = 0
        for index, char in enumerate(line):
            if char == "{":
                depth += 1
            elif char == "}":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                pattern = line[segment_start:index].strip()
                if pattern:
                    patterns.append(pattern)
                segment_start = index + 1
        pattern = line[segment_start:].strip()
        if pattern:
            patterns.append(pattern)
    return patterns


def expand_braces(pattern: str) -> list[str]:
    start = pattern.find("{")
    if start == -1:
        return [pattern]

    depth = 0
    end = -1
    for index in range(start, len(pattern)):
        char = pattern[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index
                break

    if end == -1:
        return [pattern]

    options = []
    option_start = start + 1
    depth = 0
    for index in range(start + 1, end):
        char = pattern[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            options.append(pattern[option_start:index])
            option_start = index + 1
    options.append(pattern[option_start:end])

    expanded_patterns = []
    prefix = pattern[:start]
    suffix = pattern[end + 1 :]
    for option in options:
        expanded_patterns.extend(expand_braces(f"{prefix}{option}{suffix}"))
    return expanded_patterns


def resolve_matches(patterns: list[str]) -> list[str]:
    matches = set()
    for pattern in patterns:
        for expanded_pattern in expand_braces(pattern):
            for match in glob.glob(expanded_pattern, recursive=True):
                if Path(match).is_file():
                    matches.add(os.path.normpath(match))
    return sorted(matches)


def should_ignore(path: str, ignore_patterns: list[str]) -> bool:
    posix_path = Path(path).as_posix()
    path_obj = Path(path)
    for pattern in ignore_patterns:
        for expanded_pattern in expand_braces(pattern):
            if fnmatch.fnmatch(posix_path, expanded_pattern):
                return True
            for parent in path_obj.parents:
                if fnmatch.fnmatch(parent.as_posix(), expanded_pattern):
                    return True
    return False


def escape_command_value(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property_value(value: str) -> str:
    return (
        escape_command_value(value)
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def validate_file(config_file: str) -> int:
    result = subprocess.run(
        ["cloud-init", "schema", "--config-file", config_file],
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if result.returncode == 0:
        print(f"{config_file} was valid")
        return 0

    message = output or "cloud-init schema validation failed"
    print(
        f"::error file={escape_property_value(config_file)}::"
        f"{escape_command_value(message)}"
    )
    return 1


def main() -> int:
    file_patterns = split_input_patterns(os.getenv("INPUT_FILES"), DEFAULT_FILES)
    ignore_patterns = split_input_patterns(os.getenv("INPUT_IGNORE"))
    config_files = [
        config_file
        for config_file in resolve_matches(file_patterns)
        if not should_ignore(config_file, ignore_patterns)
    ]

    had_errors = 0
    for config_file in config_files:
        if validate_file(config_file):
            had_errors = 1
    return had_errors


if __name__ == "__main__":
    sys.exit(main())
