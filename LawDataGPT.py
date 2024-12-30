import sys
import requests
import json
import time
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from tqdm import tqdm
from openai import OpenAI
import re
import os
import argparse
import logging
from retrying import retry  # リトライ戦略

# ロギングの設定
logging.basicConfig(level=logging.ERROR, format='%(asctime)s [%(levelname)s] %(message)s')

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

E_GOV_API_BASE_URL = "https://laws.e-gov.go.jp/api/1"

DEFAULT_FILE_SIZE_LIMIT = 3 * 1024 * 1024  # 3MB
CATEGORY_DESCRIPTIONS = {
    2: "憲法・法律",
    3: "政令・勅令",
    4: "府省令・規則"
}

# OpenAI APIキーの設定
client = OpenAI()
if not client.api_key:
    logging.error("OpenAI API key not set. Please set the 'OPENAI_API_KEY' environment variable.")
    sys.exit(1)

# APIレスポンスのリトライ設定
@retry(wait_exponential_multiplier=1000, stop_max_attempt_number=5)
def fetch_with_retry(url, headers):
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API call failed: {response.status_code} {response.text}")
    return response

# APIヘッダーの読み込み
def load_api_headers(file_path="api_headers.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading API headers: {e}")
        sys.exit(1)

# 法令リストを取得
def fetch_law_list(category, start_date, end_date):
    url = f"{E_GOV_API_BASE_URL}/lawlists/{category}"
    try:
        response = fetch_with_retry(url, E_GOV_API_HEADERS)
        root = ET.fromstring(response.text)
        
        law_list = []
        for law in root.findall(".//LawNameListInfo"):
            promulgation_date_str = law.find("PromulgationDate").text
            # YYYYMMDDフォーマットをパース
            promulgation_date = datetime.strptime(promulgation_date_str, "%Y%m%d")
            
            if start_date <= promulgation_date <= end_date:
                law_list.append({
                    "LawId": law.find("LawId").text,
                    "LawName": law.find("LawName").text,
                    "LawNo": law.find("LawNo").text,
                    "PromulgationDate": promulgation_date_str,
                })
        
        return law_list
    except ET.ParseError as e:
        logging.error(f"Error parsing XML: {e}")
        return []

# 法令データを取得
def fetch_law_data(law_id):
    url = f"{E_GOV_API_BASE_URL}/lawdata/{law_id}"
    try:
        response = fetch_with_retry(url, E_GOV_API_HEADERS)
        root = ET.fromstring(response.text)
        return "\n".join(
            [sentence.text for sentence in root.findall(".//Sentence") if sentence.text]
        )
    except ET.ParseError as e:
        logging.error(f"XML Parse Error for law ID {law_id}: {e}")
        return ""

# 文を分割してチャンク化
def split_text_into_sentences(text):
    sentences = re.split(r'(。|！|？)', text)
    return [''.join(sentences[i:i+2]) for i in range(0, len(sentences)-1, 2)]

def split_into_chunks(sentences, max_tokens=3000):
    chunks, current_chunk, current_length = [], "", 0
    for sentence in sentences:
        sentence_length = len(sentence)
        if current_length + sentence_length > max_tokens:
            chunks.append(current_chunk.strip())
            current_chunk, current_length = "", 0
        current_chunk += sentence
        current_length += sentence_length
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# 単一要約APIコール
def single_summary_call(text, system_prompt="法令の概要を簡潔に作成してください。"):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            # model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=3000,
            temperature=0.5
        )
        time.sleep(1)  # API制限回避
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error during OpenAI API call: {e}")
        return "Error generating summary."

# 階層的要約生成
def generate_summary_hierarchical(law_text, max_chunk_tokens=3500):
    # print(law_text)
    sentences = split_text_into_sentences(law_text)
    chunks = split_into_chunks(sentences, max_tokens=max_chunk_tokens)

    chunk_summaries = [
        single_summary_call(chunk) for chunk in chunks
    ]

    return single_summary_call(
        "\n".join(chunk_summaries),
        system_prompt="以下は各チャンクの要約です。これらを踏まえて全体の法令の概要を短くまとめてください。"
    )

# ファイルに保存
def save_to_file(data, category, file_count, start_date_str, end_date_str):
    # 出力ファイル名に取得期間を含める
    filename = f"law_data_category_{category}_{file_count}_{start_date_str}_to_{end_date_str}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(data)} laws to {filename}")
    except Exception as e:
        print(f"Error saving to file {filename}: {e}")

# 法令概要を生成
def create_law_summaries(categories, start_date, end_date, start_date_str, end_date_str):
    for category in categories:
        category_desc = CATEGORY_DESCRIPTIONS.get(category, "Unknown")
        print(f"\nProcessing category {category}: {category_desc}")
        law_list = fetch_law_list(category, start_date, end_date)

        if not law_list:
            print(f"No laws found for category {category} within the specified date range.")
            continue

        results = []
        file_count = 1
        current_file_size = 0

        for law in tqdm(law_list, desc=f"Fetching laws for category {category}"):
            law_id = law.get("LawId")
            law_name = law.get("LawName")
            law_number = law.get("LawNo")

            # 法令データ取得
            law_text = fetch_law_data(law_id)
            if not law_text:
                continue

            # 階層的要約でAPIコール数を削減
            summary = generate_summary_hierarchical(law_text, max_chunk_tokens=3500)

            law_entry = {
                "LawId": law_id,
                "LawNumber": law_number,
                "LawName": law_name,
                "PromulgationDate": law.get("PromulgationDate"),
                "Summary": summary
            }
            results.append(law_entry)

            # ファイルサイズチェック
            current_file_size += len(json.dumps(law_entry, ensure_ascii=False).encode("utf-8"))
            if current_file_size >= DEFAULT_FILE_SIZE_LIMIT:
                save_to_file(results, category, file_count, start_date_str, end_date_str)
                results = []
                current_file_size = 0
                file_count += 1

        # 残ったデータを保存
        if results:
            save_to_file(results, category, file_count, start_date_str, end_date_str)

# メイン関数
def main():
    parser = argparse.ArgumentParser(description="Fetch and summarize e-Gov law data.")
    parser.add_argument('categories', metavar='C', type=int, nargs='+',
                        help='Category numbers to process (e.g., 2 3 4)')
    parser.add_argument('--start_date', type=str, required=True,
                        help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end_date', type=str, required=True,
                        help='End date in YYYY-MM-DD format')

    args = parser.parse_args()

    categories = args.categories
    start_date_str = args.start_date
    end_date_str = args.end_date

    # 日付フォーマットの検証
    try:
        datetime.strptime(start_date_str, "%Y-%m-%d")
        datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        print("Error: Dates must be in YYYY-MM-DD format.")
        sys.exit(1)

    # start_date <= end_date の確認
    if start_date_str > end_date_str:
        print("Error: start_date must be earlier than or equal to end_date.")
        sys.exit(1)

    # 日付の変換をmain関数で行う
    start_date = datetime.strptime(start_date_str.replace('-', '.'), "%Y.%m.%d")
    end_date = datetime.strptime(end_date_str.replace('-', '.'), "%Y.%m.%d")

    print(f"Fetching laws from {start_date_str} to {end_date_str}")

    create_law_summaries(categories, start_date, end_date, start_date_str, end_date_str)

    # さらに過去のデータが必要な場合は以下を実行（例: 過去40～20年）
    # old_end_date = (datetime.strptime(start_date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    # old_start_date = (datetime.strptime(old_end_date, "%Y-%m-%d") - timedelta(days=20*365)).strftime("%Y-%m-%d")
    # create_law_summaries(categories, old_start_date, old_end_date)

if __name__ == "__main__":
    main()

# python script.py 2 3 4 --start_date 2004-12-15 --end_date 2024-12-15