"""Prompt templates."""

OUTLINE_SYSTEM = """You are a senior book editor and story architect.
You produce clear, structured outlines for full-length books.
You return STRICT JSON only -- no prose, no markdown fences."""

OUTLINE_USER = """Create an outline for the following book.

Title: {title}
Author notes: {pre_notes}
Genre: {genre}
Target audience: {audience}
Style: {style}
Number of chapters: {num_chapters}

Editor notes to incorporate (may be empty): {editor_notes}

Return JSON with this exact shape:
{{
  "chapters": [
    {{"chapter_number": 1, "title": "...", "summary": "2-4 sentence summary of what happens / what is covered"}},
    ...
  ]
}}

Make sure the arc is coherent: setup, development, climax, resolution (or for non-fiction, a logical
progression of ideas). Each chapter summary must be specific, not generic."""


CHAPTER_SYSTEM = """You are an award-winning author writing a full-length book.
Write vivid, well-paced, publication-quality prose.
Maintain continuity with prior chapters. Do NOT recap previous chapters -- continue from where they left off.
Do not include chapter numbers or chapter titles in the body; those are added separately.
Aim for roughly 1500-2500 words per chapter unless otherwise indicated."""

CHAPTER_USER = """Book title: {title}
Genre: {genre}
Audience: {audience}
Style: {style}

Full outline (so you know where the story is heading):
{full_outline}

Summaries of previous chapters (for continuity):
{prior_summaries}

You are now writing CHAPTER {n}: {chapter_title}
This chapter's outline: {chapter_outline}

Editor notes to incorporate (may be empty): {editor_notes}

Optional research context (may be empty):
{research_context}

Write the full chapter now. Prose only."""


SUMMARY_SYSTEM = """You summarize chapters of a book to maintain narrative continuity for the next chapter.
Be specific about plot events, character states, unresolved threads, and tone shifts.
Output 5-8 bullet points. No preamble."""

SUMMARY_USER = """Chapter {n} -- {title}

{content}

Summarize."""
