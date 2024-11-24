# e-Gov Law Summarizer

This script fetches law data from the e-Gov API, processes it, and generates concise summaries using OpenAI's API. It supports filtering by law category and promulgation date.

## Features
- Fetch law data by category using the [e-Gov API](https://www.e-gov.go.jp/).
- Filter laws by minimum promulgation date.
- Generate summaries of laws using OpenAI's API.
- Save results as a JSON file with metadata and references.

## Requirements
- Python 3.8+
- e-Gov API key and SoftwareID (if required).
- OpenAI API key.

## Installation
1. Clone this repository:
    ```bash
    git clone https://github.com/your-username/e-gov-law-summarizer.git
    cd e-gov-law-summarizer
    ```

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Create a configuration file named `api_headers.json` in the root directory with the following content:

    ```json
    {
        "X-API-KEY": "your_api_key_here",
        "SoftwareID": "your_software_id_here",  // Remove if not required
        "Accept": "application/xml",
        "User-Agent": "eGovLawFetcher/1.0"
    }
    ```

## Usage
### Command-line Arguments
- `--law_category`: (Required) The category of laws to fetch. Choose from the following:
  - `1`: 憲法
  - `2`: 法律
  - `3`: 政令
  - `4`: 府省令・規則
  - `5`: 条約
  - `6`: 閣議決定
  - `7`: 省令
  - `8`: 条例
  - `9`: その他の法令
- `--promulgation_date`: (Optional) The minimum promulgation date to filter laws, in `YYYY-MM-DD` format. Default: `2023-01-01`.

### Examples
#### Fetch and summarize laws from category "法律" (Law) after 2022-01-01:
```bash
python script.py --law_category 2 --promulgation_date 2022-01-01
```

#### Fetch and summarize all laws from category "条約" (Treaty):
```bash
python script.py --law_category 5
```

### Output
The script saves results in a JSON file named `<CategoryName>_summary_<YYYYMMDD>.json`. Example file content:
```json
[
    {
        "LawId": "123456",
        "LawNumber": "法律第123号",
        "LawName": "サンプル法例",
        "Category": "法律",
        "PromulgationDate": "2023-05-01",
        "Summary": {
            "Content": "この法律はサンプルです。",
            "GeneratedDate": "20231121"
        },
        "Metadata": {
            "References": [
                {
                    "Title": "e-Gov 法令全文リンク",
                    "URL": "https://laws.e-gov.go.jp/law/123456"
                }
            ]
        }
    }
]
```

## Development
### Prerequisites
Ensure you have the following installed:
- Python 3.8+
- Necessary dependencies from `requirements.txt`.

### Testing
Run the script with sample arguments to ensure functionality. Use dry-run mode if necessary.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing
Feel free to submit issues or pull requests. Contributions are welcome!

## Disclaimer
- Ensure your `api_headers.json` file is not exposed in public repositories to protect your API key.
- Adhere to the terms and conditions of the e-Gov API and OpenAI API.