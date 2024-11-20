import requests
import openai
import json
from datetime import datetime

# e-Gov API設定
E_GOV_API_BASE_URL = "https://laws.e-gov.go.jp/api/1"
LAW_CATEGORY = "4"  # 府省令・規則
E_GOV_API_HEADERS = {
    "User-Agent": "YourAppName",
    "Authorization": "Bearer YOUR_EGOV_API_KEY"  # e-Gov APIキー
}

# OpenAI API設定
openai.api_key = "YOUR_OPENAI_API_KEY"

# ファイル出力設定
OUTPUT_FILE = f"fushorei_summary_{datetime.now().strftime('%Y%m%d')}.json"

# e-Gov APIで法令名一覧を取得
def fetch_law_list():
    url = f"{E_GOV_API_BASE_URL}/lawlists/{LAW_CATEGORY}"
    response = requests.get(url, headers=E_GOV_API_HEADERS)
    if response.status_code == 200:
        return response.json().get("ApplData", {}).get("LawNameListInfo", [])
    else:
        print(f"Failed to fetch law list: {response.status_code}")
        return []

# e-Gov APIで法令データを取得
def fetch_law_data(law_id):
    url = f"{E_GOV_API_BASE_URL}/lawdata/{law_id}"
    response = requests.get(url, headers=E_GOV_API_HEADERS)
    if response.status_code == 200:
        return response.json().get("ApplData", {}).get("LawFullText", "")
    else:
        print(f"Failed to fetch law data for ID {law_id}: {response.status_code}")
        return ""

# OpenAI APIで概要を生成
def generate_summary(law_text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "法令の概要を簡潔に作成してください。"},
                {"role": "user", "content": law_text}
            ],
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "Error generating summary."

# 法令一覧を取得して概要を作成
def create_law_summaries():
    law_list = fetch_law_list()
    results = []

    for law in law_list:
        law_id = law.get("LawId")
        law_name = law.get("LawName")
        law_number = law.get("LawNo")
        promulgation_date = law.get("PromulgationDate")
        category = "府省令・規則"  # 固定値

        print(f"Processing: {law_name} (ID: {law_id})")
        
        # 法令データ取得
        law_text = fetch_law_data(law_id)
        if not law_text:
            continue
        
        # OpenAIで概要生成
        summary = generate_summary(law_text)
        
        # 結果を保存
        results.append({
            "LawId": law_id,
            "LawNumber": law_number,
            "LawName": law_name,
            "Category": category,
            "PromulgationDate": promulgation_date,
            "FullText": law_text,
            "Summary": {
                "Content": summary,
                "GeneratedDate": datetime.now().strftime("%Y%m%d")
            },
            "Metadata": {
                "EnforcementDate": None,  # 実際のデータに応じて更新
                "Amendments": [],  # 改正データの収集が必要なら追加
                "References": [
                    {
                        "Title": "e-Gov 法令全文リンク",
                        "URL": f"https://laws.e-gov.go.jp/law/{law_id}"
                    }
                ]
            }
        })

    # JSONファイルに保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"Summaries saved to {OUTPUT_FILE}")

# 実行
if __name__ == "__main__":
    create_law_summaries()
