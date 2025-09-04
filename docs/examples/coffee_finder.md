# Coffee Finder

This agent network looks for coffee options for its user,
depending on the time of the day.

It's good for testing:

* how multiple agents can provide the same service
* how to leverage AAOSA instructions to
  * Disambiguate
  * Choose the best option depending on the context

## File

[coffee_finder.hocon](../../registries/coffee_finder.hocon)

## Description

Coffee Finder is an agent network that can suggest options for coffee locations
based on the time of day.

## Example conversation

```text
Human:
Where can I find coffee?

AI:
You can get coffee at Bob's Coffee Shop, Henry's Fast Food, and Joe's Gas Station.

Bob's Coffee Shop is open daily from 7 am to 6 pm.
Henry's Fast Food serves coffee from 5:30 am to 12 am.
Joe's Gas Station offers coffee anytime.

If you need coffee at a specific time or more details, please let me know.
```
Notice how the answer does NOT mention Jack's Liquor Store, because it doesn't serve coffee.

Following-up: 

```text
Human:
It's 8 am.

AI:
You can get coffee at 8 am from the following places:

Bob's Coffee Shop (open 7 am to 6 pm)
Henry's Fast Food (open at 8 am)
Joe's Gas Station (open anytime)
All of them serve coffee at your requested time.
```

Following-up again:

```text
Human:
It's now 8 pm, where can I get coffee?

AI:
You can get coffee at 8 pm from Henry's Fast Food and Joe's Gas Station. 
Bob's Coffee Shop is closed at 8 pm.
```

And again:
```text
Human:
It's now 2 am, where can I get coffee?

AI:
At 2 am, you can get coffee at Joe's Gas Station, which is open 24/7.

Bob's Coffee Shop and Henry's Fast Food are closed at this time.
```

Bonus question:
```text
Human:
Where can I find coffee liquor?

AI:
You can buy coffee liquor at Jack's Liquor Store.
```
