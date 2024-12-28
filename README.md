# e-Gov Law Data Fetcher and Summarizer

## Overview

This script fetches law data from the Japanese e-Gov API, generates summaries using the OpenAI API, and saves the results into JSON files. It is designed to handle large volumes of data efficiently by chunking and hierarchical summarization.

## Features

- Fetches law lists and full texts for specified categories and date ranges.
- Generates hierarchical summaries of laws using the OpenAI API.
- Supports output to JSON files, automatically managing file sizes.
- Easy configuration of API keys and settings.

## Prerequisites

1. **Python 3.8 or higher**
2. Required Python libraries:
   - `requests`
   - `json`
   - `tqdm`
   - `argparse`
   - `openai`
   - `re`
   - `xml.etree.ElementTree`
3. An OpenAI API key stored as the environment variable `OPENAI_API_KEY`.
4. A valid `api_headers.json` file containing the e-Gov API headers.

## Installation

1. Clone the repository or download the script file.
2. Install the required dependencies:
   ```bash
   pip install requests tqdm openai
   ```
3. Set up the OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY="your_openai_api_key"
   ```
4. Place the `api_headers.json` file in the same directory as the script.

## Usage

Run the script using the following command:

```bash
python script.py <categories> --start_date <start_date> --end_date <end_date>
```

### Arguments

- `<categories>`: Space-separated list of category numbers to process. Available categories are:
  - `2`: Constitutional laws and acts
  - `3`: Cabinet orders and Imperial ordinances
  - `4`: Ministerial ordinances and regulations
- `--start_date`: Start date in `YYYY-MM-DD` format.
- `--end_date`: End date in `YYYY-MM-DD` format.

### Example

Fetch and summarize laws in categories 2, 3, and 4 from December 15, 2004, to December 15, 2024:

```bash
python script.py 2 3 4 --start_date 2004-12-15 --end_date 2024-12-15
```

## Output

The script saves summarized data into JSON files named according to the format:

```
law_data_category_<category>_<file_count>_<start_date>_to_<end_date>.json
```

Each file contains the following fields:

- `LawId`: Unique identifier for the law.
- `LawNumber`: Number assigned to the law.
- `LawName`: Name of the law.
- `PromulgationDate`: Date the law was promulgated.
- `Summary`: Hierarchical summary of the law's content.

## Error Handling

1. If the OpenAI API key is not set, the script exits with an error message.
2. If the `api_headers.json` file is missing or invalid, the script exits with an error message.
3. If the API response contains invalid data or fails, the script logs an appropriate message and continues processing other laws.

## Configuration

### API Key

Ensure the OpenAI API key is set as an environment variable:

```bash
export OPENAI_API_KEY="your_openai_api_key"
```

### API Headers

Prepare the `api_headers.json` file with valid e-Gov API headers:

```json
{
  "Authorization": "Bearer your_api_token",
  "Accept": "application/xml"
}
```

### File Size Limit

The default file size limit is set to 3 MB. You can modify the `DEFAULT_FILE_SIZE_LIMIT` constant in the script if needed.

## Development Notes

1. The script uses the OpenAI `gpt-4o-mini` model for summaries. Update the model name in the `single_summary_call` function if a different model is preferred.
2. API rate limits are respected using `time.sleep()` delays. Adjust these values based on actual API restrictions.
3. Date format validation ensures accurate API requests. Ensure date inputs are in `YYYY-MM-DD` format.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request with proposed changes.

## License

This script is licensed under the MIT License. See `LICENSE` for details.

## Special Thanks

Toshio Yamada ([LinkedIn](https://www.linkedin.com/in/toshioyamada/), [Github](https://github.com/montoyamada))

SUN SHIHAO
