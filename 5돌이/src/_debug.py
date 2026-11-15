import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naver
html = naver.fetch("https://finance.naver.com/sise/sise_upper.naver")
out = [f"len={len(html)}", f"code_links={len(re.findall(r'code=\w{6}', html))}",
       f"parsed={len(naver.parse_upper(html))}"]
i = html.find("top_tlt")
out.append(html[max(0, i - 300): i + 6000] if i >= 0 else html[:6000])
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "_debug.txt"), "w", encoding="utf-8").write("\n".join(out))
