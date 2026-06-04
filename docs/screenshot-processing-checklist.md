# Screenshot processing checklist

Use this checklist whenever a new screenshot appears in a restaurant inbox folder.

## 1. Check the basics
- Is the screenshot in the correct restaurant folder?
- Does the filename contain the correct date?
- Are there multiple screenshots for the same day?

## 2. Read the image
- Identify the menu date
- Identify menu items
- Identify prices
- Check whether there is any ambiguity or cropping issue

## 3. Convert to structured data
For each visible item, create structured rows with:
- `slug`
- `date`
- `label`
- `text`
- `price_huf`
- `source_url` or note if unavailable
- `certainty = manual`

## 4. Add to Review workflow
- Put the extracted rows into the `Review` tab in the Google Sheet
- Or sync them into `manual_overrides.json` through the existing review pipeline

## 5. Rebuild the feed
Run the build pipeline after the review rows are in place.

## 6. Move the screenshot
After successful ingestion:
- move it from `inbox/` to `processed/`

If it is unclear / incomplete:
- either leave it in `inbox/`
- or move it to `archive/` with a note elsewhere

## 7. Final sanity check
- Does the restaurant appear on the page?
- Is the date correct?
- Are prices correct?
- Is the text readable enough for a user?
