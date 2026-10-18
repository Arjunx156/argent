---
name: osint
description: OSINT with the local toolkit: investigate a domain, company, username, email, image or video from public sources, or audit the user's own exposure. Passive first, verified, sourced.
---

# OSINT

Answer a question from public sources, prove every finding, and leave a trail another analyst could follow.

## Scope first

Write the question in one sentence before collecting anything, for example "Which subdomains of example.com are exposed?" or "Where does the handle @x appear, and is it the same person?" The question defines when to stop.

The limits are fixed:

- Use public sources only. Never log in to anything as the target, never use leaked credentials or breach dumps, never bypass access controls.
- Private individuals are in scope only for a clear, legitimate purpose: the user's own footprint, a person who consented, or due diligence with a lawful basis. Collect the minimum. Decline anything that looks like stalking, harassment, doxxing or locating someone who does not want to be found.
- Stay passive unless the user owns the target or has written authorisation. Active steps, such as probing hosts with `httpx-toolkit`, brute-forcing DNS or `amass` active enumeration, are marked below.

## Tradecraft

- Investigate from Mullvad Browser, never from a browser signed in to personal accounts.
- Work passive before active and broad before deep. Pivot on what you find: a domain leads to emails, an email to usernames, a username to images.
- Confirm every claim with two independent sources. A single source is a lead, not a finding.
- Record provenance as you go: URL, the time retrieved (UTC), and an archive link (`https://web.archive.org/save/<url>`) for anything that may change.
- API keys belong in the environment or a password manager, never in case files.

## The toolkit

**Domains and infrastructure**

| Goal | Command |
|---|---|
| Subdomains, passive | `subfinder -d example.com -all -silent` |
| Emails, hosts, ASNs from public sources | `theHarvester -d example.com -b crtsh,duckduckgo,hackertarget,rapiddns -f out` (check `theHarvester -h` for current sources) |
| Wider passive map | `amass enum -passive -d example.com` |
| Resolve names | `dnsx -l subs.txt -a -resp -silent` |
| Look-alike and typosquat domains | `dnstwist --registered --format csv example.com` |
| Live hosts, titles, tech (**active**) | `httpx-toolkit -l subs.txt -title -status-code -tech-detect` |
| Exposed services (API key) | `shodan host <ip>` after `shodan init <key>` |
| Certificates and hosts (API key) | `censys` after `censys config` |

**People and accounts**

| Goal | Command |
|---|---|
| Where a username exists | `sherlock <user> --print-found --csv -fo out` |
| Deeper username dossier | `maigret <user> -H -fo out` (HTML report; `-P` for PDF) |
| Sites an email is registered on | `holehe <email> --only-used` |
| Username or email availability | `socialscan <user-or-email>` |

**Media and metadata**

| Goal | Command |
|---|---|
| Metadata, GPS, camera, software | `exiftool -a -G1 <file>` |
| Video metadata without downloading | `yt-dlp --skip-download --write-info-json <url>` |
| Archive a gallery or post | `gallery-dl <url>` |

**Correlation at scale.** `spiderfoot` (a shell function) starts SpiderFoot in a local container at `http://127.0.0.1:5001`, which runs hundreds of passive modules against one seed. Use it to widen a picture, then verify its leads by hand.

## Case files

Keep each investigation in its own folder:

```text
cases/<yyyy-mm-dd>-<slug>/
  question.md      the one-sentence question and its scope
  raw/             tool output, untouched
  evidence.md      each finding: claim, sources, time, archive link
  report.md        the answer
```

Write the report with the folio skill. Lead with the answer, then the evidence, then confidence and the gaps. Name what was not checked as plainly as what was found.
