# Coffee Finder Advanced

This agent network is an advanced version of the Coffee Finder example.
Like Coffee Finder, it can
* look for coffee options, depending on the time of the day
* place orders on behalf of the user

It's good for testing:

* how multiple agents can provide the same service
* how to leverage AAOSA instructions to disambiguate
* ask for more information when needed, like a username or the time of day.
* call a CodedTool

## File

[coffee_finder_advanced.hocon](../../registries/coffee_finder_advanced.hocon)

## Description

Coffee Finder Advanced is an agent network that can suggest options for coffee locations
based on the time of day, and place orders on behalf of the user.

## Example conversation

```text
Human:
Where can I get coffee?

AI:
You can get coffee at Joe's Gas Station at any time.
Both Bob's Coffee Shop and Henry's Fast Food also offer coffee,
but need to know the current time to confirm if they are open.
Would you like more details or want to place an order?
If so, please let me know the time and any preferences you have.
```

Following-up: 

```text
Human:
It's 8 am.

AI:
At 8 am, you can get coffee at the following places:
 * Joe's Gas Station (open anytime)
 * Bob's Coffee Shop (open at 8 am)
 * Henry's Fast Food (open at 8 am)
Would you like to place an order at any of these locations? If so, please provide your name and coffee order details.
```

Placing an order:

```text
Human:
Get me black coffee from Henry's

AI:
Henry's Fast Food can fulfill your black coffee order, but they need your name to proceed.
Please provide your name so I can complete your order and get you the order ID and details.
```

Following-up with the requested information:
```text
Human:
Mike

AI:
Order 201 has been placed successfully for Mike at Henry's Fast Food.
Details: black coffee.
Order ID: 201.

Let me know if you need anything else!
```
