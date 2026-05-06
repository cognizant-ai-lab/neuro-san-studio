# Book Recommender with Multiple LLM Configs

A book recommendation network that demonstrates how to assign
different Anthropic models to individual agents using per-agent `llm_config`.

It's good for testing:

* how to use per-agent `llm_config` to assign different models within one network
* how to use different models for different task complexities

## Prerequisites

This agent network requires an Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

## File

[book_recommender_multiple_llm_configs.hocon](../../../registries/basic/book_recommender_multiple_llm_configs.hocon)

## Description

Each agent has its own `llm_config` specifying an Anthropic model:

| Agent | Model | Role |
|-------|-------|------|
| **BookRecommender** | `claude-opus` | Frontman — routes requests to genre experts |
| **FictionExpert** | `claude-sonnet` | Recommends fiction and literary novels |
| **NonFictionExpert** | `claude-sonnet` | Recommends non-fiction books |
| **MysteryExpert** | `claude-sonnet` | Recommends mystery and thriller books |
| **SciFiExpert** | `claude-sonnet` | Recommends science fiction books |
| **QuickSummary** | `claude-haiku` | Provides brief one-line book summaries |

The per-agent `llm_config` is set like this:

```hocon
"llm_config": {
    "model_name": "claude-opus"
}
```

## Example conversation

```text
Human:
Suggest me a good book to read.

AI:
Since you have not specified a particular genre, I consulted all of our experts to give you a well-rounded set of options. Here are their top picks:

**Fiction:** *The Alchemist* by Paulo Coelho -- A beautifully written fable about a young shepherd pursuing his dream. It is philosophical yet accessible, emotional yet uplifting, and beloved by millions worldwide.

**Mystery/Thriller:** *The Girl with the Dragon Tattoo* by Stieg Larsson -- A gripping thriller with rich character development, particularly the unforgettable Lisbeth Salander. A page-turner that hooks you from start to finish.

**Science Fiction:** *The Hitchhiker's Guide to the Galaxy* by Douglas Adams -- A wildly funny and imaginative novel that is accessible to virtually anyone, even those who do not typically read science fiction.

If you can share more about your preferences -- such as genre, mood, or themes you enjoy -- I would be happy to narrow it down further. Otherwise, any of these three would be an excellent choice.
```


```text
Human:
I want something thrilling and suspenseful.

AI:
Given your interest in something thrilling and suspenseful, I strongly recommend:

**"The Martian" by Andy Weir**

Both our Science Fiction and Mystery/Thriller experts independently pointed to this book, which is a strong endorsement. It delivers relentless tension as an astronaut stranded alone on Mars faces one life-or-death problem after another, all while remaining accessible and engaging for newcomers.

**In a nutshell:** An astronaut stranded on Mars must use his ingenuity and scientific knowledge to survive and signal for rescue.

It strikes an excellent balance between gripping suspense and smart science fiction -- a perfect fit for what you are looking for.
```


```text
Human:
What's a good science fiction book for beginners?

AI:
Here is my recommendation for you:

**"The Hitchhiker's Guide to the Galaxy" by Douglas Adams**

This is widely considered one of the best entry points into science fiction. It is witty, fast-paced, and not too long, making it highly accessible for newcomers. Despite its humor, it still delivers classic sci-fi concepts like space travel and alien civilizations.

**In a nutshell:** An ordinary human is swept into a comedic intergalactic adventure when Earth is demolished to make way for a hyperspace bypass, and he discovers that the answer to life, the universe, and everything is 42.

It is the kind of book that makes it hard not to get hooked on the genre. A fantastic starting point for any beginner.
```
