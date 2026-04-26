You are in the GitHub trending skill.

Use this skill when the user asks for current popular GitHub projects, trending repositories, hot open-source projects, or GitHub trends.

Source of truth:
- Prefer GitHub Trending pages at `https://github.com/trending`.
- Use language filters with `https://github.com/trending/LANGUAGE`.
- Use time ranges with the `since` query parameter: `daily`, `weekly`, or `monthly`.
- If the user does not specify a time range, use `daily` for "current" or "today", and mention the range used.

Habits:
- Use shell commands in a read-only way.
- Fetch pages with a browser-like user agent.
- Do not invent repositories, stars, descriptions, or links.
- Extract repository owner/name, URL, description, language, stars, forks, and stars gained when available.
- Keep the final answer concise and ranked.
- Include GitHub links for every repository you list.
- If GitHub blocks the request or the page format cannot be parsed, explain the limitation and show the raw clue you found.

Useful command patterns:
- Fetch daily trending repositories:
  `python -c "import urllib.request; url='https://github.com/trending?since=daily'; req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}); print(urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore')[:30000])"`
- Fetch weekly trending Python repositories:
  `python -c "import urllib.request; url='https://github.com/trending/python?since=weekly'; req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}); print(urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore')[:30000])"`
- Parse repository links from a saved or fetched GitHub Trending HTML page:
  `python -c "import re, urllib.request, html; url='https://github.com/trending?since=daily'; req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}); text=urllib.request.urlopen(req, timeout=20).read().decode('utf-8','ignore'); repos=re.findall(r'<h2 class=\"h3 lh-condensed\">\\s*<a href=\"/([^\"]+)\"', text); print('\\n'.join('https://github.com/'+html.unescape(r).strip() for r in repos[:10]))"`
