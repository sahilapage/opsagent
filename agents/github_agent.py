from __future__ import annotations
import json
import base64
import structlog
from github import Github, GithubException
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from agents.state import AgentState

# ── HITL pending store ─────────────────────────────────────────────────────────
import time
_pending_github_approvals: dict = {}

GITHUB_HIGH_STAKES = {
    "create_pr", "merge_pr", "close_issue",
    "create_branch", "auto_fix_issue", "create_issue"
}

log = structlog.get_logger()


def get_github():
    s = get_settings()
    return Github(s.github_token)


def get_default_repo():
    s = get_settings()
    g = get_github()
    return g.get_repo(s.github_default_repo)


def get_llm():
    s = get_settings()
    return ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)


# ── Issues ─────────────────────────────────────────────────────────────────────

def list_issues(state: str = "open", limit: int = 10) -> str:
    repo = get_default_repo()
    issues = list(repo.get_issues(state=state))[:limit]
    if not issues:
        return f"No {state} issues found."
    output = f"Found {len(issues)} {state} issues in {repo.full_name}:\n\n"
    for issue in issues:
        labels = ", ".join([l.name for l in issue.labels]) or "none"
        output += f"#{issue.number} [{labels}] {issue.title}\n"
        output += f"  By: {issue.user.login} | Created: {issue.created_at.strftime('%Y-%m-%d')}\n"
        output += f"  URL: {issue.html_url}\n\n"
    return output


def get_issue(issue_number: int) -> str:
    repo = get_default_repo()
    issue = repo.get_issue(issue_number)
    output = f"Issue #{issue.number}: {issue.title}\n"
    output += f"State: {issue.state}\n"
    output += f"Author: {issue.user.login}\n"
    output += f"Created: {issue.created_at.strftime('%Y-%m-%d')}\n"
    output += f"Labels: {', '.join([l.name for l in issue.labels]) or 'none'}\n\n"
    output += f"Description:\n{issue.body or 'No description'}\n\n"
    comments = list(issue.get_comments())
    if comments:
        output += f"Comments ({len(comments)}):\n"
        for c in comments[:5]:
            output += f"  [{c.user.login}]: {c.body[:200]}\n"
    return output


def create_issue(title: str, body: str, labels: list[str] = None) -> str:
    repo = get_default_repo()
    kwargs = {"title": title, "body": body}
    if labels:
        kwargs["labels"] = labels
    issue = repo.create_issue(**kwargs)
    log.info("github_issue_created", number=issue.number, title=title)
    return f"Issue #{issue.number} created: {issue.html_url}"


def close_issue(issue_number: int, comment: str = None) -> str:
    repo = get_default_repo()
    issue = repo.get_issue(issue_number)
    if comment:
        issue.create_comment(comment)
    issue.edit(state="closed")
    log.info("github_issue_closed", number=issue_number)
    return f"Issue #{issue_number} closed successfully."


def comment_on_issue(issue_number: int, comment: str) -> str:
    repo = get_default_repo()
    issue = repo.get_issue(issue_number)
    issue.create_comment(comment)
    log.info("github_comment_added", issue=issue_number)
    return f"Comment added to issue #{issue_number}"


def suggest_fix_for_issue(issue_number: int) -> str:
    repo = get_default_repo()
    issue = repo.get_issue(issue_number)
    llm = get_llm()
    prompt = f"""You are a software engineer. Analyze this GitHub issue and suggest a fix.

Issue #{issue.number}: {issue.title}
Description: {issue.body or 'No description'}

Provide:
1. Root cause analysis
2. Suggested fix (with code if applicable)
3. Steps to implement
4. Any potential side effects to watch for

Be specific and actionable."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


# ── Pull Requests ──────────────────────────────────────────────────────────────

def list_prs(state: str = "open") -> str:
    repo = get_default_repo()
    prs = list(repo.get_pulls(state=state))[:10]
    if not prs:
        return f"No {state} pull requests found."
    output = f"Found {len(prs)} {state} PRs in {repo.full_name}:\n\n"
    for pr in prs:
        output += f"#{pr.number} {pr.title}\n"
        output += f"  By: {pr.user.login} | {pr.head.ref} → {pr.base.ref}\n"
        output += f"  URL: {pr.html_url}\n\n"
    return output


def get_pr(pr_number: int) -> str:
    repo = get_default_repo()
    pr = repo.get_pull(pr_number)
    output = f"PR #{pr.number}: {pr.title}\n"
    output += f"State: {pr.state} | Mergeable: {pr.mergeable}\n"
    output += f"Author: {pr.user.login}\n"
    output += f"Branch: {pr.head.ref} → {pr.base.ref}\n"
    output += f"Changed files: {pr.changed_files} | +{pr.additions} -{pr.deletions}\n\n"
    output += f"Description:\n{pr.body or 'No description'}\n\n"
    files = list(pr.get_files())[:10]
    if files:
        output += "Changed files:\n"
        for f in files:
            output += f"  {f.filename} (+{f.additions} -{f.deletions})\n"
    return output


def create_pr(title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
    repo = get_default_repo()
    pr = repo.create_pull(
        title=title,
        body=body,
        head=head_branch,
        base=base_branch,
    )
    log.info("github_pr_created", number=pr.number, title=title)
    return f"PR #{pr.number} created: {pr.html_url}"


def merge_pr(pr_number: int, commit_message: str = None) -> str:
    repo = get_default_repo()
    pr = repo.get_pull(pr_number)
    if not pr.mergeable:
        return f"PR #{pr_number} cannot be merged — conflicts exist."
    kwargs = {}
    if commit_message:
        kwargs["commit_message"] = commit_message
    result = pr.merge(**kwargs)
    log.info("github_pr_merged", number=pr_number)
    return f"PR #{pr_number} merged successfully. SHA: {result.sha}"


def code_review(pr_number: int) -> str:
    repo = get_default_repo()
    pr = repo.get_pull(pr_number)
    files = list(pr.get_files())

    diff_content = f"PR #{pr.number}: {pr.title}\n\n"
    for f in files[:5]:
        diff_content += f"File: {f.filename}\n"
        if f.patch:
            diff_content += f"{f.patch[:1000]}\n\n"

    llm = get_llm()
    prompt = f"""You are a senior software engineer doing a code review. 
Review this pull request and provide detailed feedback.

{diff_content}

Provide:
1. Overall assessment
2. Specific issues found (bugs, security, performance)
3. Code quality observations
4. Suggestions for improvement
5. Approval recommendation (approve/request changes/comment)"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


# ── Repository ─────────────────────────────────────────────────────────────────

def get_repo_summary() -> str:
    repo = get_default_repo()
    output = f"Repository: {repo.full_name}\n"
    output += f"Description: {repo.description or 'None'}\n"
    output += f"Stars: {repo.stargazers_count} | Forks: {repo.forks_count}\n"
    output += f"Language: {repo.language}\n"
    output += f"Open Issues: {repo.open_issues_count}\n"
    output += f"Default Branch: {repo.default_branch}\n"
    output += f"Last Updated: {repo.updated_at.strftime('%Y-%m-%d')}\n"
    return output


def list_commits(limit: int = 10) -> str:
    repo = get_default_repo()
    commits = list(repo.get_commits())[:limit]
    output = f"Last {len(commits)} commits in {repo.full_name}:\n\n"
    for c in commits:
        output += f"{c.sha[:7]} {c.commit.message.splitlines()[0][:60]}\n"
        output += f"  By: {c.commit.author.name} | {c.commit.author.date.strftime('%Y-%m-%d')}\n\n"
    return output


def get_file(file_path: str) -> str:
    repo = get_default_repo()
    try:
        content = repo.get_contents(file_path)
        decoded = base64.b64decode(content.content).decode("utf-8")
        return f"File: {file_path}\n\n{decoded[:3000]}"
    except Exception as e:
        return f"Could not read file {file_path}: {str(e)}"


def list_branches() -> str:
    repo = get_default_repo()
    branches = list(repo.get_branches())
    output = f"Branches in {repo.full_name}:\n\n"
    for b in branches:
        output += f"  {b.name}\n"
    return output


def create_branch(branch_name: str, from_branch: str = "main") -> str:
    repo = get_default_repo()
    source = repo.get_branch(from_branch)
    repo.create_git_ref(
        ref=f"refs/heads/{branch_name}",
        sha=source.commit.sha
    )
    log.info("github_branch_created", branch=branch_name)
    return f"Branch '{branch_name}' created from '{from_branch}'"


def search_code(query: str) -> str:
    g = get_github()
    s = get_settings()
    results = list(g.search_code(f"{query} repo:{s.github_default_repo}"))[:5]
    if not results:
        return f"No code found matching: {query}"
    output = f"Code search results for '{query}':\n\n"
    for r in results:
        output += f"File: {r.path}\n"
        output += f"  URL: {r.html_url}\n\n"
    return output


def get_workflow_runs() -> str:
    repo = get_default_repo()
    try:
        workflows = list(repo.get_workflows())
        if not workflows:
            return "No GitHub Actions workflows found."
        output = "GitHub Actions workflow runs:\n\n"
        for wf in workflows[:3]:
            runs = list(wf.get_runs())[:3]
            output += f"Workflow: {wf.name}\n"
            for run in runs:
                status_emoji = "✅" if run.conclusion == "success" else "❌" if run.conclusion == "failure" else "🔄"
                output += f"  {status_emoji} {run.display_title[:50]} | {run.conclusion or run.status}\n"
                output += f"     Branch: {run.head_branch} | {run.created_at.strftime('%Y-%m-%d')}\n"
            output += "\n"
        return output
    except Exception as e:
        return f"Could not fetch workflow runs: {str(e)}"
    
def count_repos() -> str:
    g = get_github()
    user = g.get_user()
    repos = list(user.get_repos())
    public = sum(1 for r in repos if not r.private)
    private = sum(1 for r in repos if r.private)
    return f"You have {len(repos)} total repositories:\n  - Public: {public}\n  - Private: {private}"    


def repo_health() -> str:
    repo = get_default_repo()
    open_issues = repo.open_issues_count
    open_prs = len(list(repo.get_pulls(state="open")))
    commits = list(repo.get_commits())
    last_commit = commits[0].commit.author.date.strftime("%Y-%m-%d") if commits else "unknown"
    stale_issues = [i for i in repo.get_issues(state="open")
                   if (repo.updated_at - i.created_at).days > 30]

    output = f"Repository Health Report: {repo.full_name}\n\n"
    output += f"{'✅' if open_issues < 10 else '⚠️'} Open Issues: {open_issues}\n"
    output += f"{'✅' if open_prs < 5 else '⚠️'} Open PRs: {open_prs}\n"
    output += f"📅 Last Commit: {last_commit}\n"
    output += f"{'⚠️' if len(stale_issues) > 0 else '✅'} Stale Issues (>30 days): {len(stale_issues)}\n"
    output += f"⭐ Stars: {repo.stargazers_count}\n"
    output += f"🍴 Forks: {repo.forks_count}\n\n"

    if open_issues > 10:
        output += "⚠️ High number of open issues — consider triaging.\n"
    if open_prs > 5:
        output += "⚠️ Many open PRs — consider reviewing and merging.\n"
    return output


# def auto_fix_issue(issue_number: int) -> str:
#     """The most impressive action — reads issue, reads code, generates fix, creates PR."""
#     repo = get_default_repo()
#     issue = repo.get_issue(issue_number)
#     llm = get_llm()

#     # Step 1: Understand the issue
#     issue_context = f"Issue #{issue.number}: {issue.title}\n{issue.body or ''}"

#     # Step 2: Find relevant files
#     find_files_prompt = f"""Given this GitHub issue, which files in the repository are most likely relevant?
# {issue_context}

# List up to 3 specific file paths that likely need to be modified. 
# Return ONLY a JSON array of file paths like: ["src/main.py", "utils/helper.py"]"""

#     files_response = llm.invoke([HumanMessage(content=find_files_prompt)])
#     try:
#         raw = files_response.content.strip()
#         if "```" in raw:
#             raw = raw.split("```")[1].replace("json", "").strip()
#         relevant_files = json.loads(raw)
#     except Exception:
#         relevant_files = []

#     # Step 3: Read relevant files
#     file_contents = ""
#     for fp in relevant_files[:3]:
#         content = get_file(fp)
#         file_contents += f"\n{content[:1500]}\n"

#     # Step 4: Generate fix
#     fix_prompt = f"""You are an expert software engineer. Fix the following GitHub issue.

# ISSUE:
# {issue_context}

# RELEVANT CODE:
# {file_contents if file_contents else "No specific files identified — provide general fix."}

# Provide a complete, production-ready fix with:
# 1. The exact code changes needed
# 2. Which files to modify
# 3. Step by step implementation
# 4. A commit message for the PR

# Format the fix clearly."""

#     fix_response = llm.invoke([HumanMessage(content=fix_prompt)])
#     fix = fix_response.content

#     # # Step 5: Create branch and PR
#     # try:
#     #     branch_name = f"fix/issue-{issue_number}"
#     #     create_branch(branch_name)
#     #     pr_result = create_pr(
#     #         title=f"Fix: {issue.title}",
#     #         body=f"Fixes #{issue_number}\n\n## Proposed Fix\n\n{fix[:2000]}",
#     #         head_branch=branch_name,
#     #     )
#     #     return f"Auto-fix for issue #{issue_number}:\n\n{fix}\n\n{pr_result}"
#     # except Exception as e:
#     #     return f"Generated fix for issue #{issue_number}:\n\n{fix}\n\n(Could not create PR automatically: {str(e)})"

#     # Step 5: Create branch, commit fix, and create PR
#     try:
#         branch_name = f"fix/issue-{issue_number}"
        
#         # Create branch
#         try:
#             create_branch(branch_name)
#         except Exception:
#             pass  # branch may already exist
        
#         # Commit a fix summary file to the branch
#         fix_file_path = f"fixes/issue-{issue_number}-fix.md"
#         fix_content = f"# Fix for Issue #{issue_number}: {issue.title}\n\n{fix}"
        
#         try:
#             # Check if file exists
#             existing = repo.get_contents(fix_file_path, ref=branch_name)
#             repo.update_file(
#                 path=fix_file_path,
#                 message=f"fix: implement fix for issue #{issue_number}",
#                 content=fix_content,
#                 sha=existing.sha,
#                 branch=branch_name,
#             )
#         except Exception:
#             # File doesn't exist, create it
#             repo.create_file(
#                 path=fix_file_path,
#                 message=f"fix: implement fix for issue #{issue_number}",
#                 content=fix_content,
#                 branch=branch_name,
#             )
        
#         # Now create PR
#         pr_result = create_pr(
#             title=f"Fix: {issue.title}",
#             body=f"Fixes #{issue_number}\n\n## Proposed Fix\n\n{fix}",
#             head_branch=branch_name,
#         )
#         return f"Auto-fix for issue #{issue_number}:\n\n{fix}\n\n{pr_result}"
#     except Exception as e:
#         return f"Generated fix for issue #{issue_number}:\n\n{fix}\n\n(PR creation failed: {str(e)})"

def auto_fix_issue(issue_number: int) -> str:
    """True end-to-end autonomous fix — reads code, modifies files, commits, creates PR."""
    repo = get_default_repo()
    issue = repo.get_issue(issue_number)
    llm = get_llm()
    s = get_settings()

    log.info("auto_fix_started", issue=issue_number)

    # Step 1: Understand the issue deeply
    issue_context = f"Issue #{issue.number}: {issue.title}\n{issue.body or 'No description'}"

    # Step 2: List all files in repo to understand structure
    def list_repo_files(path="", ref="main") -> list[str]:
        files = []
        try:
            contents = repo.get_contents(path, ref=ref)
            for item in contents:
                if item.type == "dir":
                    files.extend(list_repo_files(item.path, ref))
                else:
                    files.append(item.path)
        except Exception:
            pass
        return files

    all_files = list_repo_files()
    code_files = [f for f in all_files if f.endswith(
        ('.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.md')
    )][:30]  # limit to 30 files

    file_tree = "\n".join(code_files)

    # Step 3: Ask LLM which files to modify
    identify_prompt = f"""You are an expert software engineer. Given this GitHub issue and repository file tree, identify which existing files need to be modified AND which new files need to be created.

ISSUE:
{issue_context}

REPOSITORY FILES:
{file_tree}

Return a JSON object:
{{
  "files_to_modify": ["path/to/existing/file.py"],
  "files_to_create": ["path/to/new/file.py"],
  "reasoning": "brief explanation"
}}

Return ONLY valid JSON."""

    files_response = llm.invoke([HumanMessage(content=identify_prompt)])
    try:
        raw = files_response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        file_plan = json.loads(raw)
    except Exception:
        file_plan = {"files_to_modify": [], "files_to_create": [], "reasoning": ""}

    files_to_modify = file_plan.get("files_to_modify", [])[:3]
    files_to_create = file_plan.get("files_to_create", [])[:2]

    # Step 4: Read existing files
    existing_contents = {}
    for fp in files_to_modify:
        try:
            content_obj = repo.get_contents(fp)
            existing_contents[fp] = base64.b64decode(content_obj.content).decode("utf-8")
        except Exception:
            pass

    # Step 5: Generate actual code changes for each file
    file_changes = {}  # path -> new content

    for fp in files_to_modify:
        existing = existing_contents.get(fp, "# File not found")
        modify_prompt = f"""You are an expert software engineer. Modify this file to fix the GitHub issue.

ISSUE:
{issue_context}

FILE: {fp}
CURRENT CONTENT:
{existing[:3000]}

Write the COMPLETE modified file content. Include ALL existing code plus your changes.
Do NOT truncate or summarize. Write the full file.
Return ONLY the file content, no explanation, no markdown fences."""

        response = llm.invoke([HumanMessage(content=modify_prompt)])
        file_changes[fp] = response.content.strip()

    for fp in files_to_create:
        create_prompt = f"""You are an expert software engineer. Create this new file to fix the GitHub issue.

ISSUE:
{issue_context}

NEW FILE TO CREATE: {fp}

Write the COMPLETE file content.
Return ONLY the file content, no explanation, no markdown fences."""

        response = llm.invoke([HumanMessage(content=create_prompt)])
        file_changes[fp] = response.content.strip()

    if not file_changes:
        return f"Could not identify files to change for issue #{issue_number}. Manual review needed."

    # Step 6: Create branch
    branch_name = f"fix/issue-{issue_number}"
    try:
        create_branch(branch_name)
    except Exception:
        pass  # branch may already exist

    # Step 7: Commit all changed files to branch
    committed_files = []
    for fp, new_content in file_changes.items():
        try:
            try:
                # File exists — update it
                existing_file = repo.get_contents(fp, ref=branch_name)
                repo.update_file(
                    path=fp,
                    message=f"fix: update {fp} for issue #{issue_number}",
                    content=new_content,
                    sha=existing_file.sha,
                    branch=branch_name,
                )
                committed_files.append(f"Updated: {fp}")
            except Exception:
                # File doesn't exist — create it
                repo.create_file(
                    path=fp,
                    message=f"fix: create {fp} for issue #{issue_number}",
                    content=new_content,
                    branch=branch_name,
                )
                committed_files.append(f"Created: {fp}")
            log.info("file_committed", path=fp, branch=branch_name)
        except Exception as e:
            committed_files.append(f"Failed: {fp} ({str(e)[:50]})")

    # Step 8: Generate PR description
    pr_body = f"""## Automated Fix for Issue #{issue_number}

**Issue:** {issue.title}

**Files Changed:**
{chr(10).join(f'- {f}' for f in committed_files)}

**Reasoning:**
{file_plan.get('reasoning', 'Automated fix generated by OpsAgent')}

**Changes Summary:**
This PR was automatically generated by OpsAgent's autonomous code agent.
Please review the changes carefully before merging.

Fixes #{issue_number}"""

    # Step 9: Create PR
    try:
        pr = repo.create_pull(
            title=f"fix: {issue.title} (auto-generated)",
            body=pr_body,
            head=branch_name,
            base=repo.default_branch,
        )
        log.info("auto_fix_pr_created", pr=pr.number, issue=issue_number)
        result = f"✅ Auto-fix complete for issue #{issue_number}!\n\n"
        result += f"Files changed:\n" + "\n".join(f"  - {f}" for f in committed_files)
        result += f"\n\nPR #{pr.number} created: {pr.html_url}"
        return result
    except Exception as e:
        result = f"Files committed to branch '{branch_name}':\n"
        result += "\n".join(f"  - {f}" for f in committed_files)
        result += f"\n\nCould not create PR: {str(e)}"
        return result


# ── Parse intent ───────────────────────────────────────────────────────────────

GITHUB_INTENT_PROMPT = """Extract GitHub action from the user request. Return JSON only:
{
  "action": one of "list_issues", "get_issue", "create_issue", "close_issue",
             "comment_issue", "suggest_fix", "auto_fix_issue",
             "list_prs", "get_pr", "create_pr", "merge_pr", "code_review",
             "repo_summary", "list_commits", "get_file", "list_branches",
             "create_branch", "search_code", "workflow_runs", "repo_health",
  "issue_number": integer or null,
  "pr_number": integer or null,
  "title": string or null,
  "body": string or null,
  "comment": string or null,
  "state": "open" or "closed" or "all",
  "labels": list of strings or null,
  "file_path": string or null,
  "count_repos": integer or null,
  "branch_name": string or null,
  "head_branch": string or null,
  "base_branch": "main",
  "query": string or null
}
Return ONLY valid JSON."""


def parse_github_intent(task: str) -> dict:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)
    response = llm.invoke([
        SystemMessage(content=GITHUB_INTENT_PROMPT),
        HumanMessage(content=task),
    ])
    try:
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return {"action": "list_issues", "state": "open"}


# ── GitHub node ────────────────────────────────────────────────────────────────

def github_node(state: AgentState) -> AgentState:
    try:
        intent = parse_github_intent(state["task"])
        action = intent.get("action", "list_issues")
        log.info("github_node", action=action)

        # High-stakes GitHub actions require HITL
        if action in GITHUB_HIGH_STAKES:
            trace_id = state.get("trace_id", "unknown")

            # Build description
            if action == "create_pr":
                desc = f"Create PR: '{intent.get('title', '?')}' ({intent.get('head_branch', '?')} → {intent.get('base_branch', 'main')})"
            elif action == "merge_pr":
                desc = f"Merge PR #{intent.get('pr_number', '?')}"
            elif action == "close_issue":
                desc = f"Close issue #{intent.get('issue_number', '?')}"
            elif action == "create_branch":
                desc = f"Create branch '{intent.get('branch_name', '?')}'"
            elif action == "auto_fix_issue":
                desc = f"Auto-fix issue #{intent.get('issue_number', '?')} (reads code, commits fix, creates PR)"
            elif action == "create_issue":
                desc = f"Create issue: '{intent.get('title', '?')}'"
            else:
                desc = action

            # _pending_github_approvals[trace_id] = {
            #     "action": action,
            #     "intent": intent,
            #     "description": desc,
            # }
            _pending_github_approvals[trace_id] = {
                "action": action,
                "intent": intent,
                "description": desc,
                "task": state["task"],
                "timestamp": time.time(),
            }


            log.info("github_hitl_required", trace_id=trace_id, action=action)
            return {
                **state,
                "hitl_required": True,
                "hitl_action": desc,
                "final_answer": f"⏸️ **GitHub Approval Required**\n\nAction: {desc}\n\nTo approve: `POST /agent/approve/github/{trace_id}`\nTo reject: `POST /agent/reject/github/{trace_id}`",
                "results": state["results"] + [{"agent": "github", "output": "awaiting_approval"}],
            }

        # Read-only actions execute immediately
        action_map = {
            "list_issues": lambda: list_issues(state=intent.get("state", "open")),
            "get_issue": lambda: get_issue(int(intent.get("issue_number", 1))),
            "comment_issue": lambda: comment_on_issue(
                issue_number=int(intent.get("issue_number", 1)),
                comment=intent.get("comment", ""),
            ),
            "suggest_fix": lambda: suggest_fix_for_issue(int(intent.get("issue_number", 1))),
            "list_prs": lambda: list_prs(state=intent.get("state", "open")),
            "get_pr": lambda: get_pr(int(intent.get("pr_number", 1))),
            "code_review": lambda: code_review(int(intent.get("pr_number", 1))),
            "repo_summary": lambda: get_repo_summary(),
            "list_commits": lambda: list_commits(),
            "get_file": lambda: get_file(intent.get("file_path", "README.md")),
            "list_branches": lambda: list_branches(),
            "search_code": lambda: search_code(intent.get("query", "")),
            "workflow_runs": lambda: get_workflow_runs(),
            "repo_health": lambda: repo_health(),
        }

        handler = action_map.get(action, lambda: list_issues())
        result = handler()

        return {
            **state,
            "results": state["results"] + [{"agent": "github", "output": result}],
            "final_answer": result,
        }

    except GithubException as e:
        log.error("github_api_error", error=str(e))
        return {**state, "error": str(e), "final_answer": f"GitHub error: {str(e)}"}
    except Exception as e:
        log.error("github_node_error", error=str(e))
        return {**state, "error": str(e), "final_answer": f"GitHub agent error: {str(e)}"}

def approve_github_action(trace_id: str) -> str:
    if trace_id not in _pending_github_approvals:
        return "No pending GitHub action found or it has expired."
    pending = _pending_github_approvals[trace_id]
    if time.time() - pending["timestamp"] > 300:
        _pending_github_approvals.pop(trace_id)
        return "⏰ GitHub approval request expired (5 minute timeout)."
    _pending_github_approvals.pop(trace_id)
    action = pending["action"]
    intent = pending["intent"]
    log.info("github_hitl_approved", trace_id=trace_id, action=action)

    action_map = {
        "create_pr": lambda: create_pr(
            title=intent.get("title", "New PR"),
            body=intent.get("body", ""),
            head_branch=intent.get("head_branch", ""),
            base_branch=intent.get("base_branch", "main"),
        ),
        "merge_pr": lambda: merge_pr(int(intent.get("pr_number", 1))),
        "close_issue": lambda: close_issue(
            issue_number=int(intent.get("issue_number", 1)),
            comment=intent.get("comment"),
        ),
        "create_branch": lambda: create_branch(
            branch_name=intent.get("branch_name", "new-branch"),
            from_branch=intent.get("base_branch", "main"),
        ),
        "auto_fix_issue": lambda: auto_fix_issue(int(intent.get("issue_number", 1))),
        "create_issue": lambda: create_issue(
            title=intent.get("title", "New Issue"),
            body=intent.get("body", ""),
            labels=intent.get("labels"),
        ),
    }

    handler = action_map.get(action)
    if not handler:
        return f"Unknown action: {action}"
    return handler()


def reject_github_action(trace_id: str) -> str:
    if trace_id not in _pending_github_approvals:
        return "No pending GitHub action found or it has expired."
    pending = _pending_github_approvals[trace_id]
    if time.time() - pending["timestamp"] > 300:
        _pending_github_approvals.pop(trace_id)
        return "⏰ GitHub approval request expired (5 minute timeout)."
    _pending_github_approvals.pop(trace_id)
    log.info("github_hitl_rejected", trace_id=trace_id)
    return f"❌ GitHub action cancelled: {pending['description']}"
