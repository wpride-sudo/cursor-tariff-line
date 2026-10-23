# Forum post

Title: Plan usage line for the Cursor agent

I published a small Cursor plugin that shows plan pace against actual usage.

The line looks like `Allowed 86%, now 75% +1`. It appears only when usage goes up. `Allowed` spreads the plan evenly from a reset day you choose, 27 by default. `Now` is the current plan percent.

The line is green when Now is below Allowed, and red when it is equal or higher. The `+1` is red and is shown once.

You can also run the `show-usage` command to see Allowed and Now at any time.

It runs on Windows, macOS, and Linux. Set your reset day in `.cursor/hooks/config.json`:

```json
{ "resetDay": 27 }
```

GitHub topics: `cursor`, `usage`, `hooks`.
