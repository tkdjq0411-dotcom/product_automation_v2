# NAVER CHROME HELPER V14

- Chrome helper 2.2.0.
- Product image capture narrowed to the real top product gallery (main image + its thumbnails), no page-wide 30-image scrape.
- Shipping fee is read from the actual shipping block; conditional free-shipping text no longer overrides a paid base shipping fee.
- Availability uses the real purchase buttons first; unrelated '품절' text elsewhere on the page no longer marks the product out of stock.
- Required product options are captured separately.
- Naver '추가 옵션' dropdowns are opened and captured group-by-group, then shown in a new B2B '추가 옵션' section below the normal option section.
- Store-name extraction excludes skip/navigation text such as '본문으로 바로가기'.
