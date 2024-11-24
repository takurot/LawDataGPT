import requests
from openai import OpenAI
import json
from datetime import datetime
import xml.etree.ElementTree as ET
from tqdm import tqdm
import argparse
import sys

# OpenAI APIキーの設定
client = OpenAI()

# 外部ファイルからe-Gov APIヘッダーを読み込む
def load_api_headers(file_path="api_headers.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: {file_path} is not a valid JSON file.")
        sys.exit(1)

# APIヘッダーの読み込み
E_GOV_API_HEADERS = load_api_headers()

# e-Gov API設定
E_GOV_API_BASE_URL = "https://laws.e-gov.go.jp/api/1"

# LAW_CATEGORY のマッピング（カテゴリ番号と名前）
LAW_CATEGORY_MAP = {
    "1": "憲法",
    "2": "法律",
    "3": "政令",
    "4": "府省令・規則",
    "5": "条約",
    "6": "閣議決定",
    "7": "省令",
    "8": "条例",
    "9": "その他の法令"
}

# 引数解析
def parse_arguments():
    parser = argparse.ArgumentParser(description="Fetch and summarize laws from e-Gov API.")
    parser.add_argument(
        "--law_category",
        type=str,
        required=True,
        choices=LAW_CATEGORY_MAP.keys(),
        help="Specify the law category (e.g., 1 for 憲法, 2 for 法律, etc.)."
    )
    parser.add_argument(
        "--promulgation_date",
        type=str,
        default="2023-01-01",
        help="Specify the minimum promulgation date in YYYY-MM-DD format (default: 2023-01-01)."
    )
    return parser.parse_args()

# e-Gov APIで法令名一覧を取得
def fetch_law_list(law_category, min_promulgation_date):
    url = f"{E_GOV_API_BASE_URL}/lawlists/{law_category}"
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

                # 指定された日付以降の法令のみをフィルタリング
                if promulgation_date and promulgation_date >= min_promulgation_date:
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

    if response.status_code == 200:
        try:
            # XMLレスポンスを解析
            root = ET.fromstring(response.text)
            
            # 必要な法令全文を抽出
            law_full_text_list = [sentence.text for sentence in root.findall(".//Sentence") if sentence.text is not None]
            
            return "\n".join(law_full_text_list) if law_full_text_list else ""
        except ET.ParseError as e:
            print(f"XML Parse Error: {e}")
            return ""
    else:
        print(f"Failed to fetch law data for ID {law_id}: {response.status_code}")
        return ""

# OpenAI APIで概要を生成
def generate_summary(law_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "法令の概要を簡潔に作成してください。"},
                {"role": "user", "content": law_text}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "Error generating summary."

# 法令一覧を取得して概要を作成
def create_law_summaries(law_category, min_promulgation_date):
    category_name = LAW_CATEGORY_MAP[law_category]
    OUTPUT_FILE = f"{category_name}_summary_{datetime.now().strftime('%Y%m%d')}.json"

    law_list = fetch_law_list(law_category, min_promulgation_date)
    results = []

    # tqdmで進捗バーを表示
    print("Fetching law data and generating summaries...")
    for law in tqdm(law_list, desc="Processing laws", unit="law"):
        law_id = law.get("LawId")
        law_name = law.get("LawName")
        law_number = law.get("LawNo")
        promulgation_date = law.get("PromulgationDate")

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
            "Category": category_name,
            "PromulgationDate": promulgation_date,
            "Summary": {
                "Content": summary,
                "GeneratedDate": datetime.now().strftime("%Y%m%d")
            },
            "Metadata": {
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
    args = parse_arguments()
    create_law_summaries(args.law_category, args.promulgation_date)
