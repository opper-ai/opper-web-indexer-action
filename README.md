# Opper Web Indexer Action

This GitHub Action scrapes web content and adds it to an Opper index.

## Inputs

* `apikey`: The Opper API key (required)
* `index`: The name of the Opper index to update (required)
* `url`: The URL to start scraping from (required)

## Example Usage

```yaml
name: Index website in Opper
on:
  push:
    branches: [main]
jobs:
  index-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Index website in Opper
        uses: opper-ai/opper-web-indexer-action@v1.0.0
        with:
          apikey: ${{ secrets.OPPER_API_KEY }}
          index: 'my-index'
          url: 'http://docs.example.com/'
```
