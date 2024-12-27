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

# OpenAI APIキーの設定（環境変数から取得することを推奨）
client = OpenAI()

if not client.api_key:
    print("Error: OpenAI API key not set. Please set the 'OPENAI_API_KEY' environment variable.")
    sys.exit(1)

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

# 法令一覧を取得
def fetch_law_list(category, start_date_str, end_date_str):
    url = f"{E_GOV_API_BASE_URL}/lawlists/{category}"
    response = requests.get(url, headers=E_GOV_API_HEADERS)
    time.sleep(1)  # API制限回避のためにリクエスト間隔を設定

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.text)
            law_list = []
            for law_info in root.findall(".//LawNameListInfo"):
                law_id = law_info.find("LawId").text
                law_name = law_info.find("LawName").text
                law_no = law_info.find("LawNo").text
                promulgation_date = law_info.find("PromulgationDate").text

                # 日付が取得できているか確認
                if promulgation_date:
                    # 日付を文字列として比較
                    if start_date_str <= promulgation_date <= end_date_str:
                        law_list.append({
                            "LawId": law_id,
                            "LawName": law_name,
                            "LawNo": law_no,
                            "PromulgationDate": promulgation_date
                        })
            print(f"Fetched {len(law_list)} laws for category {category} between {start_date_str} and {end_date_str}")
            return law_list
        except ET.ParseError as e:
            print(f"XML Parse Error: {e}")
            return []
    else:
        print(f"Failed to fetch law list for category {category}: {response.status_code}, {response.text}")
        return []

# 法令データを取得
def fetch_law_data(law_id):
    url = f"{E_GOV_API_BASE_URL}/lawdata/{law_id}"
    response = requests.get(url, headers=E_GOV_API_HEADERS)
    time.sleep(0.5)  # API制限回避のための短い待機

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.text)
            law_full_text_list = [sentence.text for sentence in root.findall(".//Sentence") if sentence.text is not None]
            return "\n".join(law_full_text_list) if law_full_text_list else ""
        except ET.ParseError as e:
            print(f"XML Parse Error for law ID {law_id}: {e}")
            return ""
    else:
        print(f"Failed to fetch law data for ID {law_id}: {response.status_code}")
        return ""

# 文を分割
def split_text_into_sentences(text):
    sentences = re.split(r'(。|！|？)', text)
    # 文末記号と結合
    return [''.join(sentences[i:i+2]) for i in range(0, len(sentences)-1, 2)]

# チャンクに分割
def split_into_chunks(sentences, max_tokens=3000):
    chunks = []
    current_chunk = ""
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence)
        if current_length + sentence_length > max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = ""
            current_length = 0
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
        print(f"Error during OpenAI API call: {e}")
        return "Error generating summary."

# 階層的要約生成
def generate_summary_hierarchical(law_text, max_chunk_tokens=3500):
    sentences = split_text_into_sentences(law_text)
    chunks = split_into_chunks(sentences, max_tokens=max_chunk_tokens)

    if len(chunks) == 1:
        return single_summary_call(chunks[0])

    chunk_summaries = []
    for chunk in chunks:
        summary = single_summary_call(chunk)
        chunk_summaries.append(summary)

    # チャンク要約を統合
    final_summary = single_summary_call(
        "\n".join(chunk_summaries),
        system_prompt="以下は各チャンクの要約です。これらを踏まえて全体の法令の概要を短くまとめてください。"
    )
    return final_summary

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
def create_law_summaries(categories, start_date_str, end_date_str):
    # 取得したい期間をstart_date_str～end_date_strで指定する
    for category in categories:
        category_desc = CATEGORY_DESCRIPTIONS.get(category, "Unknown")
        print(f"\nProcessing category {category}: {category_desc}")
        law_list = fetch_law_list(category, start_date_str, end_date_str)

        if not law_list:
            print(f"No laws found for category {category} within the specified date range.")
            continue

        results = []
        file_count = 1
        current_file_size = 0

        for law in tqdm(law_list, desc=f"Fetching laws for category {category}"):
            promulgation_date_str = law.get("PromulgationDate")
            law_id = law.get("LawId")
            law_name = law.get("LawName")
            law_number = law.get("LawNo")

            # 日付が指定範囲内か再確認（念のため）
            if not (start_date_str <= promulgation_date_str <= end_date_str):
                continue

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
                "PromulgationDate": promulgation_date_str,
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

    print(f"Fetching laws from {start_date_str} to {end_date_str}")

    create_law_summaries(categories, start_date_str, end_date_str)

    # さらに過去のデータが必要な場合は以下を実行（例: 過去40～20年）
    # old_end_date = (datetime.strptime(start_date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    # old_start_date = (datetime.strptime(old_end_date, "%Y-%m-%d") - timedelta(days=20*365)).strftime("%Y-%m-%d")
    # create_law_summaries(categories, old_start_date, old_end_date)

if __name__ == "__main__":
    main()

# python script.py 2 3 4 --start_date 2004-12-15 --end_date 2024-12-15
