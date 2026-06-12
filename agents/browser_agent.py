from __future__ import annotations
import asyncio
from langsmith import traceable
import structlog
from playwright.async_api import async_playwright
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from agents.state import AgentState

log = structlog.get_logger()


# ── Web scraper ────────────────────────────────────────────────────────────────

async def scrape_url(url: str, timeout: int = 15000) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        try:
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Remove noise elements
            await page.evaluate("""
                ['nav','footer','header','script','style',
                 '.ads','#cookie-banner'].forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove())
                })
            """)

            text = await page.inner_text("body")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            cleaned = "\n".join(lines[:300])  # cap at 300 lines
            log.info("scraped_url", url=url, chars=len(cleaned))
            return cleaned
        except Exception as e:
            log.error("scrape_error", url=url, error=str(e))
            return f"Error scraping {url}: {str(e)}"
        finally:
            await browser.close()


# async def search_web(query: str) -> str:
#     search_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&ia=web"
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)
#         page = await browser.new_page()
#         await page.set_extra_http_headers({
#             "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
#         })
#         try:
#             await page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
#             await page.wait_for_timeout(3000)

#             # Extract search result links and snippets
#             results = await page.evaluate("""
#                 () => {
#                     const items = [];
#                     document.querySelectorAll('[data-result="web"]').forEach((el, i) => {
#                         if (i >= 5) return;
#                         const title = el.querySelector('h2')?.innerText || '';
#                         const snippet = el.querySelector('[data-result="snippet"]')?.innerText || '';
#                         const link = el.querySelector('a')?.href || '';
#                         if (title) items.push({title, snippet, link});
#                     });
#                     return items;
#                 }
#             """)

#             if not results:
#                 # Fallback — just get page text
#                 text = await page.inner_text("body")
#                 lines = [l.strip() for l in text.splitlines() if l.strip()]
#                 return "\n".join(lines[:100])

#             output = f"Search results for: '{query}'\n\n"
#             for i, r in enumerate(results, 1):
#                 output += f"[{i}] {r['title']}\n"
#                 output += f"    {r['snippet']}\n"
#                 output += f"    URL: {r['link']}\n\n"
#             return output

#         except Exception as e:
#             log.error("search_error", query=query, error=str(e))
#             return f"Search error: {str(e)}"
#         finally:
#             await browser.close()


# async def search_web(query: str) -> str:
#     try:
#         from googlesearch import search
#         output = f"Search results for: '{query}'\n\n"
#         results = list(search(query, num_results=5, lang="en"))
#         if not results:
#             return "No search results found."
        
#         # Scrape the first result for actual content
#         first_url = results[0]
#         log.info("search_top_result", url=first_url)
#         content = await scrape_url(first_url)
        
#         output += f"Top result: {first_url}\n\n"
#         output += content
#         return output

#     except Exception as e:
#         log.error("search_error", query=query, error=str(e))
#         return f"Search error: {str(e)}"

# async def search_web(query: str) -> str:
#     search_url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)
#         context = await browser.new_context(
#             user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#         )
#         page = await context.new_page()
#         try:
#             await page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
#             await page.wait_for_timeout(2000)

#             results = await page.evaluate("""
#                 () => {
#                     const items = [];
#                     document.querySelectorAll('.b_algo').forEach((el, i) => {
#                         if (i >= 5) return;
#                         const title = el.querySelector('h2')?.innerText || '';
#                         const snippet = el.querySelector('.b_caption p')?.innerText || '';
#                         const link = el.querySelector('a')?.href || '';
#                         if (title) items.push({title, snippet, link});
#                     });
#                     return items;
#                 }
#             """)

#             if not results:
#                 text = await page.inner_text("body")
#                 lines = [l.strip() for l in text.splitlines() if l.strip()]
#                 return "\n".join(lines[:150])

#             output = f"Search results for: '{query}'\n\n"
#             for i, r in enumerate(results, 1):
#                 output += f"[{i}] {r['title']}\n"
#                 output += f"    {r['snippet']}\n"
#                 output += f"    URL: {r['link']}\n\n"
#             return output

#         except Exception as e:
#             log.error("search_error", query=query, error=str(e))
#             return f"Search error: {str(e)}"
#         finally:
#             await browser.close()

async def search_web(query: str) -> str:
    import httpx
    from rag.config import get_settings
    s = get_settings()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": s.serper_api_key,
                "Content-Type": "application/json"
            },
            json={"q": query, "num": 5},
            timeout=10
        )
        data = response.json()
    
    organic = data.get("organic", [])
    if not organic:
        return "No search results found."
    
    output = f"Search results for: '{query}'\n\n"
    for i, r in enumerate(organic[:5], 1):
        output += f"[{i}] {r.get('title', '')}\n"
        output += f"    {r.get('snippet', '')}\n"
        output += f"    URL: {r.get('link', '')}\n\n"
    return output

# ── Parse browser intent ───────────────────────────────────────────────────────

def parse_browser_intent(task: str) -> dict:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)
    import json
    prompt = """Extract browser intent from the user request. Return JSON only:
{
  "action": "search" or "scrape",
  "query": "search query if action is search",
  "url": "URL if action is scrape"
}
No explanation, JSON only."""
    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=task),
    ])
    try:
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return {"action": "search", "query": task}


# ── Synthesize answer from scraped content ─────────────────────────────────────

def synthesize_answer(task: str, content: str) -> str:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)
    prompt = f"""Based on the following web content, answer the user's question concisely.
If the answer isn't in the content, say so.

User question: {task}

Web content:
{content[:3000]}

Answer:"""
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

def _run_in_new_loop(coro):
    """Run async code in a completely isolated thread + event loop."""
    import asyncio
    import threading
    result = [None]
    error = [None]

    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result[0] = loop.run_until_complete(coro)
        except Exception as e:
            error[0] = e
        finally:
            loop.close()

    t = threading.Thread(target=thread_target)
    t.start()
    t.join(timeout=30)

    if error[0]:
        raise error[0]
    return result[0]

# ── Browser node ───────────────────────────────────────────────────────────────

# def browser_node(state: AgentState) -> AgentState:
#     try:
#         intent = parse_browser_intent(state["task"])
#         action = intent.get("action", "search")
#         log.info("browser_node", action=action)

#         if action == "scrape" and intent.get("url"):
#             raw_content = asyncio.run(scrape_url(intent["url"]))
#         else:
#             query = intent.get("query", state["task"])
#             raw_content = asyncio.run(search_web(query))

#         # Synthesize a proper answer from raw content
#         answer = synthesize_answer(state["task"], raw_content)

#         return {
#             **state,
#             "results": state["results"] + [{
#                 "agent": "browser",
#                 "output": answer,
#                 "raw_content": raw_content[:500]
#             }],
#             "final_answer": answer,
#         }

#     except Exception as e:
#         log.error("browser_node_error", error=str(e))
#         return {
#             **state,
#             "error": str(e),
#             "final_answer": f"Browser agent error: {str(e)}"
#         }

# def browser_node(state: AgentState) -> AgentState:
#     import concurrent.futures
#     try:
#         intent = parse_browser_intent(state["task"])
#         action = intent.get("action", "search")
#         log.info("browser_node", action=action)

#         # Run async code in a separate thread with its own event loop
#         def run_async(coro):
#             import asyncio
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
#             try:
#                 return loop.run_until_complete(coro)
#             finally:
#                 loop.close()

#         if action == "scrape" and intent.get("url"):
#             raw_content = run_async(scrape_url(intent["url"]))
#         else:
#             query = intent.get("query", state["task"])
#             raw_content = run_async(search_web(query))

#         answer = synthesize_answer(state["task"], raw_content)

#         return {
#             **state,
#             "results": state["results"] + [{
#                 "agent": "browser",
#                 "output": answer,
#                 "raw_content": raw_content[:500]
#             }],
#             "final_answer": answer,
#         }

#     except Exception as e:
#         log.error("browser_node_error", error=str(e))
#         return {
#             **state,
#             "error": str(e),
#             "final_answer": f"Browser agent error: {str(e)}"
#         }

@traceable(name="Browser Agent", run_type="tool")
def browser_node(state: AgentState) -> AgentState:
    try:
        intent = parse_browser_intent(state["task"])
        action = intent.get("action", "search")
        log.info("browser_node", action=action)

        if action == "scrape" and intent.get("url"):
            raw_content = _run_in_new_loop(scrape_url(intent["url"]))
        else:
            query = intent.get("query", state["task"])
            raw_content = _run_in_new_loop(search_web(query))

        answer = synthesize_answer(state["task"], raw_content)

        return {
            **state,
            "results": state["results"] + [{
                "agent": "browser",
                "output": answer,
                "raw_content": raw_content[:500]
            }],
            "final_answer": answer,
        }

    except Exception as e:
        log.error("browser_node_error", error=str(e))
        return {
            **state,
            "error": str(e),
            "final_answer": f"Browser agent error: {str(e)}"
        }