---
name: show-usage
description: Show Allowed and Now plan usage percents now
---

Run `python .cursor/hooks/show-usage.py --show` from the project root. On Windows, if `python` is not found, run `python.exe .cursor/hooks/show-usage.py --show`.

Read the JSON from the script. Show the usage line it names, even when usage did not increase. Do not add a red +N. Use a small plain font, no bars. Green when Now is below Allowed. Red when Now is equal to Allowed or higher. Do not print the line as black text and do not wrap it in a span.
