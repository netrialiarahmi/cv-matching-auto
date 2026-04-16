"""Export candidates from Kalibrr via API scraping (no CSV export button).

Strategy: Use the Kalibrr ATS API to fetch candidate list as JSON,
then construct a CSV matching the Kalibrr export format.
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv('.env')

import pandas as pd

POSITION = "Account Executive Pasangiklan.com"
JOB_ID = 256571
STATE_ID = 19  # "New Applicant" state

async def main():
    kaid = os.getenv("KAID", "").strip().strip('"')
    kb = os.getenv("KB", "").strip().strip('"')
    
    if not kaid or not kb:
        print("ERROR: KAID or KB missing from .env")
        return 1
    
    print(f"Exporting: {POSITION} (JOB_ID: {JOB_ID})")
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        
        await context.add_cookies([
            {"name": "kaid", "value": kaid, "domain": "www.kalibrr.com", "path": "/"},
            {"name": "kb", "value": kb, "domain": "www.kalibrr.com", "path": "/"},
        ])
        
        page = await context.new_page()
        
        # First: load the ATS page to establish session
        url = f"https://www.kalibrr.com/ats/candidates?job_id={JOB_ID}&state_id={STATE_ID}"
        print(f"Loading: {url}")
        
        # Capture API requests INCLUDING headers to find CSRF token
        api_requests = []
        
        async def capture_request(request):
            u = request.url
            if "/api/ats/candidates" in u and request.method == "POST":
                try:
                    headers = await request.all_headers()
                    body = request.post_data
                    api_requests.append({"url": u, "method": request.method, "body": body, "headers": headers})
                except Exception:
                    pass

        api_responses = []
        
        async def capture_response(response):
            u = response.url
            if "/api/ats/candidates" in u:
                try:
                    body = await response.text()
                    api_responses.append({"url": u, "status": response.status, "body": body})
                except Exception:
                    pass
        
        page.on("request", capture_request)
        page.on("response", capture_response)
        
        try:
            await page.goto(url, timeout=60000, wait_until="networkidle")
        except Exception as e:
            print(f"Page load: {e}")
        
        await page.wait_for_timeout(5000)
        print(f"Current URL: {page.url}")
        
        # Show captured POST headers + body
        print(f"\nCaptured {len(api_requests)} POST requests to /api/ats/candidates:")
        captured_headers = {}
        post_url = None
        post_body = None
        for r in api_requests:
            print(f"  [{r['method']}] {r['url']}")
            print(f"  Body: {r['body'][:500] if r['body'] else '(empty)'}")
            print(f"  Headers:")
            for k, v in sorted(r['headers'].items()):
                display_v = v[:80] if len(v) > 80 else v
                print(f"    {k}: {display_v}")
            captured_headers = r['headers']
            post_url = r['url']
            post_body = r['body']
        
        print(f"\nCaptured {len(api_responses)} responses:")
        for r in api_responses:
            print(f"  [{r['status']}] Body preview: {r['body'][:200]}")
        
        if not captured_headers:
            print("ERROR: No POST request captured. Cannot paginate.")
            all_candidates = []
            for r in api_responses:
                if r["status"] == 200:
                    try:
                        data = json.loads(r["body"])
                        if "objects" in data:
                            all_candidates.extend(data["objects"])
                    except json.JSONDecodeError:
                        pass
            print(f"Using {len(all_candidates)} candidates from initial page load")
        else:
            # We have the page's actual request headers — use them to paginate
            print(f"\nPaginating using captured request headers...")
            
            # Build headers for context.request — skip pseudo-headers
            replay_headers = {}
            for k, v in captured_headers.items():
                if not k.startswith(":"):
                    replay_headers[k] = v
            
            use_payload = json.loads(post_body) if post_body else {
                "limit": 50, "offset": 0,
                "sort_field": "relevance", "sort_direction": "desc",
                "job_id": JOB_ID, "state_id": STATE_ID, "filters": {}
            }
            
            all_candidates = []
            offset = 0
            limit = 100
            total = None
            
            while True:
                use_payload["offset"] = offset
                use_payload["limit"] = limit
                
                resp = await context.request.post(
                    post_url,
                    headers=replay_headers,
                    data=json.dumps(use_payload),
                )
                
                if resp.status != 200:
                    body_text = await resp.text()
                    print(f"  Error at offset {offset}: HTTP {resp.status} - {body_text[:200]}")
                    break
                
                data = await resp.json()
                count = data.get("count", 0)
                objects = data.get("objects", [])
                
                if total is None:
                    total = count
                    print(f"  Total candidates: {total}")
                
                if not objects:
                    break
                
                all_candidates.extend(objects)
                offset += limit
                print(f"  Fetched {len(all_candidates)}/{total}")
                
                if len(all_candidates) >= total:
                    break
                
                await asyncio.sleep(0.5)
            
            # If header replay failed, fallback to initial response
            if not all_candidates:
                print("Header replay failed. Using initial page load data...")
                for r in api_responses:
                    if r["status"] == 200:
                        try:
                            data = json.loads(r["body"])
                            if "objects" in data:
                                all_candidates.extend(data["objects"])
                        except json.JSONDecodeError:
                            pass
                print(f"Using {len(all_candidates)} candidates from initial page load")
        
        print(f"\nTotal fetched: {len(all_candidates)}")
        
        if all_candidates:
            # Show sample record keys
            sample = all_candidates[0]
            print(f"Sample keys: {list(sample.keys())}")
            print(f"Sample: {json.dumps(sample, indent=2, default=str)[:600]}")
            
            # Flatten and save to CSV
            rows = []
            for c in all_candidates:
                row = {}
                # Flatten nested dicts
                for k, v in c.items():
                    if isinstance(v, dict):
                        for k2, v2 in v.items():
                            if not isinstance(v2, (dict, list)):
                                row[f"{k}.{k2}"] = v2
                    elif isinstance(v, list):
                        row[k] = json.dumps(v, default=str) if v else ""
                    else:
                        row[k] = v
                rows.append(row)
            
            df = pd.DataFrame(rows)
            safe_name = POSITION.replace(" ", "_").replace(".", "").replace("/", "_")
            filepath = os.path.join("data", "raw", f"{safe_name}.csv")
            os.makedirs(os.path.join("data", "raw"), exist_ok=True)
            df.to_csv(filepath, index=False)
            print(f"\nSaved: {filepath} ({len(df)} rows, {len(df.columns)} columns)")
            print(f"Columns: {list(df.columns)}")
            
            # Check for date applied column
            for col in df.columns:
                if "date" in col.lower() or "appli" in col.lower() or "created" in col.lower():
                    sample_vals = df[col].dropna().head(3).tolist()
                    if sample_vals:
                        print(f"  Date-like column '{col}': {sample_vals}")
        else:
            print("No candidates fetched. Manual export needed.")
        
        await browser.close()
        return 0 if all_candidates else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
