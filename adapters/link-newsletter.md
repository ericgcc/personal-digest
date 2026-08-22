# Link newsletter adapter

Use when a Gmail message primarily acts as an index of headlines, short extracts, or external articles and the real content cannot be understood from the email alone.

- Extract editorial candidate links and discard navigation, account, advertising, affiliate, social, and promotional links.
- Remove tracking parameters and resolve the canonical destination.
- Open relevant authoritative destinations using the available authenticated browser when needed.
- Read the full accessible article rather than relying on the email teaser.
- Cite the original article, not the newsletter that linked to it.
- Follow only links needed for the selected themes during hybrid extraction; do not open every link indiscriminately.
- Record inaccessible or limited items honestly.

This general adapter is ready for future digest profiles; it is not selected by `medium-daily`.
