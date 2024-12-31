import unittest
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
from datetime import datetime
import json
from LawDataGPT import (
    fetch_law_list,
    fetch_law_data,
    split_text_into_sentences,
    split_into_chunks,
    generate_summary_hierarchical,
    load_api_headers
)

class TestLawDataGPT(unittest.TestCase):
    
    def setUp(self):
        # テスト用のAPIヘッダー
        self.test_headers = {
            "X-API-KEY": "test_key"
        }
        
    @patch('LawDataGPT.fetch_with_retry')
    def test_fetch_law_list(self, mock_fetch):
        # モックレスポンスの準備
        mock_response = MagicMock()
        mock_response.text = '<?xml version="1.0" encoding="UTF-8"?><DataRoot><ApplData><LawNameListInfo><LawId>123</LawId><LawName>テスト法</LawName><LawNo>1号</LawNo><PromulgationDate>20240101</PromulgationDate></LawNameListInfo></ApplData></DataRoot>'
        mock_fetch.return_value = mock_response

        start_date = datetime.strptime("2024-01-01", "%Y-%m-%d")
        end_date = datetime.strptime("2024-12-31", "%Y-%m-%d")
        result = fetch_law_list(2, start_date, end_date)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["LawId"], "123")
        self.assertEqual(result[0]["LawName"], "テスト法")

    @patch('LawDataGPT.fetch_with_retry')
    def test_fetch_law_data(self, mock_fetch):
        # モックレスポンスの準備
        mock_response = MagicMock()
        mock_response.text = '<?xml version="1.0" encoding="UTF-8"?><DataRoot><ApplData><LawContents><Sentence>これはテスト法令です。</Sentence><Sentence>テスト用の文章です。</Sentence></LawContents></ApplData></DataRoot>'
        mock_fetch.return_value = mock_response

        result = fetch_law_data("123")
        
        self.assertIn("これはテスト法令です。", result)
        self.assertIn("テスト用の文章です。", result)

    def test_split_text_into_sentences(self):
        text = "これは一つ目の文です。これは二つ目の文です。これは三つ目の文です！"
        sentences = split_text_into_sentences(text)
        
        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0], "これは一つ目の文です。")
        self.assertEqual(sentences[2], "これは三つ目の文です！")

    def test_split_into_chunks(self):
        sentences = ["短い文です。", "これは長い文章です。" * 10]
        max_tokens = 100
        chunks = split_into_chunks(sentences, max_tokens=max_tokens)
        
        self.assertTrue(len(chunks) > 1)  # 複数のチャンクに分割されることを確認
        
        # 各チャンクの文字数を確認
        for chunk in chunks:
            # デバッグ用に実際の長さを表示
            chunk_bytes = len(chunk.encode('utf-8'))
            print(f"Chunk bytes: {chunk_bytes}, Content: {chunk[:50]}...")
            self.assertLessEqual(chunk_bytes, max_tokens * 3)  # UTF-8エンコードでのバイト数を確認

    @patch('LawDataGPT.client.chat.completions.create')
    def test_generate_summary_hierarchical(self, mock_completion):
        # OpenAI APIのモック
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="テスト要約"))]
        mock_completion.return_value = mock_response

        text = "これはテストの法令文です。" * 100
        summary = generate_summary_hierarchical(text)
        
        self.assertEqual(summary, "テスト要約")

    @patch('builtins.open')
    def test_load_api_headers(self, mock_open):
        # ファイル読み込みのモック
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"X-API-KEY": "test_key"}
        )

        headers = load_api_headers()
        self.assertEqual(headers["X-API-KEY"], "test_key")

if __name__ == '__main__':
    unittest.main() 