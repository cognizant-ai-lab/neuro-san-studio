# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import copy
import hashlib
import json
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import ClassVar


class ProvenanceGraph:
    """
    Append-only, hash-linked record of one chat session, organized in branches by user and operation.

    Structure:  run -> user -> operation -> tool_call -> tool_reply -> verification -> next tool_call -> ...
    Each node is {kind, time, data, parents, prev, hash}:
      parents  hashes of the earlier nodes it belongs to. The first is the previous node on its branch; a verification
               also points at the tool_call it checked.
      prev     hash of the node written just before it, on any branch: one timeline over the whole session.
      hash     sha256 of all the other fields (keys sorted, no spaces); it is also the node's id.
    heads maps each branch ("E-1042", "E-1042/ScheduleLeaveAPI") to its newest node. Heads are a shortcut, not
    evidence: they are not hashed and can be recomputed from the nodes.

    intact() detects an edited, removed or reordered node. It cannot detect removing the newest nodes, appending
    forged ones, or rewriting the tail with every later hash recomputed; those need the head() recorded somewhere else
    when the session ends (the anchor), passed to intact().
    Only code adds nodes; there is no update or delete. One graph per process and session: the harness calls reset()
    when a session starts.
    """

    _active: ClassVar["ProvenanceGraph | None"] = None

    def __init__(self) -> None:
        """Start the graph with a root node holding a random id for this session."""
        self.nodes: list[dict[str, Any]] = []  # every node, oldest first: this list is the timeline
        self.heads: dict[str, str] = {}  # branch name -> hash of that branch's newest node
        self.run_id: str = str(uuid.uuid4())  # random id for this chat session; also files its anchors
        self.root: str = self.add("run", {"run_id": self.run_id}, [])  # the first node; every branch starts here

    @classmethod
    def reset(cls) -> "ProvenanceGraph":
        """Start a fresh graph for a new chat session. :return: The new graph."""
        cls._active = ProvenanceGraph()
        return cls._active

    @classmethod
    def active(cls) -> "ProvenanceGraph":
        """:return: The current session's graph. :raises RuntimeError: If reset() was not called."""
        if cls._active is None:
            raise RuntimeError("No provenance graph: the harness must call ProvenanceGraph.reset() first.")
        return cls._active

    def extend(self, user: str, operation: str, kind: str, data: dict[str, Any], also: list[str] | None = None) -> str:
        """
        Append a node to the user/operation branch, creating the user and operation nodes the first time.

        :param also: Extra parents beyond the branch's previous node (a verification passes its tool_call).
        :return: The new node's hash, which becomes the branch's newest node.
        """
        # First time we see this user: start their branch with a "user" node hanging off the root.
        if user not in self.heads:
            self.heads[user] = self.add("user", {"user": user}, [self.root])
        # First time this user does this operation: start a sub-branch with an "operation" node under the user.
        branch: str = f"{user}/{operation}"
        if branch not in self.heads:
            self.heads[branch] = self.add("operation", {"operation": operation}, [self.heads.get(user)])
        # Attach the new node after the branch's newest node (plus any extra links), and make it the newest.
        # heads is a lookup table, so this is one step: no walking through the graph to find the branch's end.
        self.heads[branch] = self.add(kind, data, [self.heads.get(branch), *(also or [])])
        return self.heads.get(branch)

    def add(self, kind: str, data: dict[str, Any], parents: list[str]) -> str:
        """Append one node at the end of the timeline. :return: Its hash."""
        node: dict[str, Any] = {
            "kind": kind,  # what the node is: run, user, operation, tool_call, tool_reply, verification
            "time": datetime.now(timezone.utc).isoformat(),  # when it was written, in UTC
            "data": copy.deepcopy(data),  # a copy: later edits to the caller's dict cannot reach the record
            "parents": list(parents),  # links to the earlier nodes it belongs to (its branch, its tool_call)
            "prev": self.head(),  # link to the node written just before it, on any branch
        }
        # The hash covers everything above, including both kinds of links, so changing anything changes the hash.
        node["hash"] = self.digest(node)
        self.nodes.append(node)
        return node.get("hash")

    def head(self) -> str | None:
        """:return: The newest node's hash: the value to record elsewhere (anchor) when the session ends."""
        return self.nodes[-1].get("hash") if self.nodes else None

    def pending(self) -> list[str]:
        """:return: Hashes of tool_call nodes that no verification points to yet (made, but not yet checked)."""
        # Collect everything that some verification node links to...
        checked: set[str] = {p for n in self.nodes if n.get("kind") == "verification" for p in n.get("parents")}
        # ...then list the tool calls that are not in that set.
        return [n.get("hash") for n in self.nodes if n.get("kind") == "tool_call" and n.get("hash") not in checked]

    def intact(self, anchor: str | None = None) -> bool:
        """
        Recompute every hash and follow every link.

        :param anchor: The head() recorded outside the graph when the session ended, if there is one.
        :return: False if a hash does not match its node, a prev does not name the node before it, a parent is not
            an earlier node, or the graph no longer ends at the anchor.
        """
        seen: set[str] = set()  # hashes of the nodes checked so far
        prev: str | None = None  # hash of the node just before the current one (none before the first)
        # Walk the timeline from oldest to newest.
        for node in self.nodes:
            # Its prev must name the node right before it, and its hash must match its content when recomputed.
            if node.get("prev") != prev or node.get("hash") != self.digest(node):
                return False
            # Every parent must be a node already seen: links only point backwards in time.
            if any(parent not in seen for parent in node.get("parents")):
                return False
            prev = node.get("hash")
            seen.add(prev)
        # With an anchor: the graph must still end exactly at the hash recorded outside it.
        return anchor is None or prev == anchor

    def save(self, path: Path) -> None:
        """Write the head, branch heads and nodes as JSON."""
        record: dict[str, Any] = {"head": self.head(), "heads": self.heads, "nodes": self.nodes}
        path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ProvenanceGraph":
        """
        Read a graph written by save(), so another process can check it (it does not become the active graph).

        :raises json.JSONDecodeError: If the file is half-written or not a saved graph.
        """
        record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        graph: ProvenanceGraph = cls.__new__(cls)  # skip __init__: it would add a fresh root node
        graph.nodes = record.get("nodes", [])
        graph.heads = record.get("heads", {})
        graph.root = graph.nodes[0].get("hash") if graph.nodes else None
        graph.run_id = graph.nodes[0].get("data", {}).get("run_id") if graph.nodes else None
        return graph

    @staticmethod
    def digest(node: dict[str, Any]) -> str:
        """:return: sha256 of the node without its own hash, encoded one fixed way (keys sorted, no spaces)."""
        # Leave out the hash field itself: a hash cannot include itself.
        body: dict[str, Any] = {key: value for key, value in node.items() if key != "hash"}
        # Always turn the node into the exact same bytes (keys sorted, no spaces, plain ASCII), so the same content
        # always gives the same hash, whoever computes it.
        encoded: bytes = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()
