# Inline newsletter adapter

Use when the substantive article, essay, or briefing is contained in the email message itself and the reader can understand it without leaving the email app.

- Read the complete editorial message, including intentional continuations.
- Exclude signatures, unsubscribe controls, navigation, advertisements, affiliate blocks, social links, and unrelated recommendations.
- Treat links as supporting references unless the message clearly requires an external article for comprehension.
- Preserve meaningful original commentary as a distinct source during hybrid extraction.
- Resolve source provenance using the shared locator policy in `system/workflow.md`: canonical editorial URL first, then a public web version, then a reliable email deep link, otherwise no hyperlink.
- Never replace a missing article URL with a publication homepage, sender domain, archive root, tracking URL, or unrelated landing page.
- Email-only content remains eligible for inclusion even when no valid hyperlink exists.

This adapter is digest-agnostic and may be selected by any configured source group.
