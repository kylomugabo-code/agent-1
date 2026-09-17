import json
import os
import subprocess
import sys

from openai import OpenAI

from tools import (
    read_file,
    write_file,
    list_files,
    run_command,
    git_diff,
    git_status,
)


client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


TOOLS = [
    {
        "type": "function",
        "name": "list_files",
        "description": "List files in the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a text file from the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the file to read.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Create or completely replace a text file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the file.",
                },
                "content": {
                    "type": "string",
                    "description": "Complete new file contents.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "type": "function",
        "name": "run_command",
        "description": "Run a development/test command in the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "type": "function",
        "name": "git_status",
        "description": "Show changed files.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "type": "function",
        "name": "git_diff",
        "description": "Show the current git diff.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def execute_tool(name, arguments):
    if name == "list_files":
        return list_files(arguments.get("path", "."))

    if name == "read_file":
        return read_file(arguments["path"])

    if name == "write_file":
        return write_file(
            arguments["path"],
            arguments["content"],
        )

    if name == "run_command":
        return run_command(arguments["command"])

    if name == "git_status":
        return git_status()

    if name == "git_diff":
        return git_diff()

    return f"Unknown tool: {name}"


def create_branch():
    branch = "agent/task"

    subprocess.run(
        ["git", "checkout", "-b", branch],
        check=True,
    )

    return branch


def main():
    task = os.environ.get("TASK")

    if not task:
        print("ERROR: TASK environment variable is missing.")
        sys.exit(1)

    branch = create_branch()

    system_prompt = """
You are an autonomous software engineering agent.

Your job is to modify the repository to satisfy the user's task.

Rules:

1. Inspect the repository before changing anything.
2. Understand the existing architecture.
3. Make the smallest reasonable changes.
4. Do not modify unrelated files.
5. Prefer existing project conventions.
6. Add or update tests when appropriate.
7. Run the project's tests before finishing.
8. If tests fail, investigate and fix the problem.
9. Never expose secrets.
10. Never commit API keys, passwords, tokens, or credentials.
11. Review git diff before finishing.
12. Do not claim something works unless you actually tested it.

When you have completed the task, provide a concise summary.
"""

    response = client.responses.create(
        model="gpt-5",
        instructions=system_prompt,
        input=task,
        tools=TOOLS,
    )

    for _ in range(30):
        tool_calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        if not tool_calls:
            print(response.output_text)
            break

        outputs = []

        for call in tool_calls:
            try:
                arguments = json.loads(call.arguments)
                result = execute_tool(call.name, arguments)
            except Exception as exc:
                result = f"ERROR: {exc}"

            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result,
                }
            )

        response = client.responses.create(
            model="gpt-5",
            previous_response_id=response.id,
            input=outputs,
            tools=TOOLS,
        )

    else:
        print("Agent reached the maximum number of tool iterations.")
        sys.exit(1)

    status = subprocess.run(
        ["git", "status", "--short"],
        text=True,
        capture_output=True,
    )

    print("\n=== FINAL GIT STATUS ===")
    print(status.stdout)


if __name__ == "__main__":
    main()

