import os
import git
import re
from xml.sax.saxutils import escape
from tokencost import calculate_prompt_cost, count_string_tokens
import sys


def should_ignore_directory(dirname):
    # List of directory names to ignore
    ignore_list = ["node_modules", ".git", ".github"]
    return dirname in ignore_list


def should_ignore_file(filename):
    # List of file names and extensions to ignore
    ignore_list = ["LICENSE", "LICENSE.txt", "LICENSE.md", ".gitignore"]
    ignore_extensions = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".ico"]

    # Check if the file name is in the ignore list
    if filename in ignore_list:
        return True

    # Check if the file extension is in the ignore extensions list
    _, ext = os.path.splitext(filename)
    if ext.lower() in ignore_extensions:
        return True

    return False


def process_tree(tree, path=""):
    content = ""
    for item in tree.traverse():
        if item.type == "tree":
            # This is a directory
            dir_path = os.path.join(path, item.name)

            if should_ignore_directory(item.name):
                print(f"Skipping directory: {dir_path}")
                continue

            print(f"Entering directory: {dir_path}")
            content += f"<directory name='{item.name}'>\n"
            content += process_tree(item, dir_path)
            content += "</directory>\n"
        elif item.type == "blob":
            # This is a file
            file_path = os.path.join(path, item.name)

            if should_ignore_file(item.name):
                print(f"Skipping file: {file_path}")
                continue

            print(f"Processing file: {file_path}")

            try:
                file_content = item.data_stream.read().decode("utf-8", errors="ignore")

                # Skip binary files and large files
                if "\0" in file_content or len(file_content) > 100000:
                    print(f"Skipping file (binary or too large): {file_path}")
                    continue

                # Remove comments
                file_content = re.sub(r"(?m)^\s*#.*\n?", "", file_content)
                file_content = re.sub(r"(?m)^\s*//.*\n?", "", file_content)

                # Escape special characters for XML
                file_content = escape(file_content)

                content += f"<file name='{item.name}'>\n{file_content}\n</file>\n"
            except Exception as e:
                print(f"Error processing file {file_path}: {str(e)}")

    return content


def get_repo_content(repo_path, max_chars=10000):
    repo = git.Repo(repo_path)
    content = "<repository>\n"

    content += process_tree(repo.head.commit.tree)

    # if len(content) > max_chars:
    #     content = content[:max_chars]
    #     print("Reached maximum character limit. Content truncated.")

    content += "</repository>"
    return content


def create_prompt(repo_path, max_chars=10000):
    print(f"Analyzing repository: {repo_path}")
    content = get_repo_content(repo_path, max_chars)
    prompt = f"""
Please analyze the following Git repository content, which is structured in XML format to represent the directory hierarchy:

{content}

Based on this code and structure, please provide:
1. A brief summary of the project and its main functionalities.
2. An overview of the project's directory structure and organization.
3. Any notable patterns, practices, or architectural decisions you observe.
4. Potential areas for improvement or optimization, if any.
"""
    return prompt


def main():
    # Check if a repo path is provided as a command-line argument
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        # If no argument is provided, try to read from stdin (for piping)
        repo_path = sys.stdin.read().strip()

    # If we still don't have a repo path, print usage and exit
    if not repo_path:
        print("Usage: python script.py <repo_path>")
        print("   or: echo <repo_path> | python script.py")
        sys.exit(1)

    # Ensure the repo path exists
    if not os.path.exists(repo_path):
        print(f"Error: The repository path '{repo_path}' does not exist.")
        sys.exit(1)

    prompt = create_prompt(repo_path)

    model = "claude-3-sonnet-20240229"
    prompt_cost = calculate_prompt_cost(prompt, model)
    prompt_count = count_string_tokens(prompt, model)

    print(prompt)

    print(f"Count: {prompt_count}")
    print(f"Cost: ${prompt_cost}")


if __name__ == "__main__":
    main()
