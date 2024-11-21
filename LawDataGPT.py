import requests
from openai import OpenAI
import json
from datetime import datetime
import xml.etree.ElementTree as ET
from tqdm import tqdm

# OpenAI APIキーの設定
client = OpenAI()

# 外部ファイルからe-Gov APIヘッダーを読み込む
def load_api_headers(file_path="api_headers.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: {file_path} is not a valid JSON file.")
        exit(1)

# APIヘッダーの読み込み
E_GOV_API_HEADERS = load_api_headers()

# e-Gov API設定
E_GOV_API_BASE_URL = "https://laws.e-gov.go.jp/api/1"
LAW_CATEGORY = "4"  # 府省令・規則

# ファイル出力設定
OUTPUT_FILE = f"fushorei_summary_{datetime.now().strftime('%Y%m%d')}.json"

# e-Gov APIで法令名一覧を取得
def fetch_law_list():
    url = f"{E_GOV_API_BASE_URL}/lawlists/{LAW_CATEGORY}"
    response = requests.get(url, headers=E_GOV_API_HEADERS)

    if response.status_code == 200:
        try:
            # XMLレスポンスを解析
            root = ET.fromstring(response.text)
            
            # 必要なデータを抽出
            law_list = []
            for law_info in root.findall(".//LawNameListInfo"):
                law_id = law_info.find("LawId").text
                law_name = law_info.find("LawName").text
                law_no = law_info.find("LawNo").text
                promulgation_date = law_info.find("PromulgationDate").text

                # 2023年以降の日付をフィルタリング
                if promulgation_date and promulgation_date >= "2023-01-01":
                    law_list.append({
                        "LawId": law_id,
                        "LawName": law_name,
                        "LawNo": law_no,
                        "PromulgationDate": promulgation_date
                    })
            
            return law_list
        except ET.ParseError as e:
            print(f"XML Parse Error: {e}")
            return []
    else:
        print(f"Failed to fetch law list: {response.status_code}, {response.text}")
        return []

# e-Gov APIで法令データを取得
def fetch_law_data(law_id):
    url = f"{E_GOV_API_BASE_URL}/lawdata/{law_id}"
    response = requests.get(url, headers=E_GOV_API_HEADERS)

    # print(f"Status Code: {response.status_code}")
    # print(f"Response Text: {response.text}")  # レスポンスをデバッグログに出力（200文字まで）

    if response.status_code == 200:
        try:
            # XMLレスポンスを解析
            root = ET.fromstring(response.text)
            
            # 必要な法令全文を抽出
            law_full_text_list = [sentence.text for sentence in root.findall(".//Sentence") if sentence.text is not None]
            
            if isinstance(law_full_text_list, list):
                law_full_text = "\n".join(law_full_text_list)  # 各要素を改行で区切って結合
            # law_full_text = root.findall(".//Sentence")
            # print(law_full_text)
            return law_full_text if law_full_text else ""
        except ET.ParseError as e:
            print(f"XML Parse Error: {e}")
            return ""
    else:
        print(f"Failed to fetch law data for ID {law_id}: {response.status_code}")
        return ""

# OpenAI APIで概要を生成
def generate_summary(law_text):
    # print(law_text)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "法令の概要を簡潔に作成してください。"},
                {"role": "user", "content": law_text}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        # print(response)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "Error generating summary."

# 法令一覧を取得して概要を作成
def create_law_summaries():
    law_list = fetch_law_list()
    results = []

    # tqdmで進捗バーを表示
    print("Fetching law data and generating summaries...")
    for law in tqdm(law_list, desc="Processing laws", unit="law"):
        law_id = law.get("LawId")
        law_name = law.get("LawName")
        law_number = law.get("LawNo")
        promulgation_date = law.get("PromulgationDate")
        category = "府省令・規則"  # 固定値

        # デバッグ用ログ
        # print(f"Processing: {law_name} (ID: {law_id})")
        
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
            # "FullText": law_text,
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
