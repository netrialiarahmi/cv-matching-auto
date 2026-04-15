"""Test Pipeline Step 1 to diagnose failures."""
import os, sys, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from src.pipelines.scorer import (
    get_gemini_client, call_api_with_retry, _get_model_name, 
    _try_parse_json, extract_and_classify_cv
)

client = get_gemini_client()
model = _get_model_name("extract")
print(f"Model: {model}")

# Test 1: Raw API call to check response format
print("\n=== Test 1: Raw API response check ===")
resp = call_api_with_retry(
    client,
    model=model,
    messages=[
        {"role": "system", "content": "You are a precise data extraction assistant. Return only valid JSON."},
        {"role": "user", "content": 'Extract candidate info. Return JSON: {"candidate_name": "Test", "score": 50}\n\nCV: Data Analyst with SQL experience.\nJob: Data Analyst KG Media'}
    ],
    temperature=0.1,
    response_format={"type": "json_object"},
    max_tokens=500
)

raw = resp.choices[0].message.content
print(f"Raw output length: {len(raw) if raw else 0}")
print(f"Raw output (repr): {repr(raw[:800])}")
has_think = '<think>' in raw.lower() if raw else False
print(f"Has thinking tags: {has_think}")

parsed = _try_parse_json(raw)
print(f"Parsed type: {type(parsed)}")
print(f"Parsed: {parsed}")

# Test 2: Full extract_and_classify_cv with empty CV
print("\n=== Test 2: Empty CV text ===")
result = extract_and_classify_cv("", "Name: Test", "Data Analyst KG Media", "SQL and Python required")
print(f"Result with empty CV: {type(result)} -> {result is None and 'NONE (Step 1 would fail!)' or 'OK'}")

# Test 3: Full extract_and_classify_cv with real-ish data  
print("\n=== Test 3: Normal candidate ===")
result = extract_and_classify_cv(
    "Jenrico Ervian - Data Analyst at PT Higo. Built dashboards, SQL queries, Python automation. Kalbis University, Informatics.",
    "Name: Jenrico Ervian, Latest Job: Data Analyst at PT Higo Fitur Indonesia, Education: Bachelor Informatics",
    "Data Analyst KG Media",
    """Collect, process, and analyze large datasets. Build dashboards using BI tools.
Write SQL queries. Python for data analysis. Experience in media industry preferred."""
)
if result:
    print(f"Result OK - name={result.get('candidate_name')}, role_match={result.get('role_function_match')}")
else:
    print("Result is None - STEP 1 FAILURE!")

print("\n=== Done ===")
