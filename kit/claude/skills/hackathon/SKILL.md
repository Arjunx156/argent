---
name: hackathon
description: Use for anything built for a hackathon, a pitch or a demo day (PromptWars, Smart India Hackathon, HackerHouse, AWS or Google events): reading the brief like a judge, cutting scope to the clock, a live link from hour two, demo safety, and the submission pack of README, two-minute video script and pitch. Pairs with genai for AI builds.
---

# Hackathon

Judges see three minutes of a forty-eight hour build. Build those three minutes first, and make them impossible to break.

## 1. Read the brief like a judge

Before any code, write `HACKATHON.md` at the repo root with:

- every judging criterion and its weight, word for word;
- required tech ("must use Gemini", "deploy on AWS") and banned tech;
- the deadline in IST and in the organiser's timezone, and every required artifact (repo, live link, video, deck, form);
- rules that can disqualify: commits after the deadline, prebuilt code, team size.

Most hackathons check commit timestamps. Nothing gets pushed after the deadline unless the rules allow it.

## 2. Cut to one demo path

One person, one problem, one flow that ends on a moment worth filming. Write that flow as five or six steps in `HACKATHON.md`. Everything outside it is a slide, not a feature.

## 3. Work in this order

1. Skeleton deployed with a live URL by hour two. Deploy on every meaningful step after that.
2. The demo path end to end with fakes.
3. Replace fakes with real parts in the order a judge sees them.
4. Feature freeze at 75% of the clock. The last quarter is polish, README, video, deck and submission, and it always takes the whole quarter.

Commit and push with `edith ship` after each step, so the history tells the story and a dead laptop costs nothing.

## Stack defaults (all free tiers)

- Frontend: Vite, React, TypeScript and Tailwind on `bun`, hosted on Vercel, Netlify or Cloudflare Pages. It still goes through **atelier**.
- Backend: FastAPI on Render or Cloud Run, or Lambda through `sam` when the event is on AWS.
- Data: Supabase or SQLite. AI: the **genai** skill.
- Hackathon repos are public. Keys live in the host's environment settings, never the repo. Rotate any key that appears in a screenshot or the video.

## Demo safety

- Seed data that tells the story; never demo on an empty database.
- A demo mode that survives a flaky network: cache one known-good model response per demo step and fall back to it on timeout or rate limit, labelled as cached.
- Record the video by 80% of the clock, before the crunch, and re-record only if something better is built.

## The submission pack

**README**, which a judge reads in a minute: one line on what it does, a screenshot or GIF, the live link and the video link, then how it works (one diagram), run it in three commands, the stack, what's next, and the team. Map each judging criterion to where the README or demo shows it.

**Video, two minutes:**
- 0:00 to 0:15, the problem, told through one real person;
- 0:15 to 1:30, the live demo path, no slides;
- 1:30 to 1:50, how it works, one diagram;
- 1:50 to 2:00, impact and what's next.

**Deck, six to eight slides:** problem, who it's for, demo, how it works, impact with real numbers, what's next, team.

## Honesty

No fake users, fake metrics or fake testimonials. Say what's mocked. "Built in 36 hours at PromptWars" is a stronger line than any invented number.
