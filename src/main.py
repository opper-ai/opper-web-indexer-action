import requests
from bs4 import BeautifulSoup
from opperai import Opper
from opperai.types import DocumentIn
from urllib.parse import urljoin, urldefrag
from opperai.types.exceptions import APIError
import sys
import argparse
import asyncio


async def scrape_website(url, base_url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f"404 Error: Page not found for {url}")
            return "", set()
        else:
            print(f"Error fetching {url}: {e}")
            return "", set()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return "", set()

    soup = BeautifulSoup(content, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # Extract links
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(base_url, href)
        # Remove fragment and ensure it starts with base_url
        defragged_url, _ = urldefrag(full_url)
        if defragged_url.startswith(base_url):
            links.add(defragged_url)

    return text, links


def clean_text(text):
    return " ".join(text.split())


def update_status(url, status):
    sys.stdout.write(f"\r{url[:70]:<70} | {status:<20}")
    sys.stdout.flush()


async def recursive_scrape(base_url, index):
    visited = set()
    to_visit = {base_url}
    added_to_index = set()

    while to_visit:
        url = to_visit.pop()
        defragged_url, _ = urldefrag(url)
        if defragged_url in visited:
            continue

        update_status(defragged_url, "Fetching")
        content, links = await scrape_website(defragged_url, base_url)
        cleaned_text = clean_text(content)

        if cleaned_text:  # Only index if there's content
            update_status(defragged_url, "Indexing")
            if defragged_url not in added_to_index:
                index.add(
                    DocumentIn(
                        key=defragged_url,
                        content=cleaned_text,
                        metadata={"url": defragged_url},
                    )
                )
                added_to_index.add(defragged_url)
                update_status(defragged_url, "Indexed")
            else:
                update_status(defragged_url, "Already indexed")
        else:
            update_status(defragged_url, "Skipped (No content)")

        print()  # Move to the next line for the next URL
        visited.add(defragged_url)
        to_visit.update(links - visited)

    print(f"\nTotal pages added to index: {len(added_to_index)}")


async def main():
    parser = argparse.ArgumentParser(description="Index a URL")
    parser.add_argument("api_key", help="API key for Opper")
    parser.add_argument("index_name", help="Name of the index")
    parser.add_argument("url", help="URL to index")
    args = parser.parse_args()

    opper = Opper(api_key=args.api_key)
    try:
        index = opper.indexes.get(name=args.index_name)
        if index is None:
            index = opper.indexes.create(name=args.index_name)
        if index is None:
            raise Exception("Failed to get or create index")
        await recursive_scrape(args.url, index)
        print("URL indexed successfully")
    except APIError as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
